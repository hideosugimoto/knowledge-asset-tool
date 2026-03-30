#!/usr/bin/env python3
"""Analyze git diff and determine which documentation files need regeneration.

Enables incremental doc updates instead of full regeneration by mapping
changed source files to affected documentation targets.

Usage:
    python3 scripts/diff_update.py --source-dir /path/to/project --docs-dir ./docs --base HEAD~1
    python3 scripts/diff_update.py --source-dir /path/to/project --docs-dir ./docs --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from typing import Any

# ---------------------------------------------------------------------------
# Mapping rules: source file patterns -> affected documentation files
# ---------------------------------------------------------------------------
_DEFAULT_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "mapping_rules.json")

_BUILTIN_MAPPING_RULES: list[dict[str, Any]] = [
    {
        "source_pattern": "Controllers/API/*Controller.php",
        "docs": ["features/*.md", "04-api-reference.md"],
    },
    {
        "source_pattern": "Models/*.php",
        "docs": ["05-data-model.md"],
    },
    {
        "source_pattern": "pages/**/*.vue",
        "docs": ["06-screen-specs.md", "02-screen-flow.md"],
    },
    {
        "source_pattern": "store/*.js",
        "docs": ["features/*.md"],
    },
    {
        "source_pattern": "routes/api.php",
        "docs": ["04-api-reference.md", "02-screen-flow.md"],
    },
    {
        "source_pattern": "config/*",
        "docs": ["01-overview.md"],
    },
    {
        "source_pattern": "*.json",
        "docs": ["01-overview.md"],
    },
]


def _load_mapping_rules() -> list[dict[str, Any]]:
    """Load mapping rules from mapping_rules.json, falling back to built-in defaults."""
    try:
        with open(_DEFAULT_MAPPING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return list(_BUILTIN_MAPPING_RULES)


MAPPING_RULES: list[dict[str, Any]] = _load_mapping_rules()


def _matches_pattern(filepath: str, pattern: str) -> bool:
    """Check if a filepath matches a glob-like pattern.

    Handles both simple globs (``*``) and recursive globs (``**``).  The
    match is attempted against the full path as well as against just the
    basename, so patterns like ``*.json`` match ``package.json`` at the
    repo root.
    """
    # fnmatch doesn't handle ** well; expand to a simple approach:
    # For patterns with directory separators, match against the full path.
    # For simple patterns (no /), match against the basename only.
    if "/" in pattern:
        # Attempt to match any suffix of the path segments
        parts = filepath.replace("\\", "/").split("/")
        pattern_parts = pattern.replace("\\", "/").split("/")

        # Sliding window: try matching pattern against each possible
        # sub-path of the same depth or deeper.
        for start in range(len(parts)):
            tail = "/".join(parts[start:])
            if fnmatch(tail, pattern):
                return True
        return False

    # Simple pattern (no directory component) -- match basename only
    basename = filepath.replace("\\", "/").rsplit("/", 1)[-1]
    return fnmatch(basename, pattern)


def _extract_feature_name_from_controller(filename: str) -> str:
    """Extract a kebab-case feature name from a Controller filename.

    ``DashBillingController.php`` -> ``dash-billing``
    ``UserSettingsController.php`` -> ``user-settings``
    """
    basename = filename.rsplit("/", 1)[-1]
    name = basename.replace("Controller.php", "")
    # CamelCase -> kebab-case
    kebab = re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name)
    kebab = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"-\1", kebab)
    return kebab.lower().strip("-")


def _extract_feature_name_from_store(filename: str) -> str:
    """Extract a kebab-case feature name from a store filename.

    ``store/billing.js`` -> ``billing``
    ``store/userSettings.js`` -> ``user-settings``
    """
    basename = filename.rsplit("/", 1)[-1]
    name = basename.rsplit(".", 1)[0]
    # camelCase -> kebab-case
    kebab = re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name)
    return kebab.lower()


def get_changed_files(source_dir: str, base: str) -> list[str]:
    """Run ``git diff --name-only`` and return the list of changed files.

    Raises ``RuntimeError`` when the git command exits with a non-zero code.
    """
    if not os.path.isdir(source_dir):
        raise RuntimeError(f"ソースディレクトリが存在しません: {source_dir}")
    if base.startswith("-"):
        raise ValueError(f"不正な git ref（ダッシュで開始）: '{base}'")
    cmd = ["git", "-C", source_dir, "diff", "--name-only", "--", base]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed (exit {result.returncode}): {result.stderr}"
        )

    lines = result.stdout.strip().splitlines()
    return [line.strip() for line in lines if line.strip()]


def map_source_to_docs(filepath: str) -> list[str]:
    """Map a single source file path to the list of affected doc files."""
    affected: list[str] = []

    for rule in MAPPING_RULES:
        if _matches_pattern(filepath, rule["source_pattern"]):
            for doc_pattern in rule["docs"]:
                if "*" in doc_pattern:
                    # Resolve wildcard doc patterns to concrete names
                    if "features/" in doc_pattern and "Controller" in filepath:
                        feature = _extract_feature_name_from_controller(filepath)
                        affected.append(f"features/{feature}.md")
                    elif "features/" in doc_pattern and "store/" in filepath.replace("\\", "/"):
                        feature = _extract_feature_name_from_store(filepath)
                        affected.append(f"features/{feature}.md")
                    else:
                        # Cannot resolve wildcard; keep pattern as-is
                        affected.append(doc_pattern)
                else:
                    affected.append(doc_pattern)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for doc in affected:
        if doc not in seen:
            seen.add(doc)
            unique.append(doc)
    return unique


def aggregate_updates(changed_files: list[str]) -> dict[str, list[str]]:
    """Aggregate all changed files into a dict of doc -> source_files."""
    result: dict[str, list[str]] = {}

    for filepath in changed_files:
        docs = map_source_to_docs(filepath)
        for doc in docs:
            if doc not in result:
                result[doc] = []
            if filepath not in result[doc]:
                result[doc].append(filepath)

    return result


def build_update_plan(changed_files: list[str]) -> dict[str, Any]:
    """Build the final JSON-serializable update plan."""
    aggregated = aggregate_updates(changed_files)

    needs_update: list[dict[str, Any]] = []
    for doc, sources in sorted(aggregated.items()):
        filenames = ", ".join(s.rsplit("/", 1)[-1] for s in sources)
        needs_update.append(
            {
                "doc": doc,
                "reason": f"{filenames} changed",
                "source_files": list(sources),
            }
        )

    return {"needs_update": needs_update}


def main() -> int:
    """CLI entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="Determine which docs need regeneration based on git diff."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Path to the source code repository",
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="Path to the documentation directory",
    )
    parser.add_argument(
        "--base",
        default="HEAD~1",
        help="Git ref to diff against (default: HEAD~1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be regenerated, don't modify anything",
    )

    args = parser.parse_args()

    try:
        changed = get_changed_files(args.source_dir, args.base)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    plan = build_update_plan(changed)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
