import logging
from agents.security import resolve_safe_path, PathSecurityError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def view_codebase_file(file_name: str) -> str:
    """
    Returns the contents of `file_name` from the sandboxed codebase directory.
    
    The requested path is validated to ensure that it is safe and exists.
    PathSecurityError exceptions are caught and returned as an error string.
    File-reading errors may still be raised by `read_text().`
    """
    try:
        path = resolve_safe_path(file_name, must_exist=True)
    except PathSecurityError as e:
        logger.warning("Blocked view_codebase_file(%r): %s", file_name, e)
        return f"Error: {e}"
    
    content = path.read_text(encoding="utf-8", errors="replace")     # -> comeback to this later on
    
    logger.info("Read %s", path)
    return content

def patch_codebase_file(file_name: str, code_content: str) -> str:
    """
    Overwrites `file_name` with `code_content` inside the sandbox only.
    Writes to a temp file and then renames automatically to avoid leaving
    a half-written file if the process dies mid-write.
    """
    if not code_content:
        return "Error: code_content cannot be empty."

    try:
        path = resolve_safe_path(file_name, must_exist=False)    # -> For now letting create a new file
    except PathSecurityError as e:
        logger.warning("Blocked patch_codebase_file(%r): %s", file_name, e)
        return f"Error: {e}"
    
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(code_content, encoding="utf-8")
        tmp_path.replace(path)
    except OSError as e:
        logger.error("Failed writing %s: %s", path, e)
        return f"ERROR: could not write {file_name!r}: {e}"
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        
    logger.info("Wrote %s", path)
    return f"OK: {file_name} updated ({len(code_content)} chars written)."
            