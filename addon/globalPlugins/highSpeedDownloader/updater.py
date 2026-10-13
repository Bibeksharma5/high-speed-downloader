# -*- coding: utf-8 -*-
"""
yt-dlp updater module for High Speed Downloader.
Checks for updates against official GitHub releases, downloads updates
with a cancellable progress dialog, and replaces yt-dlp.exe.
"""

import os
import sys
import shutil
import urllib.request
import json
import subprocess
import threading
import wx

try:
    import addonHandler
    addonHandler.initTranslation()
    _ = _
except Exception:
    def _(text):
        return text

GITHUB_API_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
GITHUB_DIRECT_DOWNLOAD = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"

def find_ytdlp_exe() -> str:
    """Finds the path to yt-dlp.exe in the add-on folder or working directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(current_dir, "yt-dlp.exe"),
        os.path.join(current_dir, "..", "..", "..", "yt-dlp.exe"),
        os.path.join(os.getcwd(), "yt-dlp.exe")
    ]
    for p in candidates:
        norm = os.path.normpath(p)
        if os.path.isfile(norm):
            return norm
    return os.path.normpath(os.path.join(current_dir, "yt-dlp.exe"))

def get_installed_version(exe_path: str = None) -> str:
    """Runs yt-dlp.exe --version to detect the installed version."""
    if not exe_path:
        exe_path = find_ytdlp_exe()
    if not os.path.isfile(exe_path):
        return "Not installed"
    try:
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        res = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            text=True,
            creationflags=creationflags,
            timeout=10
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "Unknown"

def check_remote_version():
    """
    Queries GitHub API for the latest release of yt-dlp.
    Returns (latest_version_str, download_url) or raises Exception.
    """
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={"User-Agent": "HighSpeedDownloader-NVDA-Addon"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "").lstrip("v").strip()
        download_url = GITHUB_DIRECT_DOWNLOAD
        for asset in data.get("assets", []):
            if asset.get("name") == "yt-dlp.exe":
                download_url = asset.get("browser_download_url", download_url)
                break
        return tag, download_url

class UpdateProgressDialog(wx.Dialog):
    """Accessible dialog showing download progress for yt-dlp update with Cancel button."""
    def __init__(self, parent, target_version, download_url, target_path, on_finished_callback):
        super().__init__(
            parent,
            title=_("Downloading yt-dlp Update"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )
        self.download_url = download_url
        self.target_path = target_path
        self.target_version = target_version
        self.on_finished_callback = on_finished_callback
        self.cancel_event = threading.Event()
        self.download_thread = None

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.info_text = wx.StaticText(
            self,
            label=_("Downloading yt-dlp version {version}, please wait...").format(version=target_version)
        )
        main_sizer.Add(self.info_text, flag=wx.ALL | wx.EXPAND, border=10)

        self.gauge = wx.Gauge(self, range=100, size=(300, 25))
        main_sizer.Add(self.gauge, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        self.status_text = wx.StaticText(self, label=_("0% downloaded"))
        main_sizer.Add(self.status_text, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        btn_sizer.Add(self.cancel_btn, flag=wx.ALL, border=10)
        main_sizer.Add(btn_sizer, flag=wx.ALIGN_CENTER_HORIZONTAL)

        self.SetSizerAndFit(main_sizer)
        self.CentreOnParent()

        self.Bind(wx.EVT_CLOSE, self.on_cancel)

    def start_download(self):
        self.download_thread = threading.Thread(target=self._run_download, daemon=True)
        self.download_thread.start()

    def _run_download(self):
        temp_file = self.target_path + ".download"
        error_msg = None
        success = False
        try:
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "HighSpeedDownloader-NVDA-Addon"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = resp.headers.get("Content-Length")
                total_size = int(total_size) if total_size else 0
                downloaded = 0
                chunk_size = 64 * 1024

                with open(temp_file, "wb") as f:
                    while True:
                        if self.cancel_event.is_set():
                            break
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            percent = min(100, max(0, percent))
                            wx.CallAfter(self._update_progress, percent, downloaded, total_size)

            if not self.cancel_event.is_set():
                # Atomically replace target
                bak_file = self.target_path + ".bak"
                if os.path.isfile(bak_file):
                    try:
                        os.remove(bak_file)
                    except Exception:
                        pass
                if os.path.isfile(self.target_path):
                    shutil.move(self.target_path, bak_file)
                shutil.move(temp_file, self.target_path)
                if os.path.isfile(bak_file):
                    try:
                        os.remove(bak_file)
                    except Exception:
                        pass

                # Also update root copy if in project directory
                root_target = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "yt-dlp.exe"))
                if os.path.isfile(root_target) and os.path.normpath(root_target) != os.path.normpath(self.target_path):
                    try:
                        shutil.copy2(self.target_path, root_target)
                    except Exception:
                        pass

                success = True
        except Exception as e:
            error_msg = str(e)
        finally:
            if os.path.isfile(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

        wx.CallAfter(self._finish_download, success, error_msg)

    def _update_progress(self, percent, downloaded, total):
        if self.IsBeingDeleted():
            return
        self.gauge.SetValue(percent)
        dl_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        self.status_text.SetLabel(f"{percent}% ({dl_mb:.1f} MB / {total_mb:.1f} MB)")

    def _finish_download(self, success, error_msg):
        self.Destroy()
        if self.on_finished_callback:
            self.on_finished_callback(success, self.cancel_event.is_set(), error_msg, self.target_version)

    def on_cancel(self, evt):
        self.cancel_event.set()
        self.cancel_btn.Enable(False)
        self.status_text.SetLabel(_("Cancelling download..."))


def check_and_update(parent=None):
    """
    Full workflow to check for updates and guide the user through downloading
    and installing the update.
    """
    target_path = find_ytdlp_exe()
    current_ver = get_installed_version(target_path)

    busy = wx.BusyCursor()
    try:
        latest_ver, download_url = check_remote_version()
    except Exception as e:
        del busy
        wx.MessageBox(
            _("Failed to check for yt-dlp updates:\n{error}").format(error=str(e)),
            _("Update Check Error"),
            wx.OK | wx.ICON_ERROR,
            parent
        )
        return
    finally:
        try:
            del busy
        except Exception:
            pass

    # Compare versions
    if current_ver != "Unknown" and current_ver != "Not installed" and current_ver == latest_ver:
        wx.MessageBox(
            _("yt-dlp is already up to date.\nCurrent version: {ver}").format(ver=current_ver),
            _("yt-dlp Update"),
            wx.OK | wx.ICON_INFORMATION,
            parent
        )
        return

    msg = _(
        "A new version of yt-dlp is available!\n\n"
        "Installed version: {current}\n"
        "Latest version: {latest}\n\n"
        "Do you want to download and install the update now?"
    ).format(current=current_ver, latest=latest_ver)

    confirm = wx.MessageBox(
        msg,
        _("yt-dlp Update Available"),
        wx.YES_NO | wx.ICON_QUESTION,
        parent
    )

    if confirm != wx.YES:
        return

    def on_finished(success, cancelled, error, new_version):
        if cancelled:
            wx.MessageBox(
                _("yt-dlp update download was cancelled."),
                _("Update Cancelled"),
                wx.OK | wx.ICON_INFORMATION,
                parent
            )
        elif success:
            wx.MessageBox(
                _("yt-dlp update completed successfully!\nyt-dlp has been updated to version {version}.").format(version=new_version),
                _("Update Complete"),
                wx.OK | wx.ICON_INFORMATION,
                parent
            )
        else:
            wx.MessageBox(
                _("Failed to download yt-dlp update:\n{error}").format(error=error or _("Unknown error")),
                _("Update Failed"),
                wx.OK | wx.ICON_ERROR,
                parent
            )

    dlg = UpdateProgressDialog(parent, latest_ver, download_url, target_path, on_finished)
    dlg.start_download()
    dlg.ShowModal()
