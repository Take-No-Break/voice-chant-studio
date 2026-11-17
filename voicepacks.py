"""Portable, data-only voice packs. Never extract arbitrary ZIP paths or run code."""
from pathlib import Path
import copy,datetime,hashlib,json,os,re,shutil,tempfile,time,zipfile
import numpy as np
import soundfile as sf
from core import EVENTS,load_audio,render_audio,atomic_json
from effects import settings as effect_settings,LIMITS

FORMAT='voice-chant-studio-pack'
MAX_TOTAL=512*1024*1024
MAX_FILE=128*1024*1024
MAX_MANIFEST=8*1024*1024
MAX_MEMBERS=6001
AUDIO_NAME=re.compile(r'^audio/[0-9a-f]{64}\.wav$')

def _number(value,low,high):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not low<=value<=high:
        raise ValueError('Invalid numeric value in voice pack')
    return value
def _text(value,limit=200):
    if not isinstance(value,str) or not value or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError('Invalid text in voice pack')
    return value
def _ids(value):
    if not isinstance(value,list) or not 1<=len(value)<=64:raise ValueError('Invalid spell IDs')
    for sid in value:
        if isinstance(sid,bool) or not isinstance(sid,int) or not 1<=sid<=100000000:raise ValueError('Invalid spell ID')
    return value
def _condition(value):
    if not isinstance(value,dict) or value.get('kind') not in ('player_aura','target_aura','previous_spell'):raise ValueError('Invalid spell link')
    return {'kind':value['kind'],'ids':_ids(value.get('ids')),'seconds':_number(value.get('seconds',8),1,30),
            'source_name':_text(value.get('source_name')),'source_key':_text(value.get('source_key'))}

def selected_clips(project,class_name=None,ability_key=None):
    rows={r['key']:r for r in project.data['catalog']}
    selected=[]
    for key,row in rows.items():
        if class_name and row['class']!=class_name:continue
        if ability_key and key!=ability_key:continue
        count=int(project.data.get('success_variations',{}).get(key,1))
        if not 1<=count<=5:raise ValueError('Invalid success voice count')
        slots=[(e,1,e) for e in EVENTS]+[('success',n,'success:'+str(n)) for n in range(2,count+1)]
        for phase,slot,suffix in slots:
            clip=project.data['clips'].get(key+':'+suffix)
            if clip and clip.get('ready',True):selected.append((row,phase,slot,clip))
    return selected

def export_voicepack(project,destination,*,class_name=None,ability_key=None,editable=False,title='Voice pack'):
    selected=selected_clips(project,class_name,ability_key)
    if not selected:raise ValueError('No finished enabled voices to share')
    rows={r['key']:r for r in project.data['catalog']}
    needed={r['key'] for r,_,_,_ in selected}
    for key in list(needed):
        row=rows[key]
        if row.get('condition'):
            needed.update([row['base_key'],row['condition']['source_key']])
    if not needed<=rows.keys():raise ValueError('A linked ability is missing')
    remap={key:'a'+str(i) for i,key in enumerate(sorted(needed),1)}
    catalog=[]
    for key in sorted(needed):
        source=rows[key]
        row={k:copy.deepcopy(source[k]) for k in ['name','class','ids','name_ja','cast_seconds','passive','channeled'] if k in source}
        row['key']=remap[key]
        if source.get('condition'):
            row['base_key']=remap[source['base_key']];row['condition']={k:copy.deepcopy(source['condition'][k]) for k in ['kind','ids','seconds','source_name','source_key'] if k in source['condition']}
            row['condition']['source_key']=remap[source['condition']['source_key']]
        catalog.append(row)
    manifest={'format':FORMAT,'version':1,'title':_text(title),'mode':'editable' if editable else 'finished',
              'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'catalog':catalog,'clips':[],
              'success_variations':{remap[k]:int(project.data.get('success_variations',{}).get(k,1)) for k in needed}}
    destination=Path(destination)
    if destination.resolve().is_relative_to(project.root.resolve()):raise ValueError('Save the share pack outside the project folder')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vcs-pack-export-') as tmp:
        folder=Path(tmp);written={}
        for row,phase,slot,clip in selected:
            source=project.asset(clip['source'])
            audio,rate=load_audio(source)
            # Check trim/gain/effects even in editable mode before accepting it.
            finished=render_audio(audio,rate,clip['start'],clip['end'],clip.get('gain',1),clip.get('normalize',False),effects=clip.get('effects'))
            path=folder/'current.wav'
            if editable:
                shutil.copy2(source,path)
                saved={k:copy.deepcopy(clip[k]) for k in ['start','end','gain','normalize','effects'] if k in clip}
            else:
                sf.write(path,finished,rate,subtype='PCM_16')
                saved={'start':0,'end':len(finished)/rate,'gain':1,'normalize':False}
            digest=hashlib.sha256(path.read_bytes()).hexdigest();name='audio/'+digest+'.wav'
            if name not in written:
                keep=folder/(digest+'.wav');shutil.copy2(path,keep);written[name]=keep
            saved.update(ability=remap[row['key']],phase=phase,slot=slot,source=name,ready=True)
            manifest['clips'].append(saved)
        raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8')
        if len(raw)>MAX_MANIFEST or sum(p.stat().st_size for p in written.values())+len(raw)>MAX_TOTAL:raise ValueError('Voice pack exceeds the 512 MiB limit')
        if any(p.stat().st_size>MAX_FILE for p in written.values()):raise ValueError('An audio file exceeds the 128 MiB limit')
        handle,tempname=tempfile.mkstemp(prefix='.vcs-pack-',suffix='.zip',dir=destination.parent);os.close(handle)
        try:
            with zipfile.ZipFile(tempname,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json',raw)
                for name,path in written.items():archive.write(path,name)
            # The same reader validates our exported pack before publishing the file.
            with read_voicepack(tempname):pass
            os.replace(tempname,destination)
        finally:
            if Path(tempname).exists():Path(tempname).unlink()
    return {'clips':len(selected),'audio_files':len(written),'mode':manifest['mode']}

class VoicePack:
    def __init__(self,temporary,manifest,audio):self.temporary=temporary;self.manifest=manifest;self.audio=audio
    def close(self):self.temporary.cleanup()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def read_voicepack(path):
    temporary=tempfile.TemporaryDirectory(prefix='vcs-pack-import-')
    try:
        folder=Path(temporary.name)
        with zipfile.ZipFile(path) as archive:
            members=archive.infolist();names=[m.filename for m in members]
            if len(members)>MAX_MEMBERS or len(set(names))!=len(names) or 'manifest.json' not in names:raise ValueError('Invalid voice pack archive')
            if sum(m.file_size for m in members)>MAX_TOTAL:raise ValueError('Voice pack exceeds the 512 MiB limit')
            for member in members:
                if member.flag_bits&1 or ((member.external_attr>>16)&0o170000)==0o120000:raise ValueError('Encrypted files and links are not allowed')
                if member.filename!='manifest.json' and not AUDIO_NAME.fullmatch(member.filename):raise ValueError('Unexpected or unsafe file in voice pack')
                if member.file_size>(MAX_MANIFEST if member.filename=='manifest.json' else MAX_FILE):raise ValueError('Voice pack member is too large')
            manifest=json.loads(archive.read('manifest.json'))
            if not isinstance(manifest,dict) or manifest.get('format')!=FORMAT or type(manifest.get('version')) is not int or manifest['version']!=1:raise ValueError('Unsupported voice pack format/version')
            manifest['title']=_text(manifest.get('title'))
            if manifest.get('mode') not in ('finished','editable'):raise ValueError('Unsupported voice pack mode')
            catalog=manifest.get('catalog');clips=manifest.get('clips');counts=manifest.get('success_variations',{})
            if not isinstance(catalog,list) or not 1<=len(catalog)<=3000 or not isinstance(clips,list) or not 1<=len(clips)<=21000 or not isinstance(counts,dict):raise ValueError('Invalid voice pack manifest')
            rows={};normal_ids=set()
            for row in catalog:
                if not isinstance(row,dict):raise ValueError('Invalid ability')
                key=_text(row.get('key'));_text(row.get('name'),160);token=_text(row.get('class'),20)
                if not re.fullmatch('[A-Z]+',token) or key in rows:raise ValueError('Invalid or duplicate ability')
                _ids(row.get('ids'))
                for field in ['passive','channeled']:
                    if field in row and type(row[field]) is not bool:raise ValueError('Invalid ability flag')
                if 'cast_seconds' in row:_number(row['cast_seconds'],0,600)
                if 'name_ja' in row:_text(row['name_ja'],200)
                if row.get('condition'):
                    row['condition']=_condition(row['condition']);_text(row.get('base_key'))
                else:
                    identities={(token,sid) for sid in row['ids']}
                    if identities&normal_ids:raise ValueError('Duplicate spell IDs in normal abilities')
                    normal_ids.update(identities)
                rows[key]=row
            for key,row in rows.items():
                if row.get('condition'):
                    for dep in [row['base_key'],row['condition']['source_key']]:
                        if dep not in rows or rows[dep].get('condition') or rows[dep]['class']!=row['class']:raise ValueError('Invalid or missing spell link dependency')
                count=counts.get(key,1)
                if type(count) is not int or not 1<=count<=5:raise ValueError('Invalid voice count')
            refs=set();seen=set()
            for clip in clips:
                if not isinstance(clip,dict) or clip.get('ability') not in rows or clip.get('phase') not in EVENTS:raise ValueError('Invalid voice assignment')
                slot=clip.get('slot');phase=clip['phase'];key=clip['ability']
                if type(slot) is not int or not 1<=slot<=(counts.get(key,1) if phase=='success' else 1):raise ValueError('Invalid voice slot')
                identity=(key,phase,slot)
                if identity in seen:raise ValueError('Duplicate voice assignment')
                seen.add(identity)
                if clip.get('ready') is not True or not isinstance(clip.get('source'),str) or not AUDIO_NAME.fullmatch(clip['source']):raise ValueError('Invalid audio reference')
                refs.add(clip['source']);_number(clip.get('start'),0,600);_number(clip.get('end'),0,600)
                _number(clip.get('gain',1),0,2)
                if type(clip.get('normalize',False)) is not bool:raise ValueError('Invalid normalize flag')
                if 'effects' in clip:
                    if not isinstance(clip['effects'],dict) or set(clip['effects'])-set(LIMITS):raise ValueError('Unsupported voice effects')
                    effect_settings(clip['effects'])
            if refs!=set(names)-{'manifest.json'}:raise ValueError('Missing or unreferenced audio in pack')
            audio={};durations={}
            for name in refs:
                target=folder/Path(name).name
                digest=hashlib.sha256()
                with archive.open(name) as src,target.open('wb') as dst:
                    while data:=src.read(1024*1024):digest.update(data);dst.write(data)
                if digest.hexdigest()!=Path(name).stem:raise ValueError('Audio checksum mismatch')
                samples,rate=load_audio(target)
                if samples.size<max(1,int(rate*.03)):raise ValueError('Audio is too short')
                audio[name]=target;durations[name]=(len(samples),rate)
            for clip in clips:
                frames,rate=durations[clip['source']]
                if not 0<=clip['start']<clip['end']<=frames/rate+.001 or int(clip['end']*rate)-int(clip['start']*rate)<int(rate*.03):raise ValueError('Invalid audio trim range')
        return VoicePack(temporary,manifest,audio)
    except Exception:temporary.cleanup();raise

def _signature(row):
    c=row.get('condition')
    return None if not c else (c['kind'],tuple(sorted(c['ids'])),float(c.get('seconds',8)))

def _plan(project,pack,conflict):
    if conflict not in ('keep','replace'):raise ValueError('Choose keep or replace')
    data=copy.deepcopy(project.data);incoming=pack.manifest;mapping={};added=0
    ordered=sorted(incoming['catalog'],key=lambda r:bool(r.get('condition')))
    for original in ordered:
        row={k:copy.deepcopy(original[k]) for k in ['key','name','class','ids','name_ja','cast_seconds','passive','channeled','condition','base_key'] if k in original}
        signature=_signature(row)
        if row.get('condition'):
            row['base_key']=mapping[row['base_key']];row['condition']['source_key']=mapping[row['condition']['source_key']]
        def matches(r):
            if r['class']!=row['class'] or not set(r['ids'])&set(row['ids']):return False
            if not row.get('condition'):return not r.get('condition')
            c=r.get('condition');n=row['condition']
            return bool(c and c['kind']==n['kind'] and float(c.get('seconds',8))==float(n.get('seconds',8)) and r.get('base_key')==row['base_key'] and c.get('source_key')==n['source_key'])
        existing=next((r for r in data['catalog'] if matches(r)),None)
        if existing:
            mapping[original['key']]=existing['key']
            existing['ids']=sorted(set(existing['ids'])|set(row['ids']))
            if existing.get('condition'):existing['condition']['ids']=sorted(set(existing['condition']['ids'])|set(row['condition']['ids']))
        else:
            stem='pack_'+row['class'].lower()+'_'+str(min(row['ids']));key=stem;n=2
            used={r['key'] for r in data['catalog']}
            while key in used:key=stem+'_'+str(n);n+=1
            row['key']=key;data['catalog'].append(row);mapping[original['key']]=key;added+=1
    applied=[];skipped=0;conflicts=0
    for clip in incoming['clips']:
        rowkey=mapping[clip['ability']];suffix=clip['phase']+(':'+str(clip['slot']) if clip['slot']>1 else '')
        key=rowkey+':'+suffix
        if key in data['clips']:
            conflicts+=1
            if conflict=='keep':skipped+=1;continue
        item={k:copy.deepcopy(clip[k]) for k in ['start','end','gain','normalize','effects'] if k in clip}
        item.update(source='originals/pack_'+Path(clip['source']).name,ready=True)
        data['clips'][key]=item;applied.append((clip['source'],item['source']))
        count=incoming.get('success_variations',{}).get(clip['ability'],1)
        data.setdefault('success_variations',{})[rowkey]=max(data.get('success_variations',{}).get(rowkey,1),count)
    return data,applied,{'imported':len(applied),'skipped':skipped,'conflicts':conflicts,'added_abilities':added}

def inspect_import(project,pack):return _plan(project,pack,'keep')[2]

def import_voicepack(project,pack,*,conflict='keep'):
    before=project.path.read_bytes()
    if json.loads(before)!=project.data:raise RuntimeError('This project changed in another window. Reopen it before importing.')
    data,applied,report=_plan(project,pack,conflict)
    if not applied:
        report['added_abilities']=0
        return report
    copied=[];backup=None
    try:
        for source,relative in set(applied):
            target=project.asset(relative);target.parent.mkdir(parents=True,exist_ok=True)
            expected=Path(source).stem
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('An existing audio asset has different contents')
            else:
                copied.append(target);shutil.copyfile(pack.audio[source],target)
        if project.path.read_bytes()!=before:raise RuntimeError('Project changed while importing. Try again after closing other editor windows.')
        backup=project.root/('project-before-import-'+str(time.time_ns())+'.json');backup.write_bytes(before)
        atomic_json(project.path,data)
        project.data=data
        report['backup']=str(backup)
        return report
    except Exception:
        # Only files created by this import are rolled back. Existing originals survive.
        for path in copied:
            if path.is_file():path.unlink()
        raise
