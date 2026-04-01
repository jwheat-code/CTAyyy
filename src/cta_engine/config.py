import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
# If the shell exported an empty ANTHROPIC_API_KEY, remove it so .env can fill it in
if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ.pop("ANTHROPIC_API_KEY", None)
load_dotenv(_env_path, override=False)

# Pull from Streamlit secrets if running on Streamlit Cloud
try:
    import streamlit as st
    if hasattr(st, "secrets") and "ANTHROPIC_API_KEY" in st.secrets:
        os.environ.setdefault("ANTHROPIC_API_KEY", st.secrets["ANTHROPIC_API_KEY"])
except Exception:
    pass


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_haiku_model: str = "claude-haiku-4-5-20251001"
    crawl_delay_seconds: float = 2.5
    crawl_max_articles: int = 100
    log_level: str = "INFO"

    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = project_root / "data"
    crawled_dir: Path = data_dir / "crawled"
    classified_dir: Path = data_dir / "classified"
    cta_library_path: Path = data_dir / "cta_library.json"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
