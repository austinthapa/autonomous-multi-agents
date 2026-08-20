import subprocess
import logging

from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODEBASE_ROOT = PROJECT_ROOT / "codebase"
TEST_FILE = CODEBASE_ROOT / "test_app.py"

def run_verification_tests() -> str:
    """
    Run the configured test command inside the CODEBASE_ROOT
    
    Returns the combined stdout/stderr as a string, truncated if huge, 
    including a leading PASS/FAIL marker the LLM can key off
    """
    try:
        result = subprocess.run(
            ["pytest", str(TEST_FILE), "-v"],
            cwd=CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )  
    except FileNotFoundError as e:
        logger.error("Test command not found: %s", e)
        return f"FAIL: test command not found ({e})"
    
    status = "PASS" if result.returncode == 0 else "FAIL"
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    
    max_chars = 8000
    if len(output) > max_chars:
        output = output[:max_chars] + f"\n...[truncated, {len(output) - max_chars} more char]"
    
    logger.info("Test run finished: %s (exit code %s)", status, result.returncode)
    return f"{status} (exit code {result.returncode}) \n {output}"