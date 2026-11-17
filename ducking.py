"""Offline overlapping PCM segments for experimental in-game voice ducking."""
import hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
from core import ADDON,write_volume_variants,lua_string,volume_lua
STEP=.25
OVERLAP=.02
SMOOTH_OVERLAP=.20
def write_segments(audio,rate,directory,overlap_seconds=OVERLAP):
    if not 0<overlap_seconds<STEP:raise ValueError('Overlap must be between zero and segment step')
    directory=Path(directory);segments=[];stride=max(1,round(STEP*rate));overlap=max(1,round(overlap_seconds*rate))
    for start in range(0,len(audio),stride):
        part=np.asarray(audio[start:min(start+stride+overlap,len(audio))],dtype='float32').copy()
        if start:
            n=min(overlap,len(part));part[:n]*=np.linspace(0,1,n,dtype='float32')
        if start+stride<len(audio):
            n=len(part)-stride
            if n:part[-n:]*=np.linspace(1,0,n,dtype='float32')
        digest=hashlib.sha256(part.tobytes()+str(rate).encode()).hexdigest()[:20];name=digest+'.wav'
        sf.write(str(directory/name),part,rate,subtype='PCM_16')
        segments.append({'file':'Interface\\AddOns\\'+ADDON+'\\Audio\\'+name,'volumes':write_volume_variants(part,rate,directory)})
    return segments
def segments_lua(segments):
    return '{'+','.join('{file='+lua_string(s['file'])+',volumes='+volume_lua(s['volumes'])+'}' for s in segments)+'}'
