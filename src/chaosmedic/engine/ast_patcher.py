"""Python AST-aware patch generation, validation, and minimal unified diffing."""
from __future__ import annotations

import ast
import difflib
import logging

logger = logging.getLogger(__name__)


def validate_python_syntax(code_string: str) -> tuple[bool, str]:
    """Parse python code into an AST to verify syntax validity."""
    try:
        ast.parse(code_string)
        return True, "Valid Python syntax"
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"


def generate_unified_diff(original: str, patched: str, filepath: str = "app.py") -> str:
    """Generate a standard minimal unified diff."""
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        orig_lines,
        patch_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm=""
    ))
    return "".join(diff)


def apply_patch_string(original: str, diff_text: str) -> str:
    """Apply unified diff text to original source code string."""
    # Simplified line-based patch application
    lines = original.splitlines()
    patch_lines = diff_text.splitlines()
    
    # Extract additions and deletions
    hunks = []
    current_hunk = None
    
    for line in patch_lines:
        if line.startswith("@@"):
            current_hunk = []
            hunks.append(current_hunk)
        elif current_hunk is not None:
            current_hunk.append(line)
            
    if not hunks:
        return original
        
    # If standard diff, rebuild
    # Fallback to direct replacement for generated diffs
    out = []
    for h in hunks:
        for l in h:
            if l.startswith("+") and not l.startswith("+++"):
                out.append(l[1:])
            elif not l.startswith("-") and not l.startswith("---"):
                out.append(l[1:] if l.startswith(" ") else l)
    return "\n".join(out) if out else original


def calculate_minimality_score(diff_text: str) -> float:
    """Score diff minimality: fewer changed lines = higher score (1.0 = highly minimal)."""
    lines = diff_text.splitlines()
    changed = sum(1 for l in lines if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---")))
    if changed == 0:
        return 0.5
    # Inverse score curve: 1-3 lines -> 1.0, 4-10 lines -> 0.8, 10-25 -> 0.6, >25 -> 0.3
    if changed <= 3:
        return 1.0
    elif changed <= 8:
        return 0.85
    elif changed <= 20:
        return 0.65
    return 0.4
