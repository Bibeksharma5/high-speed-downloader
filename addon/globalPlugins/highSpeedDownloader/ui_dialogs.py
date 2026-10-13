# -*- coding: utf-8 -*-
"""
Accessible wxPython interface for High Speed Downloader NVDA add-on.
Implements the main download window, playlist video selection dialog,
and confirmation dialogs for closing during active downloads.
"""

import os
import sys
import threading
import wx

from . import config_mgr
from .downloader import (
    DownloadManager,
    DownloadItem,
    inspect_url
)

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

# Global singleton download manager to allow running downloads in background across window closes
_global_download_mgr = None

def get_download_manager():
    global _global_download_mgr
    if _global_download_mgr is None:
        _global_download_mgr = DownloadManager()
    return _global_download_mgr


class PlaylistVideosDialog(wx.Dialog):
    """
    Dialog displaying checkboxes for all videos in a playlist.
    All videos are checked by default. Clicking Continue proceeds with download.
    """
    def __init__(self, parent, playlist_title: str, entries: list):
        super().__init__(
            parent,
            title=_("Choose Videos to Download - {title}").format(title=playlist_title),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
            size=(550, 420)
        )
        self.entries = entries

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        prompt_lbl = wx.StaticText(
            self,
            label=_("&Select videos to download ({count} videos found):").format(count=len(entries))
        )
        main_sizer.Add(prompt_lbl, flag=wx.ALL, border=10)

        choices = [f"{idx + 1}. {e['title']}" for idx, e in enumerate(entries)]
        self.check_list = wx.CheckListBox(
            self,
            choices=choices,
            style=wx.LB_SINGLE | wx.LB_HSCROLL
        )
        main_sizer.Add(self.check_list, proportion=1, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        # By default, all videos must be checked
        for i in range(len(entries)):
            self.check_list.Check(i, True)

        # Quick select buttons
        quick_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.select_all_btn = wx.Button(self, label=_("Select &All"))
        self.select_all_btn.Bind(wx.EVT_BUTTON, self.on_select_all)
        quick_sizer.Add(self.select_all_btn, flag=wx.RIGHT, border=5)

        self.deselect_all_btn = wx.Button(self, label=_("&Unselect All"))
        self.deselect_all_btn.Bind(wx.EVT_BUTTON, self.on_deselect_all)
        quick_sizer.Add(self.deselect_all_btn, flag=wx.RIGHT, border=5)

        main_sizer.Add(quick_sizer, flag=wx.ALL, border=10)

        # Action buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.continue_btn = wx.Button(self, wx.ID_OK, label=_("&Continue"))
        self.continue_btn.SetDefault()
        btn_sizer.Add(self.continue_btn, flag=wx.RIGHT, border=10)

        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        btn_sizer.Add(self.cancel_btn)

        main_sizer.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)

        self.SetSizer(main_sizer)
        self.CentreOnParent()

    def on_select_all(self, evt):
        for i in range(len(self.entries)):
            self.check_list.Check(i, True)

    def on_deselect_all(self, evt):
        for i in range(len(self.entries)):
            self.check_list.Check(i, False)

    def get_selected_entries(self) -> list:
        selected = []
        for i in range(len(self.entries)):
            if self.check_list.IsChecked(i):
                selected.append(self.entries[i])
        return selected


class ActiveDownloadCloseDialog(wx.Dialog):
    """
    Prompt shown when the user attempts to close High Speed Downloader while downloads are active.
    Buttons:
    - Run download in background
    - Stop all downloads
    - Cancel
    """
    ID_BACKGROUND = 1001
    ID_STOP_ALL = 1002

    def __init__(self, parent):
        super().__init__(
            parent,
            title=_("Download is still active"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        msg_lbl = wx.StaticText(
            self,
            label=_("Download is still active. What do you want to do?")
        )
        main_sizer.Add(msg_lbl, flag=wx.ALL, border=15)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.bg_btn = wx.Button(self, self.ID_BACKGROUND, label=_("&Run download in background"))
        self.bg_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.ID_BACKGROUND))
        btn_sizer.Add(self.bg_btn, flag=wx.RIGHT, border=5)

        self.stop_btn = wx.Button(self, self.ID_STOP_ALL, label=_("&Stop all downloads"))
        self.stop_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.ID_STOP_ALL))
        btn_sizer.Add(self.stop_btn, flag=wx.RIGHT, border=5)

        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
        btn_sizer.Add(self.cancel_btn)

        main_sizer.Add(btn_sizer, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=15)

        self.SetSizerAndFit(main_sizer)
        self.CentreOnParent()


class HighSpeedDownloaderDialog(wx.Dialog):
    """
    Main User Interface for High Speed Downloader NVDA Add-on.
    """
    _instance = None

    @classmethod
    def open_dialog(cls, parent=None):
        if cls._instance is not None:
            try:
                cls._instance.Raise()
                cls._instance.SetFocus()
                cls._instance.Show()
                return cls._instance
            except Exception:
                cls._instance = None

        dlg = cls(parent)
        cls._instance = dlg
        dlg.Show()
        return dlg

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title=_("High Speed Downloader"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MINIMIZE_BOX,
            size=(640, 560)
        )
        self.download_mgr = get_download_manager()

        # Connect download manager callbacks
        self.download_mgr.on_item_updated = self._on_item_updated_async
        self.download_mgr.on_overall_progress = self._on_overall_progress_async
        self.download_mgr.on_all_completed = self._on_all_completed_async

        self._item_row_map = {}  # item_id -> list_index

        self._init_ui()
        self._populate_existing_downloads()

        self.Bind(wx.EVT_CLOSE, self.on_close_clicked)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.CentreOnScreen()

    def _init_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 1. Edit box to paste video link
        url_box = wx.BoxSizer(wx.VERTICAL)
        self.url_label = wx.StaticText(self, label=_("&Paste video or playlist link:"))
        url_box.Add(self.url_label, flag=wx.BOTTOM, border=3)

        self.url_edit = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.url_edit.Bind(wx.EVT_TEXT_ENTER, self.on_start_download)
        url_box.Add(self.url_edit, flag=wx.EXPAND)
        main_sizer.Add(url_box, flag=wx.ALL | wx.EXPAND, border=10)

        # 2. & 3. Options row: "download as:" and file format
        opts_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Download as Choice
        as_box = wx.BoxSizer(wx.VERTICAL)
        self.as_label = wx.StaticText(self, label=_("&Download as:"))
        as_box.Add(self.as_label, flag=wx.BOTTOM, border=3)

        self.download_as_choice = wx.Choice(self, choices=[_("Video"), _("Audio")])
        initial_as = config_mgr.get_download_as()
        self.download_as_choice.SetSelection(0 if initial_as == "Video" else 1)
        self.download_as_choice.Bind(wx.EVT_CHOICE, self.on_download_as_changed)
        as_box.Add(self.download_as_choice, flag=wx.EXPAND)
        opts_sizer.Add(as_box, proportion=1, flag=wx.RIGHT, border=10)

        # Format Choice
        fmt_box = wx.BoxSizer(wx.VERTICAL)
        self.fmt_label = wx.StaticText(self, label=_("&Format:"))
        fmt_box.Add(self.fmt_label, flag=wx.BOTTOM, border=3)

        self.format_choice = wx.Choice(self, choices=[])
        self._update_format_choices()
        fmt_box.Add(self.format_choice, flag=wx.EXPAND)
        opts_sizer.Add(fmt_box, proportion=1)

        main_sizer.Add(opts_sizer, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        # 4. Button to start download
        btn_start_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_btn = wx.Button(self, label=_("&Start download"))
        self.start_btn.SetDefault()
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start_download)
        btn_start_sizer.Add(self.start_btn, flag=wx.TOP | wx.BOTTOM, border=8)
        main_sizer.Add(btn_start_sizer, flag=wx.LEFT | wx.RIGHT, border=10)

        # 5. ListCtrl showing all active downloads
        list_lbl = wx.StaticText(self, label=_("&Active downloads list:"))
        main_sizer.Add(list_lbl, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        self.downloads_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
        )
        self.downloads_list.InsertColumn(0, _("Title"), width=240)
        self.downloads_list.InsertColumn(1, _("Status"), width=95)
        self.downloads_list.InsertColumn(2, _("Progress"), width=75)
        self.downloads_list.InsertColumn(3, _("Speed"), width=85)
        self.downloads_list.InsertColumn(4, _("ETA"), width=65)
        self.downloads_list.InsertColumn(5, _("Format"), width=65)

        self.downloads_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_list_selection_changed)
        self.downloads_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_list_selection_changed)
        self.downloads_list.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.on_list_selection_changed)
        self.downloads_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_list_item_activated)

        main_sizer.Add(self.downloads_list, proportion=1, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        # 6. Gauge progress bar updated real-time
        self.gauge = wx.Gauge(self, range=100, size=(-1, 20))
        main_sizer.Add(self.gauge, flag=wx.ALL | wx.EXPAND, border=10)

        # 7. Action button: Cancel selected download OR Play completed file
        # 8. Cancel all downloads button
        # 9. Close button
        actions_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.action_btn = wx.Button(self, label=_("&Cancel selected download"))
        self.action_btn.Bind(wx.EVT_BUTTON, self.on_action_button_clicked)
        self.action_btn.Enable(False)
        actions_sizer.Add(self.action_btn, flag=wx.RIGHT, border=5)

        self.cancel_all_btn = wx.Button(self, label=_("Cancel &all downloads"))
        self.cancel_all_btn.Bind(wx.EVT_BUTTON, self.on_cancel_all_clicked)
        actions_sizer.Add(self.cancel_all_btn, flag=wx.RIGHT, border=5)

        actions_sizer.AddStretchSpacer()

        self.close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_clicked)
        actions_sizer.Add(self.close_btn)

        main_sizer.Add(actions_sizer, flag=wx.ALL | wx.EXPAND, border=10)

        self.SetSizer(main_sizer)

    def _update_format_choices(self):
        sel = self.download_as_choice.GetSelection()
        is_video = (sel == 0)
        formats = config_mgr.VIDEO_FORMATS if is_video else config_mgr.AUDIO_FORMATS
        saved_fmt = config_mgr.get_video_format() if is_video else config_mgr.get_audio_format()

        self.format_choice.Clear()
        for f in formats:
            self.format_choice.Append(f)

        if saved_fmt in formats:
            self.format_choice.SetStringSelection(saved_fmt)
        else:
            self.format_choice.SetSelection(0)

    def on_download_as_changed(self, evt):
        self._update_format_choices()
        sel = self.download_as_choice.GetSelection()
        config_mgr.set_download_as("Video" if sel == 0 else "Audio")

    def on_start_download(self, evt):
        raw_url = self.url_edit.GetValue().strip()
        if not raw_url:
            ui.message(_("Please enter a video or playlist link."))
            self.url_edit.SetFocus()
            return

        # Announce download started as required
        ui.message(_("Download started, please wait"))

        # Save selected options
        download_as = "Video" if self.download_as_choice.GetSelection() == 0 else "Audio"
        format_ext = self.format_choice.GetStringSelection()
        if download_as == "Video":
            config_mgr.set_video_format(format_ext)
        else:
            config_mgr.set_audio_format(format_ext)

        quality = config_mgr.get_video_quality()
        out_dir = config_mgr.get_output_folder()

        self.url_edit.Clear()

        # Run URL inspection in background thread to avoid freezing UI
        def inspect_worker():
            info = inspect_url(raw_url)
            wx.CallAfter(self._on_url_inspected, info, raw_url, download_as, format_ext, quality, out_dir)

        threading.Thread(target=inspect_worker, daemon=True).start()

    def _on_url_inspected(self, info: dict, raw_url: str, download_as: str, format_ext: str, quality: str, out_dir: str):
        if info.get("is_playlist") and info.get("entries"):
            # Show choose videos dialog
            dlg = PlaylistVideosDialog(self, info.get("title", _("Playlist")), info["entries"])
            if dlg.ShowModal() == wx.ID_OK:
                selected_entries = dlg.get_selected_entries()
                if selected_entries:
                    self.download_mgr.add_playlist_downloads(
                        selected_entries,
                        download_as=download_as,
                        format_ext=format_ext,
                        quality=quality,
                        output_dir=out_dir
                    )
                else:
                    ui.message(_("No videos selected from playlist."))
            dlg.Destroy()
        else:
            # Single video download
            title = info.get("title") or raw_url
            self.download_mgr.add_download(
                title=title,
                url=raw_url,
                download_as=download_as,
                format_ext=format_ext,
                quality=quality,
                output_dir=out_dir
            )

    def _populate_existing_downloads(self):
        items = self.download_mgr.get_items()
        for item in items:
            self._update_or_add_list_row(item)
        self.update_action_button()

    def _on_item_updated_async(self, item: DownloadItem):
        wx.CallAfter(self._safe_update_item, item)

    def _safe_update_item(self, item: DownloadItem):
        if self.IsBeingDeleted():
            return
        self._update_or_add_list_row(item)
        self.update_action_button()

    def _update_or_add_list_row(self, item: DownloadItem):
        item_id = item.item_id
        if item_id in self._item_row_map:
            row_idx = self._item_row_map[item_id]
            if row_idx >= self.downloads_list.GetItemCount() or self.downloads_list.GetItemData(row_idx) != item_id:
                # Find matching row index
                row_idx = -1
                for i in range(self.downloads_list.GetItemCount()):
                    if self.downloads_list.GetItemData(i) == item_id:
                        row_idx = i
                        self._item_row_map[item_id] = row_idx
                        break
        else:
            row_idx = -1

        status_text = _(item.status)
        pct_text = f"{item.progress:.1f}%"
        speed_text = item.speed
        eta_text = item.eta

        if row_idx == -1:
            row_idx = self.downloads_list.InsertItem(self.downloads_list.GetItemCount(), item.title)
            self.downloads_list.SetItemData(row_idx, item_id)
            self._item_row_map[item_id] = row_idx

        self.downloads_list.SetItem(row_idx, 0, item.title)
        self.downloads_list.SetItem(row_idx, 1, status_text)
        self.downloads_list.SetItem(row_idx, 2, pct_text)
        self.downloads_list.SetItem(row_idx, 3, speed_text)
        self.downloads_list.SetItem(row_idx, 4, eta_text)
        self.downloads_list.SetItem(row_idx, 5, item.format_ext)

    def _on_overall_progress_async(self, percent: float):
        wx.CallAfter(self._safe_update_gauge, percent)

    def _safe_update_gauge(self, percent: float):
        if self.IsBeingDeleted():
            return
        val = int(round(percent))
        val = min(100, max(0, val))
        self.gauge.SetValue(val)

    def _on_all_completed_async(self):
        wx.CallAfter(self._safe_all_completed)

    def _safe_all_completed(self):
        if self.IsBeingDeleted():
            return
        self.gauge.SetValue(100)
        self.update_action_button()

    def get_selected_download_item(self) -> tuple:
        """Returns (row_index, DownloadItem or None)"""
        sel = self.downloads_list.GetFirstSelected()
        if sel == -1:
            return -1, None
        item_id = self.downloads_list.GetItemData(sel)
        item = self.download_mgr.get_item(item_id)
        return sel, item

    def on_list_selection_changed(self, evt):
        self.update_action_button()
        evt.Skip()

    def update_action_button(self):
        row, item = self.get_selected_download_item()
        if not item:
            self.action_btn.SetLabel(_("&Cancel selected download"))
            self.action_btn.Enable(False)
            return

        if item.status == "Completed":
            self.action_btn.SetLabel(_("&Play"))
            self.action_btn.Enable(True)
        elif item.status in ("Downloading", "Queued"):
            self.action_btn.SetLabel(_("&Cancel selected download"))
            self.action_btn.Enable(True)
        else:
            self.action_btn.SetLabel(_("&Cancel selected download"))
            self.action_btn.Enable(True)

    def on_action_button_clicked(self, evt):
        row, item = self.get_selected_download_item()
        if not item:
            return

        if item.status == "Completed":
            self._play_file(item)
        else:
            self._cancel_selected(row, item)

    def on_list_item_activated(self, evt):
        row, item = self.get_selected_download_item()
        if item and item.status == "Completed":
            self._play_file(item)

    def _play_file(self, item: DownloadItem):
        filepath = item.final_filepath
        if filepath and os.path.isfile(filepath):
            try:
                os.startfile(filepath)
            except Exception as e:
                wx.MessageBox(
                    _("Failed to play file:\n{error}").format(error=str(e)),
                    _("Error"),
                    wx.OK | wx.ICON_ERROR,
                    self
                )
        else:
            wx.MessageBox(
                _("Downloaded file could not be found on disk."),
                _("File Not Found"),
                wx.OK | wx.ICON_WARNING,
                self
            )

    def _cancel_selected(self, row: int, item: DownloadItem):
        item_id = item.item_id
        self.download_mgr.cancel_item(item_id)
        if row != -1 and row < self.downloads_list.GetItemCount():
            self.downloads_list.DeleteItem(row)
        if item_id in self._item_row_map:
            del self._item_row_map[item_id]

        # Re-index remaining rows
        self._item_row_map.clear()
        for i in range(self.downloads_list.GetItemCount()):
            iid = self.downloads_list.GetItemData(i)
            self._item_row_map[iid] = i

        self.update_action_button()
        ui.message(_("selected download cancelled"))

    def on_cancel_all_clicked(self, evt):
        self.download_mgr.cancel_all()
        self.downloads_list.DeleteAllItems()
        self._item_row_map.clear()
        self.gauge.SetValue(0)
        self.update_action_button()
        ui.message(_("All downloads cancelled"))

    def on_char_hook(self, evt):
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            self.on_close_clicked(evt)
        else:
            evt.Skip()

    def on_close_clicked(self, evt):
        if not self.download_mgr.has_active_downloads():
            self._destroy_dialog()
            return

        # Show active download confirmation dialog
        dlg = ActiveDownloadCloseDialog(self)
        res = dlg.ShowModal()
        dlg.Destroy()

        if res == ActiveDownloadCloseDialog.ID_BACKGROUND:
            # Continue in background, close window
            self._destroy_dialog()
        elif res == ActiveDownloadCloseDialog.ID_STOP_ALL:
            # Stop all downloads and close
            self.download_mgr.cancel_all()
            self._destroy_dialog()
        else:
            # Cancel: return to dialog
            pass

    def _destroy_dialog(self):
        HighSpeedDownloaderDialog._instance = None
        self.Destroy()
