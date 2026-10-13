# -*- coding: utf-8 -*-
"""
Automated unit and integration test suite for High Speed Downloader add-on.
"""

import os
import sys
import unittest
from pathlib import Path

# Add addon directory to sys.path
addon_pkg_dir = os.path.join(os.path.dirname(__file__), "addon", "globalPlugins")
if addon_pkg_dir not in sys.path:
    sys.path.insert(0, addon_pkg_dir)

import wx

from highSpeedDownloader import config_mgr
from highSpeedDownloader import updater
from highSpeedDownloader import downloader
from highSpeedDownloader import ui_dialogs
from highSpeedDownloader import settings_panel
from highSpeedDownloader import GlobalPlugin


class TestConfigManager(unittest.TestCase):
    def test_default_output_folder(self):
        folder = config_mgr.get_default_download_folder()
        self.assertTrue(folder.endswith(os.path.join("Downloads", "high speed downloader")))

    def test_settings_read_write(self):
        orig_q = config_mgr.get_video_quality()
        config_mgr.set_video_quality("1080p")
        self.assertEqual(config_mgr.get_video_quality(), "1080p")
        config_mgr.set_video_quality(orig_q)

        orig_fmt = config_mgr.get_video_format()
        config_mgr.set_video_format("mkv")
        self.assertEqual(config_mgr.get_video_format(), "mkv")
        config_mgr.set_video_format(orig_fmt)


class TestUpdater(unittest.TestCase):
    def test_find_ytdlp_exe(self):
        exe = updater.find_ytdlp_exe()
        self.assertTrue(os.path.isfile(exe), f"yt-dlp.exe not found at {exe}")

    def test_get_installed_version(self):
        ver = updater.get_installed_version()
        self.assertTrue(len(ver) > 4, f"Version string invalid: {ver}")
        self.assertIn("2026", ver)


class TestDownloader(unittest.TestCase):
    def test_is_playlist_link(self):
        self.assertTrue(downloader.is_playlist_link("https://www.youtube.com/playlist?list=PL12345"))
        self.assertFalse(downloader.is_playlist_link("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

    def test_download_manager_queue_and_cancel(self):
        mgr = downloader.DownloadManager()
        item = mgr.add_download(
            title="Test Item",
            url="https://www.youtube.com/watch?v=fake",
            download_as="Video",
            format_ext="mp4",
            quality="1080p"
        )
        self.assertEqual(item.title, "Test Item")
        self.assertEqual(item.format_ext, "mp4")
        self.assertTrue(mgr.has_active_downloads())

        mgr.cancel_item(item.item_id)
        self.assertFalse(mgr.has_active_downloads())

    def test_download_manager_cancel_all(self):
        mgr = downloader.DownloadManager()
        mgr.add_download("Item 1", "https://fake1")
        mgr.add_download("Item 2", "https://fake2")
        self.assertEqual(len(mgr.get_items()), 2)
        mgr.cancel_all()
        self.assertEqual(len(mgr.get_items()), 0)
        self.assertFalse(mgr.has_active_downloads())

    def test_sanitize_folder_name(self):
        cleaned = downloader.sanitize_folder_name("My Favorite: Hits / 2026? *Best*")
        self.assertNotIn(":", cleaned)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("?", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertEqual(downloader.sanitize_folder_name("..."), "Playlist")
        self.assertEqual(downloader.sanitize_folder_name("CON"), "_CON")

    def test_add_playlist_downloads_folder(self):
        mgr = downloader.DownloadManager()
        tmp_base = os.path.join(os.getcwd(), "test_output_temp")
        items = mgr.add_playlist_downloads(
            entries=[{"title": "Song 1", "url": "https://fake1"}],
            output_dir=tmp_base,
            playlist_title="Best of Rock"
        )
        self.assertEqual(len(items), 1)
        expected_dir = os.path.join(tmp_base, "Best of Rock")
        self.assertEqual(items[0].output_dir, expected_dir)
        self.assertTrue(os.path.isdir(expected_dir))
        mgr.cancel_all()
        # Clean up temporary test directory
        try:
            import shutil
            shutil.rmtree(tmp_base, ignore_errors=True)
        except Exception:
            pass


class TestUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)

    @classmethod
    def tearDownClass(cls):
        cls.app.Destroy()

    def test_main_dialog_creation(self):
        dlg = ui_dialogs.HighSpeedDownloaderDialog(parent=None)
        self.assertIsNotNone(dlg.url_edit)
        self.assertIsNotNone(dlg.download_as_choice)
        self.assertIsNotNone(dlg.format_choice)
        self.assertIsNotNone(dlg.start_btn)
        self.assertIsNotNone(dlg.downloads_list)
        self.assertIsNotNone(dlg.gauge)
        self.assertIsNotNone(dlg.action_btn)
        self.assertIsNotNone(dlg.cancel_all_btn)
        self.assertIsNotNone(dlg.close_btn)

        # 1. cancel_all_btn and gauge must be disabled and not focusable when no downloads are running
        self.assertFalse(dlg.cancel_all_btn.IsEnabled())
        self.assertFalse(dlg.gauge.IsEnabled())
        self.assertFalse(dlg.gauge.AcceptsFocus())
        self.assertFalse(dlg.gauge.AcceptsFocusFromKeyboard())

        # Check format updates when download_as changes
        dlg.download_as_choice.SetSelection(0) # Video
        dlg.on_download_as_changed(None)
        video_items = [dlg.format_choice.GetString(i) for i in range(dlg.format_choice.GetCount())]
        self.assertIn("mp4", video_items)
        self.assertIn("mkv", video_items)

        dlg.download_as_choice.SetSelection(1) # Audio
        dlg.on_download_as_changed(None)
        audio_items = [dlg.format_choice.GetString(i) for i in range(dlg.format_choice.GetCount())]
        self.assertIn("mp3", audio_items)
        self.assertIn("wav", audio_items)

        # 2. Add an item and verify first item is selected, cancel_all and gauge are enabled, gauge is focusable, percentage is whole number
        item = dlg.download_mgr.add_download(title="Test Song", url="https://fake", format_ext="mp3")
        item.progress = 45.6
        dlg._safe_update_item(item)

        self.assertTrue(dlg.cancel_all_btn.IsEnabled())
        self.assertTrue(dlg.gauge.IsEnabled())
        self.assertTrue(dlg.gauge.AcceptsFocus())
        self.assertTrue(dlg.gauge.AcceptsFocusFromKeyboard())
        self.assertEqual(dlg.downloads_list.GetSelectedItemCount(), 1)
        self.assertEqual(dlg.downloads_list.GetFirstSelected(), 0)
        # Percentage must be whole number ("46%")
        self.assertEqual(dlg.downloads_list.GetItem(0, 2).GetText(), "46%")

        # 3. Mark completed, close dialog, reopen dialog -> completed video must NOT remain, gauge disabled
        item.cancel()
        item.status = "Completed"
        dlg._destroy_dialog()

        # Reopen dialog
        dlg2 = ui_dialogs.HighSpeedDownloaderDialog.open_dialog()
        self.assertEqual(dlg2.downloads_list.GetItemCount(), 0)
        self.assertFalse(dlg2.cancel_all_btn.IsEnabled())
        self.assertFalse(dlg2.gauge.IsEnabled())
        self.assertFalse(dlg2.gauge.AcceptsFocus())
        dlg2.download_mgr.cancel_all()
        dlg2._destroy_dialog()

    def test_playlist_dialog_creation(self):
        sample_entries = [
            {"id": "1", "title": "Video 1", "url": "https://fake1"},
            {"id": "2", "title": "Video 2", "url": "https://fake2"},
            {"id": "3", "title": "Video 3", "url": "https://fake3"},
        ]
        dlg = ui_dialogs.PlaylistVideosDialog(None, "Sample Playlist", sample_entries)
        # Check that list of checkboxes exists
        self.assertIsNotNone(dlg.check_list)
        self.assertEqual(dlg.check_list.GetCount(), 3)
        for i in range(3):
            self.assertTrue(dlg.check_list.IsChecked(i))  # All checked by default

        # All items checked by default
        selected = dlg.get_selected_entries()
        self.assertEqual(len(selected), 3)

        # Deselect all
        dlg.on_deselect_all(None)
        self.assertEqual(len(dlg.get_selected_entries()), 0)

        # Select all
        dlg.on_select_all(None)
        self.assertEqual(len(dlg.get_selected_entries()), 3)
        dlg.Destroy()

    def test_close_confirm_dialog(self):
        dlg = ui_dialogs.ActiveDownloadCloseDialog(None)
        self.assertIsNotNone(dlg.bg_btn)
        self.assertIsNotNone(dlg.stop_btn)
        self.assertIsNotNone(dlg.cancel_btn)
        dlg.Destroy()

    def test_settings_panel_creation(self):
        frame = wx.Frame(None)
        panel = settings_panel.HighSpeedDownloaderSettingsPanel(frame)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.makeSettings(sizer)
        self.assertIsNotNone(panel.output_folder_edit)
        self.assertIsNotNone(panel.browse_btn)
        self.assertIsNotNone(panel.quality_choice)
        self.assertIsNotNone(panel.check_update_btn)

        # Test onSave
        panel.output_folder_edit.SetValue(config_mgr.get_default_download_folder())
        panel.quality_choice.SetStringSelection("720p")
        panel.onSave()
        self.assertEqual(config_mgr.get_video_quality(), "720p")

        frame.Destroy()

    def test_global_plugin_instance(self):
        plugin = GlobalPlugin()
        self.assertEqual(plugin.scriptCategory, "high speed downloader")
        plugin.terminate()


class TestDocumentationAndManifest(unittest.TestCase):
    def test_documentation_files_exist(self):
        root = Path(__file__).resolve().parent
        doc_html = root / "addon" / "doc" / "en" / "readme.html"
        doc_css = root / "addon" / "doc" / "style.css"
        self.assertTrue(doc_html.is_file(), f"readme.html missing at {doc_html}")
        self.assertTrue(doc_css.is_file(), f"style.css missing at {doc_css}")
        self.assertGreater(doc_html.stat().st_size, 500)

    def test_manifest_metadata(self):
        root = Path(__file__).resolve().parent
        import build_addon
        manifest_path = build_addon.generate_manifest(root)
        self.assertTrue(manifest_path.is_file())
        text = manifest_path.read_text(encoding="utf-8")
        self.assertIn("name = HighSpeedDownloader", text)
        self.assertIn("docFileName = readme.html", text)
        self.assertIn("Fast & Accessible Video and Audio Downloader", text)
        self.assertIn("https://github.com/Bibeksharma5/high-speed-downloader", text)


if __name__ == "__main__":
    unittest.main()

