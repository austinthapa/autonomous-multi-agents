from pathlib import Path
from agents.config import CODEBASE_ROOT, ALLOWED_EXTENSIONS

class PathSecurityError(ValueError):
    """
    Raises when a requested file path fails sandbox validation.
    """

def resolve_safe_path(file_name: str, must_exist: bool = False) -> Path:
    """
    Resolve `file_name` against CODEBASE_ROOT and verify that it cannot escape the sandbox.
    
    Returns:
        The absolute path on success.
        
    Raises:
        PathSecurityError: Callers should catch this and return the message to the LLM 
        as a tool result, so the agent can see the error and self-corret.
    """
    if not file_name or not isinstance(file_name, str):
        raise PathSecurityError("file_name cannot be an empty string.")
    
    if "\x00" in file_name:
        raise PathSecurityError("file_name cannot contain null byte.")
    
    candidate = Path(file_name)

    if candidate.is_absolute():
        raise PathSecurityError(
            f"Absolute paths are not allowed: {file_name!r}. Use a path relative to codebase root."
        )
    
    resolved = (CODEBASE_ROOT / candidate).resolve()
    
    if not resolved.is_relative_to(CODEBASE_ROOT):
        raise PathSecurityError("Path escapes the codebase.")
    
    if resolved.suffix not in ALLOWED_EXTENSIONS:
        raise PathSecurityError(f"Extension: {resolved.suffix!r} is not allowed.")
    
    if must_exist and not resolved.is_file():
        raise PathSecurityError("File does not exist.")
    
    return resolved