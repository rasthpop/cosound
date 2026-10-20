#!/usr/bin/env python3
"""Static layer-boundary checker for the semantic music discovery project.

Checks Python imports under src/music_discovery/ and TS/TSX imports under
frontend/src/ against the layer tables documented in
skills/music-discovery-architecture/SKILL.md. Exits 1 on violations.
Missing directories are skipped, so it can run before code exists.

Usage:
    python skills/music-discovery-architecture/scripts/check_boundaries.py [--root PATH] [--only python|ts]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

PKG = "music_discovery"

# --- Python rules -----------------------------------------------------------

# layer -> internal layers it may import (own layer always allowed)
PY_ALLOWED: dict[str, set[str]] = {
    "domain": set(),
    "infrastructure": {"domain"},
    "ingestion": {"domain"},
    "audio": {"domain"},
    "retrieval": {"domain"},
    "descriptions": {"domain"},
    "spatial": {"domain"},
    "agents": {"domain", "retrieval", "descriptions"},
    "application": {"domain", "agents", "retrieval", "descriptions", "spatial"},
    "api": {"domain", "application"},
    "evaluation": {"domain", "retrieval", "agents", "descriptions", "spatial"},
}

# package-relative files that are composition roots (may import any layer)
PY_COMPOSITION_ROOTS = {"api/dependencies.py", "api/app.py"}

# third-party top-level module -> layers allowed to import it
PY_THIRD_PARTY: dict[str, set[str]] = {
    "fastapi": {"api"},
    "starlette": {"api"},
    "uvicorn": {"api"},
    "torch": {"audio"},
    "torchaudio": {"audio"},
    "laion_clap": {"audio"},
    "transformers": {"audio"},
    "librosa": {"audio"},
    "soundfile": {"audio"},
    "audioread": {"audio"},
    "umap": {"spatial"},
    "httpx": {"ingestion", "infrastructure"},
    "requests": {"ingestion", "infrastructure"},
    "aiohttp": {"ingestion", "infrastructure"},
    "sqlalchemy": {"infrastructure"},
    "sqlite3": {"infrastructure"},
    "faiss": {"infrastructure"},
    "anthropic": {"infrastructure"},
    "openai": {"infrastructure"},
}

# --- TypeScript rules -------------------------------------------------------

# layer (first segment under frontend/src) -> allowed target path prefixes
TS_ALLOWED: dict[str, tuple[str, ...]] = {
    "api": ("api",),
    "hooks": ("api", "hooks"),
    "mocks": ("api", "mocks"),
    "theme": ("theme",),
    "components": ("components", "theme", "api/types", "api/generated"),
    "pages": ("pages", "hooks", "components", "theme", "api/types", "api/generated"),
}

# bare package prefix -> src path prefixes allowed to import it
TS_THIRD_PARTY: dict[str, tuple[str, ...]] = {
    "@deck.gl/": ("components/map",),
    "deck.gl": ("components/map",),
    "@luma.gl/": ("components/map",),
    "axios": ("api",),
}

# forbidden call patterns -> src path prefixes where they are allowed
TS_FORBIDDEN_CALLS: dict[str, tuple[str, ...]] = {
    r"\bfetch\s*\(": ("api", "mocks"),
    r"\bnew\s+XMLHttpRequest\b": ("api",),
    r"\bnew\s+EventSource\b": ("api",),
}

TS_SKIP_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".stories.tsx", ".d.ts")
TS_EXTS = (".ts", ".tsx")


@dataclass
class Violation:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


# --- Python -----------------------------------------------------------------


def _py_module_parts(pkg_root: Path, file: Path) -> list[str]:
    rel = file.relative_to(pkg_root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return parts


def _resolve_relative(current: list[str], is_pkg: bool, level: int, module: str | None) -> list[str]:
    base = current if is_pkg else current[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return base + (module.split(".") if module else [])


def check_python(root: Path) -> list[Violation]:
    pkg_root = root / "src" / PKG
    if not pkg_root.is_dir():
        return []
    out: list[Violation] = []
    for file in sorted(pkg_root.rglob("*.py")):
        rel_pkg = file.relative_to(pkg_root).as_posix()
        display = file.relative_to(root).as_posix()
        parts = _py_module_parts(pkg_root, file)
        if len(file.relative_to(pkg_root).parts) == 1:
            continue  # package-root modules (__init__, __main__, version)
        layer = parts[0]
        if layer not in PY_ALLOWED:
            out.append(Violation(display, 1, f"unknown layer '{layer}' (add it to PY_ALLOWED and the architecture skill)"))
            continue
        is_root = rel_pkg in PY_COMPOSITION_ROOTS
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=display)
        except SyntaxError as exc:
            out.append(Violation(display, exc.lineno or 1, f"syntax error: {exc.msg}"))
            continue
        is_pkg = file.name == "__init__.py"
        for node in ast.walk(tree):
            targets: list[list[str]] = []
            if isinstance(node, ast.Import):
                targets = [a.name.split(".") for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    targets = [_resolve_relative(parts, is_pkg, node.level, node.module)]
                    targets = [[PKG, *t] for t in targets]
                elif node.module:
                    targets = [node.module.split(".")]
            for t in targets:
                if not t:
                    continue
                if t[0] == PKG:
                    if len(t) < 2 or is_root:
                        continue
                    target_layer = t[1]
                    if target_layer == layer:
                        continue
                    if target_layer not in PY_ALLOWED.get(layer, set()):
                        out.append(Violation(display, node.lineno, f"layer '{layer}' must not import '{PKG}.{target_layer}'"))
                else:
                    allowed = PY_THIRD_PARTY.get(t[0])
                    if allowed is not None and layer not in allowed:
                        out.append(Violation(display, node.lineno, f"'{t[0]}' may only be imported in {sorted(allowed)}, not '{layer}'"))
    return out


# --- TypeScript -------------------------------------------------------------

_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
_LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)
_IMPORT_PATTERNS = [
    re.compile(r"""(?:^|[\s;])(?:import|export)\s+(?:type\s+)?[\w*{}\s,$]*?\s*from\s*['"]([^'"]+)['"]"""),
    re.compile(r"""(?:^|[\s;])import\s*['"]([^'"]+)['"]"""),
    re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
]


def _strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _LINE_COMMENT.sub("", text)


def _normalize_target(p: PurePosixPath) -> str:
    s = p.as_posix()
    for ext in (".tsx", ".ts", ".jsx", ".js"):
        if s.endswith(ext):
            s = s[: -len(ext)]
    if s.endswith("/index"):
        s = s[: -len("/index")]
    return s


def _resolve_ts(spec: str, file_rel: PurePosixPath) -> str | None:
    """Return src-relative target for internal imports, None for bare packages."""
    if spec.startswith("@/"):
        return _normalize_target(PurePosixPath(spec[2:]))
    if spec.startswith("src/"):
        return _normalize_target(PurePosixPath(spec[4:]))
    if spec.startswith("."):
        parts: list[str] = list(file_rel.parent.parts)
        for seg in PurePosixPath(spec).parts:
            if seg == ".":
                continue
            if seg == "..":
                if not parts:
                    return "../"  # escapes src/
                parts.pop()
            else:
                parts.append(seg)
        return _normalize_target(PurePosixPath(*parts)) if parts else ""
    return None


def _has_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def check_ts(root: Path) -> list[Violation]:
    src = root / "frontend" / "src"
    if not src.is_dir():
        return []
    out: list[Violation] = []
    for file in sorted(src.rglob("*")):
        if file.suffix not in TS_EXTS or file.name.endswith(TS_SKIP_SUFFIXES):
            continue
        if "node_modules" in file.parts:
            continue
        rel = PurePosixPath(file.relative_to(src).as_posix())
        display = file.relative_to(root).as_posix()
        if len(rel.parts) == 1:
            continue  # composition root files (main.tsx, App.tsx)
        layer = rel.parts[0]
        rel_str = _normalize_target(rel)
        text = _strip_comments(file.read_text(encoding="utf-8"))

        def line_of(pos: int) -> int:
            return text.count("\n", 0, pos) + 1

        for pat in _IMPORT_PATTERNS:
            for m in pat.finditer(text):
                spec = m.group(1)
                target = _resolve_ts(spec, rel)
                ln = line_of(m.start(1))
                if target is None:
                    for pkg, allowed in TS_THIRD_PARTY.items():
                        if spec == pkg.rstrip("/") or spec.startswith(pkg):
                            if not _has_prefix(rel_str, allowed):
                                out.append(Violation(display, ln, f"'{spec}' may only be imported under {list(allowed)}"))
                    continue
                if target.startswith("../"):
                    out.append(Violation(display, ln, f"import '{spec}' escapes frontend/src (backend code must never be imported)"))
                    continue
                target_layer = target.split("/")[0] if target else ""
                if target_layer == layer:
                    continue
                allowed = TS_ALLOWED.get(layer)
                if allowed is None:
                    continue  # unlisted layers (dev/, test/) are unrestricted
                if not _has_prefix(target, allowed):
                    out.append(Violation(display, ln, f"'{layer}/' must not import '{target}' (allowed: {list(allowed)})"))
        for pattern, allowed in TS_FORBIDDEN_CALLS.items():
            if _has_prefix(rel_str, allowed):
                continue
            for m in re.finditer(pattern, text):
                out.append(Violation(display, line_of(m.start()), f"network call '{m.group(0).strip()}' outside {list(allowed)}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    ap.add_argument("--only", choices=["python", "ts"], help="check only one side")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    violations: list[Violation] = []
    if args.only in (None, "python"):
        violations += check_python(root)
    if args.only in (None, "ts"):
        violations += check_ts(root)

    for v in violations:
        print(v)
    if violations:
        print(f"\n{len(violations)} boundary violation(s).", file=sys.stderr)
        return 1
    print("boundaries OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
