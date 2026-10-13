# -*- coding: utf-8 -*-
"""
NVDA Settings panel for High Speed Downloader.
Integrates into NVDA Preferences -> Settings under category 'high speed downloader'.
Contains:
- Output folder group with path edit field and browse button.
- Video downloading group with quality dropdown selector.
- yt-dlp updates group with check for updates button.
"""

import os
import wx

from . import config_mgr
from . import updater

try:
    import addonHandler
    addonHandler.initTranslation()
    _ = _
except Exception:
    def _(text):
        return text

try:
    from gui import settingsDialogs
    from gui import guiHelper
    BaseSettingsPanel = settingsDialogs.SettingsPanel
except Exception:
    class FakeSettingsPanel(wx.Panel):
        title = ""
        def __init__(self, parent):
            super().__init__(parent)
    BaseSettingsPanel = FakeSettingsPanel
    guiHelper = None


class HighSpeedDownloaderSettingsPanel(BaseSettingsPanel):
    title = _("high speed downloader")

    def makeSettings(self, settingsSizer):
        if guiHelper and hasattr(guiHelper, "BoxSizerHelper"):
            sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        else:
            sHelper = None

        # -----------------------------------------------------------------
        # GroupBox 1: output folder
        # -----------------------------------------------------------------
        output_box = wx.StaticBox(self, label=_("output folder"))
        output_sizer = wx.StaticBoxSizer(output_box, wx.VERTICAL)

        path_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.output_folder_edit = wx.TextCtrl(output_box, value=config_mgr.get_output_folder())
        path_row_sizer.Add(self.output_folder_edit, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)

        self.browse_btn = wx.Button(output_box, label=_("&Browse..."))
        self.browse_btn.Bind(wx.EVT_BUTTON, self.on_browse_output_folder)
        path_row_sizer.Add(self.browse_btn, flag=wx.ALIGN_CENTER_VERTICAL)

        output_sizer.Add(path_row_sizer, flag=wx.ALL | wx.EXPAND, border=8)

        if sHelper:
            output_helper = guiHelper.BoxSizerHelper(self, sizer=output_sizer)
            sHelper.addItem(output_helper)
        else:
            settingsSizer.Add(output_sizer, flag=wx.ALL | wx.EXPAND, border=10)

        # -----------------------------------------------------------------
        # GroupBox 2: Video downloading
        # -----------------------------------------------------------------
        video_box = wx.StaticBox(self, label=_("Video downloading"))
        video_sizer = wx.StaticBoxSizer(video_box, wx.VERTICAL)

        qual_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        qual_lbl = wx.StaticText(video_box, label=_("&Video quality:"))
        qual_row_sizer.Add(qual_lbl, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)

        self.quality_choice = wx.Choice(video_box, choices=config_mgr.VIDEO_QUALITIES)
        saved_q = config_mgr.get_video_quality()
        if saved_q in config_mgr.VIDEO_QUALITIES:
            self.quality_choice.SetStringSelection(saved_q)
        else:
            self.quality_choice.SetSelection(0)
        qual_row_sizer.Add(self.quality_choice, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)

        video_sizer.Add(qual_row_sizer, flag=wx.ALL | wx.EXPAND, border=8)

        if sHelper:
            video_helper = guiHelper.BoxSizerHelper(self, sizer=video_sizer)
            sHelper.addItem(video_helper)
        else:
            settingsSizer.Add(video_sizer, flag=wx.ALL | wx.EXPAND, border=10)

        # -----------------------------------------------------------------
        # GroupBox 3: yt-dlp updates
        # -----------------------------------------------------------------
        updates_box = wx.StaticBox(self, label=_("yt-dlp updates"))
        updates_sizer = wx.StaticBoxSizer(updates_box, wx.VERTICAL)

        self.check_update_btn = wx.Button(updates_box, label=_("&Check for yt-dlp update"))
        self.check_update_btn.Bind(wx.EVT_BUTTON, self.on_check_update)
        updates_sizer.Add(self.check_update_btn, flag=wx.ALL, border=8)

        if sHelper:
            updates_helper = guiHelper.BoxSizerHelper(self, sizer=updates_sizer)
            sHelper.addItem(updates_helper)
        else:
            settingsSizer.Add(updates_sizer, flag=wx.ALL | wx.EXPAND, border=10)

    def on_browse_output_folder(self, evt):
        current = self.output_folder_edit.GetValue().strip()
        if not os.path.isdir(current):
            current = os.path.expanduser("~")

        dlg = wx.DirDialog(
            self,
            message=_("Select output download folder"),
            defaultPath=current,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
        )
        if dlg.ShowModal() == wx.ID_OK:
            selected_path = dlg.GetPath()
            self.output_folder_edit.SetValue(os.path.normpath(selected_path))
        dlg.Destroy()

    def on_check_update(self, evt):
        updater.check_and_update(parent=self)

    def onSave(self):
        new_folder = self.output_folder_edit.GetValue().strip()
        if new_folder:
            config_mgr.set_output_folder(new_folder)

        new_quality = self.quality_choice.GetStringSelection()
        if new_quality:
            config_mgr.set_video_quality(new_quality)

        config_mgr.save_config()

    def onDiscard(self):
        pass
