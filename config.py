import logging
import logging.handlers
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from auth import get_credentials
from tools import get_services

load_dotenv()

# -- Logging ------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger("assistant")
logger.setLevel(logging.INFO)

_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(BASE_DIR, "bot.log"),
    maxBytes=2_000_000, backupCount=3, encoding="utf-8",
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(_file_handler)

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
)
logger.addHandler(_stream_handler)

# -- API clients --------------------------------------------------------------

client = Anthropic()
creds = get_credentials()
gmail, calendar, people, drive = get_services(creds)

# -- Modèle LLM configurable via .env ----------------------------------------
CLAUDE_MODEL = os.getenv("LLM_MODEL", os.getenv("CLAUDE_MODEL", "claude-opus-4-7"))
CLAUDE_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", os.getenv("CLAUDE_MAX_TOKENS", "4096")))

# -- Identité configurable via .env -----------------------------------------
BOT_NAME = os.getenv("BOT_NAME", "Assistant")
USER_NAME = os.getenv("USER_NAME", "l'utilisateur")

# -- State --------------------------------------------------------------------

conversations: dict[int, list] = {}

# -- Whitelist ----------------------------------------------------------------

_raw_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USERS: set[int] = {int(x.strip()) for x in _raw_ids.split(",") if x.strip()}


def is_allowed(user_id: int) -> bool:
    return not ALLOWED_USERS or user_id in ALLOWED_USERS
