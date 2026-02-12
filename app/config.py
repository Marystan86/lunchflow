# app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# .env находится в корне проекта (рядом с main.py)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_PATH = os.getenv("DB_PATH", "db.sqlite3")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "")
