#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "codex_autorunner"

HINT_CONSTANTS = {
    "PROMPT_CONTEXT_HINT",
    "WHISPER_TRANSCRIPT_DISCLAIMER",
    "FILES_HINT_TEMPLATE",
}


def _collect_parents(node: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}

    for parent in ast.walk(node):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _is_assign_target(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    if isinstance(parent, ast.Assign):
        return any(node is target for target in parent.targets)
    if isinstance(parent, ast.AnnAssign):
        return node is parent.target
    return False


def _has_wrap_ancestor(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.Call):
            func = current.func
            if isinstance(func, ast.Name) and func.id == "wrap_injected_context":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "wrap_injected_context":
                return True
    return False


def _is_in_comparison(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    if not isinstance(parent, ast.Compare):
        return False
    return any(isinstance(op, (ast.In, ast.NotIn)) for op in parent.ops)


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{path}: failed to parse ({exc})"]
    parents = _collect_parents(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name):
            continue
        if node.id not in HINT_CONSTANTS:
            continue
        if _is_assign_target(node, parents):
            continue
        if _has_wrap_ancestor(node, parents):
            continue
        if _is_in_comparison(node, parents):
            continue
        errors.append(
            f"{path}:{node.lineno}:{node.col_offset + 1} "
            f"{node.id} must be wrapped with wrap_injected_context()."
        )
    return errors


def main() -> int:
    if not SRC_ROOT.exists():
        print(f"Missing src root: {SRC_ROOT}")
        return 1
    failures: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        failures.extend(_check_file(path))
    if failures:
        print("Injected context hint check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Injected context hint check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
