# Discord Bot with Flask Integration

This project is a combined Discord bot and Flask web application. The bot manages user roles and updates a SQLite database based on Discord server activity, while the Flask app provides endpoints and a simple web interface to emulate Discord channels and send messages to the bot.

## Features

- **Discord Bot**
  - Automatically updates and manages "Family" roles on connected guilds.
  - Provides administrator commands (e.g., `!update_roles` and `!update_users`) to synchronize server data with the database.
  - Listens for commands and can relay messages from the web interface to Discord channels.

- **Flask Web App**
  - Includes user authentication with CAPTCHA verification.
  - Offers a web-based Discord clone interface to view channels and messages.
  - Provides REST endpoints to get channel data and send messages to Discord.

- **Database**
  - Uses SQLite to store user, admin, and login attempt information.
  - Updates user records dynamically based on Discord server changes.

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/luckyddddd/DISCORD-WEB-BOT.git
   cd DISCORD-WEB-BOT
2. Install dependencies:
pip install -r requirements.txt

3. Configure Environment Variables:
Create a .env file (or set these in your deployment environment):
DISCORD_TOKEN=your_discord_bot_token
OWNER_ROLE_ID=your_owner_role_id
ROLE_IDS_FILE=roles.json
Optional: initial ROLE_IDS mapping in JSON format (if desired), for example:
ROLE_IDS={"1250677566956896327": "Cooman Family", "1269043740819984457": "WHITE Family"}
ROLE_IDS={"role_id": "role_name", ...}
DB_PATH=discord_roles.db
FLASK_PORT=5000
DISCORD_TOKEN=your_discord_bot_token
OWNER_ROLE_ID=your_owner_role_id
ROLE_IDS_FILE=roles.json
Optional: initial ROLE_IDS mapping in JSON format (if desired), for example:
ROLE_IDS={"1250677566956896327": "Cooman Family", "1269043740819984457": "WHITE Family"}
ROLE_IDS={"role_id": "role_name", ...}
DB_PATH=discord_roles.db
FLASK_PORT=5000

4. Run the Application:
python app.py

## The Flask web interface will be available on the configured port (default is 5000), and the Discord bot will connect using the provided token.
