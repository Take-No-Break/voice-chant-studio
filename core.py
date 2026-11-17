"""Voice Chant Studio: non-destructive project and atomic WoW export."""
from pathlib import Path
import copy, hashlib, json, os, shutil, tempfile, time, wave
import numpy as np
import soundfile as sf

EVENTS = {'start': '詠唱開始', 'success': '発動成功・瞬間技', 'cancel': '中断時'}
ADDON = 'VoiceChantStudio'
VOLUME_LEVELS = range(10, 100, 10)

def write_volume_variants(data, rate, directory):
    """Offline PCM gain variants let Lua change only this addon's voice volume."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for level in VOLUME_LEVELS:
        samples = np.asarray(data, dtype=np.float32) * (level / 100)
        digest = hashlib.sha256(samples.tobytes()+str(rate).encode()).hexdigest()[:20]
        filename = digest+'.wav'
        sf.write(str(directory/filename), samples, rate, subtype='PCM_16')
        paths[level] = 'Interface\\AddOns\\'+ADDON+'\\Audio\\'+filename
    return paths

def volume_lua(paths):
    return '{'+','.join('['+str(level)+']='+lua_string(path) for level,path in sorted(paths.items()))+'}'

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)

def load_audio(path):
    info = sf.info(str(path))
    if info.samplerate <= 0 or info.frames / info.samplerate > 600:
        raise ValueError('10分以下の音声を選んでください。')
    data, rate = sf.read(str(path), dtype='float32', always_2d=True)
    if not len(data) or rate <= 0:
        raise ValueError('音声が空です。')
    if len(data) / rate > 600:
        raise ValueError('10分以下の音声を選んでください。')
    if not np.all(np.isfinite(data)):
        raise ValueError('音声に無効なサンプルが含まれています。')
    return np.mean(data, axis=1), rate

def render_audio(data, rate, start, end, gain=1., normalize=False, fade_ms=8):
    if not np.isfinite(gain) or not 0 <= gain <= 2:
        raise ValueError('音量は0〜2の範囲にしてください。')
    if not (0 <= start < end <= len(data) / rate + 0.001):
        raise ValueError('開始位置は終了位置より前にしてください。')
    clip = np.asarray(data[int(start*rate):min(len(data), int(end*rate))], dtype=np.float32).copy()
    if len(clip) < max(1, int(rate*0.03)):
        raise ValueError('音声は30ミリ秒以上にしてください。')
    if normalize:
        peak = float(np.max(np.abs(clip)))
        if peak > 1e-7:
            clip *= 0.9 / peak
    clip *= float(gain)
    fade = min(int(rate*fade_ms/1000), len(clip)//2)
    if fade:
        ramp = np.linspace(0, 1, fade, dtype=np.float32)
        clip[:fade] *= ramp
        clip[-fade:] *= ramp[::-1]
    return np.clip(clip, -1, 1)

def lua_string(value):
    return '"' + ''.join(('\\\\' if c == '\\' else '\\"' if c == '"' else '\\n' if c == '\n' else '\\r' if c == '\r' else '\\%03d' % ord(c) if ord(c) < 32 else c) for c in str(value)) + '"'

class Project:
    def __init__(self, directory, catalog):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'project.json'
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('version') != 1:
                raise ValueError('このプロジェクト形式は読み込めません。')
            self.upgrade_catalog(catalog)
        else:
            self.data = {'version': 1, 'catalog': copy.deepcopy(catalog), 'clips': {}, 'options': {'gap': 0.2, 'stop_on_cancel': True}, 'game': ''}
            self.save()

    def upgrade_catalog(self, catalog):
        """Add bundled classes/ranks without renaming user clip keys or losing edits."""
        changed = False
        for row in catalog:
            existing = next((r for r in self.data['catalog'] if r.get('class') == row.get('class') and (r['key'] == row['key'] or set(r['ids']) & set(row['ids']))), None)
            if existing:
                for sid in row['ids']:
                    if sid not in existing['ids']:
                        existing['ids'].append(sid); changed = True
                for field in ['cast_seconds', 'name_ja', 'passive', 'channeled']:
                    if field in row and field not in existing:
                        existing[field] = row[field]; changed = True
            else:
                addition = copy.deepcopy(row)
                keys = {r['key'] for r in self.data['catalog']}
                if addition['key'] in keys:
                    stem = row.get('class', 'spell').lower() + '_' + addition['key']
                    addition['key'] = stem
                    suffix = 2
                    while addition['key'] in keys:
                        addition['key'] = stem + '_' + str(suffix); suffix += 1
                self.data['catalog'].append(addition); changed = True
        if changed:
            # Preserve the pre-upgrade project, including its recording assignments.
            backup = self.root / ('project-before-upgrade-' + str(time.time_ns()) + '.json')
            shutil.copy2(self.path, backup)
            self.save()

    def save(self):
        atomic_json(self.path, self.data)

    def asset(self, relative):
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError('プロジェクト外の音声パスです。')
        return p

    def add_audio(self, data, rate):
        folder = self.root / 'originals'
        folder.mkdir(exist_ok=True)
        # Original takes are immutable. Trimming never rewrites these files.
        name = 'take_' + str(time.time_ns()) + '.wav'
        sf.write(str(folder/name), data, int(rate), subtype='PCM_16')
        return 'originals/' + name

    def merge_catalog(self, rows):
        if not isinstance(rows, list) or len(rows) > 3000:
            raise ValueError('一覧の形式が正しくありません。')
        # Validate the entire import before changing either the project or disk.
        # Spellbook text can be hand-edited, so do not coerce arbitrary objects
        # or strings such as "false" into valid-looking spell metadata.
        validated = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('一覧の形式が正しくありません。')
            raw_id = row.get('id')
            if isinstance(raw_id, bool) or not isinstance(raw_id, (int, float, str)):
                raise ValueError('アビリティIDが正しくありません。')
            try:
                sid = int(raw_id)
            except (ValueError, TypeError, OverflowError):
                raise ValueError('アビリティIDが正しくありません。') from None
            if sid <= 0 or sid > 100000000 or (isinstance(raw_id, float) and raw_id != sid):
                raise ValueError('アビリティIDが正しくありません。')
            name = row.get('name')
            if not isinstance(name, str) or not name.strip():
                raise ValueError('アビリティ名が正しくありません。')
            name = name.strip()[:160]
            class_name = row.get('class', 'PALADIN')
            if not isinstance(class_name, str) or not (class_name.isascii() and class_name.isalpha() and class_name.isupper()):
                raise ValueError('クラス名はMAGEなどの英大文字で指定してください。')
            normalized = {'id': sid, 'name': name, 'class': class_name}
            for field in ('passive', 'channeled'):
                if field in row:
                    if not isinstance(row[field], bool):
                        raise ValueError('アビリティの種類が正しくありません。')
                    normalized[field] = row[field]
            if 'cast_seconds' in row:
                if isinstance(row['cast_seconds'], bool):
                    raise ValueError('詠唱時間が正しくありません。')
                try:
                    duration = float(row['cast_seconds'])
                except (TypeError, ValueError, OverflowError):
                    raise ValueError('詠唱時間が正しくありません。') from None
                if not np.isfinite(duration) or not 0 <= duration <= 600:
                    raise ValueError('詠唱時間は0〜600秒の範囲にしてください。')
                normalized['cast_seconds'] = duration
            validated.append(normalized)

        catalog = copy.deepcopy(self.data['catalog'])
        by_id = {(r.get('class', 'PALADIN'), sid): r for r in catalog for sid in r['ids']}
        by_name = {(r.get('class', 'PALADIN'), r['name']): r for r in catalog}
        # A localized learned rank identifies its existing English catalog group
        # by ID. Use that alias for other imported ranks regardless of row order.
        for row in validated:
            existing = by_id.get((row['class'], row['id']))
            if existing is not None:
                by_name.setdefault((row['class'], row['name']), existing)
        added = 0
        keys = {r['key'] for r in catalog}
        for row in validated:
            sid, name, class_name = row['id'], row['name'], row['class']
            existing = by_id.get((class_name, sid)) or by_name.get((class_name, name))
            if existing is not None:
                if sid not in existing['ids']:
                    existing['ids'].append(sid)
                for field in ('passive', 'cast_seconds', 'channeled'):
                    if field in row:
                        existing[field] = row[field]
            else:
                key = 'spell_' + str(sid)
                if key in keys:
                    stem = 'spell_' + class_name.lower() + '_' + str(sid)
                    key, suffix = stem, 2
                    while key in keys:
                        key = stem + '_' + str(suffix)
                        suffix += 1
                existing = {'key': key, 'ids': [sid], 'name': name, 'class': class_name,
                            'passive': row.get('passive', False),
                            'cast_seconds': row.get('cast_seconds', 0),
                            'channeled': row.get('channeled', False)}
                catalog.append(existing)
                keys.add(key)
                added += 1
            by_id[(class_name, sid)] = existing
            by_name.setdefault((class_name, name), existing)
        if catalog != self.data['catalog']:
            previous = self.data['catalog']
            self.data['catalog'] = catalog
            try:
                self.save()
            except Exception:
                self.data['catalog'] = previous
                raise
        return added

    def export(self, game_or_folder, template, game=True):
        destination = Path(game_or_folder)
        if game:
            if (destination/'_forever_'/'Wow.exe').is_file():
                destination /= '_forever_'
            if destination.name.lower() != '_forever_' or not (destination/'Wow.exe').is_file():
                raise ValueError('Wow.exe がある _forever_ フォルダを選んでください。')
            destination = destination/'Interface'/'AddOns'/ADDON
        else:
            destination = destination/ADDON
        if destination.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('書き出し先にプロジェクト内を指定できません。')
        destination.parent.mkdir(parents=True, exist_ok=True)
        prepared = Path(tempfile.mkdtemp(prefix='voicechant-', dir=str(destination.parent)))
        try:
            (prepared/'Audio').mkdir()
            bindings = []
            count = 0
            for row in self.data['catalog']:
                slots = [(e,e) for e in EVENTS]
                number = int(self.data.get('success_variations',{}).get(row['key'],1))
                if not 1 <= number <= 5: raise ValueError('Voice variation count must be 1 to 5.')
                slots += [('success','success:'+str(i)) for i in range(2,number+1)]
                for event, slot in slots:
                    clip = self.data['clips'].get(row['key']+':'+slot)
                    if not clip or not clip.get('ready', True):
                        continue
                    data, rate = load_audio(self.asset(clip['source']))
                    rendered = render_audio(data, rate, clip['start'], clip['end'], clip.get('gain', 1), clip.get('normalize', False))
                    # Content addressed names avoid changing a sound WoW already has cached.
                    digest = hashlib.sha256(rendered.tobytes()+str(rate).encode()).hexdigest()[:20]
                    filename = digest+'.wav'
                    sf.write(str(prepared/'Audio'/filename), rendered, rate, subtype='PCM_16')
                    path = 'Interface\\AddOns\\'+ADDON+'\\Audio\\'+filename
                    volumes = write_volume_variants(rendered, rate, prepared/'Audio')
                    bindings.append('  {ids={'+','.join(str(int(i)) for i in row['ids'])+'}, class='+lua_string(row.get('class','PALADIN'))+', name='+lua_string(row['name'])+', event='+lua_string(event)+', file='+lua_string(path)+', volumes='+volume_lua(volumes)+'},')
                    count += 1
            for f in Path(template).iterdir():
                if f.is_file() and f.suffix in ('.lua', '.toc') and f.name != 'Config.lua':
                    shutil.copy2(f, prepared/f.name)
            catalog_lua = 'VoiceChantCatalog = {\n' + '\n'.join('  {id='+str(int(i))+', class='+lua_string(r.get('class','PALADIN'))+', name='+lua_string(r['name'])+'},' for r in self.data['catalog'] for i in r['ids']) + '\n}\n'
            (prepared/'Catalog.lua').write_text(catalog_lua, encoding='utf-8')
            opts = self.data.get('options', {})
            config = 'VoiceChantConfig = {gap='+str(float(opts.get('gap', .2)))+', stopOnCancel='+('true' if opts.get('stop_on_cancel', True) else 'false')+', bindings={\n'+'\n'.join(bindings)+'\n}}\n'
            (prepared/'Config.lua').write_text(config, encoding='utf-8')
            destination.mkdir(exist_ok=True)
            if (destination/'Config.lua').exists():
                backup = self.root/'export-backups'/str(time.time_ns())
                backup.mkdir(parents=True)
                shutil.copy2(destination/'Config.lua', backup/'Config.lua')
            (destination/'Audio').mkdir(exist_ok=True)
            for f in (prepared/'Audio').iterdir():
                os.replace(f, destination/'Audio'/f.name)
            # Commit config last; previous audio is retained so a running game is safe.
            for f in prepared.iterdir():
                if f.is_file() and f.name != 'Config.lua':
                    os.replace(f, destination/f.name)
            os.replace(prepared/'Config.lua', destination/'Config.lua')
            return destination, count
        finally:
            shutil.rmtree(prepared)
