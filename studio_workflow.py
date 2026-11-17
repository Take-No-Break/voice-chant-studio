"""Local presets, diagnostics, restoration and export planning; no microphone I/O."""
import copy,json,time,re,shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from effects import settings
from core import load_audio,render_audio
from voicepacks import selected_clips

BUILTINS={
 '聖なる詠唱 / Holy chant':{'pitch':1,'low':-2,'mid':1,'high':3,'vibrato_depth':.6,'vibrato_rate':4.5},
 '低い悪役声 / Dark villain':{'pitch':-5,'low':4,'mid':1,'high':-2,'tremolo_depth':12,'tremolo_rate':2.5},
 '精霊の声 / Spirit':{'pitch':4,'low':-3,'mid':0,'high':3,'vibrato_depth':2,'vibrato_rate':5.5,'tremolo_depth':10,'tremolo_rate':3},
 '原音 / Dry':{}
}
def presets(project):return {**copy.deepcopy(BUILTINS),**copy.deepcopy(project.data.get('presets',{}))}
def save_preset(project,name,effects):
    name=name.strip()
    if not name or len(name)>100:raise ValueError('Enter a preset name (1–100 characters).')
    project.data.setdefault('presets',{})[name]=settings(effects);project.save()
def apply_preset(project,name,ability_keys,phase=None):
    available=presets(project)
    if name not in available:raise ValueError('Choose a preset')
    keys=set(ability_keys);changed=0
    for key,clip in project.data['clips'].items():
        ability,event,*_=key.split(':')
        if ability in keys and (not phase or event==phase):
            clip['effects']=settings(available[name]);clip['ready']=False;changed+=1
    if changed:project.save()
    return changed
def finish_many(project,ability_keys):
    targets=[]
    for key,clip in project.data['clips'].items():
        if key.split(':')[0] not in set(ability_keys):continue
        data,rate=load_audio(project.asset(clip['source']))
        render_audio(data,rate,clip['start'],clip['end'],clip.get('gain',1),clip.get('normalize',False),effects=clip.get('effects'))
        targets.append(clip)
    for clip in targets:clip['ready']=True
    project.save();return len(targets)
def backups(project):
    paths=list((project.root/'history').glob('state-*.json'))+list(project.root.glob('project-before-*.json'))
    return sorted(paths,key=lambda p:p.stat().st_mtime,reverse=True)
def analyze(audio,rate):
    if audio is None or not len(audio):return '音声なし / No audio'
    peak=float(np.max(np.abs(audio)));rms=float(np.sqrt(np.mean(np.asarray(audio,dtype='float64')**2)))
    silence=float(np.mean(np.abs(audio)<.01))*100
    return f'{len(audio)/rate:.2f}s · Peak {20*np.log10(max(peak,1e-9)):.1f} dBFS · RMS {20*np.log10(max(rms,1e-9)):.1f} dBFS · Silence {silence:.0f}%'+(' · 音割れ注意 / Clipping risk' if peak>=.98 else '')
def export_plan(project):
    clips=selected_clips(project);bytes_total=0;errors=[]
    for row,phase,slot,clip in clips:
        try:
            info=sf.info(str(project.asset(clip['source'])))
            if not 0<=clip['start']<clip['end']<=info.duration+.001:raise ValueError('Invalid trim')
            settings(clip.get('effects'));bytes_total+=int((clip['end']-clip['start'])*info.samplerate)*2*10*(3.88 if project.data.get('options',{}).get('ducking',False) else 1)
        except Exception as e:errors.append(row['name']+': '+str(e))
    return {'finished':len(clips),'excluded':len(project.data['clips'])-len(clips),'bytes':bytes_total,'errors':errors}
def diagnostics(project):
    plan=export_plan(project)
    lines=[f"完成 / Finished: {plan['finished']} · 未完成/無効 / Excluded: {plan['excluded']} · 約 / approx {plan['bytes']/1024**2:.1f} MiB (10 volume files)"]
    game=Path(project.data.get('game') or '.')
    if (game/'_forever_').is_dir():game/='_forever_'
    addon=game/'Interface/AddOns/VoiceChantStudio'
    lines+=['ゲーム / Game: '+('OK' if game.name.lower()=='_forever_' and (game/'Wow.exe').is_file() else '未設定 / not found'),
            'Config.lua: '+('OK' if (addon/'Config.lua').is_file() else '未出力 / not exported'),
            '現在の音声 / Current audio: '+analyze_current(project),
            'ゲーム内 / In game: /vcs → diagnostics. Check Sound + Dialog; restart WoW after export.']
    return '\n'.join(lines+plan['errors'])
def analyze_current(project):
    total=sum(p.stat().st_size for p in (project.root/'originals').glob('*') if p.is_file())
    return f'{total/1024**2:.1f} MiB originals (preserved)'
def link_matches(condition,player_ids=(),target_ids=(),previous=None,elapsed=0):
    if condition['kind']=='previous_spell':return previous in condition['ids'] and 0<=elapsed<=condition.get('seconds',8)
    return bool(set(condition['ids'])&set(player_ids if condition['kind']=='player_aura' else target_ids))
def link_choice(project,target_key,phase,player_ids=(),target_ids=(),previous=None,elapsed=0):
    for row in project.data['catalog']:
        if row.get('base_key')==target_key and link_matches(row['condition'],player_ids,target_ids,previous,elapsed):
            clips=[c for r,e,_,c in selected_clips(project,ability_key=row['key']) if e==phase]
            if clips:return row,clips
    row=next(r for r in project.data['catalog'] if r['key']==target_key)
    return row,[c for r,e,_,c in selected_clips(project,ability_key=target_key) if e==phase]
def game_audio_usage(project):
    game=Path(project.data.get('game') or '.')
    if (game/'_forever_').is_dir():game/='_forever_'
    if game.name.lower()!='_forever_' or not (game/'Wow.exe').is_file():raise ValueError('Select the WoW Forever folder first')
    folder=game/'Interface/AddOns/VoiceChantStudio'
    config=(folder/'Config.lua').read_text(encoding='utf8')
    used=set(re.findall(r'([0-9a-f]{20}\.wav)',config))
    files=[p for p in (folder/'Audio').glob('*.wav') if re.fullmatch(r'[0-9a-f]{20}\.wav',p.name)]
    return folder,[p for p in files if p.name in used],[p for p in files if p.name not in used]
def archive_unused_audio(project):
    folder,used,unused=game_audio_usage(project)
    target=project.root/'audio-archive'/str(time.time_ns());target.mkdir(parents=True)
    moved=[]
    try:
        for path in unused:
            dest=target/path.name;shutil.move(str(path),str(dest));moved.append(dest)
    except Exception:
        for path in moved:shutil.move(str(path),str(folder/'Audio'/path.name))
        raise
    return target,len(moved)

class EditorLock:
    """Release automatically on process exit; never delete a live lock file."""
    def __init__(self,folder):
        import msvcrt
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        self.stream=(folder/'.editor.lock').open('a+b')
        self.stream.seek(0,2)
        if self.stream.tell()==0:self.stream.write(b'1');self.stream.flush()
        self.stream.seek(0)
        try:msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            self.stream.close();raise RuntimeError('This project is already open. / このプロジェクトは既に開いています。')
    def close(self):
        if not self.stream.closed:self.stream.close()
    def __del__(self):
        if hasattr(self,'stream'):self.close()
