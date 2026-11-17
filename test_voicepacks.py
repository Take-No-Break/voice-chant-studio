import copy,hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from core import Project,load_audio,render_audio
import voicepacks as vp
import test_app_v02 as fixtures

CAT=[{'key':'heal','class':'PALADIN','name':'Holy Light','ids':[635,639],'cast_seconds':2.5},
     {'key':'seal','class':'PALADIN','name':'Seal of Light','ids':[20165]}]
class VoicePackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.sender=Project(self.root/'sender',CAT)
        self.audio=(np.sin(np.arange(16000)*.17)*.2).astype('float32');self.source=self.sender.add_audio(self.audio,16000)
        self.clip={'source':self.source,'start':.2,'end':.8,'gain':.8,'normalize':False,'ready':True,'effects':{'pitch':2,'low':3}}
        self.sender.data['clips']['heal:success']=copy.deepcopy(self.clip)
        self.sender.data['game']='PRIVATE_GAME_PATH'
        self.sender.save();self.path=self.root/'share.voicepack.zip'
    def recipient(self):
        cat=copy.deepcopy(CAT);cat[0]['key']='receiver_heal';cat[1]['key']='receiver_seal'
        return Project(self.root/'receiver',cat)
    def rewrite(self,modify=None,extra=None):
        with zipfile.ZipFile(self.path) as z:items={n:z.read(n) for n in z.namelist()}
        if modify:
            manifest=json.loads(items['manifest.json']);modify(manifest);items['manifest.json']=json.dumps(manifest).encode()
        with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as z:
            for name,raw in items.items():z.writestr(name,raw)
            if extra:z.writestr(*extra)
    def test_finished_round_trip_contains_trimmed_render_only_and_no_private_settings(self):
        before=self.sender.asset(self.source).read_bytes();data_before=copy.deepcopy(self.sender.data)
        vp.export_voicepack(self.sender,self.path,title='Test pack')
        with vp.read_voicepack(self.path) as pack:
            self.assertEqual(pack.manifest['mode'],'finished')
            self.assertNotIn('PRIVATE_GAME_PATH',json.dumps(pack.manifest))
            self.assertEqual(len(pack.manifest['clips']),1)
            receiver=self.recipient();report=vp.import_voicepack(receiver,pack)
        self.assertEqual(report['imported'],1);self.assertTrue(Path(report['backup']).exists())
        imported=receiver.data['clips']['receiver_heal:success']
        self.assertEqual(imported['start'],0);self.assertNotIn('effects',imported)
        raw,rate=load_audio(self.sender.asset(self.source))
        expected=render_audio(raw,rate,.2,.8,.8,False,effects=self.clip['effects'])
        actual,_=load_audio(receiver.asset(imported['source']))
        np.testing.assert_allclose(actual,expected,atol=1/32768)
        self.assertEqual(before,self.sender.asset(self.source).read_bytes());self.assertEqual(self.sender.data,data_before)
    def test_editable_round_trip_preserves_original_and_fx(self):
        vp.export_voicepack(self.sender,self.path,editable=True)
        with vp.read_voicepack(self.path) as pack:
            receiver=self.recipient();vp.import_voicepack(receiver,pack)
        clip=receiver.data['clips']['receiver_heal:success']
        self.assertEqual(clip['effects'],self.clip['effects']);self.assertEqual(clip['start'],.2)
        self.assertEqual(receiver.asset(clip['source']).read_bytes(),self.sender.asset(self.source).read_bytes())
        folder,count=receiver.export(self.root/'game-export',Path(__file__).parent/'addon',game=False)
        self.assertEqual(count,1)
        self.assertIn('635',(folder/'Config.lua').read_text(encoding='utf8'))
        self.assertEqual(len(list((folder/'Audio').glob('*.wav'))),10)
    def test_keep_and_replace_conflicts_back_up_and_preserve_old_originals(self):
        vp.export_voicepack(self.sender,self.path)
        receiver=self.recipient();old=receiver.add_audio(np.ones(16000,dtype='float32')*.1,16000)
        original={'source':old,'start':0,'end':1,'ready':True}
        receiver.data['clips']['receiver_heal:success']=original.copy();receiver.data['success_variations']={'receiver_heal':5};receiver.save()
        before=receiver.path.read_bytes();old_bytes=receiver.asset(old).read_bytes()
        with vp.read_voicepack(self.path) as pack:
            self.assertEqual(vp.inspect_import(receiver,pack)['conflicts'],1)
            self.assertEqual(vp.import_voicepack(receiver,pack)['skipped'],1)
            self.assertEqual(receiver.path.read_bytes(),before)
            report=vp.import_voicepack(receiver,pack,conflict='replace')
        self.assertEqual(Path(report['backup']).read_bytes(),before)
        self.assertEqual(receiver.asset(old).read_bytes(),old_bytes)
        self.assertEqual(receiver.data['success_variations']['receiver_heal'],5)
        self.assertNotEqual(receiver.data['clips']['receiver_heal:success']['source'],old)
    def test_links_and_random_slots_remap_between_different_project_keys(self):
        link=self.sender.add_link('heal','seal','player_aura')
        self.sender.data['clips'][link['key']+':success:3']=copy.deepcopy(self.clip)
        self.sender.data['success_variations']={link['key']:3}
        self.sender.data['clips']['heal:success:2']={**self.clip,'ready':False}
        self.sender.data['clips']['heal:success:5']=copy.deepcopy(self.clip)
        self.sender.save();vp.export_voicepack(self.sender,self.path)
        with vp.read_voicepack(self.path) as pack:
            self.assertEqual(len(pack.manifest['clips']),2)
            receiver=self.recipient();vp.import_voicepack(receiver,pack)
            row=next(r for r in receiver.data['catalog'] if r.get('condition'))
            self.assertEqual(row['base_key'],'receiver_heal');self.assertEqual(row['condition']['source_key'],'receiver_seal')
            self.assertIn(row['key']+':success:3',receiver.data['clips'])
            receiver.data['catalog'][1]['ids'].append(20347);receiver.save()
            old_key=row['key'];receiver.data['catalog'][-1]['condition']['ids'].append(20347);receiver.save()
            report=vp.import_voicepack(receiver,pack)
            self.assertEqual(report['skipped'],2)
            self.assertEqual(len([r for r in receiver.data['catalog'] if r.get('condition')]),1)
            self.assertEqual(next(r['key'] for r in receiver.data['catalog'] if r.get('condition')),old_key)
    def test_scope_and_no_finished_voices(self):
        with self.assertRaises(ValueError):vp.export_voicepack(self.sender,self.path,class_name='MAGE')
        self.sender.data['clips'].clear()
        with self.assertRaises(ValueError):vp.export_voicepack(self.sender,self.path)
    def test_rejects_unsafe_members_and_code(self):
        for name in ['../outside.wav','C:/outside.wav','audio\\outside.wav','addon.lua']:
            vp.export_voicepack(self.sender,self.path);self.rewrite(extra=(name,b'bad'))
            with self.subTest(name=name),self.assertRaises(ValueError):vp.read_voicepack(self.path)
        self.assertFalse((self.root/'outside.wav').exists())
    def test_rejects_bad_metadata_missing_audio_and_size_limit(self):
        mutations=[lambda m:m.update(version=99),lambda m:m['clips'][0].update(slot=6),
                   lambda m:m['clips'][0].update(start=5),lambda m:m['clips'][0].update(effects={'pitch':99}),
                   lambda m:m['catalog'][0].update(ids=[True]),lambda m:m['clips'].append(copy.deepcopy(m['clips'][0])),
                   lambda m:m['clips'][0].update(source='audio/'+'0'*64+'.wav')]
        for modify in mutations:
            vp.export_voicepack(self.sender,self.path);self.rewrite(modify)
            with self.assertRaises(ValueError):vp.read_voicepack(self.path)
        vp.export_voicepack(self.sender,self.path)
        with patch.object(vp,'MAX_TOTAL',20),self.assertRaises(ValueError):vp.read_voicepack(self.path)
    def test_rejects_audio_tampering_duplicate_members_and_symlinks(self):
        vp.export_voicepack(self.sender,self.path)
        with zipfile.ZipFile(self.path) as z:items={n:z.read(n) for n in z.namelist()}
        audio=next(n for n in items if n.startswith('audio/'));items[audio]=items[audio][:-8]+b'changed!'
        with zipfile.ZipFile(self.path,'w') as z:
            for n,data in items.items():z.writestr(n,data)
        with self.assertRaises(ValueError):vp.read_voicepack(self.path)
        vp.export_voicepack(self.sender,self.path)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(self.path,'a') as z:z.writestr('manifest.json',b'{}')
        with self.assertRaises(ValueError):vp.read_voicepack(self.path)
        vp.export_voicepack(self.sender,self.path)
        info=zipfile.ZipInfo('audio/'+'0'*64+'.wav');info.external_attr=0o120777<<16
        with zipfile.ZipFile(self.path,'a') as z:z.writestr(info,b'target')
        with self.assertRaises(ValueError):vp.read_voicepack(self.path)
    def test_failed_commit_rolls_back_new_files_and_memory(self):
        vp.export_voicepack(self.sender,self.path);receiver=self.recipient();before=receiver.path.read_bytes();data=copy.deepcopy(receiver.data)
        with vp.read_voicepack(self.path) as pack,patch.object(vp,'atomic_json',side_effect=OSError('simulated disk error')):
            with self.assertRaises(OSError):vp.import_voicepack(receiver,pack)
        self.assertEqual(receiver.path.read_bytes(),before);self.assertEqual(receiver.data,data)
        self.assertEqual(list((receiver.root/'originals').glob('*.wav')),[])
    def test_stale_project_is_not_overwritten(self):
        vp.export_voicepack(self.sender,self.path);receiver=self.recipient()
        changed=copy.deepcopy(receiver.data);changed['options']['gap']=1
        receiver.path.write_text(json.dumps(changed))
        with vp.read_voicepack(self.path) as pack,self.assertRaises(RuntimeError):vp.import_voicepack(receiver,pack)
        self.assertEqual(json.loads(receiver.path.read_text()),changed)

class VoicePackUITests(unittest.TestCase):
    setUp=fixtures.StudioV02Tests.setUp
    destroy=fixtures.StudioV02Tests.destroy
    select=fixtures.StudioV02Tests.select
    def test_export_and_import_buttons_round_trip_synthetic_voice(self):
        from tkinter import ttk
        import voicepacks_ui as widgets
        def button(window,text):
            def walk(w):
                yield w
                for c in w.winfo_children():yield from walk(c)
            return next(w for w in walk(window) if isinstance(w,ttk.Button) and w.cget('text')==text)
        self.select('Holy Light','PALADIN')
        self.ui.set_take(np.full(44100,.1,dtype='float32'),44100)
        with patch.object(widgets.messagebox,'showinfo'):
            self.ui.save_clip()
            key=self.ui.key();path=Path(self.directory.name)/'shared.voicepack.zip'
            window=self.ui.open_voicepacks()
            with patch.object(widgets.filedialog,'asksaveasfilename',return_value=str(path)):
                button(window,self.ui.bi('音声パックを書き出す','Export voice pack')).invoke()
            self.assertTrue(path.exists());window.destroy()
            self.ui.row=None;self.ui.clip=None;self.ui.audio=None
            self.ui.project.data['clips'].clear();self.ui.project.save()
            window=self.ui.open_voicepacks()
            with patch.object(widgets.filedialog,'askopenfilename',return_value=str(path)):
                button(window,self.ui.bi('パックを選んで確認','Choose and inspect pack')).invoke()
            button(window,self.ui.bi('このプロジェクトへ取り込む','Import into this project')).invoke()
            self.assertIn(key,self.ui.project.data['clips'])
            self.assertFalse(window.winfo_exists())
    def test_sharing_dialog_opens_without_microphone_or_project_audio_writes(self):
        import tkinter as tk
        from tkinter import ttk
        before=self.ui.project.path.read_bytes();w=self.ui.open_voicepacks()
        self.assertIsInstance(w,tk.Toplevel)
        notebook=next(c for c in w.winfo_children() if isinstance(c,ttk.Notebook))
        self.assertEqual(len(notebook.tabs()),2)
        self.assertEqual(self.ui.project.path.read_bytes(),before)
        w.destroy()

if __name__=='__main__':unittest.main()
