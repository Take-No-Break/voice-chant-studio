# Voice Chant Studio v0.7 — Windows / WoW Forever

Record your own spell chants and play them over WoW Forever's original effects. The original game sounds remain audible.

日本語の説明: [README.md](README.md)

## Start and choose a language

Double-click `VoiceChantStudio-v0.7.exe`. The packaged Windows app does not require Python. The desktop **Voice Chant Studio** shortcut opens this update. Close an already open older version before launching the update.

Use **日本語 / English** at the top right to switch languages. Your choice is remembered for the next launch. English also changes the app's settings, instructions, and error dialogs. Buttons in native Windows file pickers may follow your Windows display language.

Recordings and imported audio stay on this PC. Nothing is uploaded. The microphone opens after the recording countdown finishes.

## Make your first clip

1. Choose **PALADIN / MAGE / PRIEST / DRUID / HUNTER / ROGUE / SHAMAN / WARLOCK / WARRIOR**, then select an ability from the list on the left. You can search the list.
2. Choose when to play your voice.
   - **Cast start**: when a cast or channel starts. You can enable stopping the added voice when the cast is interrupted.
   - **Successful cast / Instant ability**: for an instant ability, or when a spell succeeds.
   - **On interruption**: a separate voice for an interrupted cast. This is optional.
3. Choose your microphone and press **● Record** or **F8**. A three-second countdown plays three beeps, then recording begins.
4. Press **■ Stop** or **F8** to end the take. During the countdown, either button cancels before recording starts. Each recording can last up to 120 seconds.
5. Drag the yellow waveform markers to select the part to keep. Use the **Start (seconds) / End (seconds)** fields for precise adjustments, then **▶ Preview selection**. Volume and normalization controls are also available.
6. Click **Save finished clip**. New recordings and edited clips are drafts. This button marks the clip as ready for export. If you change its range or volume afterward, save the finished clip again.
7. Check the WoW `_forever_` folder and click **Export to game**.
8. Fully quit and restart WoW, then enable **Voice Chant Studio** in AddOns.

**F8 works only while this app has focus.** It is not a global shortcut while playing the game. Use **■ Stop** to stop a preview.

You can also use **Import audio** with WAV / OGG / FLAC / MP3 files. Imported files must be no longer than 10 minutes, and finished clips must be at least 30 milliseconds long.

## Stop clicks and trimming

**Trim last 150 ms** is enabled by default. For a manually stopped recording, it places the initial end marker 150 milliseconds before the end of the original take to help avoid the mouse click. Very short takes may keep their full length.

This is an initial trim selection, not automatic click detection or removal. It cannot guarantee removal of a click and may also shorten the end of your voice. Use **Reset to full clip** to restore the full range, then adjust the yellow markers or time fields. You can turn the option off before recording. Stopping with F8 avoids a mouse click.

Trimming and volume changes do not overwrite the original audio. Replacing a take also keeps the previous audio file in `originals`.

## Abilities and spell ranks

The bundled Forever catalog contains **491 entries across all 9 original classes**. Ranks of the same ability are grouped into one row and share the voice assigned to that row. Passive abilities have no normal cast event and are hidden by default.

The catalog does not guarantee coverage of every future or client-specific ability. In game, open `/voicechant`, then press **Ctrl+A → Ctrl+C**. Paste into **Import game spellbook** in the app to add abilities and ranks returned by your client. Ranks with the same class and English name are grouped together.

For an ability the client cannot return, use **Add an ability** and enter its Spell ID and in-game English name. A Spell ID is different from an item ID; potions need the Spell ID of their use effect. Abilities without an assigned voice play only their original game sounds.

The initial IDs were cross-checked against this PC's WhatsTraining Forever / Camelot class data, quest-granted spells and Forever talent data. Names, cast times and icon names use Wowhead's **/forever/** tooltip endpoint. See the bundled `FOREVER-CATALOG.md` and `forever-catalog-report.json` for coverage and evidence, and `Icon-Sources.json` for individual icon sources. **Catalog source** in the app explains the sources.

**Lesser Heal, Smite, Flash Heal, Holy Fire and Holy Nova belong to PRIEST.** The default view shows all classes and a class column. If you are filtering the list, choose **PRIEST** or **All** to find them. The starter catalog includes unlearned abilities, so also import your current character's spellbook from the game.

Each ability has its actual spell icon on the left. Icons are bundled and work offline. Imported or manually added spells use a bundled icon when a rank ID matches; unknown IDs display a question-mark fallback.

## Export to WoW and share

The usual destination is:

```text
World of Warcraft\_forever_\Interface\AddOns\VoiceChantStudio
```

The app converts finished clips to 16-bit PCM WAV, then copies the addon and its settings. Export is unavailable during recording. **Fully quit and restart WoW** after adding new audio files. `/reload` alone may not load a new file. The app does not operate or restart the game for you.

If Windows denies writing to Program Files, run the app as administrator, or use **Create addon ZIP** and copy its `VoiceChantStudio` folder into `Interface\AddOns` manually.

Your added voice plays locally in your own game client. It is not automatically broadcast to other players. To let a friend use the same voice pack for their own character, share the **addon ZIP**; they must extract it into their own AddOns folder and enable it. This does not broadcast your casts to them in real time. The ZIP contains the finished game addon, not the editable project.

Enable game sound and the Dialog channel, and check their volume settings.

| In-game command | Action |
| --- | --- |
| `/voicechant` | Open the ability list for import |
| `/voicechant test` | Preview the first assigned voice clip |
| `/voicechant mute` | Mute only this addon's voice |
| `/voicechant unmute` | Unmute the added voice |

The addon responds to your own cast-start, successful-cast, and interruption events reported by the game. A new voice clip stops the previous added clip, and the minimum playback interval limits repetition. The original game effects are not stopped. This version does not identify every enemy attack or every instance of incoming damage.

## Saved data and existing projects

The default data location is:

```text
%LOCALAPPDATA%\VoiceChantStudio\
  settings.json
  Projects\Paladin\
    project.json
    originals\
    export-backups\
```

`settings.json` stores preferences such as the interface language. For compatibility, the default project folder is still named **Paladin**, but that project now manages **Paladin, Mage and Priest** abilities.

`project.json` stores abilities, assignments, trim ranges, volume, and other project settings. `originals` keeps the source audio. Opening an existing project from v0.1 or another earlier catalog adds the new classes and ranks. If an upgrade changes the catalog, the previous JSON is backed up as `project-before-upgrade-*.json`. The upgrade preserves existing voice assignments and edits. `export-backups` stores previous export settings.

Use **New project / Open project** to manage other projects. To move your editable work to another PC, copy the **entire project folder**, not just `project.json`.

Start with one short test take. Preview it in the app and use `/voicechant test` in game to check your microphone, volume, and playback before recording more clips.

## Dedicated in-game voice volume (v0.7)

The addon list displays **Voice Chant Studio - Voice Effects**. Its settings category is **Voice Chant Studio**.
Open **Esc → Options → AddOns → Voice Chant Studio**, or type `/vcs` / `/voicechant settings`.
The slider adjusts only this addon's voices from 0–100% in 10% steps. It does not change game effects or NPC voice volume.
`/vcs volume 50` sets 50%; `/voicechant test` previews a voice. Volume and mute persist across logins.
100% is the clip volume exported from the editor. Original recordings remain intact. Fully restart WoW after new volume files are added.
Use editor v0.7 for future exports so the new settings remain installed.

## Success voice variations / 発動成功の音声バリエーション

Choose Successful cast / Instant ability, set Success voices to 1–5, select a Voice slot, then record/import and Save finished clip for each slot. Saved enabled slots play with equal probability; repeats are allowed. Blank/draft slots are skipped. Lowering the count preserves disabled recordings. Start/interruption still use one voice each.

「発動成功・瞬間技」を選び、成功音声数を1〜5に設定 → 録音枠を選ぶ → 各枠で録音・編集・完成を保存 → ゲームへ書き出す。登録済みの有効な枠から均等にランダム再生します。同じ声が続く場合もあります。音声数を減らしても録音は削除しません。

Game discovery checks Blizzard registration and common local install folders. If missing, use Browse: Battle.net gear → Show in Explorer → select _forever_ containing Wow.exe (or its parent folder). No AI is required. See AI-SETUP.md for detailed user/AI setup instructions.

## v0.7: User spell links and offline Voice FX

All nine original Forever classes are available. Counts: Druid: 58, Hunter: 67, Mage: 56, Paladin: 50, Priest: 52, Rogue: 58, Shaman: 55, Warlock: 50, Warrior: 45. Data comes from installed Camelot trainer/quest/rank lists and Forever-specific tooltips. Two unavailable IDs were excluded (see all-classes-report.json); this does not promise every future, item, pet or talent spell. Import the actual client spellbook for your character.

**Create spell link / 連携リンクを作成**: select a class, choose condition spell 1 and replacement spell 2, then choose player buff, your target debuff, or previous successful spell (1–30 seconds). Record on the [LINK] row, save and export. The link replaces the normal voice; unassigned phases fall back. If multiple links match, the first exported match wins. See LINK-EXAMPLES.md for retained research and condition limits. No spellcasting automation is included.

**Voice FX / EQ**: select a recorded clip. Pitch ±12 semitones preserves duration; low/mid/high EQ ±12 dB; vibrato and tremolo adjust voice pitch/loudness modulation. Preview → Apply → Save finished clip. Original takes stay intact. Processing happens offline in the editor, not in WoW. Strong effects can introduce artifacts. This is a basic voice editor, not a multitrack or plugin-host DAW.

日本語：クラスを選び「連携リンクを作成」で技1・条件・技2を指定し、追加されたLINK行に録音します。「音声FX / EQ」で加工を試聴し、適用後に「完成を保存」を押してください。音声ファイル追加後はWoWを再起動してください。

## Shared app and addon icon

The original microphone/spark icon is shared by the Windows EXE, window and desktop shortcut, and the WoW AddOns list via IconTexture. Use editor v0.7 for future exports. Close older editor windows before opening the updated desktop shortcut. Fully restart WoW to refresh addon metadata/icon files.

## Fantasy interface / WoWライクなデザイン

Original dark-leather/stone-inspired colors, bronze/gold borders, gold headings, red primary buttons and a dark waveform editor. No Blizzard UI textures are used for the app theme. Japanese and English layouts retain editing/export controls at the supported minimum size. The original microphone/spark mark is shared by the EXE, shortcut and WoW addon.


## v0.7: Voice packs / 音声パック共有

**Voice packs / 音声パック共有** exports finished voices to a `.voicepack.zip` for another user to import into the editor. Choose all saved voices, current class or selected ability. Finished-only is the default; optional editable mode includes full original takes and trim/FX settings, including trimmed-away audio. The recipient previews conflicts and keeps existing slots by default; replacements preserve original files and back up project settings. Random success slots and spell links are retained. Nothing is uploaded automatically. See [VOICE-PACKS.md](VOICE-PACKS.md) for both languages.

保存した音声を「音声パック共有」からZIPに書き出して友人へ渡せます。受け取る側も同じ画面から取り込み、自分のゲームへ書き出します。初期設定は完成音声だけの共有です。「編集元を含める」を選ぶと切り取った前後を含む元録音も渡します。詳細はVOICE-PACKS.mdをご覧ください。
