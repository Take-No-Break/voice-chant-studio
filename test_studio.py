from pathlib import Path
import json, sys, tempfile, unittest
import numpy as np
from core import Project, load_audio, render_audio

BASE=Path(__file__).parent
sys.path.insert(0,str(BASE.parent/'lua-test'))
sys.path.insert(0,str(BASE.parent/'lua-parser'))

class StudioTests(unittest.TestCase):
    def test_audio_and_project_export(self):
        from luaparser import ast
        from lupa import LuaRuntime
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=Project(root/'project',[{'key':'holy','class':'PALADIN','name':'Holy Light','ids':[635,639]}])
            rate=44100;data=np.sin(np.arange(rate*2)/rate*2*np.pi*440).astype('float32')*.2
            source=p.add_audio(data,rate);original=p.asset(source).read_bytes()
            p.data['clips']['holy:start']={'source':source,'start':.25,'end':1.25,'normalize':True,'gain':.8,'ready':True}
            p.data['clips']['holy:success']={'source':source,'start':0,'end':.2,'ready':False}
            p.save();q=Project(p.root,[]);self.assertEqual(q.data['clips'],p.data['clips'])
            game=root/'_forever_';game.mkdir();(game/'Wow.exe').write_bytes(b'test placeholder')
            target,count=q.export(game,BASE/'addon');self.assertEqual(count,1)
            audio=list((target/'Audio').glob('*.wav'));self.assertEqual(len(audio),10)
            lua=LuaRuntime();lua.execute((target/'Config.lua').read_text(encoding='utf8'))
            full=target/'Audio'/lua.globals().VoiceChantConfig.bindings[1].file.split('\\')[-1]
            clip,sr=load_audio(full);self.assertEqual(sr,rate);self.assertEqual(len(clip),rate)
            self.assertLessEqual(float(np.max(np.abs(clip))),.721)
            self.assertAlmostEqual(float(clip[0]),0,places=4);self.assertEqual(original,p.asset(source).read_bytes())
            for f in target.glob('*.lua'):ast.parse(f.read_text(encoding='utf8'))
            lua=LuaRuntime();lua.execute((target/'Config.lua').read_text(encoding='utf8'))
            self.assertEqual(lua.globals().VoiceChantConfig.bindings[1].ids[2],639)
            before=(target/'Config.lua').read_bytes();q.data['clips']['holy:start']['source']='missing.wav'
            with self.assertRaises(Exception):q.export(game,BASE/'addon')
            self.assertEqual(before,(target/'Config.lua').read_bytes())
            with self.assertRaises(ValueError):q.asset('../outside.wav')
            with self.assertRaises(ValueError):q.export(root/'not-a-game',BASE/'addon')

    def test_invalid_audio_ranges(self):
        x=np.zeros(100,dtype='float32')
        for a,b in [(1,0),(-1,1),(0,10),(0,0)]:
            with self.assertRaises(ValueError):render_audio(x,100,a,b)

    def test_gui_keeps_per_ability_and_phase(self):
        import tkinter as tk
        import app
        with tempfile.TemporaryDirectory() as d:
            app.HOME=Path(d);root=tk.Tk();root.withdraw()
            try:
                ui=app.Studio(root);rows=ui.tree.get_children();self.assertGreater(len(rows),30)
                ui.tree.selection_set(rows[0]);ui.select_row();ui.event.set('詠唱開始');ui.change_phase();key=ui.key()
                ui.set_take(np.zeros(4410,dtype='float32'),44100);ui.start.set(.01);ui.end.set(.09);ui.save_clip()
                self.assertTrue(ui.project.data['clips'][key]['ready'])
                ui.event.set('発動成功・瞬間技');ui.change_phase();self.assertIsNone(ui.clip)
                ui.set_take(np.ones(8820,dtype='float32')*.1,44100);ui.save_clip()
                self.assertEqual(len(ui.project.data['clips']),2)
                ui.event.set('詠唱開始');ui.change_phase();self.assertAlmostEqual(ui.start.get(),.01)
                self.assertAlmostEqual(ui.end.get(),.09)
                ui.tree.selection_set(rows[1]);ui.select_row();self.assertIsNone(ui.clip)
            finally:root.destroy()

    def test_addon_events_do_not_cast_or_mute_originals(self):
        from lupa import LuaRuntime
        lua=LuaRuntime()
        lua.execute('''
VoiceChantConfig={gap=.2,stopOnCancel=true,bindings={
 {ids={635,639},event="start",file="chant.wav"},
 {ids={635,639},event="success",file="finish.wav"},
 {ids={20271},event="success",file="judge.wav"}}}
VoiceChantCatalog={}; VoiceChantStudioDB={}; SlashCmdList={}; plays={}; stops={}; now=0; timers={}
C_Spell={GetSpellName=function(id) if id==635 or id==639 or id==647 then return "Holy Light" else return "Judgement" end end}
function CreateFrame() return {RegisterEvent=function()end,RegisterUnitEvent=function()end,SetScript=function(self,key,f) handler=f end} end
function GetTime() return now end
function PlaySoundFile(file,channel) table.insert(plays,{file=file,channel=channel});return true,#plays end
function StopSound(handle) table.insert(stops,handle) end
function print()end
C_Timer={After=function(delay,fn) table.insert(timers,{delay,fn}) end}
function flushShort() local old=timers;timers={};for _,t in ipairs(old)do if t[1]<1 then t[2]()else table.insert(timers,t)end end end
function issecretvalue(v)return v=="SECRET"end
''')
        lua.execute((BASE/'addon/VoiceChantStudio.lua').read_text(encoding='utf8'))
        lua.execute('''
handler(nil,"UNIT_SPELLCAST_START","player","a",635);assert(#plays==1)
handler(nil,"UNIT_SPELLCAST_STOP","player","a",635)
now=1;handler(nil,"UNIT_SPELLCAST_SUCCEEDED","player","a",635);flushShort()
assert(#plays==2 and plays[2].file=="finish.wav" and #stops==1)
now=2;handler(nil,"UNIT_SPELLCAST_START","player","b",647);assert(#plays==3)
handler(nil,"UNIT_SPELLCAST_INTERRUPTED","player","b",647);assert(#stops==3)
now=3;handler(nil,"UNIT_SPELLCAST_SUCCEEDED","player","c",20271);assert(#plays==4)
now=4;handler(nil,"UNIT_SPELLCAST_SUCCEEDED","player","SECRET","SECRET");assert(#plays==4)
handler(nil,"UNIT_SPELLCAST_SUCCEEDED","target","d",20271);assert(#plays==4)
SlashCmdList.VOICECHANTSTUDIO("mute");now=5;handler(nil,"UNIT_SPELLCAST_SUCCEEDED","player","e",20271);assert(#plays==4)
SlashCmdList.VOICECHANTSTUDIO("unmute");handler(nil,"UNIT_SPELLCAST_SUCCEEDED","player","f",20271);assert(#plays==5)
''')

if __name__=='__main__':unittest.main(verbosity=2)

