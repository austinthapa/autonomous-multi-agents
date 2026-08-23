"""
Unit tests for agents.security

These are the tests that matters most; they prove the sandbox actually 
holds against traversal, absolute paths, and disallowed extensions.
"""

import pytest

from agents import security

@pytest.fixture(autouse=True)
def sandbox_root(tmp_path, monkeypatch):
    """Point the sandbox at a throwaway tmp_path for every test."""
    root = tmp_path / "codebase"
    root.mkdir()
    monkeypatch.setattr(security, "CODEBASE_ROOT", root.resolve())
    return root


def test_current_directory_path_is_allowed():
    resolved = security.resolve_safe_path(".")
    assert resolved == security.CODEBASE_ROOT


def test_simple_relative_path_resolves_inside_root(sandbox_root):
    (sandbox_root / "app.py").write_text("print('hi')")
    resolved = security.resolve_safe_path("app.py", must_exist=True)
    assert resolved == (sandbox_root / "app.py").resolve()


def test_nested_relative_path_resolves_inside_root(sandbox_root):
    (sandbox_root / "math").mkdir()
    (sandbox_root / "math" / "mod.py").write_text("x = 1")
    resolved = security.resolve_safe_path("math/mod.py", must_exist=True)
    assert resolved == (sandbox_root / "math" / "mod.py").resolve()
    
    
def test_parent_traversal_is_blocked():
    with pytest.raises(security.PathSecurityError, match="escapes"):
        security.resolve_safe_path("../secrets.txt")
    
        
def test_deep_parent_traversal_is_blocked():
    with pytest.raises(security.PathSecurityError, match="escapes"):
        security.resolve_safe_path("../../../etc/password")
    
        
def test_absolute_path_is_blocked():
    with pytest.raises(security.PathSecurityError, match="Absolute paths"):
        security.resolve_safe_path("/etc/password")


def test_disallowed_extension_is_blocked():
    with pytest.raises(security.PathSecurityError, match="Extension"):
        security.resolve_safe_path("test.sh")

        
def test_null_byte_is_blocked():
    with pytest.raises(security.PathSecurityError, match="null byte"):
        security.resolve_safe_path("app.py\x00.sh")
        
        
def test_must_exist_for_missing_file():
    with pytest.raises(security.PathSecurityError, match="does not exist"):
        security.resolve_safe_path("unknown.py", must_exist=True)
        
        
def test_must_exist_false_allows_new_file(sandbox_root):
    resolved = security.resolve_safe_path("new_file.py", must_exist=False)
    assert resolved.parent == sandbox_root.resolve()
    
    
def test_symlink_file_escape_is_blocked(sandbox_root, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("This is outside the directory")
    link = sandbox_root / "link.py"
    link.symlink_to(outside)
    
    with pytest.raises(security.PathSecurityError):
        security.resolve_safe_path("link.py", must_exist=True)
      
        
def test_symlink_directory_escape_is_blocked(sandbox_root, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    
    (outside / "secret.py").write_text("This is env secrets.")
    
    link = sandbox_root / "link"
    link.symlink_to(outside, target_is_directory = True)
    with pytest.raises(security.PathSecurityError):
        security.resolve_safe_path("link/secret.py", must_exist=True)