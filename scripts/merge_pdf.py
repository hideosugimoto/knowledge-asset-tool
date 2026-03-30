#!/usr/bin/env python3
"""Merge manual chapter markdown files into a single consolidated document.

Concatenates all markdown files from a manual directory in order,
inserts page-break separators, generates a table of contents, and
optionally converts to PDF via pandoc.

Usage:
    python3 scripts/merge_pdf.py --manual-dir docs/manual/test6 --output docs/test6-complete.pdf
    python3 scripts/merge_pdf.py --manual-dir docs/manual/test6 --output docs/test6-complete.md
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

PAGE_BREAK = "\n\n---\n\n"
LINES_PER_PAGE_ESTIMATE = 40


def collect_files(manual_dir: Path) -> list[Path]:
    """Collect markdown files from manual_dir in correct order.

    Chapter files (00-*.md through 09-*.md) are sorted numerically.
    Feature files from features/ subdirectory are inserted immediately
    after 03-features.md, sorted alphabetically.

    Args:
        manual_dir: Path to the manual directory.

    Returns:
        Ordered list of Path objects.

    Raises:
        FileNotFoundError: If manual_dir does not exist.
        ValueError: If no markdown files are found.
    """
    manual_dir = Path(manual_dir)
    if not manual_dir.is_dir():
        raise FileNotFoundError(f"Directory not found: {manual_dir}")

    # Collect top-level .md files (chapters), sorted by name
    chapter_files = sorted(
        f for f in manual_dir.iterdir() if f.is_file() and f.suffix == ".md"
    )

    if not chapter_files:
        raise ValueError(f"No markdown files found in {manual_dir}")

    # Collect feature files if features/ subdirectory exists
    features_dir = manual_dir / "features"
    feature_files = []
    if features_dir.is_dir():
        feature_files = sorted(
            f for f in features_dir.iterdir() if f.is_file() and f.suffix == ".md"
        )

    # Insert feature files after 03-features.md
    result = []
    for chapter in chapter_files:
        result.append(chapter)
        if chapter.name == "03-features.md" and feature_files:
            result.extend(feature_files)

    return result


def generate_toc(files: list[Path]) -> str:
    """Generate a table of contents from the first H1 heading of each file.

    If a file has no H1 heading, the filename (without extension and
    numeric prefix) is used as a fallback.

    Args:
        files: Ordered list of markdown file paths.

    Returns:
        Markdown-formatted table of contents string.
    """
    h1_pattern = re.compile(r"^#\s+(.+)", re.MULTILINE)
    entries = []

    for f in files:
        content = f.read_text(encoding="utf-8")
        match = h1_pattern.search(content)
        if match:
            title = match.group(1).strip()
        else:
            # Fallback: use filename without extension, strip numeric prefix
            title = f.stem
        entries.append(f"- {title}")

    toc = "# Table of Contents\n\n" + "\n".join(entries) + "\n"
    return toc


def concatenate_markdown(files: list[Path], *, include_toc: bool = True) -> str:
    """Concatenate markdown files with page-break separators.

    Args:
        files: Ordered list of markdown file paths.
        include_toc: If True, prepend a generated table of contents.

    Returns:
        Single concatenated markdown string.
    """
    parts = []

    if include_toc:
        toc = generate_toc(files)
        parts.append(toc)

    for f in files:
        content = f.read_text(encoding="utf-8").rstrip()
        parts.append(content)

    return PAGE_BREAK.join(parts)


def merge_manual(manual_dir: Path, output: Path) -> dict:
    """Merge manual directory into a single output file.

    If the output path has a .pdf extension and pandoc is available,
    converts to PDF. Otherwise outputs as .md and suggests a pandoc
    command.

    Args:
        manual_dir: Path to the manual directory containing chapter files.
        output: Desired output file path (.md or .pdf).

    Returns:
        Dict with keys: output_path, file_size, chapter_count,
        page_estimate, fallback, and optionally pandoc_command.

    Raises:
        FileNotFoundError: If manual_dir does not exist.
        ValueError: If manual_dir contains no markdown files.
    """
    manual_dir = Path(manual_dir)
    output = Path(output)

    files = collect_files(manual_dir)
    merged = concatenate_markdown(files, include_toc=True)

    # Ensure output parent directories exist
    output.parent.mkdir(parents=True, exist_ok=True)

    want_pdf = output.suffix.lower() == ".pdf"
    fallback = False
    pandoc_command = None

    if want_pdf:
        md_path = output.with_suffix(".md")
        md_path.write_text(merged, encoding="utf-8")

        if shutil.which("pandoc"):
            cmd = [
                "pandoc",
                str(md_path),
                "-o",
                str(output),
                "--toc",
                "--pdf-engine=xelatex",
            ]
            subprocess.run(cmd, check=True)
            actual_output = output
        else:
            fallback = True
            actual_output = md_path
            pandoc_command = (
                f"pandoc {md_path} -o {output} --toc --pdf-engine=xelatex"
            )
    else:
        output.write_text(merged, encoding="utf-8")
        actual_output = output

    line_count = merged.count("\n") + 1
    page_estimate = max(1, line_count // LINES_PER_PAGE_ESTIMATE)

    result = {
        "output_path": str(actual_output),
        "file_size": actual_output.stat().st_size,
        "chapter_count": len(files),
        "page_estimate": page_estimate,
        "fallback": fallback,
    }

    if pandoc_command:
        result["pandoc_command"] = pandoc_command

    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list. Defaults to sys.argv[1:].

    Returns:
        Parsed namespace with manual_dir, output, and no_toc.
    """
    parser = argparse.ArgumentParser(
        description="Merge manual chapter markdown files into a single document."
    )
    parser.add_argument(
        "--manual-dir",
        required=True,
        help="Path to the manual directory containing chapter .md files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file path (.md or .pdf).",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        default=False,
        help="Disable table of contents generation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for CLI usage."""
    args = parse_args(argv)
    manual_dir = Path(args.manual_dir)
    output = Path(args.output)

    result = merge_manual(manual_dir, output)

    print(f"Output:     {result['output_path']}")
    print(f"File size:  {result['file_size']:,} bytes")
    print(f"Chapters:   {result['chapter_count']}")
    print(f"Pages (est): {result['page_estimate']}")

    if result.get("fallback"):
        print(f"\nNote: pandoc not found. Markdown file generated instead.")
        print(f"To convert to PDF, run:\n  {result['pandoc_command']}")


if __name__ == "__main__":
    main()
