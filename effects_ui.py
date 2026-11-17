import tkinter as tk
from tkinter import ttk,messagebox
import sounddevice as sd
from effects import LIMITS,settings
def open_effects(ui):
    if ui.controller.busy:return
    if ui.audio is None:
        messagebox.showinfo('Voice FX',ui.bi('先に録音するか音声を読み込んでください。','Record or import a clip first.'));return
    target_key=ui.key();target_project=ui.project
    w=tk.Toplevel(ui.root);w.title('Voice FX / EQ — '+ui.row['name']);w.geometry('650x570');w.transient(ui.root);w.grab_set()
    form=ttk.Frame(w,padding=20);form.pack(fill='both',expand=True)
    initial=settings(ui.clip.get('effects',{}))
    variables={key:tk.DoubleVar(value=initial[key]) for key in LIMITS}
    labels={'pitch':ui.bi('ピッチ（半音・長さを保持）','Pitch (semitones, preserve duration)'),
            'low':ui.bi('低音 EQ（dB）','Low EQ (dB)'),'mid':ui.bi('中音 EQ（dB）','Mid EQ (dB)'),
            'high':ui.bi('高音 EQ（dB）','High EQ (dB)'),
            'vibrato_depth':ui.bi('ビブラートの深さ（ms）','Vibrato depth (ms)'),
            'vibrato_rate':ui.bi('ビブラートの速さ（Hz）','Vibrato rate (Hz)'),
            'tremolo_depth':ui.bi('トレモロの深さ（%）','Tremolo depth (%)'),
            'tremolo_rate':ui.bi('トレモロの速さ（Hz）','Tremolo rate (Hz)')}
    for key,(low,high,default) in LIMITS.items():
        line=ttk.Frame(form);line.pack(fill='x',pady=7)
        ttk.Label(line,text=labels[key],width=34).pack(side='left')
        ttk.Scale(line,from_=low,to=high,variable=variables[key]).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Spinbox(line,from_=low,to=high,increment=.1,textvariable=variables[key],width=7).pack(side='left')
    def values():return settings({key:var.get() for key,var in variables.items()})
    def preview():
        old=ui.clip.get('effects')
        try:ui.clip['effects']=values();ui.preview()
        except Exception as error:messagebox.showerror('Voice FX',str(error),parent=w)
        finally:
            if old is None:ui.clip.pop('effects',None)
            else:ui.clip['effects']=old
    def apply():
        try:
            if ui.project is not target_project or ui.key()!=target_key:raise ValueError('The selected voice changed. Reopen Voice FX.')
            ui.clip['effects']=values();ui.ready=False;ui.clip['ready']=False;ui.stash();ui.update_state();w.destroy()
            ui.status.set(ui.bi('音声FXを適用しました。「完成を保存」を押してください。','Effects applied. Click Save finished clip before exporting.'))
        except Exception as error:messagebox.showerror('Voice FX',str(error),parent=w)
    buttons=ttk.Frame(form);buttons.pack(fill='x',pady=14)
    ttk.Button(buttons,text=ui.bi('加工音を試聴','Preview FX'),command=preview).pack(side='left')
    ttk.Button(buttons,text=ui.bi('停止','Stop'),command=sd.stop).pack(side='left',padx=6)
    ttk.Button(buttons,text=ui.bi('原音設定に戻す','Reset effects'),command=lambda:[variables[k].set(v[2]) for k,v in LIMITS.items()]).pack(side='left')
    ttk.Button(buttons,text=ui.bi('適用','Apply'),command=apply,style='Accent.TButton').pack(side='right')
    ttk.Label(form,text=ui.bi('元の録音は変更しません。FXはアプリで加工し、ゲームでは完成音声のみ再生します。\nビブラート＝音程の揺れ、トレモロ＝音量の揺れ。大きな加工値は声に歪みやにじみが出る場合があります。','Original recordings are preserved. Effects are rendered offline; the game only plays finished files.\nVibrato changes pitch; tremolo changes loudness. Strong settings may introduce artifacts.'),wraplength=605).pack(anchor='w',pady=8)
    return w
