"""Offline spell icons for the desktop editor; no network or microphone access."""
from pathlib import Path
import json
import tkinter as tk


class SpellIcons:
    def __init__(self, master, directory):
        self.master = master
        self.directory = Path(directory).resolve()
        self.cache = {}
        try:
            self.index = json.loads((self.directory / 'index.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.index = {}
        self.fallback = self._load(self.index.get('fallback', 'fallback.png'))
        if self.fallback is None:
            self.fallback = tk.PhotoImage(master=master, width=24, height=24)
            self.fallback.put('#314b59', to=(0, 0, 24, 24))
            self.fallback.put('#70c7b4', to=(6, 6, 18, 18))

    def _load(self, filename):
        if not filename or not isinstance(filename, str):
            return None
        if filename in self.cache:
            return self.cache[filename]
        path = (self.directory / filename).resolve()
        if not path.is_relative_to(self.directory):
            return None
        try:
            picture = tk.PhotoImage(master=self.master, file=str(path))
            if picture.width() != 24 or picture.height() != 24:
                return None
        except (OSError, tk.TclError):
            return None
        self.cache[filename] = picture
        return picture

    def for_row(self, row):
        # IDs also cover old projects with custom keys and newly imported ranks.
        candidates = [self.index.get('rows', {}).get(row.get('key'), {})]
        candidates.extend(self.index.get('spells', {}).get(str(sid), {}) for sid in row.get('ids', []))
        for record in candidates:
            picture = self._load(record.get('file')) if isinstance(record, dict) else None
            if picture is not None:
                return picture
        return self.fallback
