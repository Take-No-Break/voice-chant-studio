import json,tempfile,unittest
from pathlib import Path
import numpy as np
import test_addon_v02 as lifecycle
import test_app_v02 as gui
from core import Project
BASE=Path(__file__).parent
class VariationTests(unittest.TestCase):
    def test_random_selection_duplicate_events_volume_and_single_voice(self):
        rows='{'+','.join('{class="MAGE",ids={133},event="success",file="voice'+str(i)+'.wav",volumes={[50]="half'+str(i)+'.wav"}}' for i in range(1,6))+'}'
        lua=lifecycle.AddonLifecycleTests().runtime(rows)
        lua.execute('''
rolls=0;math.random=function(n) rolls=rolls+1;assert(n==5);return (rolls-1)%5+1 end
VoiceChantStudioAPI.SetVolume(50)
for i=1,10 do now=i;event("UNIT_SPELLCAST_SUCCEEDED","cast"..i,133);event("UNIT_SPELLCAST_SUCCEEDED","cast"..i,133) end
assert(rolls==10 and #plays==10)
for i=1,10 do assert(plays[i].file=="half"..((i-1)%5+1)..".wav") end
VoiceChantStudioAPI.SetVolume(0);now=20;event("UNIT_SPELLCAST_SUCCEEDED","silent",133);assert(rolls==10)
''')
        lua=lifecycle.AddonLifecycleTests().runtime('{{ids={133},event="success",file="only.wav"}}')
        lua.execute('math.random=function() error("Single voice needs no random call") end;event("UNIT_SPELLCAST_SUCCEEDED","a",133);assert(plays[1].file=="only.wav")')
    def test_export_only_enabled_ready_success_slots_and_preserve_disabled_sources(self):
        with tempfile.TemporaryDirectory() as d:
            p=Project(Path(d)/'p',[{'key':'fire','class':'MAGE','name':'Fireball','ids':[133]}])
            for i in range(1,6):
                src=p.add_audio(np.ones(4410,dtype='float32')*(i/10),44100)
                p.data['clips']['fire:success'+(':'+str(i) if i>1 else '')]={'source':src,'start':0,'end':.1,'ready':i!=2}
            p.data['success_variations']={'fire':3};p.save()
            before=json.loads(p.path.read_text())
            out,n=p.export(Path(d)/'out',BASE/'addon',game=False)
            self.assertEqual(n,2)
            self.assertEqual(json.loads(p.path.read_text()),before)
            from lupa import LuaRuntime
            l=LuaRuntime();l.execute((out/'Config.lua').read_text())
            self.assertEqual(len(l.globals().VoiceChantConfig.bindings),2)
            self.assertEqual(len(list((p.root/'originals').glob('*.wav'))),5)
class VariationUITests(unittest.TestCase):
    setUp=gui.StudioV02Tests.setUp
    destroy=gui.StudioV02Tests.destroy
    def test_slots_keep_separate_edits_and_restore_existing_first_voice(self):
        row=next(r for r in self.ui.project.data['catalog'] if r['name']=='Judgement')
        self.ui.tree.selection_set(row['key']);self.ui.select_row()
        self.ui.variant_count.set('5');self.ui.change_variant_count()
        for i in range(1,6):
            self.ui.variant.set(str(i));self.ui.change_variant()
            self.ui.set_take(np.ones(4410,dtype='float32')*.1,44100);self.ui.save_clip()
        self.assertEqual(len(self.ui.project.data['clips']),5)
        self.ui.variant_count.set('2');self.ui.change_variant_count()
        self.assertEqual(len(self.ui.project.data['clips']),5)
        self.assertEqual(tuple(self.ui.voice_slot_box['values']),('1','2'))
        self.ui.variant.set('1');self.ui.change_variant()
        self.assertEqual(self.ui.key(),row['key']+':success')
