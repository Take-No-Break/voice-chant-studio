"""Offline, non-destructive voice effects. No DSP runs in the game client."""
import numpy as np
LIMITS={'pitch':(-12,12,0),'low':(-12,12,0),'mid':(-12,12,0),'high':(-12,12,0),
        'vibrato_depth':(0,10,0),'vibrato_rate':(.5,10,5),'tremolo_depth':(0,100,0),'tremolo_rate':(.5,12,5)}
def settings(value):
    if value is None:return {}
    if not isinstance(value,dict):raise ValueError('Invalid voice effects')
    result={}
    for key,(low,high,default) in LIMITS.items():
        number=float(value.get(key,default))
        if not np.isfinite(number) or not low<=number<=high:raise ValueError('Invalid effect: '+key)
        result[key]=number
    return result
def _pitch(audio,semitones):
    """Hann overlap-add phase vocoder followed by resampling; preserve duration."""
    factor=2**(semitones/12);step=1/factor
    size=1024;hop=256;window=np.hanning(size)
    padded=np.pad(audio,(size//2,size+size//2))
    frame_count=1+(len(padded)-size)//hop
    steps=np.arange(0,frame_count-1,step)
    out=np.zeros(len(steps)*hop+size);weight=np.zeros_like(out)
    advance=2*np.pi*hop*np.arange(size//2+1)/size
    phase=None;stored={}
    for j,t in enumerate(steps):
        i=int(t);fraction=t-i
        for index in (i,i+1):
            if index not in stored:stored[index]=np.fft.rfft(padded[index*hop:index*hop+size]*window)
        a,b=stored[i],stored[i+1]
        if phase is None:phase=np.angle(a)
        magnitude=(1-fraction)*np.abs(a)+fraction*np.abs(b)
        frame=np.fft.irfft(magnitude*np.exp(1j*phase),n=size)*window
        start=j*hop;out[start:start+size]+=frame;weight[start:start+size]+=window**2
        delta=np.angle(b)-np.angle(a)-advance
        delta-=2*np.pi*np.round(delta/(2*np.pi))
        phase+=advance+delta
        stored={k:v for k,v in stored.items() if k>=i}
    out/=np.maximum(weight,1e-12)
    stretched=out[size//2:size//2+round(len(audio)*factor)]
    return np.interp(np.arange(len(audio))*factor,np.arange(len(stretched)),stretched).astype('float32')
def apply_effects(audio,rate,value=None):
    p=settings(value)
    if not p:return np.asarray(audio,dtype='float32').copy()
    out=np.asarray(audio,dtype='float32').copy()
    if p['pitch']:out=_pitch(out,p['pitch'])
    if any(p[key] for key in ('low','mid','high')):
        hz=np.fft.rfftfreq(len(out),1/rate)
        low=1/(1+(hz/250)**4);high=1-1/(1+(hz/4000)**4);mid=np.maximum(0,1-low-high)
        gain=10**((p['low']*low+p['mid']*mid+p['high']*high)/20)
        out=np.fft.irfft(np.fft.rfft(out)*gain,n=len(out)).astype('float32')
    time=np.arange(len(out))/rate
    if p['vibrato_depth']:
        delay=p['vibrato_depth']*.001*rate
        positions=np.arange(len(out))-delay*(1+np.sin(2*np.pi*p['vibrato_rate']*time))
        out=np.interp(positions,np.arange(len(out)),out,left=0).astype('float32')
    if p['tremolo_depth']:
        amount=p['tremolo_depth']/100
        out*=1-amount/2+amount/2*np.cos(2*np.pi*p['tremolo_rate']*time)
    return out
