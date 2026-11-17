"""Original fantasy theme inspired by classic RPG interfaces; no game textures."""
from tkinter import ttk
BG='#211b16'
FIELD='#15191b'
TEXT='#eee0bf'
GOLD='#e9bf6a'
BRONZE='#826137'
def apply_theme(root):
    root.configure(background=BG)
    root.option_add('*TCombobox*Listbox.background',FIELD)
    root.option_add('*TCombobox*Listbox.foreground',TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground','#74552d')
    root.option_add('*TCombobox*Listbox.selectForeground','#fff1c2')
    root.option_add('*Toplevel.background',BG)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=('Yu Gothic UI',10),background=BG,foreground=TEXT,
                    bordercolor=BRONZE,lightcolor=BRONZE,darkcolor='#0b0c0e',focuscolor=GOLD)
    style.configure('TFrame',background=BG)
    style.configure('TLabel',background=BG,foreground=TEXT)
    style.configure('TNotebook',background=BG,bordercolor=BRONZE)
    style.configure('TNotebook.Tab',background='#453323',foreground=TEXT,padding=(12,7))
    style.map('TNotebook.Tab',background=[('selected','#792923'),('active','#665031')],foreground=[('selected','#ffe6a2'),('active','#fff0ba')])
    style.configure('TRadiobutton',background=BG,foreground=TEXT,indicatorbackground=FIELD,indicatorforeground=GOLD)
    style.map('TRadiobutton',background=[('active',BG)],foreground=[('active',GOLD),('disabled','#93866e')],indicatorbackground=[('selected','#9d7735'),('active','#69502a')])
    style.configure('Title.TLabel',font=('Cambria',21,'bold'),foreground=GOLD)
    style.configure('Sub.TLabel',foreground='#c4b38c')
    style.configure('TButton',padding=(12,6),background='#453323',foreground='#f0d497',borderwidth=1,relief='raised')
    style.map('TButton',background=[('pressed','#261a13'),('active','#665031')],foreground=[('disabled','#8d826e'),('active','#fff0ba')])
    style.configure('Accent.TButton',background='#792923',foreground='#ffe6a2',bordercolor='#c49a51')
    style.map('Accent.TButton',background=[('pressed','#461b18'),('active','#a03c2d')],foreground=[('active','#fff5cb')])
    for control in ['TEntry','TSpinbox','TCombobox']:
        style.configure(control,fieldbackground=FIELD,background='#473726',foreground=TEXT,insertcolor=GOLD,arrowcolor=GOLD,selectbackground='#6d512e',selectforeground='#fff2c5')
        style.map(control,fieldbackground=[('readonly',FIELD),('disabled','#292721')],foreground=[('readonly',TEXT),('disabled','#93866e')],selectbackground=[('readonly','#6d512e')],selectforeground=[('readonly','#fff2c5')])
    style.configure('TCheckbutton',background=BG,foreground=TEXT,indicatorbackground=FIELD,indicatorforeground=GOLD)
    style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',GOLD),('disabled','#93866e')],indicatorbackground=[('selected','#9d7735'),('active','#69502a')])
    style.configure('Treeview',rowheight=30,background=FIELD,fieldbackground=FIELD,foreground=TEXT,bordercolor=BRONZE,borderwidth=1)
    style.map('Treeview',background=[('selected','#75582e')],foreground=[('selected','#fff4ce')])
    style.configure('Treeview.Heading',background='#493622',foreground=GOLD,font=('Yu Gothic UI',10,'bold'),relief='raised')
    style.map('Treeview.Heading',background=[('active','#60482a')])
    for name in ['Horizontal.TScrollbar','Vertical.TScrollbar']:
        style.configure(name,background='#715631',troughcolor='#151512',arrowcolor=GOLD,bordercolor=BRONZE)
        style.map(name,background=[('active','#a08045')])
    style.configure('Horizontal.TScale',background=BG,troughcolor='#101518',bordercolor=BRONZE)
    style.configure('Horizontal.TProgressbar',background='#b5994a',troughcolor='#111718',bordercolor=BRONZE)
    style.configure('TPanedwindow',background='#6a512d',sashwidth=5)
    return style
