"""v0.8 regressions: synthetic projects and Lua only, never real microphones."""
import copy,json,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
from core import Project
import studio_workflow as flow
import voicepacks as vp
import test_addon_v02 as game
import test_app_v02 as gui
BASE=Path(__file__).parent
CAT=[{'key':'a','name':'Holy Light','class':'PALADIN','ids':[635]}, {'key':'b','name':'Flash of Light','class':'PALADIN','ids':[19750]}]

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.project=Project(self.root/'project',CAT)
        for key in ['a','b']:
            source=self.project.add_audio(np.sin(np.arange(16000)*.1).astype('float32')*.2,16000)
            self.project.data['clips'][key+':success']={'source':source,'start':0,'end':1,'ready':True}
        self.project.save()
    def test_concurrent_save_rejected_and_editor_lock_released(self):
        other=Project(self.project.root,CAT);self.project.data['options']['gap']=.8;self.project.save()
        other.data['options']['gap']=.5
        with self.assertRaises(RuntimeError):other.save()
        self.assertEqual(json.loads(self.project.path.read_text())['options']['gap'],.8)
        lock=flow.EditorLock(self.project.root)
        with self.assertRaises(RuntimeError):flow.EditorLock(self.project.root)
        lock.close();again=flow.EditorLock(self.project.root);again.close()
    def test_presets_batch_apply_and_finish_preserve_audio(self):
        originals={p.name:p.read_bytes() for p in (self.project.root/'originals').glob('*.wav')}
        self.assertEqual(flow.apply_preset(self.project,'低い悪役声 / Dark villain',['a','b']),2)
        self.assertTrue(all(not c['ready'] and c['effects']['pitch']==-5 for c in self.project.data['clips'].values()))
        flow.save_preset(self.project,'custom',{'pitch':2,'high':4})
        self.assertIn('custom',flow.presets(Project(self.project.root,CAT)))
        self.assertEqual(flow.finish_many(self.project,['a','b']),2)
        self.assertEqual(originals,{p.name:p.read_bytes() for p in (self.project.root/'originals').glob('*.wav')})
    def test_snapshot_restores_previous_assignment_and_keeps_originals(self):
        before=copy.deepcopy(self.project.data);self.project.data['clips'].pop('a:success');self.project.save()
        snapshot=flow.backups(self.project)[0];self.project.restore(snapshot)
        self.assertEqual(self.project.data,before)
        self.assertEqual(len(list((self.project.root/'originals').glob('*.wav'))),2)
        for i in range(35):self.project.data['options']['gap']=i/100;self.project.save()
        self.assertLessEqual(len(list((self.project.root/'history').glob('state-*.json'))),30)
    def test_pack_disabled_slots_stay_disabled_and_reenable_explicitly(self):
        receiver=Project(self.root/'receiver',CAT);clip=copy.deepcopy(self.project.data['clips']['a:success'])
        source=receiver.add_audio(np.ones(16000,dtype='float32')*.1,16000);clip['source']=source
        receiver.data['clips']['a:success:3']=clip;receiver.data['success_variations']={'a':1};receiver.save()
        self.project.data['success_variations']={'a':5};self.project.data['clips']['a:success:2']=self.project.data['clips'].pop('a:success');self.project.save()
        vp.export_voicepack(self.project,self.root/'p.zip')
        with vp.read_voicepack(self.root/'p.zip') as pack:vp.import_voicepack(receiver,pack)
        self.assertFalse(receiver.data['clips']['a:success:3']['enabled'])
        self.assertFalse(any(slot==3 for _,_,slot,_ in vp.selected_clips(receiver,ability_key='a')))
    def test_pack_metadata_subset_and_removal_preserve_later_edits(self):
        path=self.root/'p.zip';vp.export_voicepack(self.project,path,author='Tester',description='Two healing voices')
        receiver=Project(self.root/'receiver',CAT)
        with vp.read_voicepack(path) as pack:
            self.assertEqual(pack.manifest['author'],'Tester')
            subset=vp.selected_pack(pack,[0]);self.assertEqual(len(subset.manifest['catalog']),1)
            vp.import_voicepack(receiver,subset)
        pid=next(iter(receiver.data['voicepacks']));self.assertEqual(vp.remove_pack(receiver,pid)['restored'],1)
        self.assertEqual(receiver.data['clips'],{})
        with vp.read_voicepack(path) as pack:vp.import_voicepack(receiver,pack)
        pid=next(iter(receiver.data['voicepacks']));receiver.data['clips']['a:success']['gain']=.5;receiver.save()
        result=vp.remove_pack(receiver,pid);self.assertEqual(result['preserved_edits'],1);self.assertEqual(receiver.data['clips']['a:success']['gain'],.5)
    def test_export_plan_diagnostics_and_progress(self):
        plan=flow.export_plan(self.project);self.assertEqual(plan['finished'],2);self.assertEqual(plan['bytes'],640000)
        self.assertIn('Finished: 2',flow.diagnostics(self.project))
        seen=[];out,count=self.project.export(self.root/'out',BASE/'addon',game=False,progress=seen.append)
        self.assertEqual(seen,[1,2]);self.assertIn('duration=1.0',(out/'Config.lua').read_text())
        self.assertIn('Clipping risk',flow.analyze(np.ones(10),10))
    def test_unused_audio_is_archived_reversibly_and_current_audio_survives(self):
        game_root=self.root/'_forever_';game_root.mkdir();(game_root/'Wow.exe').touch()
        self.project.data['game']=str(game_root);self.project.save();folder,_=self.project.export(game_root,BASE/'addon')
        unused=folder/'Audio'/('0'*20+'.wav');unused.write_bytes(b'old')
        _,used,unused_files=flow.game_audio_usage(self.project);self.assertEqual(unused_files,[unused]);before={p.name:p.read_bytes() for p in used}
        target,n=flow.archive_unused_audio(self.project);self.assertEqual(n,1);self.assertEqual((target/unused.name).read_bytes(),b'old')
        self.assertTrue(all(p.read_bytes()==before[p.name] for p in used))
    def test_link_simulator_priority_fallback_and_expiry(self):
        row=self.project.add_link('a','b','previous_spell',4)
        self.project.data['clips'][row['key']+':success']=copy.deepcopy(self.project.data['clips']['a:success']);self.project.save()
        chosen,clips=flow.link_choice(self.project,'a','success',previous=19750,elapsed=2);self.assertEqual(chosen['key'],row['key']);self.assertEqual(len(clips),1)
        chosen,_=flow.link_choice(self.project,'a','success',previous=19750,elapsed=5);self.assertEqual(chosen['key'],'a')
        chosen,clips=flow.link_choice(self.project,'a','start',previous=19750);self.assertEqual(chosen['key'],'a');self.assertEqual(clips,[])

class PlaybackTests(unittest.TestCase):
    def runtime(self):return game.AddonLifecycleTests().runtime('''{{ids={133},event='start',file='a.wav'},{ids={116},event='start',file='b.wav'}}''')
    def test_default_replace_and_overlap_stop_only_cancelled_cast(self):
        lua=self.runtime();lua.execute("event('UNIT_SPELLCAST_START','a',133);now=1;event('UNIT_SPELLCAST_START','b',116);assert(#plays==2 and #stops==1)")
        lua=self.runtime();lua.execute("""
assert(VoiceChantStudioAPI.SetPlayback('overlap'))
event('UNIT_SPELLCAST_START','a',133);now=1;event('UNIT_SPELLCAST_START','b',116)
assert(#plays==2 and #stops==0)
event('UNIT_SPELLCAST_INTERRUPTED','a',133);assert(#stops==1 and stops[1]==1)
VoiceChantStudioAPI.Stop();assert(#stops==2 and stops[2]==2)
assert(not VoiceChantStudioAPI.SetPlayback('invalid'))
""")
    def test_overlap_same_cast_success_transition_and_duration_cleanup(self):
        lua=game.AddonLifecycleTests().runtime("{{ids={133},event='start',file='a.wav',duration=1},{ids={133},event='success',file='done.wav',duration=.2},{ids={116},event='start',file='b.wav',duration=3}}")
        lua.execute("""
VoiceChantStudioAPI.SetPlayback('overlap');event('UNIT_SPELLCAST_START','a',133);now=.3;event('UNIT_SPELLCAST_START','b',116)
now=.6;event('UNIT_SPELLCAST_SUCCEEDED','a',133);assert(#stops==1 and stops[1]==1 and #plays==3)
advanceTo(1);VoiceChantStudioAPI.Stop();assert(#stops==2 and stops[2]==2)
""")
    def test_sequence_no_repeat_dedup_and_debug(self):
        lua=game.AddonLifecycleTests().runtime("{{ids={133},event='success',file='a.wav'},{ids={133},event='success',file='b.wav'},{ids={133},event='success',file='c.wav'}}")
        lua.execute("""
assert(VoiceChantStudioAPI.SetSelection('sequence'));math.random=function() error('sequence uses no random calls') end
for i=1,4 do now=i;event('UNIT_SPELLCAST_SUCCEEDED','s'..i,133);event('UNIT_SPELLCAST_SUCCEEDED','s'..i,133) end
assert(#plays==4 and plays[1].file=='a.wav' and plays[2].file=='b.wav' and plays[4].file=='a.wav')
VoiceChantStudioAPI.SetSelection('norepeat');math.random=function(n) return 1 end
for i=5,9 do now=i;event('UNIT_SPELLCAST_SUCCEEDED','n'..i,133);if i>5 then assert(plays[i].file~=plays[i-1].file) end end
messages={};print=function(t) table.insert(messages,t) end
SlashCmdList.VOICECHANTSTUDIO('debug');now=10;event('UNIT_SPELLCAST_SUCCEEDED','last',133)
SlashCmdList.VOICECHANTSTUDIO('diagnostics');assert(#messages>=4)
assert(not VoiceChantStudioAPI.SetSelection('bad'))
""")
    def test_newest_ducking_levels_and_fourth_voice_are_bounded(self):
        rows=[]
        for n,sid in enumerate([133,116,2136,1449]):
            token=chr(97+n)
            segments=','.join('{file="'+token+str(i)+'",volumes={[50]="'+token+'50_'+str(i)+'",[20]="'+token+'20_'+str(i)+'"}}' for i in range(1,15))
            rows.append('{ids={'+str(sid)+'},event="start",file="'+token+'.wav",duration=3.5,segmentStep=.25,segments={'+segments+'}}')
        lua=game.AddonLifecycleTests().runtime('{'+','.join(rows)+'}')
        lua.execute("""
VoiceChantStudioAPI.SetPlayback('duck');event('UNIT_SPELLCAST_START','a',133)
now=.3;event('UNIT_SPELLCAST_START','b',116);advanceTo(.5)
assert(plays[1].file=='a1' and plays[2].file=='b1' and plays[3].file=='a50_3')
now=.6;event('UNIT_SPELLCAST_START','c',2136);advanceTo(.8)
local third=false;local second=false
for _,p in ipairs(plays) do if p.file:find('a20_') then third=true end;if p.file:find('b50_') then second=true end end
assert(third and second)
advanceTo(.9);event('UNIT_SPELLCAST_START','d',1449);local count=#plays
advanceTo(1.2)
for i=count+1,#plays do assert(not plays[i].file:match('^a')) end
VoiceChantStudioAPI.Stop();count=#plays;advanceTo(2);assert(#plays==count)
""")

class DuckAssetTests(unittest.TestCase):
    def test_segments_crossfade_to_original_and_export_with_all_gain_levels(self):
        from ducking import write_segments,STEP
        from core import load_audio
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audio=(np.sin(np.arange(16000)*.1)*.2).astype('float32')
            segments=write_segments(audio,16000,root);self.assertEqual(len(segments),4)
            mixed=np.zeros_like(audio)
            for index,segment in enumerate(segments):
                part,rate=load_audio(root/Path(segment['file']).name);start=round(index*STEP*rate);mixed[start:start+len(part)]+=part
                self.assertEqual(len(segment['volumes']),9)
            np.testing.assert_allclose(mixed,audio,atol=2/32768)
            project=Project(root/'project',CAT);source=project.add_audio(audio,16000)
            project.data['clips']['a:success']={'source':source,'start':0,'end':1,'ready':True};project.data['options']['ducking']=True;project.save()
            out,_=project.export(root/'out',BASE/'addon',game=False);config=(out/'Config.lua').read_text()
            self.assertIn('ducking=true',config);self.assertIn('segmentStep=0.25',config);self.assertIn('segments={',config)

class WorkflowUITests(unittest.TestCase):
    setUp=gui.StudioV02Tests.setUp
    destroy=gui.StudioV02Tests.destroy
    select=gui.StudioV02Tests.select
    def descendants(self,w):
        yield w
        for child in w.winfo_children():yield from self.descendants(child)
    def test_tools_tabs_and_batch_preset_button(self):
        from tkinter import ttk
        self.select('Holy Light','PALADIN');self.ui.set_take(np.ones(4410,dtype='float32')*.1,44100)
        w=self.ui.open_tools();widgets=list(self.descendants(w));tabs=next(x for x in widgets if isinstance(x,ttk.Notebook));self.assertEqual(len(tabs.tabs()),5)
        button=next(x for x in widgets if isinstance(x,ttk.Button) and x.cget('text')==self.ui.bi('選択した技へ適用','Apply to selected'))
        button.invoke();self.assertEqual(self.ui.clip['effects']['pitch'],1)
        self.assertFalse(self.ui.ready);w.destroy()
    def test_fx_target_cannot_change_silently(self):
        from tkinter import ttk
        import effects_ui
        self.select('Holy Light','PALADIN');self.ui.set_take(np.ones(4410,dtype='float32')*.1,44100)
        first=self.ui.key();w=effects_ui.open_effects(self.ui);self.assertEqual(w.grab_current(),w)
        self.select('Flash of Light','PALADIN');self.ui.set_take(np.ones(4410,dtype='float32')*.1,44100)
        button=next(x for x in self.descendants(w) if isinstance(x,ttk.Button) and x.cget('text')==self.ui.bi('適用','Apply'))
        with patch.object(effects_ui.messagebox,'showerror') as error:button.invoke();error.assert_called_once()
        self.assertNotIn('effects',self.ui.clip);self.assertNotIn('effects',self.ui.project.data['clips'][first]);w.destroy()
    def test_background_export_finishes_without_blocking_ui(self):
        import workflow_ui
        self.select('Holy Light','PALADIN');self.ui.set_take(np.ones(4410,dtype='float32')*.1,44100);self.ui.save_clip()
        destination=Path(self.directory.name)/'export'
        with patch.object(workflow_ui.messagebox,'askyesno',return_value=True),patch.object(workflow_ui.messagebox,'showinfo'):
            w=workflow_ui.export_with_progress(self.ui,destination,BASE/'addon',game=False)
            self.assertTrue(self.ui.export_busy)
            deadline=time.monotonic()+5
            while self.ui.export_busy and time.monotonic()<deadline:self.root.update();time.sleep(.01)
            self.assertFalse(self.ui.export_busy);self.assertTrue((destination/'VoiceChantStudio/Config.lua').exists())

if __name__=='__main__':unittest.main()
