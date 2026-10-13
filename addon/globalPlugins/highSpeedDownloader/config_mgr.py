# -*- coding: utf-8 -*-
"""
Configuration manager for High Speed Downloader.
Handles loading, saving, and defaults for all add-on settings,
with seamless integration into NVDA config.conf and fallback storage.
"""

import os
import json

try:
    import addonHandler
    addonHandler.initTranslation()
    _ = _
except Exception:
    def _(text):
        return text

try:
    import config
    HAS_NVDA_CONFIG = hasattr(config, "conf")
except Exception:
    config = None
    HAS_NVDA_CONFIG = False

CONFIG_SECTION = "HighSpeedDownloader"

VIDEO_QUALITIES = [
    "Best Available",
    "2160p (4K)",
    "1440p (2K)",
    "1080p",
    "720p",
    "480p",
    "360p",
    "240p"
]

VIDEO_FORMATS = [
    "mp4",
    "mkv",
    "webm",
    "avi"
]

AUDIO_FORMATS = [
    "mp3",
    "m4a",
    "opus",
    "wav",
    "flac",
    "aac"
]

def get_default_download_folder() -> str:
    """Returns the default download folder: user's Downloads\\high speed downloader"""
    user_home = os.path.expanduser("~")
    downloads_dir = os.path.join(user_home, "Downloads")
    default_dir = os.path.join(downloads_dir, "high speed downloader")
    return os.path.normpath(default_dir)

_fallback_file = os.path.join(
    os.getenv("APPDATA", os.path.expanduser("~")),
    "nvda",
    "highSpeedDownloader.json"
)

_fallback_cache = {
    "outputFolder": get_default_download_folder(),
    "videoQuality": "Best Available",
    "downloadAs": "Video",
    "videoFormat": "mp4",
    "audioFormat": "mp3"
}

def _load_fallback():
    global _fallback_cache
    if os.path.isfile(_fallback_file):
        try:
            with open(_fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _fallback_cache.update(data)
        except Exception:
            pass

def _save_fallback():
    try:
        os.makedirs(os.path.dirname(_fallback_file), exist_ok=True)
        with open(_fallback_file, "w", encoding="utf-8") as f:
            json.dump(_fallback_cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

_load_fallback()

def init_nvda_config():
    """Initializes configuration spec in NVDA config system."""
    if not HAS_NVDA_CONFIG or not hasattr(config.conf, "spec"):
        return
    try:
        def_folder = get_default_download_folder().replace("\\", "\\\\")
        confspec = {
            "outputFolder": f'string(default="{def_folder}")',
            "videoQuality": 'string(default="Best Available")',
            "downloadAs": 'string(default="Video")',
            "videoFormat": 'string(default="mp4")',
            "audioFormat": 'string(default="mp3")',
        }
        config.conf.spec[CONFIG_SECTION] = confspec
    except Exception:
        pass

# Initialize right away if possible
init_nvda_config()

def get_setting(key: str, default=None):
    if HAS_NVDA_CONFIG:
        try:
            if CONFIG_SECTION in config.conf and key in config.conf[CONFIG_SECTION]:
                val = config.conf[CONFIG_SECTION][key]
                if val is not None and str(val).strip():
                    return val
        except Exception:
            pass
    return _fallback_cache.get(key, default)

def set_setting(key: str, value):
    _fallback_cache[key] = value
    _save_fallback()
    if HAS_NVDA_CONFIG:
        try:
            if CONFIG_SECTION not in config.conf:
                config.conf[CONFIG_SECTION] = {}
            config.conf[CONFIG_SECTION][key] = value
        except Exception:
            pass

def save_config():
    """Persists configuration."""
    _save_fallback()
    if HAS_NVDA_CONFIG:
        try:
            config.conf.save()
        except Exception:
            pass

def get_output_folder() -> str:
    folder = get_setting("outputFolder", get_default_download_folder())
    if not folder:
        folder = get_default_download_folder()
    return os.path.normpath(str(folder))

def set_output_folder(path: str):
    set_setting("outputFolder", os.path.normpath(str(path)))

def get_video_quality() -> str:
    quality = get_setting("videoQuality", "Best Available")
    if quality not in VIDEO_QUALITIES:
        quality = "Best Available"
    return quality

def set_video_quality(quality: str):
    if quality in VIDEO_QUALITIES:
        set_setting("videoQuality", quality)

def get_download_as() -> str:
    mode = get_setting("downloadAs", "Video")
    if mode not in ("Video", "Audio"):
        mode = "Video"
    return mode

def set_download_as(mode: str):
    if mode in ("Video", "Audio"):
        set_setting("downloadAs", mode)

def get_video_format() -> str:
    fmt = get_setting("videoFormat", "mp4")
    if fmt not in VIDEO_FORMATS:
        fmt = "mp4"
    return fmt

def set_video_format(fmt: str):
    if fmt in VIDEO_FORMATS:
        set_setting("videoFormat", fmt)

def get_audio_format() -> str:
    fmt = get_setting("audioFormat", "mp3")
    if fmt not in AUDIO_FORMATS:
        fmt = "mp3"
    return fmt

def set_audio_format(fmt: str):
    if fmt in AUDIO_FORMATS:
        set_setting("audioFormat", fmt)
