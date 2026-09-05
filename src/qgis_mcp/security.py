"""Path sandboxing and security validation for QGIS MCP Connector."""

import os
from pathlib import Path
from typing import Optional, List

# Allowed directory roots for reading / writing project files
DEFAULT_ALLOWED_ROOTS: List[Path] = [
    Path.cwd().resolve(),
    Path.home().resolve(),
    Path(os.environ.get("TEMP", "/tmp")).resolve(),
]

def sanitize_path(input_path: str) -> str:
    """Normalize path to use forward slashes and prevent double backslashes."""
    return input_path.replace("\\", "/")

def validate_safe_path(
    path_str: str,
    allow_create: bool = False,
    extra_allowed_roots: Optional[List[Path]] = None
) -> Path:
    """Ensure path is not traversing outside permitted directories."""
    clean_str = sanitize_path(path_str)
    resolved = Path(clean_str).resolve()
    
    allowed = list(DEFAULT_ALLOWED_ROOTS)
    if extra_allowed_roots:
        allowed.extend(extra_allowed_roots)

    # Basic directory traversal check
    is_safe = any(resolved == root or root in resolved.parents for root in allowed)
    if not is_safe:
        raise PermissionError(f"Access to path '{path_str}' is outside allowed directories.")

    if allow_create and not resolved.parent.exists():
        resolved.parent.mkdir(parents=True, exist_ok=True)

    return resolved