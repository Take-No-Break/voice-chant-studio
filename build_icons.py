"""Bundle real WoW spell icons; the desktop UI needs only Tk's native PNG support.

Icon names come from the Forever-specific Wowhead tooltip, never a guessed
spell-name mapping. Existing trainer/catalog caches are preferred. This tool
does not modify the catalog, projects, game installation, or runtime dependencies.
Pillow is a build-time dependency only. Re-run after extending the catalog.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent
TOOLTIP = 'https://nether.wowhead.com/forever/tooltip/spell/{id}'
CDN = 'https://wow.zamimg.com/images/wow/icons/large/{icon}.jpg'
USER_AGENT = 'VoiceChantStudio-icons-build/0.3'
ICON_NAME = re.compile(r'^[a-z0-9_]+$')


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    temporary.replace(path)


def fetch_bytes(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        value = response.read(5_000_001)
    if len(value) > 5_000_000:
        raise ValueError('Unexpectedly large icon response')
    return value


def valid_tooltip(item):
    return (isinstance(item, dict) and isinstance(item.get('name'), str)
            and isinstance(item.get('icon'), str)
            and ICON_NAME.fullmatch(item['icon'].lower()))


def load_tooltip(spell_id, cache_folders, fresh_cache, offline=False):
    errors = []
    for directory in cache_folders:
        path = directory / f'{spell_id}.json'
        if not path.is_file():
            continue
        try:
            item = json.loads(path.read_text(encoding='utf8'))
            if valid_tooltip(item):
                return item, path.relative_to(BASE).as_posix()
            errors.append('Cached tooltip has no valid icon')
        except (OSError, ValueError) as error:
            errors.append(str(error))
    if offline:
        raise ValueError('; '.join(errors) or 'No cached Forever tooltip')
    item = json.loads(fetch_bytes(TOOLTIP.format(id=spell_id)).decode('utf8'))
    if not valid_tooltip(item):
        raise ValueError('Forever tooltip has no valid name/icon')
    path = fresh_cache / f'{spell_id}.json'
    atomic_json(path, item)
    return item, path.relative_to(BASE).as_posix()


def thumbnail(icon, output, source_cache, size, offline=False):
    if not ICON_NAME.fullmatch(icon):
        raise ValueError('Unsafe icon name')
    source = source_cache / (icon + '.jpg')
    url = CDN.format(icon=icon)
    if source.is_file():
        raw = source.read_bytes()
    elif offline:
        raise ValueError('Icon image has not been downloaded')
    else:
        raw = fetch_bytes(url)
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        if image.format not in ('JPEG', 'PNG') or image.width < 24 or image.height < 24:
            raise ValueError('CDN response is not a usable icon image')
        if image.width != image.height:
            raise ValueError('Icon is not square')
        width, height = image.size
        rendered = image.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    # Never save an HTML error response as an image cache entry.
    if not source.exists():
        source.write_bytes(raw)
    filename = icon + '.png'
    path = output / filename
    rendered.save(path, format='PNG', optimize=True)
    with Image.open(path) as checked:
        checked.verify()
    return {'file': filename, 'source_url': url,
            'source_dimensions': [width, height],
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def fallback(output, size):
    image = Image.new('RGBA', (size, size), '#647580')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size-1, size-1), radius=3, outline='#b3bfc6', width=1)
    # Neutral, purpose-made placeholder, deliberately not a guessed ability icon.
    middle = size // 2
    draw.ellipse((middle-3, middle-6, middle+3, middle), outline='#f3f5f6', width=2)
    draw.line((middle+2, middle-1, middle, middle+3), fill='#f3f5f6', width=2)
    draw.rectangle((middle-1, middle+5, middle+1, middle+7), fill='#f3f5f6')
    image.save(output / 'fallback.png', format='PNG')


def build(catalog_path, size=24, offline=False):
    catalog = json.loads(catalog_path.read_text(encoding='utf8'))
    output = BASE / 'assets/icons'
    output.mkdir(parents=True, exist_ok=True)
    source_cache = BASE / 'icon-source-cache'
    source_cache.mkdir(exist_ok=True)
    fresh_cache = BASE / 'tooltip-cache-icons'
    fresh_cache.mkdir(exist_ok=True)
    cache_folders = sorted(BASE.glob('tooltip-cache*'))
    spell_ids = sorted({int(sid) for row in catalog for sid in row['ids']})
    spells = {}
    unresolved = []

    def metadata(spell_id):
        try:
            item, cache_path = load_tooltip(spell_id, cache_folders, fresh_cache, offline)
            return spell_id, item, cache_path, None
        except Exception as error:
            return spell_id, None, None, str(error)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(metadata, spell_ids))
    for spell_id, item, cache_path, error in results:
        if error:
            unresolved.append({'spell_id': spell_id, 'stage': 'tooltip', 'error': error})
            continue
        spells[str(spell_id)] = {'icon': item['icon'].lower(), 'name': item['name'],
                                 'tooltip_url': TOOLTIP.format(id=spell_id),
                                 'metadata_cache': cache_path}

    icon_names = sorted({item['icon'] for item in spells.values()})
    icons = {}

    def download(icon):
        try:
            return icon, thumbnail(icon, output, source_cache, size, offline), None
        except Exception as error:
            return icon, None, str(error)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        downloaded = list(executor.map(download, icon_names))
    for icon, information, error in downloaded:
        if error:
            unresolved.append({'icon': icon, 'stage': 'image', 'error': error})
        else:
            icons[icon] = information
    for item in spells.values():
        item['file'] = icons.get(item['icon'], {}).get('file', 'fallback.png')

    row_icons = {}
    missing_rows = []
    for row in catalog:
        # Prefer the first catalog rank whose Forever tooltip identifies this
        # exact ability; rank IDs can otherwise silently refer to another spell.
        candidates = [(sid, spells.get(str(sid))) for sid in row['ids']]
        matching = [(sid, item) for sid, item in candidates
                    if item and item['name'].casefold() == row['name'].casefold()
                    and item['file'] != 'fallback.png']
        if matching:
            sid, item = matching[0]
            row_icons[row['key']] = {'spell_id': sid, 'icon': item['icon'], 'file': item['file']}
        else:
            row_icons[row['key']] = {'file': 'fallback.png'}
            missing_rows.append({'key': row['key'], 'name': row['name'], 'ids': row['ids'],
                                 'reason': 'No matching Forever tooltip with a downloaded icon'})
    fallback(output, size)
    index = {'version': 1, 'size': size, 'fallback': 'fallback.png',
             'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'catalog_sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
             'rows': row_icons, 'spells': spells, 'icons': icons, 'missing': missing_rows,
             'provenance': {'spell_metadata': TOOLTIP, 'icon_images': CDN,
                            'mapping': 'Forever tooltip icon field; exact English ability name checked for row icons',
                            'local_sources': 'Existing tooltip-cache* directories (Forever-specific). Local trainer addon files contain spell IDs, not icon metadata.',
                            'fallback': 'Original neutral placeholder generated by this build tool'}}
    report = {'catalog_rows': len(catalog), 'spell_ids': len(spell_ids),
              'resolved_spell_ids': len(spells), 'unique_icons': len(icons),
              'rows_with_real_icons': len(catalog) - len(missing_rows),
              'missing_rows': missing_rows, 'unresolved': unresolved,
              'class_counts': dict(sorted(__import__('collections').Counter(r['class'] for r in catalog).items()))}
    atomic_json(output / 'index.json', index)
    atomic_json(output / 'missing.json', report)
    # Check every bundled file and every mapping before declaring success.
    for item in list(icons.values()) + [{'file': 'fallback.png'}]:
        with Image.open(output / item['file']) as image:
            image.load()
            assert image.format == 'PNG' and image.size == (size, size), item
    for row in catalog:
        assert (output / row_icons[row['key']]['file']).is_file(), row['key']
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=BASE / 'assets/catalog.json')
    parser.add_argument('--size', type=int, choices=(24, 28), default=24)
    parser.add_argument('--offline', action='store_true', help='Require all tooltip/image caches already present')
    args = parser.parse_args()
    build(args.catalog, args.size, args.offline)
