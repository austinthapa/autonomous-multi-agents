import pytest

from agents import security
from agents.tools import file_ops

@pytest.fixture(autouse=True)
def sandbox_root(tmp_path, monkeypatch):
    root = tmp_path / "codebase"
    root.mkdir()
    monkeypatch.setattr(security, "CODEBASE_ROOT", root.resolve())
    return root

def test_view_returns_file_content(sandbox_root):
    (sandbox_root / "app.py").write_text("Can you read this?")
    assert file_ops.view_codebase_file("app.py") == "Can you read this?"


def test_view_missing_file_returns_error_string():
    result = file_ops.view_codebase_file("missing.py")
    assert result.startswith("Error")
  
    
def test_view_blocks_traversal_and_return_error():
    result = file_ops.view_codebase_file("../../etc/password")
    assert result.startswith("Error")
    
    
def test_view_blocks_disallowed_extension(sandbox_root):
    (sandbox_root / "script.sh").write_text("echo 'hello'")
    result = file_ops.view_codebase_file("script.sh")
    assert result.startswith("Error")
    
    
def test_patch_writes_new_content(sandbox_root):
    (sandbox_root / "app.py").write_text("old text")
    result = file_ops.patch_codebase_file("app.py", "new text")
    assert result.startswith("OK")
    assert (sandbox_root / "app.py").read_text() == "new text"
    
    
def test_patch_can_create_new_file(sandbox_root):
    result = file_ops.patch_codebase_file("helper.py", "def new_function(): pass")
    assert result.startswith("OK")
    assert (sandbox_root / "helper.py").read_text() == "def new_function(): pass"
    
    
def test_patch_blocks_disallowed_extension():
    result = file_ops.patch_codebase_file("helper.exe", "Execute this virus.")
    assert result.startswith("Error")
    
    
def test_patch_block_traversal():
    result = file_ops.patch_codebase_file("../hack.py", "run the script")
    assert result.startswith("Error")
    
    
def test_patch_does_not_leave_tmp_file_behind(sandbox_root):
    file_ops.patch_codebase_file("app.py", "just a content")
    leftovers = list(sandbox_root.glob("*.tmp"))
    assert leftovers == []