"""Step versus smooth transitions: numerical PCM and mocked Lua, no live audio."""
from pathlib import Path
import tempfile,unittest
import numpy as np
from core import load_audio,Project
from ducking import write_segments,STEP,SMOOTH_OVERLAP
import test_addon_v02 as game
BASE=Path(__file__).parent

class FadeAssetTests(unittest.TestCase):
    def render_transition(self,folder,overlap):
        rate=16000;audio=np.full(rate,.4,dtype='float32');segments=write_segments(audio,rate,folder,overlap)
        out=np.zeros_like(audio)
        for i,segment in enumerate(segments):
            path=segment['file'] if i==0 else segment['volumes'][50]
            part,_=load_audio(folder/path.split('\\')[-1]);start=round(i*STEP*rate);out[start:start+len(part)]+=part
        return out/.4
    def test_smooth_ramps_during_point_two_seconds_after_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            smooth=self.render_transition(Path(tmp),SMOOTH_OVERLAP)
            self.assertAlmostEqual(float(smooth[4000]),1,places=3)
            self.assertAlmostEqual(float(smooth[5600]),.75,places=3)
            self.assertAlmostEqual(float(smooth[7200]),.5,places=3)
            self.assertTrue(np.all(np.diff(smooth[4000:7200])<.0002))
    def test_step_reaches_target_in_point_zero_two_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            step=self.render_transition(Path(tmp),.02)
            self.assertAlmostEqual(float(step[4000]),1,places=3)
            self.assertAlmostEqual(float(step[4320]),.5,places=3)
            self.assertAlmostEqual(float(step[5600]),.5,places=3)
    def test_export_contains_both_banks_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=Project(root/'project',[{'key':'a','name':'Fireball','class':'MAGE','ids':[133]}])
            source=p.add_audio(np.ones(16000,dtype='float32')*.2,16000);original=p.asset(source).read_bytes()
            p.data['clips']['a:start']={'source':source,'start':0,'end':1,'ready':True};p.data['options']['ducking']=True;p.save()
            out,_=p.export(root/'out',BASE/'addon',game=False);text=(out/'Config.lua').read_text()
            self.assertIn('smoothSegments={',text);self.assertIn('smoothOverlap=0.2',text)
            self.assertEqual(p.asset(source).read_bytes(),original)

class FadeRuntimeTests(unittest.TestCase):
    def test_mode_selection_smooth_paths_and_cancel_retains_long_tail_handles(self):
        rows=[]
        for sid,token in [(133,'a'),(116,'b')]:
            def bank(prefix):return '{'+','.join('{file="'+prefix+str(i)+'",volumes={[50]="'+prefix+'half'+str(i)+'",[20]="'+prefix+'quiet'+str(i)+'"}}' for i in range(1,9))+'}'
            rows.append('{ids={'+str(sid)+'},event="start",file="'+token+'.wav",segmentStep=.25,segmentOverlap=.02,smoothOverlap=.2,segments='+bank(token)+',smoothSegments='+bank('smooth'+token)+'}')
        lua=game.AddonLifecycleTests().runtime('{'+','.join(rows)+'}')
        lua.execute('''
VoiceChantConfig.gap=0
assert(VoiceChantStudioAPI.GetFade()=='step')
assert(not VoiceChantStudioAPI.SetFade('invalid'))
SlashCmdList.VOICECHANTSTUDIO('fade smooth');assert(VoiceChantStudioDB.duckFade=='smooth')
VoiceChantStudioAPI.SetPlayback('duck')
event('UNIT_SPELLCAST_START','a',133);now=.1;event('UNIT_SPELLCAST_START','b',116)
assert(plays[1].file=='smootha1' and plays[2].file=='smoothb1')
advanceTo(.25);assert(plays[3].file=='smoothahalf2')
now=.35;event('UNIT_SPELLCAST_INTERRUPTED','a',133)
assert(#stops==2)
local handles={};for _,h in ipairs(stops) do handles[h]=true end
assert(handles[1] and handles[3] and not handles[2])
SlashCmdList.VOICECHANTSTUDIO('fade step');assert(VoiceChantStudioAPI.GetFade()=='step')
event('ADDON_LOADED',nil,nil,'VoiceChantStudio');assert(VoiceChantStudioDB.duckFade=='step')
''')
    def test_old_export_requires_reexport_before_smooth_playback(self):
        lua=game.AddonLifecycleTests().runtime('{{ids={133},event="start",file="old.wav",segments={{file="old1"}}}}')
        lua.execute("VoiceChantStudioAPI.SetPlayback('duck');VoiceChantStudioAPI.SetFade('smooth');event('UNIT_SPELLCAST_START','a',133);assert(#plays==0)")

if __name__=='__main__':unittest.main()
