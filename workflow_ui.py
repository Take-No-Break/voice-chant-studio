"""Bilingual workflow tools. All destructive choices are previewed and reversible."""
import copy,threading,queue,zipfile,tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
import sounddevice as sd
from core import load_audio,render_audio,EVENTS
from studio_workflow import presets,save_preset,apply_preset,finish_many,backups,diagnostics,analyze,export_plan,link_choice,game_audio_usage,archive_unused_audio

def centered(ui,title,width=920,height=660,modal=True):
    w=tk.Toplevel(ui.root);w.title(title);w.transient(ui.root)
    ui.root.update_idletasks()
    x=ui.root.winfo_rootx()+max(0,(ui.root.winfo_width()-width)//2)
    y=ui.root.winfo_rooty()+max(0,(ui.root.winfo_height()-height)//2)
    w.geometry(f'{width}x{height}+{x}+{y}')
    if modal:w.grab_set()
    return w
def reload_editor(ui):
    if ui.row:
        key=ui.row['key'];ui.row=next((r for r in ui.project.data['catalog'] if r['key']==key),None)
    ui.clip=None;ui.audio=None;ui.ready=False
    ui.populate()
    if ui.row:ui.load_clip()
    else:ui.draw();ui.update_state()

def export_with_progress(ui,destination,template,game=True,zip_path=None):
    if getattr(ui,'export_busy',False):return
    plan=export_plan(ui.project)
    text=ui.bi('書き出し確認','Export review')+f"\n{plan['finished']} finished · {plan['excluded']} draft/disabled · ~{plan['bytes']/1024**2:.1f} MiB\n"+'\n'.join(plan['errors'])
    if plan['errors']:messagebox.showerror('Export',text);return
    if not messagebox.askyesno('Voice Chant Studio',text+'\n'+ui.bi('書き出しますか？','Continue?')):return
    w=centered(ui,ui.bi('書き出し中','Exporting'),500,180);ui.export_busy=True
    label=ttk.Label(w,text=ui.bi('音声を加工しています。完了までお待ちください。','Rendering voices. Please wait.'));label.pack(padx=20,pady=20)
    progress=ttk.Progressbar(w,mode='indeterminate');progress.pack(fill='x',padx=20);progress.start()
    w.protocol('WM_DELETE_WINDOW',lambda:None)
    events=queue.Queue();project=ui.project
    def worker():
        try:
            if zip_path:
                with tempfile.TemporaryDirectory() as tmp:
                    folder,count=project.export(tmp,template,game=False,progress=lambda n:events.put(('progress',n)))
                    path=Path(zip_path);staged=path.with_suffix('.building')
                    try:
                        with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED) as z:
                            for f in folder.rglob('*'):
                                if f.is_file():z.write(f,folder.name+'/'+f.relative_to(folder).as_posix())
                        staged.replace(path)
                    finally:
                        if staged.exists():staged.unlink()
                    result=(path,count)
            else:result=project.export(destination,template,game=game,progress=lambda n:events.put(('progress',n)))
            events.put(('done',result))
        except Exception as e:events.put(('error',str(e)))
    def poll():
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='progress':label.config(text=f"{value} / {plan['finished']} — "+ui.bi('音声を加工中','Rendering voices'))
                else:
                    progress.stop();w.destroy();ui.export_busy=False
                    if kind=='error':messagebox.showerror('Export',value)
                    else:
                        path,count=value;ui.status.set(str(count)+ui.bi('件を書き出しました：',' voices exported: ')+str(path))
                        messagebox.showinfo('Export',str(path)+'\n'+ui.bi('新しい音声を使うにはWoWを完全に再起動してください。','Fully restart WoW to load new audio files.'))
                    return
        except queue.Empty:ui.root.after(100,poll)
    threading.Thread(target=worker,daemon=True).start();ui.root.after(100,poll)
    return w

def open_tools(ui):
    if ui.controller.busy or getattr(ui,'export_busy',False):return
    ui.stash();w=centered(ui,ui.bi('制作ツール','Studio tools'))
    tabs=ttk.Notebook(w);tabs.pack(fill='both',expand=True,padx=12,pady=12)
    def tab(ja,en):
        frame=ttk.Frame(tabs,padding=14);tabs.add(frame,text=ui.bi(ja,en));return frame
    def guarded(fn):
        def call():
            try:return fn()
            except Exception as e:messagebox.showerror('Studio tools',str(e),parent=w)
        return call
    rows=[r for r in ui.project.data['catalog'] if not ui.selected_class() or r['class']==ui.selected_class()]
    # Presets: explicit multi-selection and separate completion to avoid exporting drafts.
    p=tab('声のプリセット','Voice presets')
    ttk.Label(p,text=ui.bi('複数選択：Ctrl / Shift。元の録音は変更しません。適用後は未完成になります。','Ctrl / Shift selects multiple abilities. Originals stay intact; applying FX marks clips as drafts.')).pack(anchor='w')
    preset=tk.StringVar(value=next(iter(presets(ui.project))))
    combo=ttk.Combobox(p,textvariable=preset,values=list(presets(ui.project)),state='readonly');combo.pack(fill='x',pady=8)
    tree=ttk.Treeview(p,columns=('class','voices'),show='tree headings',selectmode='extended',height=10)
    tree.heading('#0',text=ui.bi('対象の技','Target abilities'));tree.heading('class',text='Class');tree.heading('voices',text='Voices')
    tree.column('#0',width=440);tree.column('class',width=110);tree.column('voices',width=65)
    scroll=ttk.Scrollbar(p,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');tree.pack(fill='both',expand=True)
    for r in rows:
        count=sum(k.split(':')[0]==r['key'] for k in ui.project.data['clips'])
        if count:tree.insert('', 'end',iid=r['key'],text=ui.ability_label(r,True),values=(r['class'],count))
    if ui.row and tree.exists(ui.row['key']):tree.selection_set(ui.row['key'])
    result=ttk.Label(p);result.pack(anchor='w',pady=8)
    controls=ttk.Frame(p);controls.pack(fill='x')
    def apply():
        if not tree.selection():raise ValueError('Select abilities / 技を選んでください')
        count=apply_preset(ui.project,preset.get(),tree.selection());reload_editor(ui);result.config(text=f'{count} '+ui.bi('音声へ適用。下の「完成を保存」で確定できます。','voices updated. Save finished below when ready.'))
    def save():
        if not ui.clip:raise ValueError('Select a recorded voice first')
        name=simpledialog.askstring('Preset',ui.bi('現在のFX設定の名前','Name for the current voice FX settings'),parent=w)
        if name:
            save_preset(ui.project,name,ui.clip.get('effects',{}));combo['values']=list(presets(ui.project));preset.set(name)
    def finish():
        if not tree.selection():raise ValueError('Select abilities')
        if messagebox.askyesno('Save finished',ui.bi('選択した技のすべての録音枠を検証して完成として保存しますか？','Validate and mark all recorded slots of selected abilities as finished?'),parent=w):
            result.config(text=str(finish_many(ui.project,tree.selection()))+' finished');reload_editor(ui)
    ttk.Button(controls,text=ui.bi('選択した技へ適用','Apply to selected'),command=guarded(apply),style='Accent.TButton').pack(side='left')
    ttk.Button(controls,text=ui.bi('現在のFXをプリセット保存','Save current FX preset'),command=guarded(save)).pack(side='left',padx=6)
    ttk.Button(controls,text=ui.bi('選択した技の完成を保存','Save selected finished'),command=guarded(finish)).pack(side='left')
    ttk.Button(controls,text=ui.bi('全選択','Select all'),command=lambda:tree.selection_set(tree.get_children())).pack(side='left',padx=6)
    def preview_preset():
        if not tree.selection():raise ValueError('Select an ability')
        clip=next(c for k,c in ui.project.data['clips'].items() if k.split(':')[0]==tree.selection()[0])
        audio,rate=load_audio(ui.project.asset(clip['source']))
        sd.play(render_audio(audio,rate,clip['start'],clip['end'],clip.get('gain',1),clip.get('normalize',False),effects=presets(ui.project)[preset.get()]),rate)
    ttk.Button(p,text=ui.bi('プリセットを試聴（変更しない）','Preview preset (without changes)'),command=guarded(preview_preset)).pack(anchor='w',pady=6)
    ttk.Label(p,text=ui.bi('「音声FX / EQ」で自分好みに調整してから、ここでプリセット保存できます。','Adjust a voice in Voice FX / EQ, then save its settings here as a reusable preset.'),wraplength=820).pack(anchor='w',pady=8)
    # Assisted recording: explicit start/stop only; no automatic microphone activation.
    r=tab('録音アシスト','Recording assistant')
    labels=[ui.ability_label(row,True) for row in rows if not row.get('passive')];record_rows=[row for row in rows if not row.get('passive')]
    chosen=tk.StringVar(value=labels[0] if labels else '')
    select=ttk.Combobox(r,values=labels,textvariable=chosen,state='readonly');select.pack(fill='x')
    phase=tk.StringVar(value='start');ttk.Combobox(r,values=list(EVENTS),textvariable=phase,state='readonly',width=14).pack(anchor='w',pady=8)
    ttk.Label(r,text=ui.bi('詠唱文（この技に保存されます）','Chant script (saved for this ability)')).pack(anchor='w')
    script=tk.Text(r,height=6,font=('Yu Gothic UI',18),wrap='word',background='#15191b',foreground='#eee0bf',insertbackground='#e9bf6a');script.pack(fill='both',expand=True,pady=8)
    current=[None]
    def save_script():
        if current[0]:ui.project.data.setdefault('scripts',{})[current[0]['key']]=script.get('1.0','end').strip();ui.project.save()
    def load_script(*_):
        if ui.controller.busy:
            chosen.set(ui.ability_label(current[0],True));return
        save_script();current[0]=record_rows[labels.index(chosen.get())]
        script.delete('1.0','end');script.insert('1.0',ui.project.data.get('scripts',{}).get(current[0]['key'],''))
    if labels:load_script()
    select.bind('<<ComboboxSelected>>',load_script)
    quality=ttk.Label(r,wraplength=820);quality.pack(anchor='w',pady=8)
    def record():
        if ui.controller.busy:return
        save_script();ui.stash();ui.search.set('');ui.assigned_only.set(False);ui.hide_passive.set(False);ui.populate()
        row=current[0];ui.tree.selection_set(row['key']);ui.select_row();ui.event.set(ui.tr(EVENTS[phase.get()]));ui.change_phase();ui.record()
    def next_voice():
        if ui.controller.busy:raise ValueError('Stop recording first')
        save_script();index=(labels.index(chosen.get())+1)%len(labels);chosen.set(labels[index]);load_script()
    def save_record():
        if not ui.row or ui.row['key']!=current[0]['key']:raise ValueError('Record or load this ability in the editor before saving. / 対象の技を録音してから保存してください。')
        ui.save_clip()
    buttons=ttk.Frame(r);buttons.pack(fill='x',pady=8)
    for ja,en,fn in [('録音（3秒カウント）','Record (3-second countdown)',record),('停止','Stop',ui.stop),('完成を保存','Save finished',save_record),('次の技','Next ability',next_voice)]:
        ttk.Button(buttons,text=ui.bi(ja,en),command=guarded(fn)).pack(side='left',padx=3)
    ttk.Label(r,text=ui.bi('録音はボタンを押した時だけ開始します。成功の複数枠はメイン画面で選びます。','Recording starts only when you press Record. Choose success variation slots in the main editor.'),wraplength=820).pack(anchor='w')
    def meter():
        if not w.winfo_exists():return
        if ui.controller.busy:quality.config(text=ui.status.get())
        else:quality.config(text=analyze(ui.audio,ui.rate))
        w.after(400,meter)
    meter()
    # Read-only conditions simulator.
    s=tab('連携テスト','Link simulator')
    links=[row for row in rows if row.get('condition')]
    linklabels=[ui.ability_label(row,True) for row in links]
    link=tk.StringVar(value=linklabels[0] if links else '')
    ttk.Combobox(s,values=linklabels,textvariable=link,state='readonly').pack(fill='x',pady=8)
    active=tk.BooleanVar(value=True);elapsed=tk.DoubleVar(value=0)
    ttk.Checkbutton(s,text=ui.bi('条件のバフ/デバフ/直前の技が有効','Condition buff/debuff/previous spell is present'),variable=active).pack(anchor='w',pady=8)
    ttk.Label(s,text=ui.bi('直前の技からの秒数','Seconds since previous spell')).pack(anchor='w')
    ttk.Spinbox(s,from_=0,to=60,textvariable=elapsed).pack(anchor='w',pady=8)
    simphase=tk.StringVar(value='success');ttk.Combobox(s,values=list(EVENTS),textvariable=simphase,state='readonly').pack(anchor='w',pady=8)
    simresult=ttk.Label(s,wraplength=820);simresult.pack(anchor='w',pady=20)
    selected_clips=[[]]
    def simulate():
        if not links:raise ValueError('Create a spell link first')
        row=links[linklabels.index(link.get())];c=row['condition'];ids=c['ids'] if active.get() else []
        chosen_row,clips=link_choice(ui.project,row['base_key'],simphase.get(),ids if c['kind']=='player_aura' else [],ids if c['kind']=='target_aura' else [],ids[0] if ids and c['kind']=='previous_spell' else None,float(elapsed.get()))
        selected_clips[0]=clips;simresult.config(text=chosen_row['name']+(' [LINK]' if chosen_row.get('condition') else ' [normal / 通常]')+'\n'+str(len(clips))+' voices · '+simphase.get()+'\n'+ui.bi('複数条件では最初に一致した音声付きリンクが優先です。ゲームの実イベント検証は別途必要です。','The first matching link with a finished voice wins. Live game event verification is separate.'))
    def preview_link():
        simulate()
        if selected_clips[0]:
            clip=selected_clips[0][0];audio,rate=load_audio(ui.project.asset(clip['source']));sd.play(render_audio(audio,rate,clip['start'],clip['end'],clip.get('gain',1),clip.get('normalize',False),effects=clip.get('effects')),rate)
    ttk.Button(s,text=ui.bi('条件を試す','Simulate condition'),command=guarded(simulate)).pack(anchor='w',pady=8)
    ttk.Button(s,text=ui.bi('選ばれる声を試聴','Preview chosen voice'),command=guarded(preview_link)).pack(anchor='w')
    # Diagnostics, history and reversible storage management.
    d=tab('診断・復元・容量','Diagnostics / Restore')
    info=tk.Text(d,height=10,wrap='word',background='#15191b',foreground='#eee0bf');info.pack(fill='both',expand=True)
    def refresh():
        info.configure(state='normal');info.delete('1.0','end');info.insert('1.0',diagnostics(ui.project));info.configure(state='disabled')
        paths[:]=backups(ui.project);backupbox['values']=[p.parent.name+'/'+p.name for p in paths]
        if paths:backupbox.current(0)
    paths=[];backupbox=ttk.Combobox(d,state='readonly');backupbox.pack(fill='x',pady=10)
    def restore():
        if backupbox.current()<0:raise ValueError('No project backups available')
        if messagebox.askyesno('Restore',ui.bi('選んだ時点に設定と録音割り当てを戻します。現在の状態も履歴に残します。続けますか？','Restore settings and assignments from this snapshot? Current settings are also saved to history.'),parent=w):
            ui.project.restore(paths[backupbox.current()]);ui.row=None;reload_editor(ui);refresh()
    def storage():
        folder,used,unused=game_audio_usage(ui.project)
        messagebox.showinfo('Audio storage',f"Used: {len(used)} / {sum(p.stat().st_size for p in used)/1024**2:.1f} MiB\nUnused: {len(unused)} / {sum(p.stat().st_size for p in unused)/1024**2:.1f} MiB\n{folder}",parent=w)
    def cleanup():
        folder,used,unused=game_audio_usage(ui.project)
        if not unused:messagebox.showinfo('Audio storage','No unused audio files',parent=w);return
        if messagebox.askyesno('Archive unused audio',str(len(unused))+ui.bi('個の未使用ファイルをプロジェクト内へ退避します。WoWを完全に終了してから続けてください。\n実行しますか？',' unused files will move into the project archive. Fully exit WoW before continuing.\nContinue?'),parent=w):
            target,n=archive_unused_audio(ui.project);messagebox.showinfo('Archived',str(n)+' files\n'+str(target),parent=w)
    controls=ttk.Frame(d);controls.pack(fill='x')
    for ja,en,fn in [('再診断','Refresh',refresh),('選択した履歴へ復元','Restore snapshot',restore),('ゲーム音声の容量','Game audio storage',storage),('未使用音声を退避','Archive unused audio',cleanup)]:ttk.Button(controls,text=ui.bi(ja,en),command=guarded(fn)).pack(side='left',padx=3)
    refresh()
    m=tab('パック・録音管理','Packs / Recordings')
    from voicepacks import remove_pack
    packtree=ttk.Treeview(m,show='tree',height=5);packtree.pack(fill='x',pady=8)
    packinfo=ttk.Label(m,wraplength=820);packinfo.pack(anchor='w',pady=6)
    def refresh_packs():
        packtree.delete(*packtree.get_children())
        for pid,receipt in ui.project.data.get('voicepacks',{}).items():packtree.insert('', 'end',iid=pid,text=receipt['title']+' / '+receipt.get('author','')+' / '+str(len(receipt['installed']))+' voices')
    def pack_detail(*_):
        if packtree.selection():
            receipt=ui.project.data['voicepacks'][packtree.selection()[0]];packinfo.config(text=receipt.get('description',''))
    packtree.bind('<<TreeviewSelect>>',pack_detail)
    def uninstall():
        if not packtree.selection():raise ValueError('Select a voice pack')
        if messagebox.askyesno('Remove voice pack',ui.bi('このパックの割り当てを取り込み前に戻します。取り込み後に編集した枠と元録音は残します。続けますか？','Restore assignments replaced by this pack? Slots edited after import and original recordings are preserved.'),parent=w):
            report=remove_pack(ui.project,packtree.selection()[0]);reload_editor(ui);refresh_packs();refresh_clips();packinfo.config(text=str(report))
    ttk.Button(m,text=ui.bi('パックの割り当てを戻す','Remove pack assignments'),command=guarded(uninstall)).pack(anchor='w',pady=6)
    cliplist=ttk.Treeview(m,show='tree',height=6,selectmode='extended');cliplist.pack(fill='both',expand=True,pady=8)
    def refresh_clips():
        cliplist.delete(*cliplist.get_children());names={r['key']:r['name'] for r in ui.project.data['catalog']}
        for key,clip in ui.project.data['clips'].items():cliplist.insert('', 'end',iid=key,text=('ON · ' if clip.get('enabled',True) else 'OFF · ')+names.get(key.split(':')[0],key)+' · '+':'.join(key.split(':')[1:])+(' · finished' if clip.get('ready') else ' · draft'))
    def toggle_clips(value):
        ui.stash()
        for key in cliplist.selection():ui.project.data['clips'][key]['enabled']=value
        ui.project.save();reload_editor(ui);refresh_clips()
    controls=ttk.Frame(m);controls.pack(fill='x')
    ttk.Button(controls,text=ui.bi('選択した声を有効','Enable selected'),command=guarded(lambda:toggle_clips(True))).pack(side='left')
    ttk.Button(controls,text=ui.bi('選択した声を無効','Disable selected'),command=guarded(lambda:toggle_clips(False))).pack(side='left',padx=8)
    ttk.Label(m,text=ui.bi('成功枠はメイン画面の音声数の範囲内で、有効かつ完成済みの時だけ出力します。','Success voices export only within the enabled slot count, with ON and finished status.'),wraplength=820).pack(anchor='w',pady=8)
    refresh_packs();refresh_clips()
    # Keep recording ownership on close; never destroy a running capture's script UI.
    def close():
        if ui.controller.busy:messagebox.showinfo('Recording',ui.bi('録音を停止してから閉じてください。','Stop recording before closing.'),parent=w);return
        save_script();sd.stop();w.destroy()
    w.protocol('WM_DELETE_WINDOW',close)
    return w
