# app/config.py

import os

# Path to sqlite DB (relative to project root by default)
DB_PATH = os.getenv("DB_PATH", "db.sqlite3")

# Bot token MUST come from environment for security. Do NOT commit secrets.
# Set `BOT_TOKEN` in your environment or in a local `.env` (use python-dotenv in dev).
BOT_TOKEN = os.getenv("BOT_TOKEN")

SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")
