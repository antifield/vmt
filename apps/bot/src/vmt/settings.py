"""one place to read env vars from, everything else just gets a Settings object"""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

log = logging.getLogger(__name__)


class SettingsError(RuntimeError):
    """something in the env is missing or wrong, message already says what to fix"""


@dataclass(frozen=True)
class Settings:
    bot_token: str
    deepl_api_key: str
    deepl_free_api: bool
    elevenlabs_api_key: str | None
    turso_database_url: str | None
    turso_auth_token: str | None
    turso_remote_only: bool
    daily_limit_seconds: float
    max_voice_message_duration: int
    db_path: str


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def load_settings() -> Settings:
    """read settings from the environment (and .env) once, at startup

    collects every problem it finds instead of stopping at the first one, so you
    fix your .env in one go instead of playing whack-a-mole
    """
    load_dotenv()

    errors: list[str] = []

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        errors.append("BOT_TOKEN is not set")

    deepl_api_key = os.getenv("DEEPL_API_KEY")
    if not deepl_api_key:
        errors.append("DEEPL_API_KEY is not set")

    daily_limit_seconds = 0.0
    raw_daily_limit = os.getenv("DAILY_LIMIT_SECONDS")
    if raw_daily_limit:
        try:
            daily_limit_seconds = float(raw_daily_limit)
            if daily_limit_seconds < 0:
                raise ValueError("must not be negative")
        except ValueError:
            errors.append(
                "DAILY_LIMIT_SECONDS must be a positive number, "
                f"got {raw_daily_limit!r}"
            )

    max_voice_message_duration = 60
    raw_max_duration = os.getenv("MAX_VOICE_MESSAGE_DURATION")
    if raw_max_duration:
        try:
            max_voice_message_duration = int(raw_max_duration)
            if max_voice_message_duration <= 0:
                raise ValueError("must be positive")
        except ValueError:
            errors.append(
                "MAX_VOICE_MESSAGE_DURATION must be a positive whole number, "
                f"got {raw_max_duration!r}"
            )

    turso_database_url = os.getenv("TURSO_DATABASE_URL") or None
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN") or None
    # a token without a url does nothing, warn about it. a url without a token is
    # fine, that's how an authless self-hosted sqld works
    if turso_auth_token and not turso_database_url:
        log.warning(
            "TURSO_AUTH_TOKEN is set but TURSO_DATABASE_URL is not, so vmt will "
            "use a plain local database instead"
        )

    if errors:
        raise SettingsError(
            "config problems, fix these and try again:\n- " + "\n- ".join(errors)
        )

    if bot_token is None or deepl_api_key is None:
        # unreachable, missing keys are already in errors, this narrow is for the type checker
        raise SettingsError("missing required settings")

    return Settings(
        bot_token=bot_token,
        deepl_api_key=deepl_api_key,
        deepl_free_api=_env_bool("DEEPL_FREE_API"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY") or None,
        turso_database_url=turso_database_url,
        turso_auth_token=turso_auth_token,
        turso_remote_only=_env_bool("TURSO_REMOTE_ONLY"),
        daily_limit_seconds=daily_limit_seconds,
        max_voice_message_duration=max_voice_message_duration,
        db_path=os.getenv("DB_PATH", "data/vmt.db"),
    )
