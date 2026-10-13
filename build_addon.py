# -*- coding: utf-8 -*-
"""
Build and package script for HighSpeedDownloader NVDA add-on.
Creates HighSpeedDownloader-1.0.nvda-addon containing all plugin files,
bundled yt-dlp.exe, documentation, and manifest.ini.
"""

import os
import sys
import zipfile
import shutil
from pathlib import Path

def build_addon(output_filename="HighSpeedDownloader-1.0.nvda-addon"):
    project_root = Path(__file__).resolve().parent
    addon_dir = project_root / "addon"
    manifest_path = project_root / "manifest.ini"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    # Ensure addon/manifest.ini matches root manifest
    shutil.copy2(manifest_path, addon_dir / "manifest.ini")

    # Ensure yt-dlp.exe exists in plugin folder
    plugin_dir = addon_dir / "globalPlugins" / "highSpeedDownloader"
    plugin_ytdlp = plugin_dir / "yt-dlp.exe"
    root_ytdlp = project_root / "yt-dlp.exe"

    if not plugin_ytdlp.is_file() and root_ytdlp.is_file():
        print("Copying yt-dlp.exe to add-on directory...")
        shutil.copy2(root_ytdlp, plugin_ytdlp)

    out_path = project_root / output_filename
    if out_path.is_file():
        out_path.unlink()

    print(f"Packaging {output_filename}...")
    file_count = 0
    total_size = 0

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Write root manifest.ini
        zf.write(manifest_path, arcname="manifest.ini")
        file_count += 1
        total_size += manifest_path.stat().st_size
        print(" - Added manifest.ini")

        # 2. Add all files inside addon/
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
