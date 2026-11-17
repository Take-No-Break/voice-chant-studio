"""Rebuild MAGE facts from installed Forever trainer data and provider spell tooltips.
Does not execute addon code or alter Paladin entries. Run from this script's folder.
"""
from pathlib import Path
import concurrent.futures, datetime, html, json, re, urllib.request

BASE = Path(__file__).resolve().parent
SOURCE = Path(r'C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns\WhatsTraining\Classes\Camelot\Mage.lua')
CACHE = BASE/'tooltip-cache-mage'
CACHE.mkdir(exist_ok=True)
CATALOG = BASE/'assets/catalog.json'
# Starting spells plus active talents that do not have trainer upgrades.
# All are resolved against the Forever tooltip endpoint; expected names prevent stale ID assumptions.
EXTRA = {133:'Fireball',168:'Frost Armor',12042:'Arcane Power',12043:'Presence of Mind',11958:'Ice Block',12472:'Cold Snap'}
JA = {
 'Arcane Wrath':'アーケイン・ラス', 'Comprehend Scroll':'巻物解読', 'Amplify Magic':'魔法増幅', 'Arcane Blast':'アーケイン・ブラスト', 'Arcane Explosion':'アーケイン・エクスプロージョン',
 'Arcane Intellect':'アーケイン・インテレクト', 'Arcane Missiles':'アーケイン・ミサイル', 'Arcane Power':'アーケイン・パワー',
 'Blast Wave':'ブラスト・ウェーブ', 'Blink':'ブリンク', 'Blizzard':'ブリザード', 'Cold Snap':'コールド・スナップ',
 'Cone of Cold':'コーン・オブ・コールド', 'Conjure Food':'食料作成', 'Conjure Water':'飲料作成',
 'Conjure Mana Agate':'マナ・アゲート作成', 'Conjure Mana Jade':'マナ・ジェイド作成', 'Conjure Mana Citrine':'マナ・シトリン作成',
 'Conjure Mana Ruby':'マナ・ルビー作成', 'Counterspell':'カウンタースペル', 'Dampen Magic':'魔法抑制',
 'Evocation':'イヴォケーション', 'Fire Blast':'ファイア・ブラスト', 'Fire Ward':'炎の結界', 'Fireball':'ファイアボール',
 'Flamestrike':'フレイムストライク', 'Frost Armor':'フロスト・アーマー', 'Frost Nova':'フロスト・ノヴァ',
 'Frost Ward':'氷の結界', 'Frostbolt':'フロストボルト', 'Ice Armor':'アイス・アーマー', 'Ice Barrier':'アイス・バリア',
 'Ice Block':'アイス・ブロック', 'Mage Armor':'メイジ・アーマー', 'Mana Shield':'マナ・シールド',
 'Polymorph':'ポリモーフ', 'Presence of Mind':'プレゼンス・オブ・マインド', 'Pyroblast':'パイロブラスト',
 'Remove Lesser Curse':'解呪', 'Scorch':'スコーチ', 'Slow Fall':'スローフォール', 'Arcane Surge':'アーケイン・サージ',
 'Frostfire Bolt':'フロストファイア・ボルト', 'Ice Lance':'アイス・ランス', 'Living Bomb':'リビング・ボム',
 'Spellfrost Bolt':'スペルフロスト・ボルト', 'Time Warp':'タイム・ワープ', 'Icy Veins':'アイシー・ヴェインズ',
}
CITIES={'Stormwind':'ストームウィンド','Ironforge':'アイアンフォージ','Darnassus':'ダーナサス','Orgrimmar':'オーグリマー','Undercity':'アンダーシティ','Thunder Bluff':'サンダー・ブラフ'}

def fetch(sid):
    path=CACHE/f'{sid}.json'
    try:
        if path.exists(): item=json.loads(path.read_text(encoding='utf-8'))
        else:
            request=urllib.request.Request(f'https://nether.wowhead.com/forever/tooltip/spell/{sid}',headers={'User-Agent':'VoiceChantStudio-catalog-build/0.2'})
            with urllib.request.urlopen(request,timeout=20) as response:item=json.load(response)
            path.write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
        return sid,item
    except Exception as error:return sid,{'error':str(error)}

source=SOURCE.read_text(encoding='utf-8')
ids=set(map(int,re.findall(r'(?:\bid\s*=|\brequiredTalentId\s*=)\s*(\d+)',source)))
for group in re.findall(r'requiredIds\s*=\s*{([^}]+)}',source):ids.update(map(int,re.findall(r'\d+',group)))
ids.update(EXTRA)
original=json.loads(CATALOG.read_text(encoding='utf-8'))
paladin=[r for r in original if r.get('class')=='PALADIN']
groups={};errors=[];skipped_extras=[]
for sid,item in concurrent.futures.ThreadPoolExecutor(8).map(fetch,sorted(ids)):
    name=item.get('name')
    if not name:errors.append({'id':sid,'error':item.get('error','No tooltip name')});continue
    if sid in EXTRA and name!=EXTRA[sid]:skipped_extras.append({'id':sid,'expected':EXTRA[sid],'actual':name});continue
    tooltip=item.get('tooltip','')
    text=html.unescape(re.sub('<[^>]+>',' ',tooltip))
    passive=bool(re.search(r'\bPassive\b',text))
    match=re.search(r'(\d+(?:\.\d+)?)\s+sec cast',text)
    cast=float(match[1]) if match else 0.0
    channel=bool(re.search(r'\bChanneled\b',text))
    group=groups.setdefault(name,{'name':name,'class':'MAGE','ids':[],'passive':passive,'cast_seconds':cast,'channeled':channel})
    group['ids'].append(sid)
    # A positive cast duration on any rank makes start the natural default.
    group['cast_seconds']=max(group['cast_seconds'],cast)
    group['passive']=group['passive'] and passive
    group['channeled']=group['channeled'] or channel

mage=[]
for name,row in sorted(groups.items()):
    row['ids']=sorted(set(row['ids']));row['key']='mage_'+str(min(row['ids']))
    if name in JA:row['name_ja']=JA[name]
    elif name.startswith('Teleport: '):row['name_ja']='テレポート：'+CITIES.get(name[10:],name[10:])
    elif name.startswith('Portal: '):row['name_ja']='ポータル：'+CITIES.get(name[8:],name[8:])
    mage.append(row)

all_rows=[r for r in original if r.get('class')!='MAGE']+mage
seen={};keys=set()
for row in all_rows:
    assert row['key'] not in keys,row['key'];keys.add(row['key'])
    assert len(row['ids'])==len(set(row['ids'])),row['name']
    for sid in row['ids']:
        key=(row['class'],sid)
        assert key not in seen,(key,seen.get(key),row['name'])
        seen[key]=row['name']
assert [r for r in all_rows if r.get('class')=='PALADIN']==paladin,'Paladin data changed'
assert not errors,errors
CATALOG.write_text(json.dumps(all_rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report={'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':str(SOURCE),'tooltip_url_pattern':'https://nether.wowhead.com/forever/tooltip/spell/{id}',
 'mage_abilities':len(mage),'mage_rank_ids':sum(len(r['ids']) for r in mage),'mage_passives':sum(r['passive'] for r in mage),'mage_japanese_labels':sum('name_ja' in r for r in mage),
 'paladin_abilities_preserved':len(paladin),'fetch_errors':errors,'skipped_extra_ids':skipped_extras,
 'scope':'Initial trainer/rank-prerequisite snapshot plus tooltip-verified starting spells and selected active talents; learned spellbook and current-level candidates/talent imports in game remain authoritative. Japanese labels are descriptive translations, not an official Japanese WoW localization.'}
(BASE/'mage-catalog-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
print('\nMage names:',', '.join(r['name'] for r in mage))
