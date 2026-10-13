# -*- coding: utf-8 -*-
"""
High speed download engine for NVDA High Speed Downloader add-on.
Utilizes yt-dlp with multi-fragment concurrent downloading (-N 8) and
chunked streaming (--http-chunk-size 10M) to achieve blazing fast downloads.
Supports parallel multi-threaded batch/playlist downloads with bounded concurrency.
"""

import os
import sys
import re
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Callable

from .updater import find_ytdlp_exe
from . import config_mgr

try:
    import addonHandler
    addonHandler.initTranslation()
    _ = _
except Exception:
    def _(text):
        return text

try:
    import ui
except Exception:
    class FakeUI:
        @staticmethod
        def message(text):
            print("[NVDA UI]:", text)
    ui = FakeUI()

# Regex patterns for progress parsing
RE_PERCENT = re.compile(r"(\d+(?:\.\d+)?)%")
RE_SPEED = re.compile(r"at\s+([~0-9\.]+[kKmMgGtT]i?B/s)")
RE_ETA = re.compile(r"ETA\s+([0-9:]+)")
RE_DEST = re.compile(r'Destination:\s*(.+)$')
RE_MERGER = re.compile(r'Merging formats into "(.+?)"')

def is_playlist_link(url: str) -> bool:
    """Quick heuristic check if a URL is likely a playlist."""
    if not url:
        return False
    lower = url.lower()
    return ("list=" in lower and "watch?" not in lower) or ("/playlist" in lower)

def inspect_url(url: str) -> Dict:
    """
    Extracts information using yt-dlp --flat-playlist -J.
    Returns dict:
      {
        'is_playlist': bool,
        'title': str,
        'entries': [{'id': ..., 'title': ..., 'url': ...}], # if playlist
      }
    """
    exe_path = find_ytdlp_exe()
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    cmd = [
        exe_path,
        "-J",
        "--flat-playlist",
        "--no-warnings",
        url
    ]

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            timeout=25
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if data.get("_type") == "playlist" and "entries" in data and len(data["entries"]) > 1:
                entries = []
                for idx, entry in enumerate(data["entries"], 1):
                    if not entry:
                        continue
                    e_id = entry.get("id", "")
                    e_title = entry.get("title") or f"Video {idx}"
                    e_url = entry.get("url") or f"https://www.youtube.com/watch?v={e_id}"
                    entries.append({
                        "id": e_id,
                        "title": e_title,
                        "url": e_url
                    })
                return {
                    "is_playlist": True,
                    "title": data.get("title") or _("Playlist"),
                    "entries": entries
                }
            else:
                title = data.get("title") or url
                return {
                    "is_playlist": False,
                    "title": title,
                    "entries": []
                }
    except Exception:
        pass

    # Fallback if extraction timed out or failed
    return {
        "is_playlist": is_playlist_link(url),
        "title": url,
        "entries": []
    }


class DownloadItem:
    """Represents a single video or audio download task."""
    def __init__(
        self,
        item_id: int,
        title: str,
        url: str,
        download_as: str = "Video",
        format_ext: str = "mp4",
        quality: str = "Best Available",
        output_dir: str = ""
    ):
        self.item_id = item_id
        self.title = title
        self.url = url
        self.download_as = download_as
        self.format_ext = format_ext
        self.quality = quality
        self.output_dir = output_dir or config_mgr.get_output_folder()

        self.status = "Queued"  # Queued, Downloading, Completed, Cancelled, Error
        self.progress = 0.0
        self.speed = "--"
        self.eta = "--"
        self.final_filepath = ""
        self.error_message = ""
        self.process: Optional[subprocess.Popen] = None
        self.cancel_requested = False
        self.partial_files: List[str] = []

    def cancel(self):
        """Cancels download and terminates process."""
        self.cancel_requested = True
        self.status = "Cancelled"
        if self.process:
            try:
                if self.process.stdout and not self.process.stdout.closed:
                    self.process.stdout.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=0.2)
                except (subprocess.TimeoutExpired, Exception):
                    self.process.kill()
                    self.process.wait(timeout=0.2)
            except Exception:
                pass
        self._cleanup_partials()

    def _cleanup_partials(self):
        for p in self.partial_files:
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


class DownloadManager:
    """
    Manages queue, background execution, concurrency (3 workers for playlist),
    speed optimization flags, and real-time updates.
    """
    def __init__(
        self,
        on_item_updated: Optional[Callable[[DownloadItem], None]] = None,
        on_overall_progress: Optional[Callable[[float], None]] = None,
        on_all_completed: Optional[Callable[[], None]] = None
    ):
        self.items: List[DownloadItem] = []
        self._lock = threading.RLock()
        self._next_id = 1
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_count = 0
        self._max_workers = 3  # Bounded concurrency to prevent overloading

        self.on_item_updated = on_item_updated
        self.on_overall_progress = on_overall_progress
        self.on_all_completed = on_all_completed

    def has_active_downloads(self) -> bool:
        with self._lock:
            return any(item.status in ("Queued", "Downloading") for item in self.items)

    def get_items(self) -> List[DownloadItem]:
        with self._lock:
            return list(self.items)

    def get_item(self, item_id: int) -> Optional[DownloadItem]:
        with self._lock:
            for item in self.items:
                if item.item_id == item_id:
                    return item
        return None

    def add_download(
        self,
        title: str,
        url: str,
        download_as: str = "Video",
        format_ext: str = "mp4",
        quality: str = "Best Available",
        output_dir: str = ""
    ) -> DownloadItem:
        with self._lock:
            item = DownloadItem(
                item_id=self._next_id,
                title=title,
                url=url,
                download_as=download_as,
                format_ext=format_ext,
                quality=quality,
                output_dir=output_dir
            )
            self._next_id += 1
            self.items.append(item)

        if not self._executor:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        self._executor.submit(self._worker_download, item)
        self._notify_item(item)
        self._calc_overall_progress()
        return item

    def add_playlist_downloads(
        self,
        entries: List[Dict],
        download_as: str = "Video",
        format_ext: str = "mp4",
        quality: str = "Best Available",
        output_dir: str = ""
    ) -> List[DownloadItem]:
        created = []
        with self._lock:
            for entry in entries:
                item = DownloadItem(
                    item_id=self._next_id,
                    title=entry.get("title", "Video"),
                    url=entry.get("url", ""),
                    download_as=download_as,
                    format_ext=format_ext,
                    quality=quality,
                    output_dir=output_dir
                )
                self._next_id += 1
                self.items.append(item)
                created.append(item)

        if not self._executor:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        for item in created:
            self._executor.submit(self._worker_download, item)
            self._notify_item(item)

        self._calc_overall_progress()
        return created

    def cancel_item(self, item_id: int):
        with self._lock:
            item = self.get_item(item_id)
            if item:
                item.cancel()
                if item in self.items:
                    self.items.remove(item)
        self._calc_overall_progress()

    def cancel_all(self):
        with self._lock:
            for item in list(self.items):
                item.cancel()
            self.items.clear()
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None
        if self.on_overall_progress:
            self.on_overall_progress(0.0)

    def cleanup_non_active(self):
        """Removes all downloads that are not actively Queued or Downloading."""
        with self._lock:
            self.items = [i for i in self.items if i.status in ("Queued", "Downloading")]

    def _worker_download(self, item: DownloadItem):
        if item.cancel_requested:
            return

        with self._lock:
            item.status = "Downloading"
            self._active_count += 1
        self._notify_item(item)

        exe_path = find_ytdlp_exe()
        out_dir = item.output_dir
        os.makedirs(out_dir, exist_ok=True)

        out_template = os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s")

        # Build High-Speed yt-dlp arguments
        cmd = [
            exe_path,
            "--no-playlist",
            # Speed enhancement flags
            "-N", "8",                  # Download 8 fragments in parallel
            "--http-chunk-size", "10M",  # 10MB chunking bypasses YouTube streaming throttling
            "--buffer-size", "1024K",    # 1MB buffer
            "--retries", "10",
            "--fragment-retries", "10",
            "--newline",
            "--progress-template", "download:[PROGRESS] %(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|%(progress.filename)s",
            "-o", out_template,
        ]

        if item.download_as == "Audio":
            cmd.extend([
                "-x",
                "--audio-format", item.format_ext,
                "--audio-quality", "0"
            ])
        else:
            # Video quality selection
            q = item.quality
            if q == "Best Available":
                format_spec = "bestvideo+bestaudio/best"
            elif "2160p" in q:
                format_spec = "bestvideo[height<=2160]+bestaudio/best[height<=2160]"
            elif "1440p" in q:
                format_spec = "bestvideo[height<=1440]+bestaudio/best[height<=1440]"
            elif "1080p" in q:
                format_spec = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
            elif "720p" in q:
                format_spec = "bestvideo[height<=720]+bestaudio/best[height<=720]"
            elif "480p" in q:
                format_spec = "bestvideo[height<=480]+bestaudio/best[height<=480]"
            elif "360p" in q:
                format_spec = "bestvideo[height<=360]+bestaudio/best[height<=360]"
            elif "240p" in q:
                format_spec = "bestvideo[height<=240]+bestaudio/best[height<=240]"
            else:
                format_spec = "bestvideo+bestaudio/best"

            cmd.extend([
                "-f", format_spec,
                "--merge-output-format", item.format_ext
            ])

        cmd.append(item.url)

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            item.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )

            for line in iter(item.process.stdout.readline, ""):
                if item.cancel_requested:
                    break
                line = line.strip()
                if not line:
                    continue

                self._parse_line(item, line)
                self._notify_item(item)
                self._calc_overall_progress()

            item.process.stdout.close()
            ret = item.process.wait()

            with self._lock:
                if item.cancel_requested:
                    item.status = "Cancelled"
                elif ret == 0:
                    item.status = "Completed"
                    item.progress = 100.0
                    item.speed = "--"
                    item.eta = "--"
                    # If final_filepath is not set, search matching file in output_dir
                    if not item.final_filepath or not os.path.isfile(item.final_filepath):
                        self._resolve_final_file(item)
                else:
                    item.status = "Error"
                    item.error_message = _("Download exited with error code {code}").format(code=ret)

        except Exception as e:
            if not item.cancel_requested:
                item.status = "Error"
                item.error_message = str(e)
        finally:
            with self._lock:
                self._active_count = max(0, self._active_count - 1)
            item.process = None
            self._notify_item(item)
            self._calc_overall_progress()
            self._check_all_finished()

    def _parse_line(self, item: DownloadItem, line: str):
        # Progress template line: [PROGRESS] 45.2%|5.4MiB/s|00:15|filename.ext
        if "[PROGRESS]" in line:
            parts = line.split("[PROGRESS]", 1)[1].strip().split("|")
            if len(parts) >= 3:
                pct_str = parts[0].strip()
                spd_str = parts[1].strip()
                eta_str = parts[2].strip()
                fn_str = parts[3].strip() if len(parts) > 3 else ""

                m = RE_PERCENT.search(pct_str)
                if m:
                    item.progress = float(m.group(1))
                if spd_str and spd_str != "NA":
                    item.speed = spd_str
                if eta_str and eta_str != "NA":
                    item.eta = eta_str
                if fn_str and fn_str != "NA":
                    if not os.path.isabs(fn_str):
                        fn_str = os.path.join(item.output_dir, fn_str)
                    item.final_filepath = os.path.normpath(fn_str)
                    if fn_str.endswith(".part") or fn_str.endswith(".ytdl"):
                        if fn_str not in item.partial_files:
                            item.partial_files.append(fn_str)
            return

        # Fallback regex parsing
        m_pct = RE_PERCENT.search(line)
        if m_pct:
            try:
                item.progress = float(m_pct.group(1))
            except ValueError:
                pass

        m_spd = RE_SPEED.search(line)
        if m_spd:
            item.speed = m_spd.group(1)

        m_eta = RE_ETA.search(line)
        if m_eta:
            item.eta = m_eta.group(1)

        m_dest = RE_DEST.search(line)
        if m_dest:
            dest_file = m_dest.group(1).strip()
            if not os.path.isabs(dest_file):
                dest_file = os.path.join(item.output_dir, dest_file)
            dest_file = os.path.normpath(dest_file)
            if dest_file.endswith(".part"):
                if dest_file not in item.partial_files:
                    item.partial_files.append(dest_file)
                base = dest_file[:-5]
                item.final_filepath = base
            else:
                item.final_filepath = dest_file

        m_merger = RE_MERGER.search(line)
        if m_merger:
            m_file = m_merger.group(1).strip()
            if not os.path.isabs(m_file):
                m_file = os.path.join(item.output_dir, m_file)
            item.final_filepath = os.path.normpath(m_file)

    def _resolve_final_file(self, item: DownloadItem):
        try:
            candidates = os.listdir(item.output_dir)
            # Find newest file matching format_ext
            matched = []
            for c in candidates:
                if c.endswith(f".{item.format_ext}"):
                    full = os.path.join(item.output_dir, c)
                    matched.append((os.path.getmtime(full), full))
            if matched:
                matched.sort(reverse=True)
                item.final_filepath = matched[0][1]
        except Exception:
            pass

    def _notify_item(self, item: DownloadItem):
        if self.on_item_updated:
            self.on_item_updated(item)

    def _calc_overall_progress(self):
        with self._lock:
            if not self.items:
                pct = 0.0
            else:
                total = sum(i.progress for i in self.items)
                pct = total / len(self.items)
                pct = min(100.0, max(0.0, pct))
        if self.on_overall_progress:
            self.on_overall_progress(pct)

    def _check_all_finished(self):
        with self._lock:
            active = any(i.status in ("Queued", "Downloading") for i in self.items)
        if not active and self.on_all_completed:
            self.on_all_completed()
