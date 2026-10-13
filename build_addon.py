# -*- coding: utf-8 -*-
"""
Build and package script for HighSpeedDownloader NVDA add-on.
Generates manifest.ini from buildVars.py and creates HighSpeedDownloader-1.0.nvda-addon
containing all plugin files, bundled yt-dlp.exe, documentation, and manifest.ini.
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

def parse_build_vars(file_path: Path) -> dict:
    """Parses addon_info dictionary from buildVars.py using AST without external dependencies."""
    import ast
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    info = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", "") == "addon_info" and isinstance(node.value, ast.Call):
                    for kw in node.value.keywords:
                        val = kw.value
                        if isinstance(val, ast.Constant):
                            info[kw.arg] = val.value
                        elif isinstance(val, ast.Call) and getattr(val.func, "id", "") == "_":
                            if val.args and isinstance(val.args[0], ast.Constant):
                                info[kw.arg] = val.args[0].value
    return info

def generate_manifest(project_root: Path) -> Path:
    """Generates manifest.ini in project_root based on buildVars.py."""
    info = parse_build_vars(project_root / "buildVars.py")

    content = f"""name = {info.get('addon_name', 'HighSpeedDownloader')}
summary = "{info.get('addon_summary', 'High Speed Downloader')}"
description = \"\"\"{info.get('addon_description', '')}\"\"\"
author = "{info.get('addon_author', 'Bibek Sharma Dhakal')}"
url = {info.get('addon_url', '')}
version = {info.get('addon_version', '1.0')}
docFileName = {info.get('addon_docFileName', 'readme.html')}
minimumNVDAVersion = {info.get('addon_minimumNVDAVersion', '2026.1')}
lastTestedNVDAVersion = {info.get('addon_lastTestedNVDAVersion', '2026.3')}
updateChannel = {info.get('addon_updateChannel', None)}
"""
    manifest_path = project_root / "manifest.ini"
    manifest_path.write_text(content, encoding="utf-8")
    print(f"Generated manifest.ini from buildVars.py at {manifest_path}")
    return manifest_path

def build_addon(output_filename="HighSpeedDownloader-1.0.nvda-addon"):
    project_root = Path(__file__).resolve().parent
    addon_dir = project_root / "addon"

    # 1. Generate/refresh manifest.ini
    manifest_path = generate_manifest(project_root)

    # Ensure addon/manifest.ini matches root manifest
    shutil.copy2(manifest_path, addon_dir / "manifest.ini")

    # 2. Ensure yt-dlp.exe exists in plugin folder
    plugin_dir = addon_dir / "globalPlugins" / "highSpeedDownloader"
    plugin_ytdlp = plugin_dir / "yt-dlp.exe"
    root_ytdlp = project_root / "yt-dlp.exe"

    if not plugin_ytdlp.is_file() and root_ytdlp.is_file():
        print("Copying yt-dlp.exe to add-on directory...")
        shutil.copy2(root_ytdlp, plugin_ytdlp)

    # 3. Ensure doc files exist in addon/doc
    doc_en_html = addon_dir / "doc" / "en" / "readme.html"
    if not doc_en_html.is_file():
        raise FileNotFoundError(f"Documentation file missing at {doc_en_html}")

    out_path = project_root / output_filename
    if out_path.is_file():
        out_path.unlink()

    print(f"Packaging {output_filename}...")
    file_count = 0
    total_size = 0

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write root manifest.ini
        zf.write(manifest_path, arcname="manifest.ini")
        file_count += 1
        total_size += manifest_path.stat().st_size
        print(" - Added manifest.ini")

        # Add all files inside addon/
        for root, dirs, files in os.walk(addon_dir):
            for file in files:
                if file.endswith((".pyc", ".pyo", ".bak", ".download")) or "__pycache__" in root:
                    continue
                file_full = Path(root) / file
                # Relative path inside the add-on archive
                rel_path = file_full.relative_to(addon_dir)
                if rel_path.name == "manifest.ini":
                    # Already added at root
                    continue
                zf.write(file_full, arcname=str(rel_path).replace("\\", "/"))
                file_count += 1
                total_size += file_full.stat().st_size
                print(f" - Added {rel_path}")

    print("\nPackage built successfully:")
    print(f"  File: {out_path.name}")
    print(f"  Total files: {file_count}")
    print(f"  Uncompressed size: {total_size / (1024*1024):.2f} MB")
    print(f"  Archive size: {out_path.stat().st_size / (1024*1024):.2f} MB")
    return str(out_path)

if __name__ == "__main__":
    build_addon()
