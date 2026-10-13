# High Speed Downloader for NVDA

**High Speed Downloader** is an accessible, high-performance NVDA screen reader add-on designed to download YouTube videos and playlists at maximum speed in multiple formats and qualities.

## Features

- **Blazing-Fast Downloads:** Uses `yt-dlp` with multi-fragment concurrent downloading (`-N 8`) and 10MB chunking (`--http-chunk-size 10M`) to bypass YouTube bandwidth throttling and download even long videos in a fraction of the time.
- **Video & Audio Formats:** Download as video (`mp4`, `mkv`, `webm`, `avi`) or audio (`mp3`, `m4a`, `opus`, `wav`, `flac`, `aac`).
- **Flexible Video Qualities:** Choose from Best Available, 2160p (4K), 1440p (2K), 1080p, 720p, 480p, 360p, or 240p in NVDA settings.
- **Intelligent Playlist Support:** Automatically detects playlist links and displays a list of checkboxes with all videos in the playlist (all checked by default). Download multiple videos in parallel with bounded multi-threading.
- **Real-Time Progress:** Dynamic progress bar (gauge) and detailed download list showing title, status, percentage, download speed, and ETA.
- **Convenient Controls:**
  - Cancel any selected active download or cancel all downloads.
  - Contextual Play button: When focusing on a completed download, the Cancel button dynamically turns into a **Play** button to immediately open the file in your default media player.
  - Safe exit protection: If you close the window while downloads are running, a prompt lets you run in the background, stop all downloads, or cancel.
- **In-Add-on yt-dlp Updater:** Check for updates against the official yt-dlp GitHub releases and install them directly from the NVDA settings panel with a cancellable progress dialog.

## Keyboard Shortcuts

- **NVDA+Ctrl+y**: Open High Speed Downloader (can be customized in NVDA menu -> Preferences -> Input Gestures -> "high speed downloader" category).

## Tools Menu

High Speed Downloader is also accessible from the NVDA menu:
- Press `NVDA+n` -> **Tools** -> **High Speed Downloader...**

## NVDA Settings Category

In NVDA Preferences -> Settings (`NVDA+Ctrl+g`), open the **high speed downloader** category:
1. **Output folder:** Set the full directory path for downloads (default is your Downloads folder > `high speed downloader`). Use the **Browse...** button to select a folder.
2. **Video downloading:** Select your preferred default video quality from the dropdown.
3. **yt-dlp updates:** Click **Check for yt-dlp update** to check for and install newer versions of yt-dlp.

## Author & Homepage

- **Author:** Bibek Sharma Dhakal
- **Homepage:** https://github.com/Bibeksharma5/high-speed-downloader
- **Minimum NVDA Version:** 2026.1
- **Last Tested NVDA Version:** 2026.3