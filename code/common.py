"""Shared helpers for chapter scripts in this `code/` folder."""

from pathlib import Path

from dotenv import load_dotenv

_CODE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CODE_DIR.parent

# Prefer keys from code/.env; then fill any missing vars from rag_federal_individual/.env
# (python-dotenv does not override existing environment variables by default).
OPENAI_KEY_HINT = (
    "Set OPENAI_API_KEY in code/.env or rag_federal_individual/.env "
    "(copy code/.env.example to code/.env)."
)


def load_env() -> None:
    load_dotenv(_CODE_DIR / ".env")
    load_dotenv(_REPO_ROOT / "rag_federal_individual" / ".env")
