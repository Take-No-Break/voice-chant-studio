"""Upgrade/UI regression tests. Synthetic audio only; never use mic or speakers."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import tkinter as tk
import unittest
from unittest.mock import patch

import numpy as np

import app
from core import EVENTS, Project, load_audio
from recording import RecordingController
from test_recording import Factory, Scheduler


class ProjectUpgradeTests(unittest.TestCase):
    def test_upgrade_keeps_user_keys_recordings_and_finished_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'legacy'
            original_catalog = [{'key': 'my_heal', 'name': 'My Holy Light',
                                 'class': 'PALADIN', 'ids': [635]}]
            p = Project(root, original_catalog)
            source = p.add_audio(np.full(1000, .1, dtype=np.float32), 1000)
            original_audio = p.asset(source).read_bytes()
            clip = {'source': source, 'start': .12, 'end': .91, 'gain': .75,
                    'normalize': True, 'ready': True}
            p.data['clips']['my_heal:start'] = copy.deepcopy(clip)
            p.data['options'] = {'gap': .7, 'stop_on_cancel': False}
            p.data['game'] = 'user-selected-game'
            p.save()
            before = copy.deepcopy(p.data)
            bundled = [
                {'key': 'holy_light', 'name': 'Holy Light', 'class': 'PALADIN',
                 'ids': [635, 639], 'cast_seconds': 2.5, 'name_ja': '聖なる光'},
                {'key': 'mage_channel', 'name': 'Arcane Missiles', 'class': 'MAGE',
                 'ids': [5143], 'cast_seconds': 0, 'channeled': True}]
            upgraded = Project(root, bundled)
            self.assertEqual(upgraded.data['clips'], before['clips'])
            self.assertEqual(upgraded.data['options'], before['options'])
            self.assertEqual(upgraded.data['game'], before['game'])
            heal = upgraded.data['catalog'][0]
            self.assertEqual((heal['key'], heal['name']), ('my_heal', 'My Holy Light'))
            self.assertEqual(heal['ids'], [635, 639])
            self.assertTrue(upgraded.data['catalog'][1]['channeled'])
            self.assertEqual(upgraded.asset(source).read_bytes(), original_audio)
            backups = list(root.glob('project-before-upgrade-*.json'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text(encoding='utf8')), before)
            # Opening again must be idempotent, without more migration backups.
            self.assertEqual(Project(root, bundled).data, upgraded.data)
            self.assertEqual(len(list(root.glob('project-before-upgrade-*.json'))), 1)

    def test_catalog_nested_ids_are_independent_across_projects(self):
        catalog = [{'key': 'heal', 'name': 'Heal', 'class': 'PALADIN', 'ids': [635]}]
        original = copy.deepcopy(catalog)
        with tempfile.TemporaryDirectory() as directory:
            one = Project(Path(directory) / 'one', catalog)
            two = Project(Path(directory) / 'two', catalog)
            one.data['catalog'][0]['ids'].append(639)
            one.data['catalog'][0]['name'] = 'User name'
            self.assertEqual(catalog, original)
            self.assertEqual(two.data['catalog'], original)
            # Newly appended upgrade rows must also own their nested lists.
            more = catalog + [{'key': 'mage', 'name': 'Mage', 'class': 'MAGE', 'ids': [133]}]
            one.upgrade_catalog(more)
            one.data['catalog'][1]['ids'].append(143)
            self.assertEqual(more[1]['ids'], [133])

    def test_game_catalog_import_keeps_channeled_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Project(directory, [])
            rows = [{'id': 5143, 'name': 'Arcane Missiles', 'class': 'MAGE',
                     'cast_seconds': 0, 'channeled': True}]
            self.assertEqual(p.merge_catalog(rows), 1)
            self.assertTrue(p.data['catalog'][0]['channeled'])
            p.merge_catalog([dict(rows[0], id=5144)])
            self.assertEqual(p.data['catalog'][0]['ids'], [5143, 5144])
            self.assertTrue(Project(directory, []).data['catalog'][0]['channeled'])


class StudioV02Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.scheduler = Scheduler()
        self.factory = Factory()
        self.beeps = []

        def controller(_root, **callbacks):
            return RecordingController(self.scheduler, self.factory,
                                       beep=lambda: self.beeps.append(self.scheduler.now),
                                       **callbacks)

        def devices(index=None):
            device = {'name': 'Synthetic test input', 'max_input_channels': 1,
                      'default_samplerate': 44100}
            return [device] if index is None else device

        self.stack.enter_context(patch.object(app, 'HOME', Path(self.directory.name)))
        self.stack.enter_context(patch.object(app, 'detect_game', return_value=''))
        self.stack.enter_context(patch.object(app, 'RecordingController', side_effect=controller))
        self.stack.enter_context(patch.object(app.sd, 'default', SimpleNamespace(device=(0, 0))))
        self.stack.enter_context(patch.object(app.sd, 'query_devices', side_effect=devices))
        self.stack.enter_context(patch.object(app.sd, 'InputStream', side_effect=AssertionError('Real microphone prohibited')))
        self.stack.enter_context(patch.object(app.sd, 'play', side_effect=AssertionError('Speaker playback prohibited')))
        self.stack.enter_context(patch.object(app.sd, 'stop'))
        for method in ('showinfo', 'showerror'):
            self.stack.enter_context(patch.object(app.messagebox, method,
                                                 side_effect=AssertionError('Unexpected dialog: ' + method)))
        self.stack.enter_context(patch.object(app.messagebox, 'askyesno', return_value=True))
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.destroy)
        self.ui = app.Studio(self.root)

    def destroy(self):
        if hasattr(self, 'ui'):
            self.ui.controller.close()
        if self.root.winfo_exists():
            self.root.destroy()

    def select(self, name, class_name=None):
        if class_name:
            self.ui.class_filter.set(class_name)
            self.ui.populate()
        row = next(r for r in self.ui.project.data['catalog'] if r['name'] == name)
        self.ui.tree.selection_set(row['key'])
        self.ui.select_row()
        return row

    def wait_for_state(self, state):
        deadline = time.monotonic() + 2
        while self.ui.controller.state != state and time.monotonic() < deadline:
            self.ui.controller.poll()
            time.sleep(.002)
        self.assertEqual(self.ui.controller.state, state)

    def test_mage_filter_and_instant_cast_and_channel_default_phases(self):
        self.assertIn('MAGE', self.ui.classes['values'])
        self.select('Fire Blast', 'MAGE')
        self.assertEqual(self.ui.event_key(), 'success')
        self.select('Fireball')
        self.assertEqual(self.ui.event_key(), 'start')
        # A channel may have zero conventional cast time in an imported book.
        channel = next(r for r in self.ui.project.data['catalog'] if r['name'] == 'Arcane Missiles')
        channel['cast_seconds'] = 0
        self.select('Arcane Missiles')
        self.assertTrue(self.ui.row['channeled'])
        self.assertEqual(self.ui.event_key(), 'start')
        self.assertTrue(all(self.ui.project.data['catalog'][
            next(i for i, r in enumerate(self.ui.project.data['catalog']) if r['key'] == key)
        ]['class'] == 'MAGE' for key in self.ui.tree.get_children()))

    def test_language_toggle_persists_and_keeps_finished_clip_and_phase(self):
        self.select('Holy Light')
        self.ui.set_take(np.full(44100, .1, dtype=np.float32), 44100)
        self.ui.start.set(.12)
        self.ui.end.set(.81)
        self.ui.gain.set(.7)
        self.ui.normalize.set(True)
        self.ui.save_clip()
        key = self.ui.key()
        before = copy.deepcopy(self.ui.project.data['clips'][key])
        source = self.ui.project.asset(before['source'])
        original_bytes = source.read_bytes()
        self.ui.language_choice.set('English')
        self.ui.change_language()
        self.assertEqual(self.ui.language, 'en')
        self.assertEqual(self.ui.event_key(), 'start')
        self.assertEqual(self.ui.phase_box['values'], tuple(self.ui.tr(value) for value in EVENTS.values()))
        self.assertEqual(self.ui.record_button['text'], '● Record')
        self.assertEqual(self.ui.project.data['clips'][key], before)
        self.assertTrue(self.ui.ready)
        self.assertEqual(source.read_bytes(), original_bytes)
        settings = json.loads((app.HOME / 'settings.json').read_text(encoding='utf8'))
        self.assertEqual(settings['language'], 'en')
        # Merely rebuilding/translating UI must not make a finished clip a draft.
        self.ui.language_choice.set('日本語')
        self.ui.change_language()
        self.assertEqual(self.ui.project.data['clips'][key], before)
        self.assertTrue(self.ui.ready)
        self.assertEqual(self.ui.event_key(), 'start')

    def test_f8_countdown_can_cancel_without_opening_microphone(self):
        self.select('Holy Light')
        with patch.object(app.time, 'monotonic', side_effect=[10.0, 11.0]):
            self.assertEqual(self.ui.toggle_record(), 'break')
            self.assertEqual(self.ui.controller.state, 'countdown')
            self.assertEqual(self.beeps, [0])
            self.assertEqual(self.ui.toggle_record(), 'break')
        self.scheduler.advance(4000)
        self.ui.controller.poll()
        self.assertEqual(self.ui.controller.state, 'idle')
        self.assertEqual(self.factory.streams, [])
        self.assertFalse(self.ui.project.data['clips'])

    def test_stopped_recording_preserves_full_original_with_reversible_tail_guard(self):
        self.select('Holy Light')
        key = self.ui.key()
        self.ui.record()
        self.scheduler.advance(2999)
        self.assertEqual(self.factory.streams, [])
        self.assertEqual(self.beeps, [0, 1000, 2000])
        self.scheduler.advance(1)
        self.wait_for_state('recording')
        take = np.full(44100, .1, dtype=np.float32)
        take[-200:] = .9  # Simulate stop-button click at the very end.
        self.factory.streams[0].audio(take)
        self.ui.controller.poll()
        self.ui.stop()
        self.wait_for_state('idle')
        clip = self.ui.project.data['clips'][key]
        self.assertAlmostEqual(clip['end'], .85)
        self.assertFalse(clip['ready'])
        source = self.ui.project.asset(clip['source'])
        original_bytes = source.read_bytes()
        original, rate = load_audio(source)
        self.assertEqual((len(original), rate), (44100, 44100))
        self.assertGreater(float(original[-1]), .89)
        self.assertLess(float(np.max(self.ui.rendered())), .11)
        self.ui.full_range()
        self.assertAlmostEqual(self.ui.end.get(), 1)
        self.assertEqual(source.read_bytes(), original_bytes)
        self.assertTrue(self.factory.streams[0].closed)

    def test_filtering_during_countdown_cannot_retarget_take_or_crash_selection(self):
        old = self.select('Holy Light')
        self.ui.record()
        context = self.ui.controller.context
        self.ui.class_filter.set('MAGE')
        self.ui.populate()
        mage = next(r for r in self.ui.project.data['catalog'] if r['name'] == 'Fireball')
        if self.ui.tree.exists(mage['key']):
            self.ui.tree.selection_set(mage['key'])
            self.ui.select_row()
        self.assertEqual(self.ui.row['key'], old['key'])
        self.assertEqual(self.ui.controller.context, context)
        self.ui.stop()

    def test_save_export_and_waveform_remain_visible_at_supported_window_sizes(self):
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        # Map an invisible window so Tk computes actual geometry, without showing
        # or interacting with a second application window on the user's desktop.
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        for language in ('日本語', 'English'):
            self.ui.language_choice.set(language)
            self.ui.change_language()
            for width, height in ((1240, 840), (1040, 740)):
                with self.subTest(language=language, size=(width, height)):
                    self.root.geometry(f'{width}x{height}')
                    self.root.update_idletasks()
                    self.root.update()
                    self.root.update_idletasks()
                    widgets = list(descendants(self.root))
                    for text in (self.ui.tr('完成を保存'), self.ui.tr('ゲームへ書き出す')):
                        button = next(w for w in widgets if w.winfo_class() == 'TButton'
                                      and str(w.cget('text')) == text)
                        self.assertTrue(button.winfo_ismapped(), text)
                        self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth(), text)
                        self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight(), text)
                        # Check every clipping ancestor, not just the root bounds.
                        widget = button
                        while widget is not self.root:
                            parent = widget.nametowidget(widget.winfo_parent())
                            self.assertGreaterEqual(widget.winfo_x(), 0, text)
                            self.assertGreaterEqual(widget.winfo_y(), 0, text)
                            self.assertLessEqual(widget.winfo_x() + widget.winfo_width(),
                                                 parent.winfo_width(), text)
                            self.assertLessEqual(widget.winfo_y() + widget.winfo_height(),
                                                 parent.winfo_height(), text)
                            widget = parent
                    self.assertTrue(self.ui.canvas.winfo_ismapped())
                    self.assertGreater(self.ui.canvas.winfo_width(), 1)
                    self.assertGreater(self.ui.canvas.winfo_height(), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
