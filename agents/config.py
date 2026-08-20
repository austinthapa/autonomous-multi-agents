import os
from pathlib import Path


## LLM
MODEL_NAME: str = os.getenv("MODEL", "gpt-4o")
MODEL_TEMPERATURE: float = os.getenv("TEMPERATURE", 0.0)

MAX_ATTEMPTS = os.getenv("MAX_ATTEMPTS", 10)

ALLOWED_EXTENSIONS = {".py", ".txt", ".cfg",".ini", "toml", ".md"}
MAX_FILE_BYTES:int = os.getenv("MAX_FILE_BYTES", 1000000)
CODEBASE_ROOT:Path = Path(
    os.getenv("AGENT_CODEBASE_ROOT", str(Path(__file__).resolve().parent.parent / "codebase"))
)
TEST_COMMAND = os.getenv("AGENT_TEST_COMMAND", "pytest test_app.py -v").split()