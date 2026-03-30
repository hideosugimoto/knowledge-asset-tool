#!/usr/bin/env python3
"""Pre-scan a target codebase to generate a prioritized file list for analysis.

Outputs a JSON manifest of files categorized by importance with recommended
read order, enabling thorough documentation generation.

Usage:
    python3 scripts/scan_sources.py --source-dir /path/to/project [--output manifest.json]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Directories to always exclude from scanning
EXCLUDED_DIRS = {
    "node_modules",
    "vendor",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".nuxt",
    ".output",
    ".cache",
    "coverage",
    ".idea",
    ".vscode",
}

# Category priority order for read_order generation
CATEGORY_ORDER = ["critical", "high", "medium", "low"]

# File extensions considered low-priority assets
ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".avi", ".mov", ".webm",
    ".pdf", ".zip", ".tar", ".gz",
}

# Lock / generated files that are always low priority
LOW_PRIORITY_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "Gemfile.lock",
    "poetry.lock",
    "Pipfile.lock",
    ".env.example",
    ".env.local",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".prettierrc",
    ".prettierrc.json",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.js",
    "tsconfig.json",
    "tailwind.config.js",
    "tailwind.config.ts",
    "postcss.config.js",
    "postcss.config.mjs",
    "babel.config.js",
    "webpack.config.js",
    "vite.config.js",
    "vite.config.ts",
}


def detect_project_type(source_dir: str) -> str:
    """Detect the project type(s) by analyzing marker files.

    Returns a string like 'laravel', 'nuxt', 'laravel+nuxt', or 'generic'.
    """
    detected: list[str] = []
    root = Path(source_dir)

    # Laravel detection
    composer_path = root / "composer.json"
    if composer_path.exists():
        try:
            data = json.loads(composer_path.read_text(encoding="utf-8"))
            requires = {**data.get("require", {}), **data.get("require-dev", {})}
            if any("laravel" in pkg for pkg in requires):
                detected.append("laravel")
        except (json.JSONDecodeError, OSError):
            pass

    # Nuxt detection
    if (root / "nuxt.config.js").exists() or (root / "nuxt.config.ts").exists():
        detected.append("nuxt")

    # Vue detection (only if not already nuxt)
    if "nuxt" not in detected and (root / "vue.config.js").exists():
        detected.append("vue")

    # Next.js detection
    if (
        (root / "next.config.js").exists()
        or (root / "next.config.mjs").exists()
        or (root / "next.config.ts").exists()
    ):
        detected.append("nextjs")

    # Express detection
    pkg_path = root / "package.json"
    if pkg_path.exists() and "express" not in [d for d in detected]:
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "express" in deps:
                detected.append("express")
        except (json.JSONDecodeError, OSError):
            pass

    if not detected:
        return "generic"
    return "+".join(detected)


def should_exclude(path: str) -> bool:
    """Return True if the path should be excluded from scanning."""
    parts = Path(path).parts
    return any(part in EXCLUDED_DIRS for part in parts)


def categorize_file(rel_path: str, project_type: str) -> str:
    """Categorize a file into critical/high/medium/low based on path and project type."""
    filename = os.path.basename(rel_path)
    _, ext = os.path.splitext(filename)

    # Always low: lock files, asset files, generated files
    if filename in LOW_PRIORITY_FILES:
        return "low"
    if ext.lower() in ASSET_EXTENSIONS:
        return "low"
    if rel_path.startswith("public/css/") or rel_path.startswith("public/js/"):
        return "low"
    if filename.startswith(".env"):
        return "low"

    types = project_type.split("+")

    # --- Critical rules ---
    # Laravel
    if "laravel" in types:
        if re.match(r"^routes/", rel_path):
            return "critical"
        if re.match(r"^app/Models/", rel_path):
            return "critical"
        if re.match(r"^app/Http/Controllers/", rel_path):
            return "critical"

    # Nuxt / Vue
    if "nuxt" in types or "vue" in types:
        if re.match(r"^pages/", rel_path):
            return "critical"

    # Next.js
    if "nextjs" in types:
        if re.match(r"^app/", rel_path) and (
            filename.startswith("page.") or filename.startswith("route.") or filename.startswith("layout.")
        ):
            return "critical"
        if re.match(r"^pages/", rel_path):
            return "critical"

    # Express
    if "express" in types:
        if re.match(r"^routes/", rel_path):
            return "critical"

    # Generic entry points
    if filename in ("main.py", "main.ts", "main.js", "index.ts", "index.js", "app.py", "app.ts", "app.js"):
        if rel_path.count("/") == 0:
            return "critical"

    # Schema / model files (generic)
    if re.search(r"(models?|schemas?|entities)/", rel_path, re.IGNORECASE):
        if "laravel" not in types:  # already handled above for laravel
            return "critical"

    # --- High rules ---
    if "laravel" in types:
        if re.match(r"^app/Services/", rel_path):
            return "high"
        if re.match(r"^app/Repositories/", rel_path):
            return "high"
        if re.match(r"^app/Http/Middleware/", rel_path):
            return "high"
        if re.match(r"^database/migrations/", rel_path):
            return "high"

    if "nuxt" in types or "vue" in types:
        if re.match(r"^store/", rel_path) or re.match(r"^stores/", rel_path):
            return "high"
        if re.match(r"^composables/", rel_path):
            return "high"

    if "nextjs" in types:
        if re.match(r"^lib/", rel_path) or re.match(r"^src/lib/", rel_path):
            return "high"

    if "express" in types:
        if re.match(r"^middleware/", rel_path):
            return "high"

    # Generic high: services, repositories, middleware, state
    if re.search(r"(services?|repositories|middleware|store|redux|hooks)/", rel_path, re.IGNORECASE):
        return "high"
    if re.search(r"(migrations?|seeds?|factories)/", rel_path, re.IGNORECASE):
        return "high"

    # --- Medium rules ---
    if re.search(r"(components?|utils?|helpers?|lib)/", rel_path, re.IGNORECASE):
        return "medium"
    if re.search(r"(tests?|spec|__tests__)/", rel_path, re.IGNORECASE):
        return "medium"
    if filename.endswith(".test.ts") or filename.endswith(".test.js") or filename.endswith(".spec.ts"):
        return "medium"
    if re.search(r"(views?|layouts?|templates?)/", rel_path, re.IGNORECASE):
        return "medium"

    # --- Default: medium for code, low for others ---
    code_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".php",
        ".rb", ".go", ".rs", ".java", ".kt", ".swift", ".c", ".cpp", ".h",
        ".css", ".scss", ".sass", ".less",
        ".html", ".htm", ".xml",
        ".sql", ".graphql", ".gql",
        ".sh", ".bash", ".zsh",
        ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".md", ".mdx", ".txt", ".rst",
        ".json",
    }
    if ext.lower() in code_extensions:
        return "medium"

    return "low"


def estimate_tokens(char_count: int) -> int:
    """Estimate token count from character count (roughly chars / 4)."""
    return char_count // 4


def scan_directory(source_dir: str) -> dict[str, Any]:
    """Scan a directory and return a categorized manifest of files."""
    project_type = detect_project_type(source_dir)
    root = Path(source_dir)

    categories: dict[str, list[dict[str, Any]]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
    }

    for dirpath, dirnames, filenames in os.walk(source_dir):
        # Prune excluded directories in-place for efficiency
        dirnames[:] = [
            d for d in dirnames if d not in EXCLUDED_DIRS
        ]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, source_dir)

            # Normalize path separators
            rel_path = rel_path.replace("\\", "/")

            if should_exclude(rel_path):
                continue

            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = 0

            category = categorize_file(rel_path, project_type)
            entry = {
                "path": rel_path,
                "size": size,
                "tokens_est": estimate_tokens(size),
            }
            categories[category].append(entry)

    # Sort each category by path for deterministic output
    for cat in categories.values():
        cat.sort(key=lambda f: f["path"])

    # Build read_order: critical first, then high, medium, low
    read_order = []
    for cat_name in CATEGORY_ORDER:
        for entry in categories[cat_name]:
            read_order.append(entry["path"])

    total_files = sum(len(files) for files in categories.values())
    summary = {cat_name: len(categories[cat_name]) for cat_name in CATEGORY_ORDER}

    return {
        "project_type": project_type,
        "total_files": total_files,
        "categories": categories,
        "read_order": read_order,
        "summary": summary,
    }


def print_summary(manifest: dict[str, Any]) -> None:
    """Print a human-readable summary to stdout."""
    print(f"\n=== Source Scan Summary ===")
    print(f"Project type: {manifest['project_type']}")
    print(f"Total files: {manifest['total_files']}")
    print()
    for cat_name in CATEGORY_ORDER:
        count = manifest["summary"][cat_name]
        tokens = sum(f["tokens_est"] for f in manifest["categories"][cat_name])
        print(f"  {cat_name:10s}: {count:4d} files  (~{tokens:,} tokens)")
    total_tokens = sum(
        f["tokens_est"]
        for cat in manifest["categories"].values()
        for f in cat
    )
    print(f"\n  Estimated total tokens: ~{total_tokens:,}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-scan a codebase to generate a prioritized file manifest."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Path to the source directory to scan.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the JSON manifest. If omitted, prints to stdout.",
    )
    args = parser.parse_args()

    source_dir = os.path.abspath(args.source_dir)
    if not os.path.isdir(source_dir):
        print(f"Error: {source_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    manifest = scan_directory(source_dir)
    print_summary(manifest)

    if args.output:
        output_path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"Manifest written to: {output_path}")
    else:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
