"""Exact-text Japanese/English translations for Voice Chant Studio.

Japanese is the source language. Unknown strings are deliberately preserved so
device names, filenames, exceptions from audio drivers, and user text survive.
F-string literal fragments are included because the UI translates those before
interpolating values. Spell display names are maintained in the spell catalog.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


EN = {
    'アビリティIDが正しくありません。': 'The ability ID is invalid.',
    'アビリティ名が正しくありません。': 'The ability name is invalid.',
    'クラス名はMAGEなどの英大文字で指定してください。': 'Use an uppercase class name such as MAGE.',
    '詠唱時間が正しくありません。': 'The cast time is invalid.',
    '詠唱時間は0〜600秒の範囲にしてください。': 'The cast time must be between 0 and 600 seconds.',
    'アビリティの種類が正しくありません。': 'The ability type is invalid.',
    'Voice Chant Studio — 自分の声で、魔法を唱える': 'Voice Chant Studio — Cast spells with your own voice',
    '表示言語を日本語に変更しました。': 'The display language is now Japanese.',
    '録音を停止してからプロジェクトを切り替えてください。': 'Stop recording before switching projects.',
    '録音開始まで ': 'Recording starts in ',
    ' 秒 · 停止／F8で中止': ' s · Stop / F8 to cancel',
    'マイクを準備中…': 'Preparing microphone…',
    ' 秒 · ■ 停止／F8（最大120秒）': ' s · ■ Stop / F8 (maximum 120 seconds)',
    '3秒前から合図音 · F8で録音／停止': '3-second audible countdown · F8 to record / stop',
    '末尾150msを除く': 'Exclude the final 150 ms',
    'このタイミングの音声を新しいテイクに変更しますか？ 元の録音ファイルは残ります。': 'Replace the voice for this timing with a new take? The original recording file will be kept.',
    '録音を停止して保存中…': 'Stopping and saving recording…',
    '録音を開始せずに中止しました。': 'Cancelled before recording started.',
    '録音・元ファイルを保存しました。範囲を調整し「完成を保存」を押してください。': 'Original audio saved. Adjust the trim range, then click Save finished clip.',
    'ゲームのアビリティ一覧を取り込む': 'Import abilities from the game',
    'アビリティを追加': 'Add an ability',
    'Spell IDを入力（ポーションの効果もSpell IDで指定）': 'Enter a Spell ID (use the effect Spell ID for potions, too)',
    'アビリティ名': 'Ability name',
    'ゲーム内と同じ英語名を入力してください。': 'Enter the same English name shown in the game.',
    '使い方': 'How to use',
    '① アビリティを選ぶ\n② タイミングを選ぶ（詠唱開始 / 発動成功 / 中断）\n③ 録音、または音声ファイルを読み込む\n④ 波形の黄色の線で前後をカットし、試聴\n⑤「完成を保存」\n⑥「ゲームへ書き出す」→ WoWを完全に再起動\n\n/voicechant：ゲームからアビリティ一覧をコピー\n/voicechant test：追加音声の試聴\n/voicechant mute / unmute：追加音声だけ切替\n\n原音は残ります。録音はこのPC内に保存され、アップロードしません。\n既存テイクは非破壊編集。新しいファイルを追加したらWoWの完全再起動が必要です。\n全ダメージ・敵の攻撃の識別は今回の対象外です。\n他のプレイヤーには自動で音声は届きません。':
        '1. Select an ability.\n2. Choose when to play it (cast start / successful cast / interruption).\n3. Record your voice, or import an audio file.\n4. Drag the yellow waveform markers to trim the clip, then preview it.\n5. Click Save finished clip.\n6. Click Export to game, then fully restart WoW.\n\n/voicechant: copy your ability list from the game\n/voicechant test: preview an added voice clip\n/voicechant mute / unmute: toggle the added voice only\n\nThe original game sounds remain. Recordings stay on this PC and are never uploaded.\nEditing is nondestructive. Fully restart WoW after adding a new audio file.\nDetecting every incoming hit or enemy attack is outside this version\'s scope.\nOther players do not automatically hear your voice clips.',
    'エラー': 'Error',
    'アビリティを選び、「録音」または「音声を読み込む」から始めます。': 'Select an ability, then start with Record or Import audio.',
    'パラディン / ローカル保存': 'Paladin / Saved locally',
    'アビリティ / ランクは共通': 'Abilities / Shared across ranks',
    '音声': 'Voice clip',
    'アビリティを選択': 'Select an ability',
    '初期一覧 + ゲームのスペルブックを取り込んで拡張': 'Starter catalog + abilities imported from your in-game spellbook',
    '● 録音': '● Record',
    '未録音': 'No recording',
    'すべて': 'All',
    '左の一覧からアビリティを選んでください。': 'Select an ability from the list on the left.',
    '録音中です。停止で確定します（最大120秒）。': 'Recording. Press Stop to finish (maximum 120 seconds).',
    '録音が短すぎます。もう一度録音してください。': 'The recording is too short. Please record again.',
    '先に録音するか音声を読み込んでください。': 'Record or import an audio file first.',
    '割当を解除': 'Remove assignment',
    'このタイミングの音声割当を解除しますか？ 元の音声ファイルは残ります。': 'Remove the voice assignment for this timing? The original audio file will be kept.',
    'WoWの _forever_ フォルダを選択': 'Select your WoW _forever_ folder',
    '録音中': 'Recording',
    '録音を停止してから書き出してください。': 'Stop recording before exporting.',
    '書き出しました': 'Export complete',
    'project.json を選択': 'Select project.json',
    '新規プロジェクトを保存するフォルダ': 'Choose a folder for the new project',
    'マイクを認識できません（ファイル読込は使用可）': 'No microphone detected (you can still import audio)',
    '項目表示 / 全': ' shown / ',
    '項目': ' total',
    '保存済み · 書き出し対象': 'Saved · Ready to export',
    '読み込みエラー': 'Import error',
    '録り直す': 'Record a new take',
    'このタイミングの音声を新しい録音に変更しますか？ 元の録音ファイルは残ります。': 'Replace the voice for this timing with a new recording? The original recording will be kept.',
    '● 録音中': '● Recording',
    'マイクを開けません': 'Cannot open microphone',
    '録音機器の警告: ': 'Recording device warning: ',
    '録音中 ': 'Recording ',
    ' 秒  ·  ■ 停止で録音を終えます': ' s  ·  ■ Stop ends the recording',
    '選択範囲を試聴中（': 'Previewing selection (',
    '秒）。■ 停止で止められます。': ' s). Press ■ Stop to stop playback.',
    '試聴できません': 'Cannot preview audio',
    '完成を保存しました。': 'Finished clip saved. ',
    '秒 / 「ゲームへ書き出す」で反映します。': ' s / Click Export to game to install it.',
    '保存できません': 'Cannot save',
    'あなたの声を録音、または音声ファイルを読み込む': 'Record your voice, or import an audio file',
    's → ': 's → ',
    's  /  全体 ': 's  /  Total ',
    '間隔は0〜5秒です。': 'The interval must be between 0 and 5 seconds.',
    '設定エラー': 'Settings error',
    '件の保存済み音声を書き出しました。\n\n': ' saved voice clips exported.\n\n',
    '\n\nWoWを完全に終了して再起動し、AddOnsで Voice Chant Studio を有効にしてください。\n\n/voicechant test で最初の音声を試聴できます。\nゲーム本来の効果音はそのまま残ります。': '\n\nFully quit and restart WoW, then enable Voice Chant Studio in AddOns.\n\nUse /voicechant test to preview the first clip.\nThe original game sound effects remain.',
    'ゲームへ書き出しました：': 'Exported to game: ',
    '件。WoWを完全に再起動してください。': ' clips. Fully restart WoW.',
    '書き出しできません': 'Cannot export',
    '配布用ZIPを保存しました（': 'Addon ZIP saved (',
    '音声）。友人はAddOnsへ展開できます。': ' clips). Your friend can extract it into AddOns.',
    'ZIP作成エラー': 'ZIP creation error',
    'プロジェクトを開けません': 'Cannot open project',
    '\n詳細: ': '\nDetails: ',
    '  原音を残して、あなたの詠唱を重ねる。': '  Add your own chant over the original game sounds.',
    'プロジェクトを開く': 'Open project',
    '新規プロジェクト': 'New project',
    'ゲームの一覧を取り込む': 'Import game spellbook',
    ' 検索 ': ' Search ',
    '音声ありだけ表示': 'Show assigned voices only',
    'パッシブを隠す': 'Hide passive abilities',
    '声を鳴らすタイミング': 'When to play your voice',
    '詠唱のある魔法 → 開始 ／ 瞬間発動 → 発動成功。元の効果音はそのまま。': 'Cast-time spells → Cast start / Instant spells → Successful cast. Original sounds remain.',
    'マイク': 'Microphone',
    '■ 停止': '■ Stop',
    '音声を読み込む': 'Import audio',
    '▶ 選択範囲を試聴': '▶ Preview selection',
    '黄色の境界をドラッグして切り出す範囲を指定。元の録音は残ります。': 'Drag the yellow markers to choose the trim range. The original recording is kept.',
    '開始（秒）': 'Start (seconds)',
    '終了（秒）': 'End (seconds)',
    '全体に戻す': 'Reset to full clip',
    '音量': 'Volume',
    '音量をそろえる': 'Normalize volume',
    '完成を保存': 'Save finished clip',
    'この音声割当を解除': 'Remove this voice assignment',
    '詠唱を中断したら、追加音声も止める': 'Stop the added voice when the cast is interrupted',
    '連続再生の最小間隔（秒）': 'Minimum interval between plays (seconds)',
    '参照': 'Browse',
    'ゲームへ書き出す': 'Export to game',
    '配布用ZIP': 'Create addon ZIP',
    '新しい音声ファイルを追加した後は、WoWを完全に終了して起動し直してください。/reload だけでは反映されない場合があります。': 'Fully quit and restart WoW after adding new audio files. /reload alone may not load them.',
    'ランクID': 'Rank IDs',
    '  ·  パッシブ（詠唱イベントなし）': '  ·  Passive (no cast event)',
    '編集中 · 完成を保存してください': 'Editing · Save your finished clip',
    '別テイクへ変更': 'Replace take',
    'このタイミングの音声を新しいテイクに変更しますか？ 元の音声ファイルは残ります。': 'Replace the voice for this timing with a new take? The original audio file will be kept.',
    '\nWindowsのマイク許可と入力機器を確認してください。': '\nCheck Windows microphone permissions and your input device.',
    '\nProgram Filesへの書き込みが拒否された場合はアプリを管理者として起動するか、配布用ZIPから手動コピーしてください。': '\nIf writing to Program Files is denied, run the app as administrator or manually copy the files from the addon ZIP.',
    'Voice Chant プロジェクト': 'Voice Chant project',
    'ゲーム内で /voicechant → Ctrl+A / Ctrl+C → 下に貼り付け。\nゲームから取得したランクIDを既存のアビリティにまとめます。': 'In game: /voicechant → Ctrl+A / Ctrl+C → Paste below.\nRank IDs from the game will be merged into existing abilities.',
    '一覧を更新しました。': 'Ability list updated. ',
    '項目追加。': ' abilities added.',
    '取り込みエラー': 'Import error',
    '一覧を取り込む': 'Import ability list',
    '—': '—',
    '音声の読み込みエラー: ': 'Audio import error: ',
    '  ·  ': '  ·  ',
    '詠唱開始': 'Cast start',
    '発動成功・瞬間技': 'Successful cast / Instant ability',
    '中断時': 'On interruption',
    '10分以下の音声を選んでください。': 'Choose an audio file no longer than 10 minutes.',
    '音声が空です。': 'The audio file is empty.',
    '音声に無効なサンプルが含まれています。': 'The audio contains invalid samples.',
    '音量は0〜2の範囲にしてください。': 'The volume must be between 0 and 2.',
    '開始位置は終了位置より前にしてください。': 'The start position must be before the end position.',
    '音声は30ミリ秒以上にしてください。': 'The clip must be at least 30 milliseconds long.',
    'プロジェクト外の音声パスです。': 'The audio path is outside this project.',
    '一覧の形式が正しくありません。': 'The ability list format is invalid.',
    '書き出し先にプロジェクト内を指定できません。': 'The export destination cannot be inside the project folder.',
    'このプロジェクト形式は読み込めません。': 'This project format is not supported.',
    'Wow.exe がある _forever_ フォルダを選んでください。': 'Select the _forever_ folder containing Wow.exe.',
    # Driver-independent recording errors can also be translated directly.
    'invalid_audio_length': 'The audio length or sample rate is invalid.',
    'invalid_tail_guard': 'The end-click guard must be between 0 and 1000 milliseconds.',
    'invalid_sample_rate': 'The recording sample rate is invalid.',
    'recording_too_short': 'The recording is too short. Please record again.',
}


def translate(text: str, language: str = 'ja') -> str:
    """Translate a source string; Japanese and unknown text stay unchanged."""
    if language == 'en':
        return EN.get(text, text)
    return text


def untranslated_strings(*source_paths: str | Path) -> list[tuple[str, int, str]]:
    """Report Japanese string literals missing from EN, without importing the UI.

    This is a developer aid, not a runtime warning. Strings inside dictionaries
    named JP are ability labels, whose translations live in the spell catalog.
    """
    missing = []
    japanese = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
    for source in source_paths:
        path = Path(source)
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        ignored = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'JP' for t in node.targets):
                ignored.update(id(child) for child in ast.walk(node.value))
        seen = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or id(node) in ignored:
                continue
            if japanese.search(node.value) and node.value not in EN and node.value not in seen:
                seen.add(node.value)
                missing.append((str(path), node.lineno, node.value))
    return missing
