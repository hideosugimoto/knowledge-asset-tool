#!/usr/bin/env python3
"""Export generated docs to external platform formats.

Supported formats:
  - single-html : Merge all markdown into one self-contained HTML file
  - pdf-bundle  : Generate a single PDF via pandoc (delegates to merge_pdf.py)
  - confluence   : Convert to Confluence storage format (XHTML)
  - notion       : Convert to Notion-compatible Markdown (split pages)

Usage:
    python scripts/export_docs.py --docs-dir ./docs --name system-name --format single-html
    python scripts/export_docs.py --docs-dir ./docs --name system-name --format pdf-bundle
    python scripts/export_docs.py --docs-dir ./docs --name system-name --format confluence
    python scripts/export_docs.py --docs-dir ./docs --name system-name --format notion
"""

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

EXPORT_DIR = Path("exports")


def collect_markdown_files(docs_dir: Path, name: str, include_slides: bool = False) -> list[Path]:
    """Collect all markdown files related to *name* under *docs_dir*.

    Looks in well-known subdirectories (architecture/, manual/{name}/,
    explanations/{name}/, decisions/, meta/) and also picks up top-level
    files like {name}-index.md, {name}-llms.txt, {name}-AGENTS.md.

    Returns an ordered list of paths.
    """
    files: list[Path] = []

    # Top-level project files
    for pattern in [f"{name}-index.md", f"{name}-llms.txt", f"{name}-AGENTS.md"]:
        p = docs_dir / pattern
        if p.is_file():
            files.append(p)

    # Subdirectories to scan
    sub_dirs = [
        docs_dir / "architecture",
        docs_dir / "manual" / name,
        docs_dir / "manual" / name / "features",
        docs_dir / "explanations" / name,
        docs_dir / "decisions",
        docs_dir / "meta",
    ]

    for d in sub_dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix in (".md", ".txt", ".yaml"):
                files.append(f)

    # Optionally include slide HTML files
    if include_slides:
        slides_dir = docs_dir / "slides"
        if slides_dir.is_dir():
            for f in sorted(slides_dir.iterdir()):
                if f.is_file() and name in f.name and f.suffix == ".html":
                    files.append(f)

    return files


def read_text(path: Path) -> str:
    """Read a file as UTF-8, returning empty string on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ---------------------------------------------------------------------------
# single-html
# ---------------------------------------------------------------------------

BASIC_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
       max-width: 960px; margin: 0 auto; padding: 2rem; line-height: 1.6; color: #24292e; }
h1, h2, h3, h4 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #dfe2e5; padding: 6px 13px; text-align: left; }
th { background: #f6f8fa; }
code { background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%; }
pre { background: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #dfe2e5; padding: 0 1em; color: #6a737d; margin: 0; }
hr { border: none; border-top: 2px solid #eaecef; margin: 2rem 0; }
img, svg { max-width: 100%; }
.page-break { page-break-after: always; }
"""


def _md_to_html_simple(md_text: str) -> str:
    """Minimal Markdown to HTML conversion (no external dependencies).

    Handles headings, bold, italic, inline code, code blocks, links,
    images, tables, blockquotes, horizontal rules, and lists.
    Good enough for export; not a full CommonMark parser.
    """
    lines = md_text.split("\n")
    out: list[str] = []
    in_code_block = False
    in_table = False
    in_list = False
    list_type = "ul"

    for line in lines:
        # Fenced code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                out.append("</code></pre>")
                in_code_block = False
            else:
                lang = line.strip().lstrip("`").strip()
                out.append(f'<pre><code class="language-{html.escape(lang)}">' if lang else "<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            out.append(html.escape(line))
            continue

        stripped = line.strip()

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            if in_list:
                out.append(f"</{list_type}>")
                in_list = False
            if in_table:
                out.append("</table>")
                in_table = False
            out.append('<hr class="page-break">')
            continue

        # Table rows
        if "|" in stripped and stripped.startswith("|"):
            # Skip separator rows like |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            if not in_table:
                out.append("<table><thead>")
                in_table = True
                tag = "th"
            else:
                if out[-1] == "<table><thead>":
                    # First data row after header declaration
                    pass
                tag = "td"
                # Close thead after first row, switch to tbody
                if "<thead>" in "".join(out[-5:]) and "</thead>" not in "".join(out[-5:]):
                    out.append("</thead><tbody>")
                    tag = "td"
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            row = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue

        if in_table and not stripped.startswith("|"):
            out.append("</tbody></table>")
            in_table = False

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            if in_list:
                out.append(f"</{list_type}>")
                in_list = False
            level = len(m.group(1))
            text = _inline(m.group(2))
            out.append(f"<h{level}>{text}</h{level}>")
            continue

        # Blockquote
        if stripped.startswith(">"):
            text = _inline(stripped.lstrip("> "))
            out.append(f"<blockquote><p>{text}</p></blockquote>")
            continue

        # Unordered list
        m_ul = re.match(r"^[-*+]\s+(.*)", stripped)
        if m_ul:
            if not in_list or list_type != "ul":
                if in_list:
                    out.append(f"</{list_type}>")
                out.append("<ul>")
                in_list = True
                list_type = "ul"
            out.append(f"<li>{_inline(m_ul.group(1))}</li>")
            continue

        # Ordered list
        m_ol = re.match(r"^\d+\.\s+(.*)", stripped)
        if m_ol:
            if not in_list or list_type != "ol":
                if in_list:
                    out.append(f"</{list_type}>")
                out.append("<ol>")
                in_list = True
                list_type = "ol"
            out.append(f"<li>{_inline(m_ol.group(1))}</li>")
            continue

        # Close list if we hit a non-list line
        if in_list and stripped == "":
            out.append(f"</{list_type}>")
            in_list = False

        # Paragraph
        if stripped:
            out.append(f"<p>{_inline(stripped)}</p>")

    # Close any open elements
    if in_code_block:
        out.append("</code></pre>")
    if in_table:
        out.append("</tbody></table>")
    if in_list:
        out.append(f"</{list_type}>")

    return "\n".join(out)


def _inline(text: str) -> str:
    """Handle inline Markdown formatting."""
    # Images
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _inline_svg_references(html_content: str, docs_dir: Path) -> str:
    """Replace <img> tags pointing to local .svg files with inlined SVG content."""

    def replace_svg(m: re.Match) -> str:
        src = m.group(1)
        svg_path = docs_dir / src
        if svg_path.is_file() and svg_path.suffix == ".svg":
            svg_content = read_text(svg_path)
            if svg_content:
                return svg_content
        return m.group(0)

    return re.sub(r'<img\s+src="([^"]+\.svg)"[^>]*>', replace_svg, html_content)


def export_single_html(
    docs_dir: Path, name: str, output: Path, include_slides: bool = False
) -> Path:
    """Merge all markdown files into one self-contained HTML file."""
    files = collect_markdown_files(docs_dir, name, include_slides)
    if not files:
        print(f"[WARN] No files found for '{name}' in {docs_dir}")
        return output

    parts: list[str] = []
    for f in files:
        if f.suffix in (".md", ".txt"):
            content = read_text(f)
            parts.append(f"<!-- source: {f.relative_to(docs_dir)} -->\n")
            parts.append(_md_to_html_simple(content))
            parts.append('<hr class="page-break">')
        elif f.suffix == ".html":
            parts.append(f"<!-- slide: {f.name} -->\n")
            parts.append(read_text(f))

    body = "\n".join(parts)
    body = _inline_svg_references(body, docs_dir)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(name)} - Documentation</title>
<style>{BASIC_CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")
    print(f"[OK] single-html: {output} ({output.stat().st_size:,} bytes)")
    return output


# ---------------------------------------------------------------------------
# pdf-bundle
# ---------------------------------------------------------------------------

def export_pdf_bundle(
    docs_dir: Path, name: str, output: Path, include_slides: bool = False
) -> Path:
    """Generate a single PDF by delegating to merge_pdf.py logic.

    Looks for a manual directory first; falls back to collecting all
    markdown and using pandoc directly.
    """
    manual_dir = docs_dir / "manual" / name
    if manual_dir.is_dir():
        # Use merge_pdf.py
        scripts_dir = Path(__file__).resolve().parent
        cmd = [
            sys.executable,
            str(scripts_dir / "merge_pdf.py"),
            "--manual-dir", str(manual_dir),
            "--output", str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
        return output

    # Fallback: collect all markdown, merge, convert with pandoc
    files = collect_markdown_files(docs_dir, name, include_slides)
    md_files = [f for f in files if f.suffix in (".md", ".txt")]
    if not md_files:
        print(f"[WARN] No markdown files found for '{name}' in {docs_dir}")
        return output

    # Concatenate into a temp markdown file
    merged_md = output.with_suffix(".md")
    parts = []
    for f in md_files:
        parts.append(read_text(f))
    merged_md.parent.mkdir(parents=True, exist_ok=True)
    merged_md.write_text("\n\n---\n\n".join(parts), encoding="utf-8")

    if shutil.which("pandoc"):
        cmd = [
            "pandoc", str(merged_md), "-o", str(output),
            "--toc", "--pdf-engine=xelatex",
        ]
        subprocess.run(cmd, check=False)
        if output.is_file():
            print(f"[OK] pdf-bundle: {output} ({output.stat().st_size:,} bytes)")
        else:
            print(f"[WARN] pandoc failed. Markdown available at: {merged_md}")
    else:
        print(f"[WARN] pandoc not found. Markdown saved to: {merged_md}")
        print(f"  To convert: pandoc {merged_md} -o {output} --toc --pdf-engine=xelatex")

    return output


# ---------------------------------------------------------------------------
# confluence
# ---------------------------------------------------------------------------

def _md_to_confluence(md_text: str) -> str:
    """Convert Markdown to Confluence storage format (XHTML).

    Produces good-enough XHTML that can be pasted into the Confluence
    editor.  Mermaid code blocks become {code} macros.
    """
    lines = md_text.split("\n")
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    in_table = False
    header_done = False

    for line in lines:
        # Fenced code blocks
        if line.strip().startswith("```"):
            if in_code:
                code_content = html.escape("\n".join(code_lines))
                if code_lang == "mermaid":
                    out.append(
                        f'<ac:structured-macro ac:name="code">'
                        f'<ac:parameter ac:name="language">text</ac:parameter>'
                        f'<ac:parameter ac:name="title">Mermaid Diagram</ac:parameter>'
                        f'<ac:plain-text-body><![CDATA[{chr(10).join(code_lines)}]]>'
                        f'</ac:plain-text-body></ac:structured-macro>'
                    )
                else:
                    lang_param = f'<ac:parameter ac:name="language">{html.escape(code_lang)}</ac:parameter>' if code_lang else ""
                    out.append(
                        f'<ac:structured-macro ac:name="code">'
                        f'{lang_param}'
                        f'<ac:plain-text-body><![CDATA[{chr(10).join(code_lines)}]]>'
                        f'</ac:plain-text-body></ac:structured-macro>'
                    )
                in_code = False
                code_lines = []
                code_lang = ""
            else:
                in_code = True
                code_lang = line.strip().lstrip("`").strip()
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            if in_table:
                out.append("</tbody></table>")
                in_table = False
                header_done = False
            out.append("<hr />")
            continue

        # Table
        if "|" in stripped and stripped.startswith("|"):
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                out.append("<table><tbody>")
                in_table = True
                header_done = False
                tag = "th"
            else:
                tag = "td"
            row = "".join(f"<{tag}>{_inline_confluence(c)}</{tag}>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            if tag == "th":
                header_done = True
            continue

        if in_table and not stripped.startswith("|"):
            out.append("</tbody></table>")
            in_table = False
            header_done = False

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            text = _inline_confluence(m.group(2))
            out.append(f"<h{level}>{text}</h{level}>")
            continue

        # Blockquote -> Confluence info macro
        if stripped.startswith(">"):
            text = _inline_confluence(stripped.lstrip("> "))
            out.append(
                f'<ac:structured-macro ac:name="info">'
                f'<ac:rich-text-body><p>{text}</p></ac:rich-text-body>'
                f'</ac:structured-macro>'
            )
            continue

        # Lists
        m_ul = re.match(r"^[-*+]\s+(.*)", stripped)
        if m_ul:
            out.append(f"<ul><li>{_inline_confluence(m_ul.group(1))}</li></ul>")
            continue

        m_ol = re.match(r"^\d+\.\s+(.*)", stripped)
        if m_ol:
            out.append(f"<ol><li>{_inline_confluence(m_ol.group(1))}</li></ol>")
            continue

        # Paragraph
        if stripped:
            out.append(f"<p>{_inline_confluence(stripped)}</p>")

    if in_code:
        out.append(
            f'<ac:structured-macro ac:name="code">'
            f'<ac:plain-text-body><![CDATA[{chr(10).join(code_lines)}]]>'
            f'</ac:plain-text-body></ac:structured-macro>'
        )
    if in_table:
        out.append("</tbody></table>")

    return "\n".join(out)


def _inline_confluence(text: str) -> str:
    """Handle inline Markdown for Confluence XHTML."""
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<ac:image><ri:url ri:value="\2" /></ac:image>', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def export_confluence(
    docs_dir: Path, name: str, output: Path, include_slides: bool = False
) -> Path:
    """Export docs to Confluence storage format (.xhtml)."""
    files = collect_markdown_files(docs_dir, name, include_slides)
    md_files = [f for f in files if f.suffix in (".md", ".txt")]
    if not md_files:
        print(f"[WARN] No files found for '{name}' in {docs_dir}")
        return output

    parts: list[str] = []
    for f in md_files:
        content = read_text(f)
        parts.append(f"<!-- source: {f.relative_to(docs_dir)} -->")
        parts.append(_md_to_confluence(content))
        parts.append("<hr />")

    xhtml = "\n".join(parts)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(xhtml, encoding="utf-8")
    print(f"[OK] confluence: {output} ({output.stat().st_size:,} bytes)")
    return output


# ---------------------------------------------------------------------------
# notion
# ---------------------------------------------------------------------------

def _md_to_notion(md_text: str) -> str:
    """Convert Markdown to Notion-compatible Markdown.

    Main changes:
    - Mermaid code blocks stay as ```mermaid (Notion renders them)
    - Remove HTML comments
    - Keep GFM tables as-is (Notion supports them)
    - Simplify metadata lines
    """
    # Remove HTML comments
    result = re.sub(r"<!--.*?-->", "", md_text, flags=re.DOTALL)
    # Remove consecutive blank lines (Notion handles spacing)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def export_notion(
    docs_dir: Path, name: str, output_dir: Path, include_slides: bool = False
) -> Path:
    """Export docs to Notion-compatible Markdown, split into page files."""
    files = collect_markdown_files(docs_dir, name, include_slides)
    md_files = [f for f in files if f.suffix in (".md", ".txt")]
    if not md_files:
        print(f"[WARN] No files found for '{name}' in {docs_dir}")
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in md_files:
        content = read_text(f)
        notion_md = _md_to_notion(content)
        # Determine output filename -- flatten directory structure
        rel = f.relative_to(docs_dir)
        out_name = str(rel).replace("/", "_").replace("\\", "_")
        if not out_name.endswith(".md"):
            out_name = Path(out_name).stem + ".md"
        out_path = output_dir / out_name
        out_path.write_text(notion_md, encoding="utf-8")
        count += 1

    # Create a _index.md with links to all pages
    index_lines = [f"# {name} Documentation\n"]
    for f in sorted(output_dir.iterdir()):
        if f.is_file() and f.suffix == ".md" and f.name != "_index.md":
            title = f.stem.replace("_", " / ")
            index_lines.append(f"- [{title}]({f.name})")
    index_path = output_dir / "_index.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    print(f"[OK] notion: {output_dir}/ ({count} pages + _index.md)")
    return output_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

FORMATS = ("single-html", "pdf-bundle", "confluence", "notion")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export generated docs to external platform formats."
    )
    parser.add_argument(
        "--docs-dir",
        default="./docs",
        help="Path to the docs directory (default: ./docs)",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Project / system name",
    )
    parser.add_argument(
        "--format",
        required=True,
        choices=FORMATS,
        dest="fmt",
        help=f"Output format: {', '.join(FORMATS)}",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: auto-generated under exports/)",
    )
    parser.add_argument(
        "--include-slides",
        action="store_true",
        default=False,
        help="Include slide HTML files in the export",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    docs_dir = Path(args.docs_dir)
    name = args.name
    fmt = args.fmt

    if not docs_dir.is_dir():
        print(f"[ERROR] docs directory not found: {docs_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output = Path(args.output)
    else:
        if fmt == "single-html":
            output = EXPORT_DIR / f"{name}.html"
        elif fmt == "pdf-bundle":
            output = EXPORT_DIR / f"{name}.pdf"
        elif fmt == "confluence":
            output = EXPORT_DIR / f"{name}-confluence.xhtml"
        elif fmt == "notion":
            output = EXPORT_DIR / f"{name}-notion"
        else:
            output = EXPORT_DIR / name

    # Dispatch
    if fmt == "single-html":
        export_single_html(docs_dir, name, output, args.include_slides)
    elif fmt == "pdf-bundle":
        export_pdf_bundle(docs_dir, name, output, args.include_slides)
    elif fmt == "confluence":
        export_confluence(docs_dir, name, output, args.include_slides)
    elif fmt == "notion":
        export_notion(docs_dir, name, output, args.include_slides)


if __name__ == "__main__":
    main()
