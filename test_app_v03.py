"""Priest/class/icon upgrade checks using temporary projects and synthetic audio.

No real microphone, speaker playback, live-game folder, or visible game UI.
"""
import copy
import json
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import font as tkfont, ttk
import unittest

import numpy as np

import app
from core import Project
from icons import SpellIcons
import test_app_v02 as previous_tests


REQUESTED_PRIEST = {
    'Lesser Heal': {2050, 2052, 2053},
    'Smite': {585, 591, 598, 984, 1004, 6060, 10933, 10934},
    'Flash Heal': {2061, 9472, 9473, 9474, 10915, 10916, 10917},
    'Holy Fire': {14914, 15261, 15262, 15263, 15264, 15265, 15266, 15267},
    'Holy Nova': {15237, 15430, 15431, 27799, 27800, 27801},
}


class ForeverPriestCatalogTests(unittest.TestCase):
    def test_requested_spells_are_priest_and_not_duplicate_mage_abilities(self):
        rows = app.CATALOG
        for name, ids in REQUESTED_PRIEST.items():
            with self.subTest(spell=name):
                matches = [r for r in rows if r['name'] == name]
                self.assertEqual(len(matches), 1)
                row = matches[0]
                self.assertEqual(row['class'], 'PRIEST')
                self.assertEqual(set(row['ids']), ids)
                self.assertFalse(row.get('passive'))
                self.assertTrue(row.get('name_ja'))
                self.assertTrue(row['key'].startswith('priest_'))
                self.assertFalse(any(set(r['ids']) & ids
                                     for r in rows if r['class'] == 'MAGE'))

    def test_adding_priest_catalog_preserves_user_clips_options_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing-user-project'
            legacy = [
                {'key': 'user_fireball', 'name': 'My custom Fireball', 'class': 'MAGE',
                 'ids': [133], 'cast_seconds': 2.5},
                {'key': 'user_holy_light', 'name': 'My custom Holy Light',
                 'class': 'PALADIN', 'ids': [635], 'cast_seconds': 2.5},
            ]
            p = Project(path, legacy)
            source = p.add_audio(np.full(1000, .1, dtype=np.float32), 1000)
            source_bytes = p.asset(source).read_bytes()
            p.data['clips'] = {
                'user_fireball:start': {'source': source, 'start': .13, 'end': .92,
                                       'gain': .8, 'normalize': True, 'ready': True},
                'user_holy_light:success': {'source': source, 'start': .21, 'end': .81,
                                          'gain': .6, 'normalize': False, 'ready': False},
            }
            p.data['options'] = {'gap': .6, 'stop_on_cancel': False, 'future_option': 'keep'}
            p.data['game'] = 'untouched-user-game-choice'
            p.save()
            before = copy.deepcopy(p.data)
            upgraded = Project(path, app.CATALOG)
            for field in ('clips', 'options', 'game'):
                self.assertEqual(upgraded.data[field], before[field])
            self.assertEqual(upgraded.asset(source).read_bytes(), source_bytes)
            for original in legacy:
                row = next(r for r in upgraded.data['catalog'] if r['key'] == original['key'])
                self.assertEqual(row['name'], original['name'])
                self.assertEqual(row['class'], original['class'])
                self.assertTrue(set(original['ids']) <= set(row['ids']))
            for name in REQUESTED_PRIEST:
                row = next(r for r in upgraded.data['catalog'] if r['name'] == name)
                self.assertEqual(row['class'], 'PRIEST')
            backups = list(path.glob('project-before-upgrade-*.json'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text(encoding='utf8')), before)
            again = Project(path, app.CATALOG)
            self.assertEqual(again.data, upgraded.data)
            self.assertEqual(len(list(path.glob('project-before-upgrade-*.json'))), 1)

    def test_upgrade_with_cross_class_key_collision_preserves_user_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            original = {'key': 'priest_2050', 'name': 'User Fireball', 'class': 'MAGE', 'ids': [133]}
            p = Project(directory, [original])
            p.data['clips']['priest_2050:start'] = {'source': 'user-original.wav', 'ready': True}
            p.save()
            clips = copy.deepcopy(p.data['clips'])
            bundled = [{'key': 'priest_2050', 'name': 'Lesser Heal', 'class': 'PRIEST',
                        'ids': [2050, 2052, 2053], 'cast_seconds': 1.5}]
            upgraded = Project(directory, bundled)
            self.assertEqual(upgraded.data['catalog'][0], original)
            priest = upgraded.data['catalog'][1]
            self.assertEqual(priest['class'], 'PRIEST')
            self.assertEqual(priest['ids'], [2050, 2052, 2053])
            self.assertNotEqual(priest['key'], original['key'])
            self.assertEqual(upgraded.data['clips'], clips)
            self.assertEqual(len({r['key'] for r in upgraded.data['catalog']}), 2)
            self.assertEqual(Project(directory, bundled).data, upgraded.data)


class StudioV03Tests(unittest.TestCase):
    # Reuse the existing hardware-free fixture without inheriting/rerunning its
    # independent tests. All app files and user settings stay in a temp directory.
    setUp = previous_tests.StudioV02Tests.setUp
    destroy = previous_tests.StudioV02Tests.destroy

    def switch_class(self, token):
        self.ui.search.set('')
        self.ui.class_filter.set(token)
        self.ui.populate()
        self.assertEqual(self.ui.selected_class(), token)
        return self.ui.tree.get_children()

    def visible_rows(self):
        visible = set(self.ui.tree.get_children())
        return [r for r in self.ui.project.data['catalog'] if r['key'] in visible]

    def image_name(self, key):
        value = self.ui.tree.item(key, 'image')
        if isinstance(value, (tuple, list)):
            return str(value[0]) if value else ''
        values = self.root.tk.splitlist(value)
        return str(values[0]) if values else ''

    def assert_tree_image(self, row):
        self.assertTrue(self.ui.tree.exists(row['key']))
        name = self.image_name(row['key'])
        self.assertTrue(name, f"No icon for {row['name']}")
        self.assertIn(name, tuple(str(n) for n in self.root.tk.call('image', 'names')))
        self.assertEqual(int(self.root.tk.call('image', 'width', name)), 24)
        self.assertEqual(int(self.root.tk.call('image', 'height', name)), 24)
        self.assertEqual(name, str(self.ui.icon_for(row)))
        return name

    def test_class_filters_and_labels_work_in_japanese_and_english(self):
        japanese_labels = {}
        for display, language in (('日本語', 'ja'), ('English', 'en')):
            self.ui.language_choice.set(display)
            self.ui.change_language()
            self.assertEqual(self.ui.language, language)
            for token in ('PALADIN', 'MAGE', 'PRIEST'):
                with self.subTest(language=language, class_name=token):
                    keys = self.switch_class(token)
                    self.assertTrue(keys)
                    self.assertTrue(all(r['class'] == token for r in self.visible_rows()))
                    self.assertIn(token, self.ui.classes['values'])
                    label = self.ui.class_label(token)
                    self.assertTrue(label)
                    if language == 'ja':
                        japanese_labels[token] = label
                    else:
                        self.assertIn(token.title(), label)
                        self.assertNotEqual(label, japanese_labels[token])
            self.ui.class_filter.set(self.ui.tr('すべて'))
            self.ui.populate()
            self.assertIsNone(self.ui.selected_class())
            self.assertEqual({r['class'] for r in self.visible_rows()},
                             {r['class'] for r in app.CATALOG if not r.get('passive')})
            self.assertIn('class', self.ui.tree['columns'])
            for row in self.visible_rows():
                self.assertEqual(self.ui.tree.set(row['key'], 'class'),
                                 self.ui.class_label(row['class']))

    def test_localized_class_names_fit_the_class_column_and_controls_fit_minimum_window(self):
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        for display in ('日本語', 'English'):
            self.ui.language_choice.set(display)
            self.ui.change_language()
            self.root.geometry('1040x740')
            self.root.update_idletasks()
            self.root.update()
            self.root.update_idletasks()
            font = tkfont.Font(root=self.root, font=ttk.Style(self.root).lookup('Treeview', 'font'))
            column_width = int(self.ui.tree.column('class', 'width'))
            for token in ('PALADIN', 'MAGE', 'PRIEST'):
                with self.subTest(language=display, class_name=token):
                    self.assertGreaterEqual(column_width,
                                            font.measure(self.ui.class_label(token)) + 8)
            self.assertLessEqual(self.ui.class_hint.winfo_x() + self.ui.class_hint.winfo_width(),
                                 self.ui.class_hint.master.winfo_width())
        # The established minimum-size check verifies clipping at every parent
        # of save/export controls and that the waveform remains usable.
        previous_tests.StudioV02Tests.test_save_export_and_waveform_remain_visible_at_supported_window_sizes(self)

    def test_priest_names_localize_search_and_preserve_the_selected_class(self):
        self.switch_class('PRIEST')
        for name in REQUESTED_PRIEST:
            row = next(r for r in self.ui.project.data['catalog'] if r['name'] == name)
            with self.subTest(spell=name):
                self.assertIn(row['name_ja'], self.ui.ability_label(row, combined=True))
                self.assertIn(name, self.ui.ability_label(row, combined=True))
                self.ui.search.set(row['name_ja'])
                self.ui.populate()
                self.assertTrue(self.ui.tree.exists(row['key']))
                self.assertTrue(all(r['class'] == 'PRIEST' for r in self.visible_rows()))
        self.ui.search.set('')
        self.ui.language_choice.set('English')
        self.ui.change_language()
        self.assertEqual(self.ui.selected_class(), 'PRIEST')
        for name in REQUESTED_PRIEST:
            row = next(r for r in self.ui.project.data['catalog'] if r['name'] == name)
            self.assertEqual(self.ui.ability_label(row), name)
            self.ui.search.set(name)
            self.ui.populate()
            self.assertTrue(self.ui.tree.exists(row['key']))

    def test_native_icons_are_attached_to_tree_rows_in_each_class(self):
        for token, name in (('PALADIN', 'Holy Light'), ('MAGE', 'Fireball'),
                            ('PRIEST', 'Lesser Heal')):
            with self.subTest(class_name=token):
                self.switch_class(token)
                row = next(r for r in self.ui.project.data['catalog'] if r['name'] == name)
                before = self.assert_tree_image(row)
                # Rebuilding the list must not let Tk images get garbage-collected.
                self.ui.populate()
                self.root.update_idletasks()
                self.assertEqual(self.assert_tree_image(row), before)

    def test_unmapped_custom_ability_has_a_visible_fallback_and_id_lookup_handles_legacy_keys(self):
        original = next(r for r in self.ui.project.data['catalog'] if r['name'] == 'Fireball')
        custom = {'key': 'custom_unmapped_spell', 'class': 'MAGE',
                  'name': 'Unmapped custom spell', 'ids': [99999999], 'passive': False}
        legacy = copy.deepcopy(original)
        legacy.update(key='old_user_fireball_key', name='User named Fireball')
        self.ui.project.data['catalog'].extend([custom, legacy])
        self.switch_class('MAGE')
        fallback = self.assert_tree_image(custom)
        native = self.assert_tree_image(original)
        self.assertNotEqual(fallback, native)
        self.assertEqual(self.assert_tree_image(legacy), native)


class IconFallbackTests(unittest.TestCase):
    def test_missing_icon_and_missing_index_fallback_still_render_offline(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                (folder / 'index.json').write_text(json.dumps({
                    'fallback': 'missing-fallback.png',
                    'rows': {'broken': {'file': 'missing-icon.png'}},
                    'spells': {'133': {'file': '../outside.png'}},
                }), encoding='utf8')
                library = SpellIcons(root, folder)
                for row in ({'key': 'broken', 'ids': [99999999]},
                            {'key': 'unmapped', 'ids': [99999999]},
                            {'key': 'traversal', 'ids': [133]}):
                    with self.subTest(row=row['key']):
                        image = library.for_row(row)
                        self.assertIs(image, library.fallback)
                        self.assertEqual((image.width(), image.height()), (24, 24))
                no_index = SpellIcons(root, folder / 'does-not-exist')
                image = no_index.for_row({'key': 'custom', 'ids': [133]})
                self.assertEqual((image.width(), image.height()), (24, 24))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main(verbosity=2)
