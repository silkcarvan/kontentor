"""Configuration and safe credential loader for Kontentor."""

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = BASE_DIR / "projects"
OUTPUT_DIR = BASE_DIR / "output"
STYLE_MEMORY_PATH = DATA_DIR / "style_memory.json"


def _load_env_file(env_path: Path) -> None:
    """Safely load key=value pairs from a .env file into os.environ."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value


def load_credentials() -> dict:
    """Load credentials from project .env and ~/.env."""
    _load_env_file(Path.home() / ".env")
    _load_env_file(BASE_DIR / ".env")

    return {
        "luna_api_key": os.environ.get("LUNA_API_KEY")
        or os.environ.get("EXPERIENTIAL_API_KEY")
        or os.environ.get("OPENAI_API_KEY", ""),
        "luna_base_url": os.environ.get(
            "LUNA_BASE_URL", "https://api.experientiallabs.ai/v1"
        ),
        "luna_model": os.environ.get("LUNA_MODEL", "gpt-6-luna"),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "gemini_model": os.environ.get("GEMINI_MODEL", "gemini-4-hydrogen"),
        "cf_account_id": os.environ.get("CF_ACCOUNT_ID", ""),
        "cf_api_token": os.environ.get("CF_API_TOKEN", ""),
        "flux_model": os.environ.get(
            "FLUX_MODEL", "@cf/black-forest-labs/flux-1-schnell"
        ),
        "cf_llm_model": os.environ.get(
            "CF_LLM_MODEL", "@cf/moonshotai/kimi-k2.7-code"
        ),
        "default_voice": os.environ.get("DEFAULT_VOICE", "en-US-AndrewNeural"),
        "youtube_api_key": os.environ.get("YOUTUBE_API_KEY", ""),
        "youtube_channel_id": os.environ.get("YOUTUBE_CHANNEL_ID", ""),
    }


def load_style_memory() -> dict:
    """Load the self-improving style memory JSON."""
    if not STYLE_MEMORY_PATH.exists():
        return {}
    return json.loads(STYLE_MEMORY_PATH.read_text(encoding="utf-8"))


def save_style_memory(memory: dict) -> None:
    """Persist updated style memory and learned insights."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STYLE_MEMORY_PATH.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
