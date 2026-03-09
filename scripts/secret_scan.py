#!/usr/bin/env python3
"""Lightweight high-confidence secret scanner for tracked source files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ALLOW_MARKER = "secret-scan:allow"

PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        "OpenAI-style key",
        re.compile(r"\bsk-(?:proj-|live-|test-|user-)?[A-Za-z0-9]{20,}\b"),
    ),
    (
        "GitHub token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    ),
    (
        "Credentialed URL",
        re.compile(r"https?://[^/\s:@]+:[^/\s@]+@"),
    ),
    (
        "AWS access key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
]

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov", ".avi", ".webm",
    ".sqlite", ".db",
}


def _tracked_files() -> Iterable[Path]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    for rel in proc.stdout.splitlines():
        if rel.strip():
            yield ROOT / rel.strip()


def _from_cli_paths(paths: Iterable[str]) -> Iterable[Path]:
    for p in paths:
        candidate = (ROOT / p).resolve() if not Path(p).is_absolute() else Path(p)
        if candidate.is_file():
            yield candidate


def _should_skip(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    return False


def _mask_secret(text: str) -> str:
    masked = text
    for _, pattern in PATTERNS:
        masked = pattern.sub("<redacted>", masked)
    return masked


def scan_files(files: Iterable[Path]) -> List[str]:
    findings: List[str] = []
    for path in files:
        if _should_skip(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        rel_path = path.relative_to(ROOT)
        for line_number, line in enumerate(content.splitlines(), start=1):
            if ALLOW_MARKER in line:
                continue
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    snippet = _mask_secret(line.strip())[:160]
                    findings.append(
                        f"{rel_path}:{line_number}: {name} -> {snippet}"
                    )
                    break
    return findings


def main() -> int:
    files = list(_from_cli_paths(sys.argv[1:])) if len(sys.argv) > 1 else list(_tracked_files())
    findings = scan_files(files)
    if findings:
        print("Secret scan failed. Potential secrets found:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("Secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

