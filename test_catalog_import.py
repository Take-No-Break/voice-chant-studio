"""Transactional spellbook import tests; never touches the real project or game."""
from pathlib import Path
import copy
import tempfile
import unittest
from unittest.mock import patch

from core import Project


class CatalogImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Project(Path(self.temp.name) / 'project', [{
            'key': 'mage_arcane_missiles', 'ids': [5143], 'class': 'MAGE',
            'name': 'Arcane Missiles', 'name_ja': '魔力の矢', 'passive': False,
            'cast_seconds': 0, 'channeled': False, 'custom_metadata': 'keep',
        }])
        self.project.data['clips']['mage_arcane_missiles:start'] = {'source': 'unchanged.wav'}
        self.project.save()

    def test_later_bad_row_has_no_partial_memory_mutation_or_file_rewrite(self):
        before = copy.deepcopy(self.project.data)
        raw = self.project.path.read_bytes()
        rows = [
            {'id': 5144, 'name': 'Arcane Missiles', 'class': 'MAGE', 'channeled': True},
            {'id': 133, 'name': 'Fireball', 'class': 'MAGE'},
            {'id': 999, 'name': '   ', 'class': 'MAGE'},
        ]
        with patch.object(self.project, 'save') as save:
            with self.assertRaises(ValueError):
                self.project.merge_catalog(rows)
            save.assert_not_called()
        self.assertEqual(self.project.data, before)
        self.assertEqual(self.project.path.read_bytes(), raw)

    def test_localized_ranks_join_existing_english_group_in_any_order_and_update_metadata(self):
        rows = [
            {'id': 5144, 'name': '魔力の矢', 'class': 'MAGE', 'cast_seconds': 5, 'channeled': True},
            {'id': 5143, 'name': '魔力の矢', 'class': 'MAGE', 'cast_seconds': 5,
             'channeled': True, 'passive': True},
            {'id': 5144, 'name': '魔力の矢', 'class': 'MAGE'},
        ]
        self.assertEqual(self.project.merge_catalog(rows), 0)
        row = self.project.data['catalog'][0]
        self.assertEqual(row['name'], 'Arcane Missiles')
        self.assertEqual(row['ids'], [5143, 5144])
        self.assertEqual(row['key'], 'mage_arcane_missiles')
        self.assertEqual(row['class'], 'MAGE')
        self.assertEqual(row['custom_metadata'], 'keep')
        self.assertEqual(row['name_ja'], '魔力の矢')
        self.assertEqual(row['cast_seconds'], 5)
        self.assertTrue(row['passive'])
        self.assertTrue(row['channeled'])
        self.assertEqual(self.project.data['clips'], {'mage_arcane_missiles:start': {'source': 'unchanged.wav'}})
        self.assertEqual(Project(self.project.root, []).data, self.project.data)

    def test_missing_metadata_preserves_values_and_explicit_false_updates_them(self):
        self.project.merge_catalog([{'id': 5143, 'name': 'Arcane Missiles', 'class': 'MAGE',
                                     'channeled': True, 'passive': True, 'cast_seconds': 5}])
        self.project.merge_catalog([{'id': 5143, 'name': 'Arcane Missiles', 'class': 'MAGE'}])
        row = self.project.data['catalog'][0]
        self.assertTrue(row['channeled'])
        self.assertTrue(row['passive'])
        self.assertEqual(row['cast_seconds'], 5)
        self.project.merge_catalog([{'id': 5143, 'name': 'Arcane Missiles', 'class': 'MAGE',
                                     'channeled': False, 'passive': False, 'cast_seconds': 0}])
        row = self.project.data['catalog'][0]
        self.assertFalse(row['channeled'])
        self.assertFalse(row['passive'])
        self.assertEqual(row['cast_seconds'], 0)

    def test_new_duplicate_ranks_count_as_one_group_and_never_cross_classes(self):
        self.assertEqual(self.project.merge_catalog([
            {'id': '133', 'name': 'Fireball', 'class': 'MAGE'},
            {'id': 143, 'name': 'Fireball', 'class': 'MAGE'},
            {'id': 133, 'name': 'Fireball', 'class': 'MAGE'},
            {'id': 133, 'name': 'Fireball', 'class': 'PALADIN'},
        ]), 2)
        mage, paladin = self.project.data['catalog'][1:]
        self.assertEqual(mage['ids'], [133, 143])
        self.assertEqual(paladin['ids'], [133])
        self.assertNotEqual(mage['key'], paladin['key'])
        self.assertEqual(mage['class'], 'MAGE')
        self.assertEqual(paladin['class'], 'PALADIN')

    def test_malformed_rows_are_rejected_atomically(self):
        valid = {'id': 133, 'name': 'Fireball', 'class': 'MAGE'}
        malformed = [None, [], 'row', {},
                     {**valid, 'id': True}, {**valid, 'id': 0},
                     {**valid, 'id': 100000001}, {**valid, 'id': 133.5},
                     {**valid, 'id': float('nan')}, {**valid, 'id': []},
                     {**valid, 'name': None}, {**valid, 'name': ''},
                     {**valid, 'name': ' \t\n'}, {**valid, 'name': 133},
                     {**valid, 'class': 'mage'}, {**valid, 'class': None},
                     {**valid, 'class': 'MAGE CLASS'}, {**valid, 'class': 'MAGE1'},
                     {**valid, 'class': 'ＭＡＧＥ'},
                     {**valid, 'passive': 'false'}, {**valid, 'channeled': 1}]
        malformed += [{**valid, 'cast_seconds': v}
                      for v in (-1, 600.01, float('nan'), float('inf'), 'NaN', True, [], None)]
        before, raw = copy.deepcopy(self.project.data), self.project.path.read_bytes()
        for bad in malformed:
            with self.subTest(row=bad), patch.object(self.project, 'save') as save:
                with self.assertRaises(ValueError):
                    self.project.merge_catalog([valid, bad])
                save.assert_not_called()
                self.assertEqual(self.project.data, before)
                self.assertEqual(self.project.path.read_bytes(), raw)
        for bad_list in (None, {}, '[]', [valid] * 3001):
            with self.subTest(rows_type=type(bad_list).__name__), patch.object(self.project, 'save') as save:
                with self.assertRaises(ValueError):
                    self.project.merge_catalog(bad_list)
                save.assert_not_called()

    def test_save_failure_rolls_back_memory(self):
        before, raw = copy.deepcopy(self.project.data), self.project.path.read_bytes()
        with patch.object(self.project, 'save', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.project.merge_catalog([{'id': 133, 'name': 'Fireball', 'class': 'MAGE'}])
        self.assertEqual(self.project.data, before)
        self.assertEqual(self.project.path.read_bytes(), raw)

    def test_legacy_class_default_and_noop_import(self):
        self.assertEqual(self.project.merge_catalog([{'id': 635, 'name': 'Holy Light'}]), 1)
        self.assertEqual(self.project.data['catalog'][-1]['class'], 'PALADIN')
        with patch.object(self.project, 'save') as save:
            self.assertEqual(self.project.merge_catalog([]), 0)
            self.assertEqual(self.project.merge_catalog([{'id': 635, 'name': 'Holy Light'}]), 0)
            save.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
