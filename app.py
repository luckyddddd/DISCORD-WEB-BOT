
import discord
from discord.ext import commands
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import bcrypt
import os
import time
import random
import string
import threading
import json
import asyncio

# --- Settings ---
# Load configuration from environment variables
ROLE_IDS_FILE = os.getenv("ROLE_IDS_FILE", "roles.json")
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is not set.")
OWNER_ROLE_ID = int(os.getenv("OWNER_ROLE_ID", "0"))
# Load ROLE_IDS mapping from environment if provided; otherwise, use an empty dictionary
ROLE_IDS_ENV = os.getenv("ROLE_IDS")
if ROLE_IDS_ENV:
    ROLE_IDS = json.loads(ROLE_IDS_ENV)
else:
    ROLE_IDS = {}
DB_PATH = os.getenv("DB_PATH", "discord_roles.db")

# --- Discord Bot Setup ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Database Setup ---
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
# Create tables if they do not exist
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    role TEXT,
    discord_id INTEGER UNIQUE
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS login_attempts (
    username TEXT,
    attempts INTEGER,
    last_attempt REAL
)
""")
# Add necessary columns if they do not exist
c.execute("PRAGMA table_info(users)")
columns = [col[1] for col in c.fetchall()]
if "owner" not in columns:
    c.execute("ALTER TABLE users ADD COLUMN owner INTEGER DEFAULT 0")
if "server_nickname" not in columns:
    c.execute("ALTER TABLE users ADD COLUMN server_nickname TEXT")
conn.commit()

# --- Discord Bot Events and Commands ---
@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user.name} is running!")
    print(f"📌 Loaded commands: {bot.commands}")

    # Update roles list (Family roles)
    conn_db = sqlite3.connect(DB_PATH)
    c_db = conn_db.cursor()
    global ROLE_IDS
    updated_roles = False
    for guild in bot.guilds:
        for role in guild.roles:
            if "Family" in role.name and role.id not in ROLE_IDS:
                ROLE_IDS[role.id] = role.name
                updated_roles = True
    if updated_roles:
        with open(ROLE_IDS_FILE, "w") as file:
            json.dump(ROLE_IDS, file, indent=4)
        print("✅ Roles list updated and saved to roles.json")
    
    # Update users in the database
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            role_name = None
            is_owner = 1 if OWNER_ROLE_ID in [role.id for role in member.roles] else 0
            server_nickname = member.nick if member.nick else member.name
            for role in member.roles:
                if role.id in ROLE_IDS:
                    role_name = ROLE_IDS[role.id]
            c_db.execute("SELECT id FROM users WHERE discord_id = ?", (member.id,))
            if not c_db.fetchone():
                c_db.execute(
                    "INSERT INTO users (username, server_nickname, role, discord_id, owner) VALUES (?, ?, ?, ?, ?)",
                    (member.name, server_nickname, role_name, member.id, is_owner)
                )
            else:
                c_db.execute(
                    "UPDATE users SET server_nickname = ?, role = ?, owner = ? WHERE discord_id = ?",
                    (server_nickname, role_name, is_owner, member.id)
                )
    conn_db.commit()
    conn_db.close()
    print("✅ Data loaded into the database!")

@bot.command()
async def webcommand(ctx, *, arg):
    if ctx.author.guild_permissions.administrator:
        await ctx.send(f"✅ Command executed: {arg}")
    else:
        await ctx.send("❌ Insufficient permissions to execute this command.")

@bot.command()
@commands.has_permissions(administrator=True)
async def update_roles(ctx):
    global ROLE_IDS
    updated_roles = False
    for guild in bot.guilds:
        for role in guild.roles:
            if "Family" in role.name and role.id not in ROLE_IDS:
                ROLE_IDS[role.id] = role.name
                updated_roles = True
    if updated_roles:
        with open(ROLE_IDS_FILE, "w") as file:
            json.dump(ROLE_IDS, file, indent=4)
        await ctx.send("✅ Roles list updated and saved to roles.json")
    else:
        await ctx.send("⚠️ No new roles found.")

@bot.command()
@commands.has_permissions(administrator=True)
async def update_users(ctx):
    await ctx.send("Working...")
    conn_db = sqlite3.connect(DB_PATH)
    c_db = conn_db.cursor()
    existing_users = {row[0] for row in c_db.execute("SELECT discord_id FROM users").fetchall()}
    server_users = set()
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            role_name = None
            is_owner = 1 if OWNER_ROLE_ID in [role.id for role in member.roles] else 0
            server_nickname = member.nick if member.nick else member.name
            server_users.add(member.id)
            for role in member.roles:
                if role.id in ROLE_IDS:
                    role_name = ROLE_IDS[role.id]
            if member.id in existing_users:
                c_db.execute(
                    "UPDATE users SET server_nickname = ?, role = ?, owner = ? WHERE discord_id = ?",
                    (server_nickname, role_name, is_owner, member.id)
                )
            else:
                c_db.execute(
                    "INSERT INTO users (username, server_nickname, role, discord_id, owner) VALUES (?, ?, ?, ?, ?)",
                    (member.name, server_nickname, role_name, member.id, is_owner)
                )
    for user_id in existing_users - server_users:
        c_db.execute("DELETE FROM users WHERE discord_id = ?", (user_id,))
    conn_db.commit()
    conn_db.close()
    await ctx.send("✅ User database updated!")

# --- New endpoints for Discord server emulation ---
@app.route("/get_channels", methods=["GET"])
def get_channels():
    try:
        future = asyncio.run_coroutine_threadsafe(fetch_channels_data(), bot.loop)
        channels_data = future.result(timeout=10)
        return jsonify(channels_data)
    except Exception as e:
        return jsonify({"error": str(e)})

async def fetch_channels_data():
    # Use the first guild (adjust logic for multiple guilds if needed)
    if not bot.guilds:
        return []
    guild = bot.guilds[0]
    channels_data = []
    for channel in guild.text_channels:
        messages = []
        # Get the last 10 messages from the channel
        async for msg in channel.history(limit=10):
            messages.append({
                "author": msg.author.name,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat()
            })
        # Reverse the order so that the oldest messages appear first
        messages = messages[::-1]
        channels_data.append({
            "channel_name": channel.name,
            "channel_id": channel.id,
            "messages": messages
        })
    return channels_data

@app.route("/send_discord_message", methods=["POST"])
def send_discord_message():
    data = request.get_json()
    channel_name = data.get("channel")
    message = data.get("message")
    if not message:
        return jsonify({"response": "❌ Message cannot be empty!"})
    bot.loop.create_task(send_message_to_discord(channel_name, message))
    return jsonify({"response": f"💬 Message sent to #{channel_name}"})

async def send_message_to_discord(channel_name, message):
    # Use the first guild
    guild = bot.guilds[0]
    discord_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if discord_channel:
        await discord_channel.send(f"{message}")
    else:
        print(f"⚠️ Channel #{channel_name} not found in Discord!")

# --- Discord emulation page ---
@app.route("/discord_clone")
def discord_clone():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("discord_clone.html")

# --- Endpoint for sending a command to the bot (if needed) ---
@app.route("/send_command", methods=["POST"])
def send_command():
    if "user" not in session:
        return jsonify({"response": "Error: Login required!"})
    data = request.get_json()
    command = data.get("command")
    if not command:
        return jsonify({"response": "Error: Command is empty!"})
    bot.loop.create_task(run_bot_command(command))
    return jsonify({"response": f"Command '{command}' sent to the bot!"})

async def run_bot_command(command):
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="general")  # Change to desired channel name
    if channel:
        await channel.send(f"!{command}")
    else:
        print("Channel not found.")

# --- Flask routes for authentication and main page ---
def generate_captcha():
    CAPTCHA_LENGTH = 6
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=CAPTCHA_LENGTH))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if "captcha" not in session:
        session["captcha"] = generate_captcha()
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        captcha_input = request.form["captcha"]
        if captcha_input != session["captcha"]:
            session["captcha"] = generate_captcha()
            return render_template("login.html", error="Invalid CAPTCHA", captcha=session["captcha"])
        conn_db = sqlite3.connect(DB_PATH)
        c_db = conn_db.cursor()
        c_db.execute("SELECT attempts, last_attempt FROM login_attempts WHERE username = ?", (username,))
        attempt_data = c_db.fetchone()
        if attempt_data:
            attempts, last_attempt = attempt_data
            if attempts >= 5 and time.time() - last_attempt < 300:
                conn_db.close()
                return render_template("login.html", error="Too many login attempts. Try again later.", captcha=session["captcha"])
        else:
            attempts = 0
        c_db.execute("SELECT password FROM admins WHERE username = ?", (username,))
        result = c_db.fetchone()
        if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
            session["user"] = username
            c_db.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
            conn_db.commit()
            conn_db.close()
            return redirect(url_for("index_page"))
        else:
            attempts += 1
            c_db.execute("REPLACE INTO login_attempts (username, attempts, last_attempt) VALUES (?, ?, ?)",
                         (username, attempts, time.time()))
            conn_db.commit()
            conn_db.close()
            session["captcha"] = generate_captcha()
            return render_template("login.html", error="Invalid credentials", captcha=session["captcha"])
    return render_template("login.html", captcha=session["captcha"])

@app.route("/logout")
def logout_page():
    session.pop("user", None)
    return redirect(url_for("login_page"))

@app.route("/")
def index_page():
    if "user" not in session:
        return redirect(url_for("login_page"))
    conn_db = sqlite3.connect(DB_PATH)
    c_db = conn_db.cursor()
    c_db.execute("SELECT id, username, server_nickname, role, discord_id, owner FROM users")
    users = c_db.fetchall()
    conn_db.close()
    return render_template("index.html", users=users)

# --- Running the Application ---
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")), use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()  # Start Flask in a separate thread
    bot.run(TOKEN)
