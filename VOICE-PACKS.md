# Voice packs / 音声パックの共有

## 日本語

1. 共有したい音声を「完成を保存」で保存します。ランダム用の枠は有効な音声数に含めてください。
2. 「音声パック共有」→「送る：エクスポート」で、すべて・表示中のクラス・選択中の技から共有範囲を選びます。
3. 通常は「編集元を含める」をオフにします。カットとFXを適用した完成音声だけを共有し、切り取った部分を含む元録音は渡しません。
4. 相手にも元の録音を編集してほしい場合だけ「編集元を含める」をオンにします。**切り取った前後の音声も相手に渡ります。**
5. 「音声パックを書き出す」で `.voicepack.zip` を保存し、Google Driveや普段のファイル共有方法で友人へ渡します。アプリは自動アップロードしません。
6. 相手はv0.7以降のアプリの「音声パック共有」→「受け取る：インポート」→「パックを選んで確認」で開きます。内容と重複件数を確認して取り込みます。
7. 重複は既存音声を保持するのが初期設定です。置き換える場合も元録音は削除せず、変更前のproject.jsonをプロジェクト内へバックアップします。
8. 相手が試聴・必要な編集を行い、自分のゲームの場所を指定して「ゲームへ書き出す」を押します。WoWを完全に再起動してください。

開始・成功・中断の完成音声、成功枠1〜5、FX、連携条件を扱います。空き枠・未完成・無効な枠は共有しません。リンク先と条件元の技の情報も含めますが、その技の別の録音は選択されていなければ含めません。ゲームの場所、アカウント、音量などの個人設定は共有しません。

これはアプリ用の共有形式です。既存の「配布用ZIP」はゲームへ直接配置する完成アドオンです。過去のアドオンZIPはこの機能へインポートできません。受け取った人のPCだけで音が鳴り、パーティーへ自動送信する機能ではありません。

パックは最大512 MiB、音声1ファイルは最大128 MiB・10分です。音声とデータだけを受け入れ、コードや実行ファイルは取り込みません。共有する権利のある音声を使ってください。取り込み前に同じプロジェクトを開いた別ウィンドウを閉じてください。

## English

1. Save each finished clip; enable the desired success variation slots.
2. Open **Voice packs → Send: export**. Choose all saved voices, the current class, or the selected ability.
3. Leave **Include editable sources** off to share only trimmed, processed audio. Originals and trimmed-away conversation stay on your PC.
4. Enable editable sources only if the recipient needs the full original take and trim/FX settings. **This includes audio outside the trim boundaries.**
5. Export a `.voicepack.zip` and send it using your usual file-sharing service. Nothing is uploaded automatically.
6. In v0.7 or later, the recipient opens **Voice packs → Receive: import → Choose and inspect pack**. Review the contents and conflict count, then import.
7. Existing conflicting slots are kept by default. Replacement preserves original audio files and creates a pre-import project.json backup inside the project folder.
8. Preview/edit, select your own WoW Forever folder, **Export to game**, then fully restart WoW.

Finished start/success/interruption clips, success slots 1–5, FX and spell links are supported. Draft, empty and disabled slots are excluded. Link dependencies include ability metadata, without unrelated recordings. Game paths, accounts and personal game settings are not included.

This format is separate from the finished game addon ZIP, which cannot be imported as an editable voice pack. Each recipient installs the voices locally; party members do not automatically hear them. Limits: 512 MiB per pack, 128 MiB and 10 minutes per audio file. Only audio and data are accepted; no scripts/executables are imported. Share only audio you have permission to share. Close other windows editing the same project before importing.
