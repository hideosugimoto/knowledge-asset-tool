#!/usr/bin/env python3
"""
Automatic frontend project detection for knowledge-asset-tool.

Scans a given source directory and its surroundings for frontend projects,
identifying framework, UI library, state management, and component counts.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRAMEWORK_MARKERS = {
    "nuxt": "nuxt",
    "@nuxt/core": "nuxt",
    "next": "next",
    "react": "react",
    "react-dom": "react",
    "vue": "vue",
    "@angular/core": "angular",
    "svelte": "svelte",
    "solid-js": "solid",
}

NUXT_CONFIG_NAMES = ["nuxt.config.js", "nuxt.config.ts"]
NEXT_CONFIG_NAMES = ["next.config.js", "next.config.ts", "next.config.mjs"]

STATE_MANAGEMENT = {
    "vuex": "vuex",
    "pinia": "pinia",
    "@reduxjs/toolkit": "redux-toolkit",
    "redux": "redux",
    "zustand": "zustand",
    "recoil": "recoil",
    "jotai": "jotai",
    "mobx": "mobx",
    "@ngrx/store": "ngrx",
}

UI_LIBRARIES = {
    "ant-design-vue": "ant-design-vue",
    "antd": "antd",
    "element-ui": "element-ui",
    "element-plus": "element-plus",
    "vuetify": "vuetify",
    "@mui/material": "material-ui",
    "@material-ui/core": "material-ui",
    "chakra-ui": "chakra-ui",
    "@chakra-ui/react": "chakra-ui",
    "tailwindcss": "tailwindcss",
    "@headlessui/react": "headlessui",
    "bootstrap": "bootstrap",
    "react-bootstrap": "react-bootstrap",
    "primevue": "primevue",
    "quasar": "quasar",
    "naive-ui": "naive-ui",
}

SIBLING_NAMES = [
    "frontend",
    "front",
    "client",
    "web",
    "app",
    "ui",
    "spa",
    "dashboard",
]

SUBDIRECTORY_PATHS = [
    "frontend",
    "client",
    "web",
    "app",
    "resources/js",
    "resources/ts",
]

MONOREPO_GLOBS = [
    "packages/*/package.json",
    "apps/*/package.json",
]

PAGE_DIR_NAMES = ["pages", "views", "screens", "routes"]
COMPONENT_DIR_NAMES = ["components"]
STORE_DIR_NAMES = ["store", "stores", "state"]

VUE_EXTENSIONS = {".vue"}
REACT_EXTENSIONS = {".jsx", ".tsx"}
SVELTE_EXTENSIONS = {".svelte"}
ANGULAR_EXTENSIONS = {".component.ts"}
ALL_COMPONENT_EXTENSIONS = VUE_EXTENSIONS | REACT_EXTENSIONS | SVELTE_EXTENSIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict:
    """Read a JSON file, returning empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def _detect_framework(pkg: dict) -> tuple:
    """Return (framework_key, version_string) from package.json contents."""
    all_deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        all_deps.update(pkg.get(key, {}))

    # Check nuxt first (it depends on vue, so order matters)
    for dep, fw in FRAMEWORK_MARKERS.items():
        if dep in all_deps:
            if fw == "nuxt":
                version = all_deps.get(dep, "")
                major = _extract_major(version)
                label = f"nuxt{major}" if major else "nuxt"
                return label, _clean_version(version)
            if fw == "next":
                version = all_deps.get(dep, "")
                return "nextjs", _clean_version(version)
            if fw == "vue":
                version = all_deps.get("vue", "")
                major = _extract_major(version)
                label = f"vue{major}" if major else "vue"
                return label, _clean_version(version)
            if fw == "react":
                version = all_deps.get("react", "") or all_deps.get("react-dom", "")
                return "react", _clean_version(version)
            if fw == "angular":
                version = all_deps.get("@angular/core", "")
                return "angular", _clean_version(version)
            if fw == "svelte":
                version = all_deps.get("svelte", "")
                return "svelte", _clean_version(version)
            if fw == "solid":
                version = all_deps.get("solid-js", "")
                return "solid", _clean_version(version)

    return None, None


def _extract_major(version_str: str) -> str:
    """Extract major version number from a semver string like ^2.15.8."""
    m = re.search(r"(\d+)", version_str)
    return m.group(1) if m else ""


def _clean_version(version_str: str) -> str:
    """Remove leading ^, ~, >= etc. from version string."""
    return re.sub(r"^[^0-9]*", "", version_str)


def _detect_state_management(pkg: dict) -> str:
    """Detect state management library from package.json."""
    all_deps = {}
    for key in ("dependencies", "devDependencies"):
        all_deps.update(pkg.get(key, {}))

    for dep, name in STATE_MANAGEMENT.items():
        if dep in all_deps:
            return name
    return None


def _detect_ui_library(pkg: dict) -> str:
    """Detect UI library from package.json."""
    all_deps = {}
    for key in ("dependencies", "devDependencies"):
        all_deps.update(pkg.get(key, {}))

    for dep, name in UI_LIBRARIES.items():
        if dep in all_deps:
            return name
    return None


def _detect_router_type(project_dir: Path, framework: str) -> str:
    """Detect router type: file-based or config-based."""
    if framework and ("nuxt" in framework or "next" in framework):
        return "file-based"

    # Check for router config files
    router_files = [
        "src/router/index.ts",
        "src/router/index.js",
        "src/router.ts",
        "src/router.js",
        "app/router.ts",
        "app/router.js",
    ]
    for rf in router_files:
        if (project_dir / rf).exists():
            return "config-based"

    return None


def _count_files_in_dirs(project_dir: Path, dir_names: list, extensions: set) -> int:
    """Count files matching extensions inside any of the named directories."""
    count = 0
    for dir_name in dir_names:
        for candidate in [
            project_dir / dir_name,
            project_dir / "src" / dir_name,
            project_dir / "app" / dir_name,
        ]:
            if candidate.is_dir():
                count += _count_recursive(candidate, extensions)
    return count


def _count_recursive(directory: Path, extensions: set) -> int:
    """Recursively count files matching any of the given extensions."""
    count = 0
    try:
        for entry in directory.iterdir():
            if entry.is_file():
                if any(entry.name.endswith(ext) for ext in extensions):
                    count += 1
            elif entry.is_dir() and not entry.name.startswith("."):
                count += _count_recursive(entry, extensions)
    except PermissionError:
        pass
    return count


def _get_component_extensions(framework: str) -> set:
    """Return relevant file extensions based on the detected framework."""
    if framework is None:
        return ALL_COMPONENT_EXTENSIONS
    if "vue" in framework or "nuxt" in framework:
        return VUE_EXTENSIONS
    if framework in ("react", "nextjs"):
        return REACT_EXTENSIONS
    if framework == "svelte":
        return SVELTE_EXTENSIONS
    if framework == "angular":
        return ANGULAR_EXTENSIONS
    return ALL_COMPONENT_EXTENSIONS


def _analyze_frontend(project_dir: Path) -> dict:
    """Analyze a single frontend project directory."""
    pkg_path = project_dir / "package.json"
    if not pkg_path.exists():
        return None

    pkg = _read_json(pkg_path)
    if not pkg:
        return None

    framework, framework_version = _detect_framework(pkg)
    if framework is None:
        return None

    extensions = _get_component_extensions(framework)

    page_count = _count_files_in_dirs(project_dir, PAGE_DIR_NAMES, extensions)
    component_count = _count_files_in_dirs(project_dir, COMPONENT_DIR_NAMES, extensions)
    store_count = _count_files_in_dirs(
        project_dir,
        STORE_DIR_NAMES,
        {".ts", ".js"},
    )

    result = {
        "path": str(project_dir.resolve()),
        "framework": framework,
    }
    if framework_version:
        result["framework_version"] = framework_version

    ui_lib = _detect_ui_library(pkg)
    if ui_lib:
        result["ui_library"] = ui_lib

    state_mgmt = _detect_state_management(pkg)
    if state_mgmt:
        result["state_management"] = state_mgmt

    router_type = _detect_router_type(project_dir, framework)
    if router_type:
        result["router_type"] = router_type

    result["page_count"] = page_count
    result["store_count"] = store_count
    result["component_count"] = component_count

    return result


def _is_frontend_package(pkg_path: Path) -> bool:
    """Quick check if a package.json looks like a frontend project."""
    pkg = _read_json(pkg_path)
    all_deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        all_deps.update(pkg.get(key, {}))
    return any(dep in all_deps for dep in FRAMEWORK_MARKERS)


# ---------------------------------------------------------------------------
# Detection strategies
# ---------------------------------------------------------------------------


def _detect_in_source(source_dir: Path) -> list:
    """Check if the source directory itself is a frontend project."""
    result = _analyze_frontend(source_dir)
    if result:
        result["relative_path"] = "."
        return [result], "source_directory"
    return [], None


def _detect_subdirectories(source_dir: Path) -> list:
    """Check known subdirectory paths within the source directory."""
    results = []
    for subdir in SUBDIRECTORY_PATHS:
        candidate = source_dir / subdir
        if candidate.is_dir():
            info = _analyze_frontend(candidate)
            if info:
                info["relative_path"] = subdir
                results.append(info)
    if results:
        return results, "subdirectory"
    return [], None


def _detect_siblings(source_dir: Path) -> list:
    """Check sibling directories of the source directory."""
    parent = source_dir.parent
    if not parent.is_dir():
        return [], None

    results = []
    try:
        for entry in parent.iterdir():
            if not entry.is_dir():
                continue
            if entry == source_dir:
                continue
            name_lower = entry.name.lower()
            # Match known sibling names or names containing "front"
            is_candidate = (
                name_lower in SIBLING_NAMES
                or "front" in name_lower
                or "client" in name_lower
                or "web" == name_lower
            )
            if is_candidate:
                pkg_path = entry / "package.json"
                if pkg_path.exists() and _is_frontend_package(pkg_path):
                    info = _analyze_frontend(entry)
                    if info:
                        info["relative_path"] = os.path.relpath(
                            str(entry), str(source_dir)
                        )
                        results.append(info)
    except PermissionError:
        pass

    if results:
        return results, "sibling_directory"
    return [], None


def _detect_monorepo(source_dir: Path) -> list:
    """Check monorepo patterns (packages/*, apps/*)."""
    # Try both in source_dir and parent
    results = []
    search_dirs = [source_dir, source_dir.parent]

    for base_dir in search_dirs:
        for glob_pattern in MONOREPO_GLOBS:
            for pkg_path in base_dir.glob(glob_pattern):
                if _is_frontend_package(pkg_path):
                    project_dir = pkg_path.parent
                    if project_dir == source_dir:
                        continue
                    info = _analyze_frontend(project_dir)
                    if info:
                        info["relative_path"] = os.path.relpath(
                            str(project_dir), str(source_dir)
                        )
                        results.append(info)

    if results:
        return results, "monorepo"
    return [], None


def detect_frontends(source_dir: str) -> dict:
    """
    Main detection function. Tries multiple strategies in order:
    1. Source directory itself
    2. Subdirectories
    3. Sibling directories
    4. Monorepo patterns
    """
    source_path = Path(source_dir).resolve()

    if not source_path.is_dir():
        return {
            "frontends": [],
            "detection_method": None,
            "error": f"Directory not found: {source_dir}",
        }

    strategies = [
        _detect_in_source,
        _detect_subdirectories,
        _detect_siblings,
        _detect_monorepo,
    ]

    all_frontends = []
    detection_method = None

    for strategy in strategies:
        found, method = strategy(source_path)
        if found:
            all_frontends.extend(found)
            if detection_method is None:
                detection_method = method

    # Deduplicate by resolved path
    seen = set()
    unique = []
    for fe in all_frontends:
        resolved = fe["path"]
        if resolved not in seen:
            seen.add(resolved)
            unique.append(fe)

    return {
        "frontends": unique,
        "detection_method": detection_method,
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_human(result: dict) -> str:
    """Format detection result for human-readable display."""
    frontends = result.get("frontends", [])

    if not frontends:
        return "フロントエンドプロジェクトは検出されませんでした。"

    lines = ["フロントエンドプロジェクトが検出されました。", ""]
    lines.append("  検出されたフロントエンド:")

    for i, fe in enumerate(frontends, 1):
        fw = fe.get("framework", "unknown")
        ver = fe.get("framework_version", "")
        path = fe.get("relative_path", fe.get("path", ""))
        pages = fe.get("page_count", 0)
        stores = fe.get("store_count", 0)
        components = fe.get("component_count", 0)
        ui = fe.get("ui_library", "")
        state = fe.get("state_management", "")

        fw_display = f"{fw} {ver}".strip()
        detail_parts = []
        if pages:
            detail_parts.append(f"{pages}画面")
        if stores:
            detail_parts.append(f"{stores}ストア")
        if components:
            detail_parts.append(f"{components}コンポーネント")
        detail = ", ".join(detail_parts) if detail_parts else "検出中"

        line = f"    {i}. {fw_display} ({path})"
        if ui:
            line += f" [UI: {ui}]"
        if state:
            line += f" [State: {state}]"
        line += f" -- {detail}"
        lines.append(line)

    lines.append("")
    lines.append(f"  検出方法: {result.get('detection_method', 'N/A')}")
    return "\n".join(lines)


def _format_json(result: dict) -> str:
    """Format detection result as JSON."""
    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Detect frontend projects associated with a source directory."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Path to the target source directory",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output in JSON format (default)",
    )
    output_group.add_argument(
        "--human",
        action="store_true",
        dest="output_human",
        help="Output in human-readable format",
    )

    args = parser.parse_args()

    result = detect_frontends(args.source_dir)

    if args.output_human:
        print(_format_human(result))
    else:
        print(_format_json(result))

    # Exit with 0 if frontends found, 1 if none
    sys.exit(0 if result.get("frontends") else 1)


if __name__ == "__main__":
    main()
