"""Portable Forever discovery; no account files, whole-drive scans or AI required."""
import os
from pathlib import Path
def resolve_game(value):
    p=Path(value)
    if p.is_file():p=p.parent
    for candidate in [p,p/'_forever_',*list(p.parents)[:3]]:
        if candidate.name.lower()=='_forever_' and (candidate/'Wow.exe').is_file():return str(candidate)
    return ''
def detect_game():
    candidates=[]
    for key in ['ProgramFiles(x86)','ProgramFiles']:
        if os.environ.get(key):candidates.append(Path(os.environ[key])/'World of Warcraft')
    try:
        import winreg
        for name in [r'SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft',r'SOFTWARE\Blizzard Entertainment\World of Warcraft']:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,name) as entry:candidates.append(Path(winreg.QueryValueEx(entry,'InstallPath')[0]))
            except OSError:pass
    except ImportError:pass
    for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        drive=Path(letter+':/')
        if os.name=='nt':
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(str(drive))!=3:continue
        if drive.is_dir():
            candidates.extend(drive/folder for folder in ['World of Warcraft','Games/World of Warcraft','Program Files (x86)/World of Warcraft','Program Files/World of Warcraft'])
    return next((found for p in candidates if (found:=resolve_game(p))), '')
