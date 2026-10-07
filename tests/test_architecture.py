"""The rules layer must stay independent of presentation."""

from __future__ import annotations

import ast
from pathlib import Path

import neon_royale

PACKAGE = Path(neon_royale.__file__).resolve().parent
CORE = PACKAGE / "core"
FORBIDDEN_ROOTS = {"pygame", "numpy"}
FORBIDDEN_SIBLINGS = {"ui", "audio"}


def _imports(path: Path) -> list[tuple[str, int]]:
    """Every module imported by ``path`` as (absolute-ish name, relative level)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def _resolve(path: Path, module: str, level: int) -> str:
    if level == 0:
        return module
    parts = list(path.relative_to(PACKAGE.parent).with_suffix("").parts)
    base = parts[:-level]
    return ".".join([*base, module] if module else base)


def test_core_modules_exist() -> None:
    assert list(CORE.rglob("*.py")), "core package should not be empty"


def test_core_never_imports_presentation() -> None:
    offenders = []
    for path in CORE.rglob("*.py"):
        for module, level in _imports(path):
            name = _resolve(path, module, level)
            root = name.split(".")[0]
            parts = name.split(".")
            touches_ui = (
                len(parts) > 1 and parts[0] == "neon_royale" and (parts[1] in FORBIDDEN_SIBLINGS)
            )
            if root in FORBIDDEN_ROOTS or touches_ui:
                offenders.append(f"{path.relative_to(PACKAGE)} imports {name}")
    assert not offenders, "core must stay pure Python:\n" + "\n".join(offenders)
