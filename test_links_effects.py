import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import test_addon_v02 as lifecycle
import test_app_v02 as fixtures
from core import Project,render_audio,load_audio
from effects import apply_effects
BASE=Path(__file__).parent

class EffectsTests(unittest.TestCase):
    def test_pitch_preserves_length_and_changes_frequency(self):
        rate=16000;data=(.2*np.sin(2*np.pi*440*np.arange(rate)/rate)).astype('float32')
        original=data.copy()
        for pitch,hz in [(12,880),(-12,220)]:
            out=apply_effects(data,rate,{'pitch':pitch})
            self.assertEqual(len(out),len(data));self.assertTrue(np.all(np.isfinite(out)))
            center=out[2000:-2000];frequency=np.fft.rfftfreq(len(center),1/rate)[np.argmax(abs(np.fft.rfft(center)))]
            self.assertAlmostEqual(frequency,hz,delta=5)
        np.testing.assert_array_equal(data,original)
    def test_eq_vibrato_tremolo_and_invalid_settings(self):
        rate=16000;t=np.arange(rate)/rate;data=(.2*np.sin(2*np.pi*80*t)).astype('float32')
        np.testing.assert_array_equal(apply_effects(data,rate,{}),data)
        boosted=apply_effects(data,rate,{'low':6})
        self.assertGreater(np.std(boosted),1.9*np.std(data))
        for effects in [{'vibrato_depth':5},{'tremolo_depth':70},{'pitch':4,'high':6,'vibrato_depth':2}]:
            out=render_audio(data,rate,0,1,effects=effects)
            self.assertEqual(len(out),len(data));self.assertTrue(np.all(np.isfinite(out)));self.assertLessEqual(np.max(abs(out)),1)
            self.assertFalse(np.array_equal(out,data))
        for effects in [{'pitch':99},{'low':float('nan')},{'vibrato_depth':-1}]:
            with self.assertRaises(ValueError):apply_effects(data,rate,effects)

class LinksTests(unittest.TestCase):
    def runtime(self,kind='player_aura'):
        rows='''{{class="MAGE",ids={133},event="success",file="normal.wav"},
{class="MAGE",ids={133},event="success",file="linked.wav",condition={tag="link",kind="%s",ids={12043},seconds=8}}}'''%kind
        lua=lifecycle.AddonLifecycleTests().runtime(rows)
        lua.execute('''originalHandler=handler; auras={player={},target={}}
C_UnitAuras={GetAuraDataByIndex=function(unit,i,filter) return auras[unit][i] end}
function UnitName(unit) return "Enemy" end
''')
        lua.execute((BASE/'addon/Conditions.lua').read_text(encoding='utf8'))
        lua.execute('VoiceChantConditions.Initialize(VoiceChantConfig.bindings); auraHandler=handler;handler=originalHandler')
        return lua
    def test_player_aura_snapshot_survives_consumption_and_falls_back_without_aura(self):
        lua=self.runtime()
        lua.execute('''
auras.player={{spellId=12043}};auraHandler(nil,"UNIT_AURA","player")
handler(nil,"UNIT_SPELLCAST_SENT","player","Enemy","a",133)
auras.player={};auraHandler(nil,"UNIT_AURA","player")
event("UNIT_SPELLCAST_SUCCEEDED","a",133); assert(#plays==1 and plays[1].file=="linked.wav")
event("UNIT_SPELLCAST_SUCCEEDED","a",133); assert(#plays==1)
now=1;event("UNIT_SPELLCAST_SUCCEEDED","b",133);assert(plays[2].file=="normal.wav")
''')
    def test_sequence_tracks_unassigned_spells_and_expires(self):
        lua=self.runtime('previous_spell')
        lua.execute('''
event("UNIT_SPELLCAST_SUCCEEDED","first",12043)
now=1;event("UNIT_SPELLCAST_SUCCEEDED","second",133);assert(plays[1].file=="linked.wav")
now=2;event("UNIT_SPELLCAST_SUCCEEDED","third",133);assert(plays[2].file=="normal.wav")
now=3;event("UNIT_SPELLCAST_SUCCEEDED","fourth",12043)
now=20;event("UNIT_SPELLCAST_SUCCEEDED","fifth",133);assert(plays[3].file=="normal.wav")
''')
    def test_target_aura_and_secret_values(self):
        lua=self.runtime('target_aura')
        lua.execute('''
auras.target={{spellId=12043}};auraHandler(nil,"PLAYER_TARGET_CHANGED")
handler(nil,"UNIT_SPELLCAST_SENT","player","Enemy","a",133)
auras.target={};auraHandler(nil,"PLAYER_TARGET_CHANGED")
event("UNIT_SPELLCAST_SUCCEEDED","a",133);assert(plays[1].file=="linked.wav")
auras.player={{spellId="SECRET"}};auraHandler(nil,"UNIT_AURA","player")
''')
    def test_user_link_export_migration_and_effects_keep_sources(self):
        with tempfile.TemporaryDirectory() as d:
            catalog=[{'key':'fire','class':'MAGE','name':'Fireball','ids':[133]},
                     {'key':'pom','class':'MAGE','name':'Presence of Mind','ids':[12043]}]
            p=Project(Path(d)/'p',catalog)
            row=p.add_link('fire','pom','player_aura');self.assertEqual(p.add_link('fire','pom','player_aura')['key'],row['key'])
            src=p.add_audio(np.sin(np.arange(4410)*.1).astype('float32')*.2,44100);before=p.asset(src).read_bytes()
            p.data['clips'][row['key']+':success']={'source':src,'start':0,'end':.1,'ready':True,'effects':{'pitch':3}}
            p.save();original=copy.deepcopy(p.data)
            q=Project(p.root,catalog);self.assertEqual(q.data,original)
            changed=q.add_link('fire','pom','previous_spell',6,replace_key=row['key'])
            self.assertEqual(changed['key'],row['key']);self.assertEqual(q.data['clips'],original['clips'])
            q.add_link('fire','pom','player_aura',replace_key=row['key'])
            q.merge_catalog([{'id':143,'name':'Fireball','class':'MAGE'}])
            self.assertNotIn(143,next(r for r in q.data['catalog'] if r.get('condition'))['ids'])
            folder,n=q.export(Path(d)/'out',BASE/'addon',game=False);self.assertEqual(n,1)
            from lupa import LuaRuntime
            l=LuaRuntime();l.execute((folder/'Config.lua').read_text(encoding='utf8'))
            self.assertEqual(l.globals().VoiceChantConfig.bindings[1].condition.kind,'player_aura')
            self.assertEqual(p.asset(src).read_bytes(),before)

class AllClassesTests(unittest.TestCase):
    def test_all_nine_classes_and_unique_primary_keys(self):
        rows=json.loads((BASE/'assets/catalog.json').read_text(encoding='utf8'))
        self.assertEqual({r['class'] for r in rows},{'MAGE','PALADIN','PRIEST','DRUID','HUNTER','ROGUE','SHAMAN','WARLOCK','WARRIOR'})
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        for cls in {r['class'] for r in rows}:
            self.assertGreater(sum(r['class']==cls for r in rows),30)

class FeatureUITests(unittest.TestCase):
    setUp=fixtures.StudioV02Tests.setUp
    destroy=fixtures.StudioV02Tests.destroy
    def test_link_dialog_selectors_and_creation(self):
        import tkinter as tk
        from tkinter import ttk
        row=next(r for r in self.ui.project.data['catalog'] if r['name']=='Judgement')
        self.ui.tree.selection_set(row['key']);self.ui.select_row();self.ui.create_link()
        win=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        def children(w):
            for x in w.winfo_children():yield x;yield from children(x)
        widgets=list(children(win));combos=[w for w in widgets if isinstance(w,ttk.Combobox)]
        combos[0].set('Seal of Righteousness');combos[2].set('Judgement')
        button=next(w for w in widgets if isinstance(w,ttk.Button) and 'Create link' in w.cget('text')) if self.ui.language=='en' else next(w for w in widgets if isinstance(w,ttk.Button) and 'リンクを作成' in w.cget('text'))
        button.invoke()
        self.assertEqual(self.ui.row['condition']['source_name'],'Seal of Righteousness')
        self.assertIn('LINK',self.ui.ability_label(self.ui.row))
    def test_fx_apply_marks_finished_clip_draft_and_preserves_original(self):
        import tkinter as tk
        from tkinter import ttk
        self.ui.tree.selection_set(self.ui.tree.get_children()[0]);self.ui.select_row()
        self.ui.set_take(np.sin(np.arange(4410)*.1).astype('float32')*.1,44100);self.ui.save_clip()
        source=self.ui.project.asset(self.ui.clip['source']);before=source.read_bytes()
        self.ui.open_effects()
        win=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        def descendants(w):
            for x in w.winfo_children():yield x;yield from descendants(x)
        widgets=list(descendants(win));scale=next(w for w in widgets if isinstance(w,ttk.Scale));scale.set(4)
        apply=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text') in ('Apply','適用'));apply.invoke()
        self.assertFalse(self.ui.ready);self.assertEqual(self.ui.clip['effects']['pitch'],4)
        self.assertEqual(source.read_bytes(),before)
        self.ui.save_clip();self.assertTrue(self.ui.ready)
