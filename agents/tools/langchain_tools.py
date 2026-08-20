from langchain_core.tools import tool
from agents.tools.file_ops import view_codebase_file, patch_codebase_file
from agents.tools.test_runner import run_verification_tests

@tool
def view_codebase(file_name: str) -> str:
    """
    Reads and returns the contents of a file inside the sandboxed codebase directory.
    """
    return view_codebase_file(file_name)

@tool
def patch_codebase(file_name: str, code_content: str) -> str:
    """
    Overwrites a file inside the sandboxed codebase directory with new content.
    """
    return patch_codebase_file(file_name, code_content)

@tool
def run_pytest_suite() -> str:
    """
    Run the project pytest suite and return the result and logs.
    """
    return run_verification_tests()
    
AGENT_TOOLS = [view_codebase, patch_codebase, run_pytest_suite]
TOOL_MAP = {tool.name:tool for tool in AGENT_TOOLS}