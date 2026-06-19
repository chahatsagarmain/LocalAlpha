import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "local_alpha.db"
REPORTS_DIR = BASE_DIR / "reports"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure directories exist
REPORTS_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# LLM Configuration
# Supports: "ollama" (default), "openai", "anthropic", "gemini"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama settings
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# External provider fallbacks if environment variables are provided
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Scraping settings
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Dynamic overrides from CLI arguments
MOCK = False
API_KEY_OVERRIDE = None
PROVIDER_OVERRIDE = None
MODEL_OVERRIDE = None
