import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    db_path: str
    admin_tg_ids: set[int]
    env: str
    dev_auth_enabled: bool
    dev_auth_user_id: int
    survey_scheduler_enabled: bool
    survey_interval_seconds: int
    use_new_meeting_model: bool
    use_new_store_model: bool

    def is_admin(self, tg_id: int) -> bool:
        return int(tg_id) in self.admin_tg_ids


def _parse_admin_ids(raw_value: str | None) -> set[int]:
    if not raw_value:
        return set()
    result: set[int] = set()
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            result.add(int(chunk))
        except ValueError:
            continue
    return result


def _load_settings() -> Settings:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    db_path = os.getenv("DB_PATH", "./db.sqlite3").strip() or "./db.sqlite3"
    admin_tg_ids = _parse_admin_ids(os.getenv("ADMIN_TG_IDS", ""))
    env = os.getenv("ENV", "prod").strip().lower() or "prod"
    if env not in {"dev", "prod"}:
        env = "prod"
    dev_auth_enabled = os.getenv("DEV_AUTH_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    dev_auth_user_id = int(os.getenv("DEV_AUTH_USER_ID", "1"))
    survey_scheduler_enabled = os.getenv("NEW_SURVEY_SCHEDULER_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    survey_interval_seconds = int(os.getenv("SURVEY_SCHEDULER_INTERVAL_SECONDS", "300"))
    use_new_meeting_model = os.getenv("USE_NEW_MEETING_MODEL", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    use_new_store_model = os.getenv("USE_NEW_STORE_MODEL", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return Settings(
        bot_token=bot_token,
        db_path=db_path,
        admin_tg_ids=admin_tg_ids,
        env=env,
        dev_auth_enabled=dev_auth_enabled and env == "dev",
        dev_auth_user_id=max(1, dev_auth_user_id),
        survey_scheduler_enabled=survey_scheduler_enabled,
        survey_interval_seconds=max(30, survey_interval_seconds),
        use_new_meeting_model=use_new_meeting_model,
        use_new_store_model=use_new_store_model,
    )


settings = _load_settings()


def is_admin(tg_id: int) -> bool:
    return settings.is_admin(tg_id)


def is_dev_mode() -> bool:
    return settings.env == "dev"
