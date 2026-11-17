"""Add Forever Priest and quest spells without replacing existing editor keys."""
from pathlib import Path
import concurrent.futures
import datetime
import hashlib
import html
import json
import re
import urllib.request

BASE = Path(__file__).resolve().parent
SOURCE = Path(r'C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns\WhatsTraining\Classes\Camelot')
ENDPOINT = 'https://nether.wowhead.com/forever/tooltip/spell/{}'
EXTRAS = {2050: 'Lesser Heal', 585: 'Smite', 1243: 'Power Word: Fortitude',
          14751: 'Inner Focus', 10060: 'Power Infusion', 15487: 'Silence',
          15286: 'Vampiric Embrace', 15473: 'Shadowform'}
JA = {'Lesser Heal':'レッサー・ヒール','Smite':'スマイト','Flash Heal':'フラッシュ・ヒール',
      'Holy Fire':'ホーリー・ファイア','Holy Nova':'ホーリー・ノヴァ',
      'Heal':'ヒール','Greater Heal':'グレーター・ヒール','Renew':'リニュー',
      'Prayer of Healing':'プレイヤー・オブ・ヒーリング','Resurrection':'リザレクション',
      'Power Word: Shield':'パワー・ワード：シールド','Power Word: Fortitude':'パワー・ワード：フォーティチュード',
      'Prayer of Fortitude':'プレイヤー・オブ・フォーティチュード','Divine Spirit':'ディヴァイン・スピリット',
      'Prayer of Spirit':'プレイヤー・オブ・スピリット','Inner Fire':'インナー・ファイア',
      'Inner Focus':'インナー・フォーカス','Power Infusion':'パワー・インフュージョン',
      'Shadow Word: Pain':'シャドウ・ワード：ペイン','Mind Blast':'マインド・ブラスト',
      'Mind Flay':'マインド・フレイ','Mind Control':'マインド・コントロール',
      'Mind Soothe':'マインド・スーズ','Mind Vision':'マインド・ヴィジョン',
      'Psychic Scream':'サイキック・スクリーム','Fade':'フェード','Silence':'サイレンス',
      'Shadowform':'シャドウフォーム','Vampiric Embrace':'ヴァンピリック・エンブレイス',
      'Shadow Protection':'シャドウ・プロテクション','Prayer of Shadow Protection':'プレイヤー・オブ・シャドウ・プロテクション',
      'Dispel Magic':'ディスペル・マジック','Cure Disease':'キュア・ディジーズ','Abolish Disease':'アボリッシュ・ディジーズ',
      'Mana Burn':'マナ・バーン','Shackle Undead':'シャックル・アンデッド','Levitate':'レヴィテート',
      'Desperate Prayer':'デスパレート・プレイヤー','Feedback':'フィードバック','Starshards':'スターシャード',
      "Elune's Grace":'エルーンの加護','Touch of Weakness':'タッチ・オブ・ウィークネス',
      'Hex of Weakness':'ヘックス・オブ・ウィークネス','Shadowguard':'シャドウガード',
      'Divine Grace':'ディヴァイン・グレイス','Chastise':'チャスタイズ','Dark Sacrifice':'ダーク・サクリファイス',
      'Confounding Flash':'コンファウンディング・フラッシュ','Contingency Plan':'コンティンジェンシー・プラン',
      'Polymorph':'ポリモーフ','Conjure Water':'飲料作成'}

def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    temp.replace(path)

def tooltip(sid):
    folders = ['tooltip-cache-priest','tooltip-cache-forever','tooltip-cache-icons','tooltip-cache-mage','tooltip-cache']
    for folder in folders:
        path = BASE / folder / f'{sid}.json'
        if path.is_file():
            item = json.loads(path.read_text(encoding='utf8'))
            if item.get('name') and item.get('tooltip') and item.get('icon'):
                return sid, item
    errors = []
    for _ in range(2):
        try:
            request = urllib.request.Request(ENDPOINT.format(sid), headers={'User-Agent':'VoiceChantStudio-catalog/0.3'})
            with urllib.request.urlopen(request, timeout=15) as response:
                item = json.load(response)
            if not all(item.get(field) for field in ['name','tooltip','icon']):
                raise ValueError('Missing Forever tooltip fields')
            folder = BASE / 'tooltip-cache-forever'
            folder.mkdir(exist_ok=True)
            atomic_json(folder / f'{sid}.json', item)
            return sid, item
        except Exception as error:
            errors.append(str(error))
    return sid, {'error':errors}

def main():
    priest_file = SOURCE / 'Priest.lua'
    priest_source = priest_file.read_text(encoding='utf8')
    assert 'forClass("PRIEST")' in priest_source
    trainer = set(map(int, re.findall(r'(?:\bid\s*=|\brequiredTalentId\s*=)\s*(\d+)', priest_source)))
    for group in re.findall(r'requiredIds\s*=\s*{([^}]+)}', priest_source):
        trainer.update(map(int, re.findall(r'\d+', group)))
    quests_file = SOURCE / 'QuestSpells.lua'
    quest_source = quests_file.read_text(encoding='utf8')
    quest_ids = {}
    for token in ['PRIEST','MAGE']:
        block = re.search(r'\n    '+token+r' = \{(.*?)(?=\n    [A-Z]+ =|\n})', quest_source, re.S).group(1)
        quest_ids[token] = set(map(int, re.findall(r'^        \[(\d+)\]', block, re.M)))
    wanted = trainer | quest_ids['PRIEST'] | set(EXTRAS) | quest_ids['MAGE']
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = dict(pool.map(tooltip, sorted(wanted)))
    errors = {str(sid): item for sid, item in results.items() if not item.get('name')}
    assert not errors, errors
    for sid, expected in EXTRAS.items():
        assert results[sid]['name'] == expected, (sid, expected, results[sid]['name'])
    catalog_file = BASE / 'assets/catalog.json'
    original = json.loads(catalog_file.read_text(encoding='utf8'))
    catalog = json.loads(json.dumps(original))
    added = []
    for token, ids in [('PRIEST', wanted - quest_ids['MAGE']), ('MAGE', quest_ids['MAGE'])]:
        for sid in sorted(ids):
            item = results[sid]
            text = html.unescape(re.sub('<[^>]+>', ' ', item['tooltip']))
            match = re.search(r'(\d+(?:\.\d+)?)\s+sec cast', text)
            cast = float(match.group(1)) if match else 0.0
            row = next((r for r in catalog if r['class'] == token and r['name'] == item['name']), None)
            if row is None:
                row = {'key':token.lower()+'_'+str(sid), 'class':token, 'name':item['name'],
                       'name_ja':JA.get(item['name'],item['name']), 'ids':[], 'cast_seconds':cast,
                       'passive': bool(re.search(r'\bPassive\b', text)), 'channeled': bool(re.search(r'\bChanneled\b', text))}
                catalog.append(row)
                added.append(row['key'])
            if sid not in row['ids']:
                row['ids'].append(sid)
                row['ids'].sort()
            if row['key'] in added:
                row['cast_seconds'] = max(row['cast_seconds'], cast)
                row['channeled'] = row['channeled'] or bool(re.search(r'\bChanneled\b',text))
    for old in original:
        new = next(r for r in catalog if r['key'] == old['key'])
        assert all(new[k] == v for k,v in old.items() if k != 'ids')
        assert set(old['ids']) <= set(new['ids'])
    assert len({r['key'] for r in catalog}) == len(catalog)
    for token in ['PALADIN','MAGE','PRIEST']:
        ids = [sid for r in catalog if r['class'] == token for sid in r['ids']]
        assert len(ids) == len(set(ids)), (token,'Duplicate IDs')
    atomic_json(catalog_file,catalog)
    report = {'version':'0.3.0','built_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sources':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in [priest_file,quests_file,SOURCE/'Mage.lua']],
              'tooltip_endpoint':ENDPOINT,'priest_trainer_and_prerequisite_ids':sorted(trainer),
              'quest_ids':{c:sorted(ids) for c,ids in quest_ids.items()},
              'verified_starting_and_unranked_active_ids':{str(sid):name for sid,name in EXTRAS.items()},
              'classes':{c:{'abilities':sum(r['class']==c for r in catalog),'rank_ids':sum(len(r['ids']) for r in catalog if r['class']==c)} for c in ['PALADIN','MAGE','PRIEST']},
              'new_rows':added,'unresolved_ids':[],
              'spells':{str(sid):{'name':item['name'],'icon':item['icon'],'url':ENDPOINT.format(sid)} for sid,item in results.items()},
              'limits':['Includes unlearned and race-specific abilities; not the current character spellbook.',
                        'Does not promise every future, item-granted, talent-passive or build-specific spell.',
                        'Starting and unranked active talent IDs are name-checked against Forever tooltips; full passive talent tree is not included.',
                        'Use /voicechant import for actual client spells. Existing Paladin catalog retained; Mage trainer data audited separately in MAGE-CATALOG.md.']}
    atomic_json(BASE/'forever-catalog-report.json', report)
    (BASE/'FOREVER-CATALOG.md').write_text('''# WoW Forever catalog, v0.3

The catalog uses the installed **WhatsTraining/Classes/Camelot** data loaded for the Forever client, not its Vanilla or TBC class tables. The local Priest file explicitly checks `forClass("PRIEST")`.

- Priest: every trainer ID, prerequisite rank, required talent root, starting spells, all 12 Priest entries in Camelot/QuestSpells.lua, plus name-checked unranked active talents (Inner Focus, Power Infusion, Silence, Vampiric Embrace and Shadowform).
- Mage: existing 55 entries and keys retained; added quest-granted Polymorph (Pig, 28272) and Conjure Water rank 7 (10140). Existing trainer evidence is in MAGE-CATALOG.md.
- Paladin: existing entries and keys retained.
- Names, cast times and icon names use `https://nether.wowhead.com/forever/tooltip/spell/{ID}`. No character, account, or recording data is sent.

Lesser Heal, Smite, Flash Heal, Holy Fire and Holy Nova are **PRIEST**, as confirmed by the Forever class table and the Forever tooltips. The app now includes this class; they are not added as Mage spells.

The JSON report records exact local source hashes, IDs and per-spell source URLs. Japanese names are descriptive labels, not official localization. Icons are fetched by the tooltip's icon name, bundled for offline display, with sources in Icon-Sources.json.

This starter catalog includes unlearned, talented and race-specific abilities; it does not mean your current character knows them. Passive talent trees and every future/item/build-specific spell are not guaranteed. Import `/voicechant` from the actual client to add your own current spells. Unknown imported IDs have a fallback icon.

Rebuild with `python build_forever_catalog.py`, then `python build_icons.py`. Existing editor row keys/metadata remain intact and rank IDs are added. The builder never opens user projects or writes to the game installation.
''',encoding='utf8')
    print(json.dumps(report['classes']), 'unresolved:',errors)

if __name__ == '__main__':
    main()
