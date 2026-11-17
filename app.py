import ctypes, json, os, queue, shutil, sys, time, traceback, tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog
import numpy as np
import sounddevice as sd
from core import Project, EVENTS, load_audio, render_audio, atomic_json
from recording import RecordingController
from i18n import translate
from icons import SpellIcons
from game_paths import detect_game, resolve_game
VERSION = '0.5'
BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
HOME = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'VoiceChantStudio'
CATALOG = json.loads((BASE / 'assets/catalog.json').read_text(encoding='utf-8'))
JP = {'Holy Light': '聖なる光', 'Flash of Light': '光の閃光', 'Judgement': 'ジャッジメント', 'Lay on Hands': 'レイ・オン・ハンズ', 'Divine Shield': 'ディヴァイン・シールド', 'Consecration': '聖別', 'Redemption': '蘇生', 'Blessing of Might': '力の祝福', 'Blessing of Wisdom': '知恵の祝福', 'Blessing of Kings': '王の祝福', 'Holy Strike': 'ホーリー・ストライク'}

class Studio:

    def __init__(self, root):
        try:
            self.preferences = json.loads((HOME / 'settings.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.preferences = {}
        self.language = self.preferences.get('language', 'ja')
        if self.language not in ('ja', 'en'):
            self.language = 'ja'
        self.language_choice = tk.StringVar(value='English' if self.language == 'en' else '日本語')
        self.tail_guard = tk.BooleanVar(value=self.preferences.get('tail_guard', True))
        self.closing = False
        self.last_hotkey = 0
        self.active_event = 'start'
        self.variant = tk.StringVar(value='1')
        self.variant_count = tk.StringVar(value='1')
        self.root = root
        root.title(self.tr('Voice Chant Studio — 自分の声で、魔法を唱える')+' · '+VERSION)
        root.studio_language=self.language
        root.geometry('1240x840')
        root.minsize(1040, 740)
        self.project = Project(HOME / 'Projects/Paladin', CATALOG)
        self.row = None
        self.clip = None
        self.audio = None
        self.rate = 44100
        self.dragging = None
        self.recording = False
        self.stream = None
        self.chunks = []
        self.frames = 0
        self.audio_queue = queue.Queue()
        self.ready = False
        self.loading = False
        self.event = tk.StringVar(value=self.tr(list(EVENTS.values())[0]))
        self.search = tk.StringVar()
        self.assigned_only = tk.BooleanVar()
        self.hide_passive = tk.BooleanVar(value=True)
        initial_class = self.preferences.get('class_filter', '*')
        if initial_class not in {r.get('class') for r in self.project.data['catalog']}:initial_class = self.tr('すべて')
        self.class_filter = tk.StringVar(value=initial_class)
        self.icon_library = SpellIcons(root, BASE / 'assets/icons')
        self.start = tk.DoubleVar(value=0)
        self.end = tk.DoubleVar(value=0)
        self.gain = tk.DoubleVar(value=1)
        self.normalize = tk.BooleanVar(value=False)
        self.game = tk.StringVar(value=self.project.data.get('game') or detect_game())
        self.status = tk.StringVar(value=self.tr('アビリティを選び、「録音」または「音声を読み込む」から始めます。'))
        self.stop_on_cancel = tk.BooleanVar(value=self.project.data['options'].get('stop_on_cancel', True))
        self.gap = tk.DoubleVar(value=self.project.data['options'].get('gap', 0.2))
        self.device_names = []
        self.devices = []
        self.mic = tk.StringVar()
        self.refresh_devices()
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Yu Gothic UI', 10), background='#f5f4ef', foreground='#172c38')
        style.configure('TFrame', background='#f5f4ef')
        style.configure('TLabel', background='#f5f4ef')
        style.configure('Title.TLabel', font=('Yu Gothic UI', 22, 'bold'))
        style.configure('Sub.TLabel', foreground='#657883')
        style.configure('TButton', padding=(12, 8))
        style.configure('Accent.TButton', background='#137c75', foreground='white')
        style.map('Accent.TButton', background=[('active', '#0d625d')])
        style.configure('Treeview', rowheight=30, fieldbackground='white', background='white')
        self.controller = RecordingController(root, on_state=self.on_record_state, on_level=self.on_record_level, on_take=self.on_record_take, on_error=self.on_record_error, on_warning=lambda text: self.status.set(self.tr('録音機器の警告: ') + text))
        self.build()
        self.populate()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(60, self.poll)
        self.root.bind('<F8>', self.toggle_record)

    def tr(self, text):
        return translate(text, self.language)

    def bi(self, ja, en):
        return ja if self.language == 'ja' else en

    def save_preferences(self):
        self.preferences.update(language=self.language, tail_guard=self.tail_guard.get(), class_filter=self.selected_class() or '*')
        atomic_json(HOME / 'settings.json', self.preferences)

    def change_language(self, event=None):
        if self.controller.busy:
            self.language_choice.set('English' if self.language == 'en' else '日本語')
            return
        self.stash()
        phase = self.event_key()
        was_all = self.class_filter.get() == self.tr('すべて')
        self.language = 'en' if self.language_choice.get() == 'English' else 'ja'
        self.save_preferences()
        self.event.set(self.tr(EVENTS[phase]))
        if was_all:
            self.class_filter.set(self.tr('すべて'))
        sd.stop()
        for child in self.root.winfo_children():
            child.destroy()
        self.root.title(self.tr('Voice Chant Studio — 自分の声で、魔法を唱える')+' · '+VERSION)
        self.root.studio_language=self.language
        self.build()
        self.populate()
        if self.row and self.tree.exists(self.row['key']):
            self.tree.selection_set(self.row['key'])
        if self.row:
            self.load_clip()
        self.status.set(self.bi('表示言語を日本語に変更しました。', 'Interface language changed to English.'))

    def ability_label(self, row, combined=False):
        jp = row.get('name_ja') or JP.get(row['name'])
        if self.language == 'ja' and jp:
            return jp + ' / ' + row['name'] if combined else jp
        return row['name']

    def selected_class(self):
        value = self.class_filter.get()
        return None if value in ('*', 'すべて', 'All', self.tr('すべて')) else value

    def class_label(self, token):
        return {'PALADIN':self.bi('パラディン','Paladin'), 'MAGE':self.bi('メイジ','Mage'), 'PRIEST':self.bi('プリースト','Priest')}.get(token, token)

    def icon_for(self, row):
        return self.icon_library.for_row(row)

    def refresh_devices(self):
        self.devices = []
        self.device_names = []
        try:
            default = sd.default.device[0]
            default_index = 0
            for i, d in enumerate(sd.query_devices()):
                if d['max_input_channels'] > 0:
                    if i == default:
                        default_index = len(self.devices)
                    self.devices.append(i)
                    self.device_names.append(f"{i}: {d['name']}")
            if self.device_names:
                self.mic.set(self.device_names[default_index])
            else:
                self.device_names = [self.tr('マイクを認識できません（ファイル読込は使用可）')]
                self.mic.set(self.device_names[0])
        except Exception:
            self.device_names = [self.tr('マイクを認識できません（ファイル読込は使用可）')]
            self.mic.set(self.device_names[0])

    def build(self):
        if not self.devices:
            self.device_names=[self.tr('マイクを認識できません（ファイル読込は使用可）')]
            self.mic.set(self.device_names[0])
        top = ttk.Frame(self.root, padding=(24, 18))
        top.pack(fill='x')
        ttk.Label(top, text='VOICE CHANT STUDIO · '+VERSION, style='Title.TLabel').pack(side='left')
        ttk.Button(top, text=self.tr('使い方'), command=self.help).pack(side='right')
        lang = ttk.Combobox(top, textvariable=self.language_choice, values=['日本語', 'English'], state='readonly', width=10)
        lang.pack(side='right', padx=12)
        lang.bind('<<ComboboxSelected>>', self.change_language)
        ttk.Label(top, text=self.tr('  原音を残して、あなたの詠唱を重ねる。'), style='Sub.TLabel').pack(side='left', padx=10)
        toolbar = ttk.Frame(self.root, padding=(24, 0))
        toolbar.pack(fill='x')
        ttk.Button(toolbar, text=self.tr('プロジェクトを開く'), command=self.open_project).pack(side='left')
        ttk.Button(toolbar, text=self.tr('新規プロジェクト'), command=self.new_project).pack(side='left', padx=8)
        ttk.Button(toolbar, text=self.tr('ゲームの一覧を取り込む'), command=self.import_book).pack(side='left')
        ttk.Button(toolbar, text=self.tr('アビリティを追加'), command=self.add_spell).pack(side='left', padx=8)
        ttk.Button(toolbar, text=self.bi('一覧の出典','Catalog source'), command=self.catalog_source).pack(side='left')
        self.project_label = ttk.Label(toolbar, text=self.project.root.name, style='Sub.TLabel')
        self.project_label.pack(side='right')
        body = ttk.Panedwindow(self.root, orient='horizontal')
        body.pack(fill='both', expand=True, padx=24, pady=15)
        left = ttk.Frame(body, padding=(0, 0, 16, 0))
        right = ttk.Frame(body, padding=(16, 0, 0, 0))
        body.add(left, weight=1)
        body.add(right, weight=3)
        filters = ttk.Frame(left)
        filters.pack(fill='x')
        self.classes = ttk.Combobox(filters, textvariable=self.class_filter, values=['PALADIN', self.tr('すべて')], state='readonly', width=12)
        self.classes.pack(side='left')
        self.classes.bind('<<ComboboxSelected>>', self.change_class)
        ttk.Label(filters, text=self.tr(' 検索 ')).pack(side='left')
        ttk.Entry(filters, textvariable=self.search, width=18).pack(side='left', fill='x', expand=True)
        if hasattr(self, 'search_trace'):
            self.search.trace_remove('write', self.search_trace)
        self.search_trace = self.search.trace_add('write', lambda *_: self.populate())
        ttk.Checkbutton(left, text=self.tr('音声ありだけ表示'), variable=self.assigned_only, command=self.populate).pack(anchor='w', pady=(8, 0))
        ttk.Checkbutton(left, text=self.tr('パッシブを隠す'), variable=self.hide_passive, command=self.populate).pack(anchor='w')
        self.class_hint=ttk.Label(left,style='Sub.TLabel',wraplength=400)
        self.class_hint.pack(anchor='w',pady=(5,0))
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill='both', expand=True, pady=(8, 0))
        self.tree = ttk.Treeview(tree_frame, columns=('class','state'), show='tree headings', selectmode='browse')
        self.tree.heading('#0', text=self.tr('アビリティ / ランクは共通'))
        self.tree.heading('state', text=self.tr('音声'))
        self.tree.heading('class',text=self.bi('クラス','Class'))
        self.tree.column('class',width=60,stretch=False)
        self.tree.column('#0', width=240)
        self.tree.column('state', width=40, stretch=False)
        tree_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        tree_scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.select_row)
        self.count = ttk.Label(left, style='Sub.TLabel')
        self.count.pack(anchor='w', pady=6)
        self.heading = ttk.Label(right, text=self.tr('アビリティを選択'), font=('Yu Gothic UI', 19, 'bold'))
        self.heading.pack(anchor='w')
        self.detail = ttk.Label(right, text=self.tr('初期一覧 + ゲームのスペルブックを取り込んで拡張'), style='Sub.TLabel')
        self.detail.pack(anchor='w', pady=(3, 12))
        phase = ttk.Frame(right)
        phase.pack(fill='x')
        ttk.Label(phase, text=self.tr('声を鳴らすタイミング')).pack(side='left')
        self.phase_box = ttk.Combobox(phase, textvariable=self.event, values=[self.tr(v) for v in EVENTS.values()], state='readonly', width=24)
        self.phase_box.pack(side='left', padx=12)
        self.phase_box.bind('<<ComboboxSelected>>', self.change_phase)
        variants=ttk.Frame(right);variants.pack(fill='x',pady=(4,0))
        ttk.Label(variants,text=self.bi('成功音声数','Success voices')).pack(side='left')
        self.voice_count_box=ttk.Combobox(variants,textvariable=self.variant_count,values=['1','2','3','4','5'],state='readonly',width=3)
        self.voice_count_box.pack(side='left',padx=5);self.voice_count_box.bind('<<ComboboxSelected>>',self.change_variant_count)
        ttk.Label(variants,text=self.bi('録音枠','Voice slot')).pack(side='left')
        self.voice_slot_box=ttk.Combobox(variants,textvariable=self.variant,values=['1'],state='readonly',width=3)
        self.voice_slot_box.pack(side='left',padx=5);self.voice_slot_box.bind('<<ComboboxSelected>>',self.change_variant)
        ttk.Label(variants,text=self.bi('保存済みから均等にランダム再生','Random choice among saved voices'),style='Sub.TLabel').pack(side='left')
        ttk.Label(right, text=self.tr('詠唱のある魔法 → 開始 ／ 瞬間発動 → 発動成功。元の効果音はそのまま。'), style='Sub.TLabel').pack(anchor='w', pady=(8, 10))
        microw = ttk.Frame(right)
        microw.pack(fill='x')
        ttk.Label(microw, text=self.tr('マイク')).pack(side='left')
        self.micbox = ttk.Combobox(microw, textvariable=self.mic, values=self.device_names, state='readonly', width=45)
        self.micbox.pack(side='left', fill='x', expand=True, padx=8)
        self.level = ttk.Progressbar(microw, maximum=1, length=100)
        self.level.pack(side='right')
        actions = ttk.Frame(right)
        actions.pack(fill='x', pady=12)
        self.record_button = ttk.Button(actions, text=self.tr('● 録音'), command=self.record)
        self.record_button.pack(side='left')
        ttk.Button(actions, text=self.tr('■ 停止'), command=self.stop).pack(side='left', padx=6)
        ttk.Button(actions, text=self.tr('音声を読み込む'), command=self.import_audio).pack(side='left')
        ttk.Button(actions, text=self.tr('▶ 選択範囲を試聴'), command=self.preview).pack(side='left', padx=6)
        recopts = ttk.Frame(right)
        recopts.pack(fill='x', pady=(0, 8))
        ttk.Label(recopts, text=self.bi('3秒前から合図音 · F8で録音／停止', '3-second beep countdown · F8 to record / stop'), style='Sub.TLabel').pack(side='left')
        ttk.Checkbutton(recopts, text=self.bi('末尾150msを除く', 'Trim last 150 ms'), variable=self.tail_guard, command=self.save_preferences).pack(side='right')
        self.canvas = tk.Canvas(right, bg='#122b38', height=185, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<Button-1>', self.wave_click)
        self.canvas.bind('<B1-Motion>', self.wave_drag)
        self.canvas.bind('<ButtonRelease-1>', self.wave_release)
        trim_note=ttk.Label(right, text=self.tr('黄色の境界をドラッグして切り出す範囲を指定。元の録音は残ります。'), style='Sub.TLabel')
        trim_note.pack(anchor='w',pady=6)
        trim = ttk.Frame(right)
        trim.pack(fill='x')
        ttk.Label(trim, text=self.tr('開始（秒）')).pack(side='left')
        a = ttk.Spinbox(trim, from_=0, to=600, increment=0.01, textvariable=self.start, width=9, command=self.edit_changed)
        a.pack(side='left', padx=5)
        a.bind('<FocusOut>', lambda e: self.edit_changed())
        ttk.Label(trim, text=self.tr('終了（秒）')).pack(side='left', padx=(10, 0))
        b = ttk.Spinbox(trim, from_=0, to=600, increment=0.01, textvariable=self.end, width=9, command=self.edit_changed)
        b.pack(side='left', padx=5)
        b.bind('<FocusOut>', lambda e: self.edit_changed())
        ttk.Button(trim, text=self.tr('全体に戻す'), command=self.full_range).pack(side='right')
        vol = ttk.Frame(right)
        vol.pack(fill='x', pady=10)
        ttk.Label(vol, text=self.tr('音量')).pack(side='left')
        ttk.Scale(vol, from_=0, to=2, variable=self.gain, command=lambda _: self.edit_changed()).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Checkbutton(vol, text=self.tr('音量をそろえる'), variable=self.normalize, command=self.edit_changed).pack(side='right')
        savebar = ttk.Frame(right)
        savebar.pack(fill='x')
        ttk.Button(savebar, text=self.tr('完成を保存'), style='Accent.TButton', command=self.save_clip).pack(side='left')
        ttk.Button(savebar, text=self.tr('この音声割当を解除'), command=self.remove_clip).pack(side='left', padx=8)
        self.clip_state = ttk.Label(savebar, text=self.tr('未録音'), style='Sub.TLabel')
        self.clip_state.pack(side='right')
        # Keep editing/save controls visible; the waveform takes the spare height.
        for child in [self.canvas,trim_note,trim,vol,savebar]:child.pack_forget()
        savebar.pack(fill='x',side='bottom')
        vol.pack(fill='x',side='bottom',pady=10)
        trim.pack(fill='x',side='bottom')
        trim_note.pack(anchor='w',side='bottom',pady=6)
        self.canvas.pack(fill='both',expand=True)
        bottom = ttk.Frame(self.root, padding=(24, 0, 24, 10))
        bottom.pack(fill='x')
        opts = ttk.Frame(bottom)
        opts.pack(fill='x', pady=(0, 8))
        ttk.Checkbutton(opts, text=self.tr('詠唱を中断したら、追加音声も止める'), variable=self.stop_on_cancel, command=self.save_options).pack(side='left')
        ttk.Label(opts, text=self.tr('連続再生の最小間隔（秒）')).pack(side='left', padx=(18, 5))
        ttk.Spinbox(opts, from_=0, to=5, increment=0.1, textvariable=self.gap, width=5, command=self.save_options).pack(side='left')
        pathrow = ttk.Frame(bottom)
        pathrow.pack(fill='x')
        ttk.Label(pathrow, text='WoW Forever').pack(side='left')
        ttk.Entry(pathrow, textvariable=self.game).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(pathrow, text=self.tr('参照'), command=self.choose_game).pack(side='left')
        ttk.Button(pathrow, text=self.tr('ゲームへ書き出す'), style='Accent.TButton', command=self.export_game).pack(side='left', padx=8)
        ttk.Button(pathrow, text=self.tr('配布用ZIP'), command=self.export_zip).pack(side='right')
        ttk.Label(bottom, text=self.tr('新しい音声ファイルを追加した後は、WoWを完全に終了して起動し直してください。/reload だけでは反映されない場合があります。'), style='Sub.TLabel').pack(anchor='w', pady=(8, 0))
        ttk.Label(self.root, textvariable=self.status, anchor='w', padding=(24, 10), background='#dfece8').pack(fill='x', side='bottom')
        # Reserve the footer before the expanding editor, including on small windows.
        bottom.pack_forget();body.pack_forget()
        bottom.pack(fill='x',side='bottom')
        body.pack(fill='both',expand=True,padx=24,pady=15)

    def event_key(self):
        return next((k for k, v in EVENTS.items() if self.event.get() in (v, self.tr(v))))

    def change_class(self,event=None):
        if self.controller.busy:return
        self.populate();self.save_preferences()

    def catalog_source(self):
        counts={token:sum(r.get('class')==token for r in self.project.data['catalog']) for token in sorted({r.get('class','') for r in self.project.data['catalog']})}
        summary=' / '.join(token+': '+str(count) for token,count in counts.items())
        message=self.bi(
            'WoW Forever用アビリティ一覧\n\n取得元：\n・このPCのForever用「What’s Training?」Camelotクラスデータ\n・Wowheadの /forever/ 専用スペル情報\n・Forever用タレントデータ（同梱の出典レポートに記録）\n\nLesser Heal、Smite、Flash Heal、Holy Fire、Holy NovaはPRIESTです。\n\nこの一覧には未習得のアビリティも含まれます。現在のキャラのスペルブックは、ゲーム内 /voicechant から取り込めます。\n\n',
            'WoW Forever ability catalog\n\nSources:\n• The installed Forever What’s Training? Camelot class data\n• Wowhead /forever/ spell information\n• Forever talent data documented in the bundled source report\n\nLesser Heal, Smite, Flash Heal, Holy Fire and Holy Nova belong to PRIEST.\n\nThe starter catalog includes unlearned abilities. Import your current character’s spellbook using /voicechant in game.\n\n')
        messagebox.showinfo(self.bi('一覧の出典','Catalog source'),message+summary)

    def key(self):
        if not self.row:return None
        suffix=':'+self.variant.get() if self.event_key()=='success' and self.variant.get()!='1' else ''
        return self.row['key'] + ':' + self.event_key()+suffix

    def change_variant(self,event=None):
        if self.controller.busy:return
        self.stash();self.load_clip()

    def change_variant_count(self,event=None):
        if not self.row or self.controller.busy:return
        self.stash()
        self.project.data.setdefault('success_variations',{})[self.row['key']]=int(self.variant_count.get())
        self.project.save();self.load_clip()

    def populate(self):
        if self.controller.busy:return
        old = self.tree.selection()
        self.loading = True
        for i in self.tree.get_children():
            self.tree.delete(i)
        query = self.search.get().casefold()
        count = 0
        classes = sorted({r.get('class', 'PALADIN') for r in self.project.data['catalog']})
        self.classes['values'] = classes + [self.tr('すべて')]
        selected_class=self.selected_class()
        hint=self.class_label(selected_class)+' ('+selected_class+')' if selected_class else self.bi('全クラスを表示。回復・聖魔法はPRIESTにもあります。','All classes. Healing and holy spells also appear under PRIEST.')
        self.class_hint.config(text=hint)
        for row in sorted(self.project.data['catalog'], key=lambda r: r['name']):
            label = self.ability_label(row, combined=True)
            if query and query not in (row['name'] + ' ' + row.get('name_ja', '') + ' ' + JP.get(row['name'], '') + ' ' + ','.join(map(str, row['ids']))).casefold():
                continue
            if selected_class and row.get('class') != selected_class:
                continue
            if self.hide_passive.get() and row.get('passive'):
                continue
            clips = [self.project.data['clips'].get(row['key'] + ':' + e) for e in EVENTS]
            clips += [self.project.data['clips'].get(row['key']+':success:'+str(i)) for i in range(2,int(self.project.data.get('success_variations',{}).get(row['key'],1))+1)]
            ready = sum((bool(c and c.get('ready')) for c in clips))
            if self.assigned_only.get() and (not any(clips)):
                continue
            self.tree.insert('', 'end', iid=row['key'], text=label, image=self.icon_for(row), values=(self.class_label(row.get('class','')),str(ready) + '/'+str(len(clips)) if any(clips) else '—'))
            count += 1
        self.count.config(text=f"{count}{self.tr('項目表示 / 全')}{len(self.project.data['catalog'])}{self.tr('項目')}")
        self.loading = False
        if old and self.tree.exists(old[0]):
            self.tree.selection_set(old[0])
        elif not old:
            self.tree.yview_moveto(0)
        if self.row and (not self.tree.exists(self.row['key'])) and (not self.controller.busy):
            self.stash()
            self.row = None
            self.clip = None
            self.audio = None
            self.ready = False
            self.heading.config(text=self.tr('アビリティを選択'))
            self.detail.config(text='')
            self.update_state()
            self.draw()

    def select_row(self, event=None):
        if self.loading:
            return
        selected = self.tree.selection()
        if not selected:
            return
        if self.controller.busy:
            if self.row and selected[0] != self.row['key'] and self.tree.exists(self.row['key']):
                self.tree.selection_set(self.row['key'])
            return
        self.stash()
        changed = not self.row or self.row['key'] != selected[0]
        self.row = next((r for r in self.project.data['catalog'] if r['key'] == selected[0]))
        if changed:
            self.event.set(self.tr(EVENTS['start' if self.row.get('cast_seconds', 0) > 0 or self.row.get('channeled') else 'success']))
        self.load_clip()

    def change_phase(self, event=None):
        if self.controller.busy:
            self.event.set(self.tr(EVENTS[self.active_event]))
            return
        self.stash()
        self.load_clip()

    def stash(self):
        if not self.row or self.clip is None:
            return
        try:
            self.clip.update(start=float(self.start.get()), end=float(self.end.get()), gain=float(self.gain.get()), normalize=bool(self.normalize.get()), ready=self.ready)
            self.project.save()
        except (ValueError, tk.TclError):
            pass

    def load_clip(self):
        if not self.row:
            return
        number=int(self.project.data.get('success_variations',{}).get(self.row['key'],1))
        self.variant_count.set(str(number))
        self.voice_slot_box['values']=[str(i) for i in range(1,number+1)]
        if int(self.variant.get())>number:self.variant.set('1')
        state='readonly' if self.event_key()=='success' and not self.controller.busy else 'disabled'
        self.voice_slot_box.configure(state=state);self.voice_count_box.configure(state=state)
        sd.stop()
        self.loading = True
        self.audio = None
        self.active_event = self.event_key()
        self.clip = self.project.data['clips'].get(self.key())
        self.ready = bool(self.clip and self.clip.get('ready'))
        self.heading.config(text=self.ability_label(self.row))
        self.detail.config(text=self.row['name'] + '  ·  '+self.row.get('class','')+'  ·  ' + str(len(self.row['ids'])) + self.tr('ランクID') + (self.tr('  ·  パッシブ（詠唱イベントなし）') if self.row.get('passive') else ''))
        if self.clip:
            try:
                self.audio, self.rate = load_audio(self.project.asset(self.clip['source']))
                self.start.set(self.clip['start'])
                self.end.set(self.clip['end'])
                self.gain.set(self.clip.get('gain', 1))
                self.normalize.set(self.clip.get('normalize', False))
            except Exception as e:
                self.status.set(self.tr('音声の読み込みエラー: ') + self.tr(str(e)))
        else:
            self.start.set(0)
            self.end.set(0)
            self.gain.set(1)
            self.normalize.set(False)
        self.loading = False
        self.update_state()
        self.draw()

    def update_state(self):
        self.clip_state.config(text=self.tr('保存済み · 書き出し対象') if self.ready else self.tr('編集中 · 完成を保存してください') if self.audio is not None else self.tr('未録音'))

    def edit_changed(self):
        if self.loading or self.audio is None:
            return
        if self.clip:
            try:
                values = (float(self.start.get()), float(self.end.get()), float(self.gain.get()), bool(self.normalize.get()))
                saved = (self.clip['start'], self.clip['end'], self.clip.get('gain', 1), self.clip.get('normalize', False))
                if values == saved:
                    return
            except (ValueError, tk.TclError):
                return
        self.ready = False
        self.update_state()
        self.draw()

    def set_take(self, data, rate, key=None, suggested_end=None):
        relative = self.project.add_audio(data, rate)
        self.project.data['clips'][key or self.key()] = {'source': relative, 'start': 0, 'end': len(data) / rate if suggested_end is None else suggested_end, 'gain': 1, 'normalize': False, 'ready': False}
        self.project.save()
        self.load_clip()
        self.status.set(self.tr('録音・元ファイルを保存しました。範囲を調整し「完成を保存」を押してください。'))

    def import_audio(self):
        if not self.row:
            messagebox.showinfo(self.tr('アビリティを選択'), self.tr('左の一覧からアビリティを選んでください。'))
            return
        if self.recording:
            return
        p = filedialog.askopenfilename(filetypes=[(self.tr('音声'), '*.wav *.ogg *.flac *.mp3'), (self.tr('すべて'), '*.*')])
        if not p:
            return
        try:
            if self.clip and (not messagebox.askyesno(self.tr('別テイクへ変更'), self.tr('このタイミングの音声を新しいテイクに変更しますか？ 元の録音ファイルは残ります。'))):
                return
            data, rate = load_audio(p)
            self.set_take(data, rate)
        except Exception as e:
            messagebox.showerror(self.tr('読み込みエラー'), self.tr(str(e)))

    def record(self):
        if not self.row:
            messagebox.showinfo(self.tr('アビリティを選択'), self.tr('左の一覧からアビリティを選んでください。'))
            return
        if self.controller.busy:
            return
        if self.clip and (not messagebox.askyesno(self.tr('録り直す'), self.tr('このタイミングの音声を新しい録音に変更しますか？ 元の録音ファイルは残ります。'))):
            return
        try:
            sd.stop()
            if not self.devices:
                raise ValueError(self.tr('マイクを認識できません（ファイル読込は使用可）'))
            device = self.devices[self.device_names.index(self.mic.get())]
            rate = int(sd.query_devices(device)['default_samplerate'])
            self.controller.start(device, rate, context=self.key(), countdown=True, trim_tail_ms=150 if self.tail_guard.get() else 0)
        except Exception as e:
            self.on_record_error(e)

    def toggle_record(self, event=None):
        now = time.monotonic()
        if now - self.last_hotkey < 0.3:
            return 'break'
        self.last_hotkey = now
        if self.controller.busy:
            self.stop()
        else:
            self.record()
        return 'break'

    def on_record_state(self, state, value):
        self.recording = self.controller.busy
        if state == 'countdown':
            self.record_button.config(text=str(value) + '…')
            self.status.set(self.bi(f'録音開始まで {value} 秒 · 停止／F8で中止', f'Recording starts in {value} s · Stop / F8 to cancel'))
        elif state == 'starting':
            self.status.set(self.bi('マイクを準備中…', 'Opening microphone…'))
        elif state == 'recording':
            self.record_button.config(text=self.tr('● 録音中'))
        elif state == 'stopping':
            self.status.set(self.bi('録音を停止して保存中…', 'Stopping and saving recording…'))
        else:
            self.record_button.config(text=self.tr('● 録音'))
            self.level['value'] = 0
            if value == 'cancelled':
                self.status.set(self.bi('録音を開始せずに中止しました。', 'Countdown canceled; microphone was not recorded.'))

    def on_record_level(self, peak, elapsed):
        self.level['value'] = peak
        if self.controller.state == 'recording':
            self.status.set(self.bi(f'録音中 {elapsed:.1f} 秒 · ■ 停止／F8（最大120秒）', f'Recording {elapsed:.1f} s · Stop / F8 (120 s limit)'))

    def on_record_take(self, data, rate, context, suggested_end):
        try:
            self.set_take(data, rate, context, suggested_end)
            self.populate()
        except Exception as e:
            self.on_record_error(e)

    def on_record_error(self, error):
        message = self.tr('録音が短すぎます。もう一度録音してください。') if str(error) == 'recording_too_short' else str(error)
        messagebox.showerror(self.tr('マイクを開けません'), self.tr(message) + self.tr('\nWindowsのマイク許可と入力機器を確認してください。'))

    def poll(self):
        self.controller.poll()
        if self.closing and (not self.controller.busy):
            self.finish_close()
            return
        self.root.after(60, self.poll)

    def stop(self):
        sd.stop()
        self.controller.stop()

    def rendered(self):
        if self.audio is None:
            raise ValueError(self.tr('先に録音するか音声を読み込んでください。'))
        return render_audio(self.audio, self.rate, float(self.start.get()), float(self.end.get()), float(self.gain.get()), self.normalize.get())

    def preview(self):
        if self.recording:
            return
        try:
            data = self.rendered()
            sd.play(data, self.rate)
            self.status.set(f"{self.tr('選択範囲を試聴中（')}{len(data) / self.rate:.2f}{self.tr('秒）。■ 停止で止められます。')}")
        except Exception as e:
            messagebox.showerror(self.tr('試聴できません'), self.tr(str(e)))

    def save_clip(self):
        if self.recording:
            return
        try:
            data = self.rendered()
            self.ready = True
            self.stash()
            self.update_state()
            self.populate()
            self.status.set(f"{self.tr('完成を保存しました。')}{len(data) / self.rate:.2f}{self.tr('秒 / 「ゲームへ書き出す」で反映します。')}")
        except Exception as e:
            messagebox.showerror(self.tr('保存できません'), self.tr(str(e)))

    def remove_clip(self):
        if self.recording or not self.row:
            return
        if self.clip and messagebox.askyesno(self.tr('割当を解除'), self.tr('このタイミングの音声割当を解除しますか？ 元の音声ファイルは残ります。')):
            self.project.data['clips'].pop(self.key(), None)
            self.clip = None
            self.project.save()
            self.load_clip()
            self.populate()

    def full_range(self):
        if self.audio is not None:
            self.start.set(0)
            self.end.set(len(self.audio) / self.rate)
            self.edit_changed()

    def draw(self):
        c = self.canvas
        c.delete('all')
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        if self.audio is None:
            c.create_text(w / 2, h / 2, text=self.tr('あなたの声を録音、または音声ファイルを読み込む'), fill='#a6c6cf', font=('Yu Gothic UI', 12))
            return
        try:
            duration = len(self.audio) / self.rate
            s = float(self.start.get())
            e = float(self.end.get())
        except (ValueError, tk.TclError):
            return
        c.create_rectangle(s / duration * w, 0, e / duration * w, h, fill='#204a53', outline='')
        step = max(1, len(self.audio) // max(1, w))
        points = self.audio[::step][:w]
        for i, v in enumerate(points):
            section = self.audio[i * step:min(len(self.audio), (i + 1) * step)]
            lo = float(np.min(section))
            hi = float(np.max(section))
            c.create_line(i, h / 2 - hi * (h * 0.42), i, h / 2 - lo * (h * 0.42), fill='#68d9c4')
        c.create_line(0, h / 2, w, h / 2, fill='#41636d')
        for t in (s, e):
            c.create_line(t / duration * w, 0, t / duration * w, h, fill='#ffd072', width=3)
        c.create_text(10, 12, anchor='w', text=f"{s:.2f}s → {e:.2f}{self.tr('s  /  全体 ')}{duration:.2f}s", fill='white')

    def wave_click(self, event):
        if self.audio is None or self.recording:
            return
        duration = len(self.audio) / self.rate
        t = max(0, min(duration, event.x / max(1, self.canvas.winfo_width()) * duration))
        self.dragging = 'start' if abs(t - self.start.get()) < abs(t - self.end.get()) else 'end'
        self.wave_drag(event)

    def wave_drag(self, event):
        if self.audio is None or self.dragging is None:
            return
        duration = len(self.audio) / self.rate
        t = max(0, min(duration, event.x / max(1, self.canvas.winfo_width()) * duration))
        if self.dragging == 'start':
            self.start.set(round(min(t, max(0, self.end.get() - 0.03)), 3))
        else:
            self.end.set(round(max(t, min(duration, self.start.get() + 0.03)), 3))
        self.edit_changed()

    def wave_release(self, event):
        self.dragging = None
        self.stash()

    def save_options(self):
        try:
            gap = float(self.gap.get())
            if not 0 <= gap <= 5:
                raise ValueError(self.tr('間隔は0〜5秒です。'))
            self.project.data['options'].update(gap=gap, stop_on_cancel=self.stop_on_cancel.get())
            self.project.data['game'] = self.game.get()
            self.project.save()
            return True
        except (ValueError, tk.TclError) as e:
            messagebox.showerror(self.tr('設定エラー'), self.tr(str(e)))
            return False

    def choose_game(self):
        messagebox.showinfo('WoW Forever',self.bi('Battle.netの歯車 → エクスプローラーで表示、からゲームの場所を確認できます。\n次の画面で Wow.exe がある _forever_、またはその親フォルダを選んでください。','Find your game using Battle.net → gear menu → Show in Explorer.\nSelect the _forever_ folder containing Wow.exe, or its parent folder.'))
        p = filedialog.askdirectory(title=self.tr('WoWの _forever_ フォルダを選択'))
        if p:
            found=resolve_game(p)
            if not found:
                messagebox.showerror('WoW Forever',self.bi('Wow.exeがある _forever_ フォルダが見つかりません。RetailやAddOnsフォルダではなく、Foreverのインストール場所を確認してください。','No _forever_ folder containing Wow.exe was found. Select the Forever installation, not Retail.'))
                return
            self.game.set(found)
            self.save_options()

    def export_game(self):
        if self.recording:
            messagebox.showinfo(self.tr('録音中'), self.tr('録音を停止してから書き出してください。'))
            return
        self.stash()
        if not self.save_options():return
        if not self.game.get():
            self.choose_game()
        if not self.game.get():
            return
        try:
            path, count = self.project.export(self.game.get(), BASE / 'addon')
            messagebox.showinfo(self.tr('書き出しました'), f"{count}{self.tr('件の保存済み音声を書き出しました。\n\n')}{path}{self.tr('\n\nWoWを完全に終了して再起動し、AddOnsで Voice Chant Studio を有効にしてください。\n\n/voicechant test で最初の音声を試聴できます。\nゲーム本来の効果音はそのまま残ります。')}")
            self.status.set(f"{self.tr('ゲームへ書き出しました：')}{count}{self.tr('件。WoWを完全に再起動してください。')}")
        except Exception as e:
            messagebox.showerror(self.tr('書き出しできません'), self.tr(str(e)) + self.tr('\nProgram Filesへの書き込みが拒否された場合はアプリを管理者として起動するか、配布用ZIPから手動コピーしてください。'))

    def export_zip(self):
        import tempfile, zipfile
        if self.recording:
            return
        self.stash()
        if not self.save_options():return
        p = filedialog.asksaveasfilename(defaultextension='.zip', initialfile='VoiceChantStudio-Addon.zip', filetypes=[('ZIP', '*.zip')])
        if not p:
            return
        try:
            with tempfile.TemporaryDirectory() as d:
                folder, count = self.project.export(d, BASE / 'addon', game=False)
                with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in folder.rglob('*'):
                        if f.is_file():
                            z.write(f, str(Path(folder.name) / f.relative_to(folder)))
            self.status.set(f"{self.tr('配布用ZIPを保存しました（')}{count}{self.tr('音声）。友人はAddOnsへ展開できます。')}")
        except Exception as e:
            messagebox.showerror(self.tr('ZIP作成エラー'), self.tr(str(e)))

    def switch_project(self, directory):
        if self.controller.busy:
            self.status.set(self.bi('録音を停止してからプロジェクトを切り替えてください。', 'Stop recording before switching projects.'))
            return
        self.stash()
        try:
            p = Project(directory, CATALOG)
            self.project = p
            self.row = None
            self.clip = None
            self.audio = None
            self.ready = False
            self.game.set(p.data.get('game') or detect_game())
            self.stop_on_cancel.set(p.data['options'].get('stop_on_cancel', True))
            self.gap.set(p.data['options'].get('gap', 0.2))
            self.project_label.config(text=p.root.name)
            self.populate()
            self.draw()
            self.update_state()
            self.status.set(str(p.root))
        except Exception as e:
            messagebox.showerror(self.tr('プロジェクトを開けません'), self.tr(str(e)))

    def open_project(self):
        p = filedialog.askopenfilename(title=self.tr('project.json を選択'), filetypes=[(self.tr('Voice Chant プロジェクト'), 'project.json')])
        if p:
            self.switch_project(Path(p).parent)

    def new_project(self):
        p = filedialog.askdirectory(title=self.tr('新規プロジェクトを保存するフォルダ'))
        if p:
            self.switch_project(p)

    def import_book(self):
        window = tk.Toplevel(self.root)
        window.title(self.tr('ゲームのアビリティ一覧を取り込む'))
        window.geometry('720x440')
        ttk.Label(window, text=self.tr('ゲーム内で /voicechant → Ctrl+A / Ctrl+C → 下に貼り付け。\nゲームから取得したランクIDを既存のアビリティにまとめます。'), padding=16).pack(fill='x')
        text = tk.Text(window, wrap='word', font=('Consolas', 10))
        text.pack(fill='both', expand=True, padx=16)

        def run():
            try:
                self.stash()
                n = self.project.merge_catalog(json.loads(text.get('1.0', 'end')))
                self.populate()
                window.destroy()
                self.status.set(f"{self.tr('一覧を更新しました。')}{n}{self.tr('項目追加。')}")
            except Exception as e:
                messagebox.showerror(self.tr('取り込みエラー'), self.tr(str(e)), parent=window)
        ttk.Button(window, text=self.tr('一覧を取り込む'), command=run).pack(pady=12)

    def add_spell(self):
        if self.controller.busy:return
        window=tk.Toplevel(self.root);window.title(self.tr('アビリティを追加'));window.geometry('540x270');window.transient(self.root)
        form=ttk.Frame(window,padding=20);form.pack(fill='both',expand=True)
        token=tk.StringVar(value=self.selected_class() or (self.row or {}).get('class',''))
        sid=tk.StringVar();name=tk.StringVar()
        for label,var in [(self.bi('クラス','Class'),token),('Spell ID',sid),(self.bi('ゲーム内の英語名','English in-game name'),name)]:
            line=ttk.Frame(form);line.pack(fill='x',pady=5)
            ttk.Label(line,text=label,width=20).pack(side='left')
            if var is token:
                ttk.Combobox(line,textvariable=token,values=sorted({r.get('class','PALADIN') for r in self.project.data['catalog']}),state='readonly',width=25).pack(side='left',fill='x',expand=True)
            else:ttk.Entry(line,textvariable=var).pack(side='left',fill='x',expand=True)
        def save():
            try:
                if not token.get():raise ValueError(self.bi('クラスを選択してください。','Select a class.'))
                self.stash()
                self.project.merge_catalog([{'id':sid.get(),'name':name.get(),'class':token.get()}])
                self.class_filter.set(token.get());self.search.set('');self.assigned_only.set(False);self.populate()
                row=next(r for r in self.project.data['catalog'] if r.get('class')==token.get() and int(sid.get()) in r['ids'])
                self.tree.selection_set(row['key']);self.tree.see(row['key']);self.select_row();self.save_preferences();window.destroy()
            except Exception as error:messagebox.showerror(self.tr('エラー'),self.tr(str(error)),parent=window)
        ttk.Button(form,text=self.tr('アビリティを追加'),command=save,style='Accent.TButton').pack(pady=(18,0))

    def help(self):
        messagebox.showinfo(self.tr('使い方'),self.bi(
            '① PALADIN / MAGE / PRIEST を選び、アビリティを選択\n② 詠唱開始 / 発動成功 / 中断のタイミングを選択\n③ 録音またはF8 → 3回の合図の後に録音開始\n④ ■ 停止またはF8で終了。カウントダウン中なら中止\n⑤ 黄色の境界で前後をカットし、選択範囲を試聴\n⑥ 完成を保存 → ゲームへ書き出す → WoWを完全に再起動\n\nF8はこのアプリにフォーカスがある間に使えます。\n末尾150msを除く設定は停止クリック音を避ける初期範囲です。\n声の末尾まで切れた場合は「全体に戻す」で調整してください。\n切り取りは非破壊で、元の録音はこのPCに残ります。\n右上の日本語 / Englishで表示言語を切り替えます。\n\n/voicechant：アビリティ一覧の取り込み用\n/voicechant test：追加音声の試聴\n/voicechant mute / unmute：追加音声だけ切替\n\nゲームの原音は残ります。音声はアップロードしません。\n他のプレイヤーに音声は自動で届きません。',
            '1. Choose PALADIN / MAGE / PRIEST, then an ability.\n2. Choose Cast start / Successful cast / Interrupted.\n3. Record or F8: recording begins after three countdown beeps.\n4. Stop or F8 ends the take; during countdown it cancels.\n5. Drag the yellow boundaries to trim, then preview the selection.\n6. Save finished clip → Export to game → fully restart WoW.\n\nF8 works while this app has focus.\nTrim last 150 ms sets an initial end marker to avoid a stop click.\nIf it cuts off your voice, use Full range and adjust the marker.\nTrimming preserves the complete original recording on this PC.\nUse Japanese / English at the top right to switch languages.\n\n/voicechant: copy the game ability list for import\n/voicechant test: preview an extra voice clip\n/voicechant mute / unmute: toggle extra voice only\n\nOriginal game effects remain audible. Nothing is uploaded.\nOther players do not automatically hear your voice clips.'))

    def close(self):
        self.closing = True
        sd.stop()
        if self.controller.busy:
            self.controller.stop()
        else:
            self.finish_close()

    def finish_close(self):
        self.stash()
        self.save_preferences()
        self.controller.close()
        self.root.destroy()

def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()

    def report(exc, value, tb):
        HOME.mkdir(parents=True, exist_ok=True)
        (HOME / 'last-error.txt').write_text(''.join(traceback.format_exception(exc, value, tb)), encoding='utf-8')
        messagebox.showerror(translate('エラー',getattr(root,'studio_language','ja')), str(value) + '\n' + str(HOME / 'last-error.txt'))
    root.report_callback_exception = report
    Studio(root)
    root.mainloop()
if __name__ == '__main__':
    main()
