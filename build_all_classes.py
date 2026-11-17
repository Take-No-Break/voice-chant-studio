"""Add local Forever/Camelot trainer, prerequisite, quest and selected talent spells."""
from pathlib import Path
import concurrent.futures,copy,hashlib,html,json,re
from build_forever_catalog import BASE,SOURCE,tooltip,atomic_json

EXTRA={
 'DRUID':{5176:'Wrath',5185:'Healing Touch',1126:'Mark of the Wild',17116:"Nature's Swiftness",18562:'Swiftmend',16979:'Feral Charge (Bear)',24858:'Moonkin Form'},
 'HUNTER':{75:'Auto Shot',2973:'Raptor Strike',19434:'Aimed Shot',19503:'Scatter Shot',19577:'Intimidation',19574:'Bestial Wrath',19263:'Deterrence',23989:'Readiness'},
 'ROGUE':{1752:'Sinister Strike',2098:'Eviscerate',14177:'Cold Blood',14185:'Preparation',14183:'Premeditation',13750:'Adrenaline Rush',13877:'Blade Flurry',16511:'Hemorrhage',14278:'Ghostly Strike'},
 'SHAMAN':{403:'Lightning Bolt',331:'Healing Wave',8017:'Rockbiter Weapon',16166:'Lightning Mastery',16188:"Nature's Swiftness",17364:'Stormstrike',16190:'Mana Tide Totem'},
 'WARLOCK':{686:'Shadow Bolt',687:'Demon Skin',688:'Summon Imp',18288:'Amplify Curse',18708:'Fel Domination',18220:'Dark Pact',17962:'Conflagrate',17877:'Shadowburn',18265:'Siphon Life'},
 'WARRIOR':{6603:'Attack',78:'Heroic Strike',2457:'Battle Stance',12975:'Last Stand',12328:'Death Wish',12292:'Sweeping Strikes',12809:'Concussion Blow',12323:'Piercing Howl'},
 'MAGE':{11129:'Combustion'},'PALADIN':{},'PRIEST':{}}

def main():
    original=json.loads((BASE/'assets/catalog.json').read_text(encoding='utf8'))
    rows=[copy.deepcopy(r) for r in original if not r.get('condition')]
    quest=(SOURCE/'QuestSpells.lua').read_text(encoding='utf8')
    needed={};sources={}
    for token,extra in EXTRA.items():
        path=SOURCE/(token.title()+'.lua'); text=path.read_text(encoding='utf8')
        assert 'forClass("'+token+'")' in text
        ids=set(map(int,re.findall(r'(?:\bid\s*=|\brequiredTalentId\s*=)\s*(\d+)',text)))
        for group in re.findall(r'requiredIds\s*=\s*{([^}]+)}',text):ids.update(map(int,re.findall(r'\d+',group)))
        for group in re.findall(r'local\s+\w+\s*=\s*{([\d,\s]+)}',text):ids.update(map(int,re.findall(r'\d+',group)))
        block=re.search(r'\n    '+token+r' = \{(.*?)(?=\n    [A-Z]+ =|\n})',quest,re.S)
        if block:ids.update(map(int,re.findall(r'^        \[(\d+)\]',block[1],re.M)))
        ids.update(extra);needed[token]=ids
        sources[token]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'requested_ids':sorted(ids)}
    ids=set.union(*needed.values())
    with concurrent.futures.ThreadPoolExecutor(16) as pool:results=dict(pool.map(tooltip,sorted(ids)))
    failures=[];skipped=[]
    for token,ids in needed.items():
        for sid in sorted(ids):
            item=results[sid]
            if not item.get('name'):failures.append({'class':token,'id':sid,'error':item});continue
            if sid in EXTRA[token] and item['name']!=EXTRA[token][sid]:skipped.append({'class':token,'id':sid,'expected':EXTRA[token][sid],'actual':item['name']});continue
            existing=next((r for r in rows if r['class']==token and (sid in r['ids'] or r['name']==item['name'])),None)
            if existing:
                if sid not in existing['ids']:existing['ids'].append(sid)
                continue
            text=html.unescape(re.sub('<[^>]+>',' ',item['tooltip']))
            cast=re.search(r'(\d+(?:\.\d+)?)\s+sec cast',text)
            rows.append({'key':token.lower()+'_'+str(sid),'class':token,'name':item['name'],'ids':[sid],
                         'cast_seconds':float(cast[1]) if cast else 0,'passive':bool(re.search(r'\bPassive\b',text)),
                         'channeled':bool(re.search(r'\bChanneled\b',text))})
    if failures:
        atomic_json(BASE/'all-classes-errors.json',failures)
        print('Unavailable Forever IDs excluded and recorded:',len(failures))
    for row in rows:row['ids']=sorted(set(row['ids']))
    for old in original:
        if old.get('condition'):continue
        updated=next(r for r in rows if r['key']==old['key'])
        assert all(updated[k]==v for k,v in old.items() if k!='ids')
    atomic_json(BASE/'assets/catalog.json',rows)
    report={'sources':sources,'classes':{c:{'abilities':sum(r['class']==c for r in rows),'rank_ids':sum(len(r['ids']) for r in rows if r['class']==c)} for c in EXTRA},'unresolved':failures,'skipped_name_mismatch':skipped,
            'scope':'All IDs in installed Forever trainer/prerequisite/local rank groups and class quests, plus name-verified selected unranked talents. Not a guarantee of all future/item/pet/talent spells. Import the actual client spellbook for learned and build-specific skills.'}
    atomic_json(BASE/'all-classes-report.json',report)
    print(json.dumps(report['classes']), 'skipped:',skipped)
if __name__=='__main__':main()
