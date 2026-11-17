"""Explicit local sharing; no automatic uploads and no game/account data in packs."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from voicepacks import export_voicepack,selected_clips,read_voicepack,inspect_import,import_voicepack

def open_voicepacks(ui):
    if ui.controller.busy:return
    ui.stash()
    window=tk.Toplevel(ui.root);window.title(ui.bi('音声パック共有','Voice packs'));window.transient(ui.root)
    ui.root.update_idletasks()
    x=ui.root.winfo_rootx()+max(0,(ui.root.winfo_width()-740)//2)
    y=ui.root.winfo_rooty()+max(0,(ui.root.winfo_height()-530)//2)
    window.geometry(f'740x530+{x}+{y}');window.resizable(False,False)
    window.grab_set()
    tabs=ttk.Notebook(window);tabs.pack(fill='both',expand=True,padx=16,pady=16)
    send=ttk.Frame(tabs,padding=16);receive=ttk.Frame(tabs,padding=16)
    tabs.add(send,text=ui.bi('送る：エクスポート','Send: export'));tabs.add(receive,text=ui.bi('受け取る：インポート','Receive: import'))
    scope_names=[ui.bi('すべての保存済み音声','All saved voices'),ui.bi('表示中のクラス','Current class'),ui.bi('選択中のアビリティ','Selected ability')]
    scope=tk.StringVar(value=scope_names[1] if ui.selected_class() else scope_names[0])
    title=tk.StringVar(value='Voice pack');editable=tk.BooleanVar(value=False)
    ttk.Label(send,text=ui.bi('パック名（共有先に表示されます）','Pack title (visible to the recipient)')).pack(anchor='w')
    ttk.Entry(send,textvariable=title).pack(fill='x',pady=(4,12))
    ttk.Label(send,text=ui.bi('共有する範囲','Voices to share')).pack(anchor='w')
    box=ttk.Combobox(send,textvariable=scope,values=scope_names,state='readonly');box.pack(fill='x',pady=4)
    summary=ttk.Label(send,wraplength=660);summary.pack(anchor='w',pady=10)
    def selection():
        index=scope_names.index(scope.get())
        if index==1:
            token=ui.selected_class() or (ui.row or {}).get('class')
            if not token:raise ValueError(ui.bi('クラスを選択するか、すべての保存済み音声を選んでください。','Select a class, or choose All saved voices.'))
            return {'class_name':token}
        if index==2:
            if not ui.row:raise ValueError(ui.bi('共有するアビリティを先に選択してください。','Select an ability before opening Voice packs.'))
            return {'ability_key':ui.row['key']}
        return {}
    def refresh(*_):
        try:
            clips=selected_clips(ui.project,**selection())
            summary.config(text=ui.bi('共有対象：','Included: ')+str(len(clips))+ui.bi('件の完成音声。空き枠・未完成・無効な枠は含めません。',' finished voices. Empty, draft and disabled slots are excluded.'))
        except Exception as error:summary.config(text=str(error))
    box.bind('<<ComboboxSelected>>',refresh);refresh()
    ttk.Checkbutton(send,text=ui.bi('編集元を含める（切り取った前後も含まれます）','Include editable sources (including trimmed-away audio)'),variable=editable).pack(anchor='w',pady=10)
    ttk.Label(send,text=ui.bi('通常は完成した音声だけを共有します。元の録音はこのPCに残ります。\n編集元を含める場合は、切り取り・FXの設定と元の録音も渡します。\nパックにゲームのインストール先、アカウント設定、別の録音は含めません。\nZIPは自動送信しません。作ったファイルを友人へ渡してください。','By default, share only the finished audio. Originals stay on your PC.\nEditable mode also shares the original takes, trim and FX settings.\nNo game path, account settings or unrelated recordings are included.\nNothing is uploaded. Send the resulting ZIP to your friend yourself.'),wraplength=660).pack(anchor='w',pady=10)
    def export():
        try:
            kwargs=selection()
            path=filedialog.asksaveasfilename(parent=window,defaultextension='.voicepack.zip',initialfile='VoiceChantStudio.voicepack.zip',filetypes=[('Voice Chant Studio pack','*.voicepack.zip'),('ZIP','*.zip')])
            if not path:return
            result=export_voicepack(ui.project,path,title=title.get(),editable=editable.get(),**kwargs)
            messagebox.showinfo('Voice Chant Studio',ui.bi('共有パックを保存しました。','Voice pack saved. ')+str(result['clips'])+ui.bi('音声\n\n',' voices\n\n')+path,parent=window)
        except Exception as error:messagebox.showerror('Voice pack',str(error),parent=window)
    ttk.Button(send,text=ui.bi('音声パックを書き出す','Export voice pack'),command=export,style='Accent.TButton').pack(anchor='w',pady=8)

    pack=[None]
    def close():
        if pack[0]:pack[0].close();pack[0]=None
        window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    ttk.Label(receive,text=ui.bi('友人から受け取った .voicepack.zip を選択してください。\nゲーム用の「配布用ZIP」とは別の形式です。','Choose a .voicepack.zip received from a friend.\nThis is different from the finished game addon ZIP.'),wraplength=660).pack(anchor='w',pady=(0,12))
    details=ttk.Label(receive,text=ui.bi('パック未選択','No pack selected'),wraplength=660);details.pack(anchor='w',pady=10)
    conflict=tk.StringVar(value='keep')
    ttk.Radiobutton(receive,text=ui.bi('重複する枠は現在の音声を残す（推奨）','Keep my existing voices for conflicting slots (recommended)'),variable=conflict,value='keep').pack(anchor='w',pady=4)
    ttk.Radiobutton(receive,text=ui.bi('重複する枠をパックの音声で置き換える','Replace conflicting slots with this pack'),variable=conflict,value='replace').pack(anchor='w',pady=4)
    def choose():
        path=filedialog.askopenfilename(parent=window,filetypes=[('Voice packs','*.zip')])
        if not path:return
        try:
            incoming=read_voicepack(path)
            try:report=inspect_import(ui.project,incoming)
            except Exception:incoming.close();raise
            if pack[0]:pack[0].close()
            pack[0]=incoming;m=incoming.manifest
            text=m['title']+'\n'+str(len(m['clips']))+ui.bi('音声 / 重複する枠：',' voices / conflicting slots: ')+str(report['conflicts'])+'\n'+', '.join(sorted({r['class'] for r in m['catalog']}))
            text+='\n'+ui.bi('編集元を含むパックです。','Includes editable original takes.') if m['mode']=='editable' else '\n'+ui.bi('完成音声のみのパックです。','Finished audio only.')
            details.config(text=text);apply.configure(state='normal')
        except Exception as error:messagebox.showerror('Voice pack',str(error),parent=window)
    def import_pack():
        if not pack[0]:return
        try:
            report=import_voicepack(ui.project,pack[0],conflict=conflict.get())
            ui.row=None;ui.clip=None;ui.audio=None;ui.ready=False;ui.search.set('');ui.assigned_only.set(False);ui.class_filter.set(ui.tr('すべて'));ui.populate();ui.draw();ui.update_state()
            ui.status.set(ui.bi('音声パックを取り込みました：','Imported voice pack: ')+str(report['imported'])+ui.bi('件。必要なら完成を保存し、ゲームへ書き出してください。',' voices. Export to game when ready.'))
            note=ui.bi('\n変更前のプロジェクトをバックアップしました。','\nThe previous project was backed up before changes.') if report.get('backup') else ui.bi('\n既存プロジェクトへの変更はありません。','\nThe existing project was not changed.')
            messagebox.showinfo('Voice Chant Studio',ui.bi('取り込み：','Imported: ')+str(report['imported'])+ui.bi('件 / 既存を保持：',' / existing voices kept: ')+str(report['skipped'])+note,parent=window)
            close()
        except Exception as error:messagebox.showerror('Voice pack',str(error),parent=window)
    buttons=ttk.Frame(receive);buttons.pack(fill='x',pady=16)
    ttk.Button(buttons,text=ui.bi('パックを選んで確認','Choose and inspect pack'),command=choose).pack(side='left')
    apply=ttk.Button(buttons,text=ui.bi('このプロジェクトへ取り込む','Import into this project'),command=import_pack,style='Accent.TButton',state='disabled');apply.pack(side='right')
    ttk.Label(receive,text=ui.bi('取り込み後はアプリで試聴・編集し、「ゲームへ書き出す」で反映します。\n元の録音ファイルは削除しません。置き換える場合も旧設定をバックアップします。','After importing, preview/edit in the app, then Export to game.\nExisting original recordings are never deleted. Replacements have a project backup.'),wraplength=660).pack(anchor='w',pady=10)
    return window
