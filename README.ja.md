# Voice Chant Studio v0.7 — Windows / WoW Forever

自分で録音した詠唱を、WoW Foreverの元の効果音に重ねるアプリとアドオンです。ゲームの元の音は残ります。

English instructions: [README.en.md](README.en.md)

## 起動と言語

`VoiceChantStudio-v0.7.exe` をダブルクリックしてください。配布版の実行にPythonは不要です。デスクトップの **Voice Chant Studio** ショートカットも更新版を開きます。更新前のアプリが開いている場合は、先に閉じてください。

右上の **日本語 / English** で表示言語を切り替えます。選んだ言語は次回起動時も引き継ぎます。Englishではボタン、設定、アプリの案内・エラーダイアログも英語になります。Windows標準のファイル選択画面のボタンなどは、Windowsの言語設定に従う場合があります。

録音と読み込んだ音声はこのPC内に保存します。アップロードしません。マイクは録音前のカウントダウンが終わってから開きます。

## 最初の音声を作る

1. **PALADIN / MAGE / PRIEST / DRUID / HUNTER / ROGUE / SHAMAN / WARLOCK / WARRIOR** を選び、左の一覧からアビリティを選択します。検索も使えます。
2. 声を鳴らすタイミングを選びます。
   - **詠唱開始**：詠唱やチャネルの開始時。詠唱を中断したら追加音声も止める設定があります。
   - **発動成功・瞬間技**：瞬間発動の技、または魔法の成功時。
   - **中断時**：詠唱が中断されたときの声。必要な場合だけ設定します。
3. マイクを選び、**● 録音** または **F8**。3秒のカウントダウンで合図が3回鳴り、その後に録音が始まります。
4. **■ 停止** または **F8** で録音を終えます。カウントダウン中に押した場合は録音開始を取り消します。録音は最長120秒です。
5. 黄色の境界をドラッグして、残す範囲を指定します。**開始（秒） / 終了（秒）** の数値で細かく調整し、**▶ 選択範囲を試聴** で確認します。音量調整と「音量をそろえる」も使えます。
6. **完成を保存** を押します。新しい録音や編集後の音声は下書きです。このボタンを押した音声が書き出し対象になります。保存後に範囲や音量を変更したら、もう一度押してください。
7. WoWの `_forever_` フォルダを確認し、**ゲームへ書き出す** を押します。
8. WoWを完全に終了して起動し直し、AddOnsで **Voice Chant Studio** を有効にします。

**F8はこのアプリにフォーカスがある間だけ使えます。** ゲームを操作中の共通ホットキーではありません。試聴中の音声は「■ 停止」で止められます。

録音の代わりに **音声を読み込む** からWAV / OGG / FLAC / MP3ファイルも使えます。読み込みは10分以下、完成音声は30ミリ秒以上にしてください。

## 停止クリックと切り取り

初期設定では **末尾150msを除く** が有効です。手動で停止した録音の終了位置を、元の音声より150ミリ秒手前に設定し、マウスの停止クリックを避けやすくします。短い録音では全体を残す場合があります。

これは取り込み後の最初の切り取り範囲であり、クリック音を検出・除去する処理ではありません。クリック音を必ず消せるわけではなく、声の末尾も短くなることがあります。**全体に戻す** で元の長さに戻し、黄色の境界や秒数で調整できます。チェックを外して録音することもできます。F8で停止するとマウスクリックを避けられます。

切り取りや音量調整は元の録音を書き換えません。別のテイクに変更しても、元のファイルは `originals` に残ります。

## アビリティとランク

同梱のForever用初期一覧は **9クラス491項目** です。同じアビリティのランクは1行にまとめ、その行に設定した音声を共有します。パッシブは通常の詠唱イベントがないため、初期状態では非表示です。

この一覧が、今後追加される技やクライアント独自の技を含めてすべてを網羅するという保証はありません。ゲーム内で `/voicechant` を開き、**Ctrl+A → Ctrl+C**。アプリの **ゲームの一覧を取り込む** に貼り付けると、クライアントが返すアビリティとランクを追加できます。同じクラス・同じ英語名のランクはまとめます。

取得できない技は **アビリティを追加** でSpell IDとゲーム内の英語名を入力できます。Spell IDはアイテムIDとは異なり、ポーションには使用効果のSpell IDが必要です。音声を割り当てていない技では、元のゲーム音だけが鳴ります。

初期IDは、このPCのWhatsTrainingのForever / Camelot用クラスデータ、クエストで覚えるスペル、Forever用タレントデータを照合しています。名前・詠唱時間・アイコン名はWowheadの **/forever/** 専用tooltipを参照しています。出典と収録範囲は同梱の `FOREVER-CATALOG.md` と `forever-catalog-report.json`、各アイコンの取得元は `Icon-Sources.json` に記録しています。アプリの **一覧の出典** でも概要を確認できます。

**Lesser Heal、Smite、Flash Heal、Holy Fire、Holy NovaはPRIEST（プリースト）です。** 起動時は全クラスが見え、左側のクラス欄でも区別できます。クラスで絞り込んでいる場合は **PRIEST** または **すべて** を選んで検索してください。未習得のアビリティも含むため、現在のキャラで使える技はゲームから取り込んだスペルブックも確認してください。

各アビリティの左に実際のスペルアイコンを表示します。アイコンはアプリに同梱しており、表示のためのインターネット接続は不要です。手動追加・取り込みで未知のSpell IDを追加した場合は、同梱済みのランクIDに一致すれば同じアイコン、一致しない場合は「?」を表示します。

## ゲームへの書き出しと共有

通常の書き出し先は次のフォルダです。

```text
World of Warcraft\_forever_\Interface\AddOns\VoiceChantStudio
```

アプリが完成済みの音声を16-bit PCM WAVへ変換し、アドオンと設定をコピーします。録音中は書き出せません。新しい音声を追加した後は、**WoWの完全終了・再起動** が必要です。`/reload` だけでは新しいファイルを読み込まない場合があります。アプリはゲームを自動操作・再起動しません。

Program Filesへの書き込みが拒否された場合は、アプリを管理者として起動するか、**配布用ZIP** を作って中の `VoiceChantStudio` フォルダを `Interface\AddOns` へコピーしてください。

聞こえるのは、自分のクライアントで再生される自分の声です。他のプレイヤーへ自動配信しません。同じボイスパックを友人自身のキャラクターで使う場合は **配布用ZIP** を渡し、友人のAddOnsへ展開して有効にします。友人に自分の詠唱をリアルタイム配信する機能はありません。ZIPはゲーム用の完成アドオンで、編集元のプロジェクトではありません。

ゲーム設定のサウンドとDialog（会話）チャンネルを有効にし、音量を確認してください。

| ゲーム内コマンド | 動作 |
| --- | --- |
| `/voicechant` | 取り込み用アビリティ一覧を開く |
| `/voicechant test` | 最初に設定した追加音声を試聴 |
| `/voicechant mute` | このアドオンの声だけミュート |
| `/voicechant unmute` | ミュート解除 |

アドオンはゲームが通知する自分の詠唱開始・発動成功・中断に反応します。新しい追加音声は前の追加音声を止め、連続再生の最小間隔で連打時の重複を抑えます。元の効果音は停止しません。敵の全攻撃や、すべての被ダメージを識別する機能は含みません。

## 保存場所と既存プロジェクト

既定の保存場所は次のとおりです。

```text
%LOCALAPPDATA%\VoiceChantStudio\
  settings.json
  Projects\Paladin\
    project.json
    originals\
    export-backups\
```

`settings.json` には表示言語などを保存します。既定プロジェクトのフォルダ名は互換性のため **Paladin** のままですが、そのプロジェクト内で **パラディン・メイジ・プリースト** を管理します。

`project.json` にアビリティ、割当、切り取り範囲、音量などを保存し、`originals` に元の音声を残します。v0.1などの既存プロジェクトを開くと、新しいクラス・ランクを追加します。変更がある場合は、更新前のJSONを `project-before-upgrade-*.json` にバックアップします。既存の音声割当や編集を保持するための更新です。`export-backups` には過去の書き出し設定を保存します。

別のプロジェクトは **新規プロジェクト / プロジェクトを開く** から管理できます。編集を別PCへ移す場合は、`project.json` だけでなく **プロジェクトフォルダ全体** をコピーしてください。

初めての録音では、短いテイクを1本作り、試聴とゲーム内の `/voicechant test` でマイク・音量・再生を確認してから音声を増やしてください。

## ゲーム内の専用音量設定（v0.7）

アドオン一覧では **Voice Chant Studio - Voice Effects**、設定ページでは **Voice Chant Studio** です。
**Esc → Options → AddOns → Voice Chant Studio**、または `/vcs` / `/voicechant settings` で開きます。
このアドオンの声だけを0〜100%、10%刻みで変更できます。ゲームの効果音やNPCの音量は変更しません。
`/vcs volume 50` は50%、`/voicechant test` は試聴です。音量とミュートは次回ログインにも引き継ぎます。
100%はアプリで書き出した音量が基準です。元の録音は変更しません。新しい音量用ファイルの追加後はWoWを完全に再起動してください。
設定を保つには、今後の書き出しに更新版v0.7を使用してください。

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
