# -*- coding: utf-8 -*-
"""
High Speed Downloader NVDA Global Plugin.
Provides fast multi-fragment downloading of YouTube videos and playlists in various qualities.
Registers NVDA+Ctrl+y keyboard shortcut and Tools menu entry.
"""

import os
import sys
import wx

try:
    import addonHandler
    addonHandler.initTranslation()
    _ = _
except Exception:
    def _(text):
        return text

try:
    import globalPluginHandler
    from scriptHandler import script
    import gui
    from gui import settingsDialogs
    HAS_NVDA_CORE = True
except Exception:
    HAS_NVDA_CORE = False
    class FakeGlobalPlugin:
        def __init__(self):
            pass
        def terminate(self):
            pass
    class globalPluginHandler:
        GlobalPlugin = FakeGlobalPlugin

    def script(**kwargs):
        def decorator(func):
            return func
        return decorator

from .ui_dialogs import HighSpeedDownloaderDialog
from .settings_panel import HighSpeedDownloaderSettingsPanel
from . import config_mgr


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("high speed downloader")

    def __init__(self):
        super().__init__()
        self.menu_item = None
        self.tools_menu = None

        if HAS_NVDA_CORE:
            # Register settings category in NVDA Preferences -> Settings
            if HighSpeedDownloaderSettingsPanel not in settingsDialogs.NVDASettingsDialog.categoryClasses:
                settingsDialogs.NVDASettingsDialog.categoryClasses.append(HighSpeedDownloaderSettingsPanel)

            # Add High Speed Downloader to NVDA Tools menu
            try:
                self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
                self.menu_item = self.tools_menu.Append(
                    wx.ID_ANY,
                    _("High Speed Downloader..."),
                    _("Download YouTube videos and playlists in high speed")
                )
                gui.mainFrame.Bind(wx.EVT_MENU, self.on_menu_open, self.menu_item)
            except Exception:
                self.menu_item = None

    @script(
        gesture="kb:NVDA+control+y",
        description=_("Opens high speed downloader")
    )
    def script_openHighSpeedDownloader(self, gesture):
        self.open_downloader()

    def on_menu_open(self, evt):
        self.open_downloader()

    def open_downloader(self):
        parent = gui.mainFrame if HAS_NVDA_CORE and hasattr(gui, "mainFrame") else None
        HighSpeedDownloaderDialog.open_dialog(parent)

    def terminate(self):
        if HAS_NVDA_CORE:
            try:
                if HighSpeedDownloaderSettingsPanel in settingsDialogs.NVDASettingsDialog.categoryClasses:
                    settingsDialogs.NVDASettingsDialog.categoryClasses.remove(HighSpeedDownloaderSettingsPanel)
            except Exception:
                pass

            if self.tools_menu and self.menu_item:
                try:
                    self.tools_menu.Remove(self.menu_item)
                except Exception:
                    pass
        super().terminate()


def main():
    """Standalone entry point for testing outside NVDA."""
    app = wx.App(False)
    dlg = HighSpeedDownloaderDialog.open_dialog()
    app.MainLoop()


if __name__ == "__main__":
    main()
