# v0.8 workflows / 制作ツールと再生設定

## 日本語

メイン画面の「制作ツール」に以下をまとめました。既存の録音を上書き加工しません。

- **声のプリセット**：聖なる詠唱・低い悪役声・精霊の声・原音。Ctrl/Shiftで複数の技を選び、試聴してから一括適用できます。適用後は未完成です。「選択した技の完成を保存」で検証・確定できます。自分で「音声FX / EQ」で調整した声の設定も、名前を付けてプリセット保存できます。プリセットはプロジェクトごとに保存します。
- **録音アシスト**：技と開始/成功/中断のタイミングを選び、詠唱文を書いて録音します。録音はボタンを押した時だけ、3秒カウント後に始まります。停止→完成を保存→次の技、と進められます。長さ・ピーク・RMS・無音率を表示します。無音率は簡易判定で、ノイズ除去ではありません。成功の複数枠は先にメイン画面で選んでください。
- **連携テスト**：条件が有効/無効、直前の技からの秒数、再生タイミングを指定して、通常音声/リンク音声のどちらが選ばれるか試します。複数一致では出力順で最初の音声付きリンクが優先です。実ゲームのイベントやAura IDの確認とは別です。
- **診断・復元・容量**：完成/未完成/無効件数、推定出力容量、ゲームの場所とConfigを確認します。履歴を選んで設定・録音割り当てを復元できます。通常保存の直前の状態を直近30件残します。元録音を削除しません。
- **ゲーム音声の整理**：現在のConfigが使っていない、このアドオンの音声だけをプロジェクト内のaudio-archiveへ移します。削除ではありません。古い音声を使うWoWを完全に終了してから実行してください。復旧する場合は表示された退避フォルダのWAVを同じアドオンのAudioへ戻せます。
- **パック・録音管理**：取り込んだパックの作者・説明・割り当てを表示します。パックを外すと、そのパックが置き換えた割り当てを戻します。取り込み後に編集した枠は残します。個別の録音枠をON/OFFにでき、成功枠はメイン画面の音声数の範囲内だけ出力されます。

### ゲーム内の再生

`/vcs` から選びます。

1. **前の声を止める**：新しい技の声で前の声を止めます。
2. **通常の重ね再生**：別のキャストの声を重ねます。同じキャストの開始→成功は切り替えます。最大8音声。
3. **最新優先（試験）**：最新100%、1つ前50%、2つ前20%、それより古い声は停止・無音です。終了した古い声は再開しません。現在鳴っている声の順位に応じて音量を選びます。中断はそのキャストの声だけを止めます。

最新優先はv0.8で再書き出しした音声区間が必要です。区間を含む新規出力では、ゲーム内で別の方式を保存していなければ最新優先が初期値です。既存の出力は再書き出しまで従来方式で再生できます。書き出し後はWoWを完全に再起動してください。

**試験モードの制限**：再生中の任意の音声ハンドルの音量変更を公開APIで確認できなかったため、0.25秒単位・20msの重なりを持つ音声区間を事前に作り、再生時に音量別ファイルを選びます。通常の連続音声の途中を直接調整する方式ではありません。音量の追従に最大約0.25秒とフレーム/タイマー遅延があり、負荷状況によって継ぎ目が聞こえる可能性があります。実ゲームでの聴感・FPS/CPU負荷は未検証です。音量はアドオン音量と掛け合わせて10%刻みに丸めるため、小さい設定では3声目が無音になる場合があります。

区間再生は音声が鳴っている間だけタイマーを使い、OnUpdateは使いません。最大3声・1声あたり毎秒4区間です。出力容量は通常の音量別ファイルに加え区間分が必要で、おおむね約3.9倍、ファイル数も増えます。書き出し確認で容量を確認できます。これらは設計上の上限/見積りで、実ゲームでの性能測定結果ではありません。気になる場合は「前の声を止める」へ切り替えてください。ゲーム全体やNPCの音量は変更しません。

成功音声の選び方は **均等ランダム / 連続重複を避ける / 順番** の3つです。設定はゲーム側に保存されます。

`/vcs debug` で診断ログを有効/無効、`/vcs diagnostics` で再生状態と直近ログをチャットへ表示します。ログは有効な時のみ最大60件をメモリに保持します。`/vcs mode duck|replace|overlap`、`/vcs variation random|norepeat|sequence` でも選べます。

共有画面では作者/説明を付けられ、受け取り側は試聴して必要な音声だけ選んで取り込めます。共有パックはアプリが加工し直すため、ゲーム用の区間ファイルを含めずに共有します。元録音を含める場合は切り取った前後も共有されることに注意してください。

二重起動は同じプロジェクトへのロックで防ぎ、通常保存でも外部変更を検出します。旧版はこのロックを知らないため、アップデート時には旧版を閉じてください。

## English

Open **Studio tools** for voice presets (Holy chant, Dark villain, Spirit, Dry), multi-ability FX application, custom preset saving, a chant-script recording assistant, condition simulation, diagnostics, snapshot restore, reversible game audio archival, and installed pack / individual recording management. FX application creates drafts; validate/save selected finished clips before export. Presets and scripts are project-local. Recording starts only after an explicit Record action and the three-second countdown.

Normal saves retain the preceding 30 project snapshots without deleting original takes. Restore assignments/settings from the history selector. Pack removal restores unchanged assignments it replaced, while preserving clips edited after import. Archived unused game WAV files remain in the project's audio-archive folder and can be copied back into the addon's Audio folder. Exit WoW before archiving.

In game, `/vcs` offers **Stop previous**, **Overlap** (up to eight voices), and **Newest priority (beta)**: newest 100%, previous 50%, third 20%, older voices stopped. Interruptions stop only the relevant cast. Start/success phases of one cast replace each other. Finished voices leave the ranking; voices stopped as fourth-or-older do not resume.

**Beta limitation:** this is pre-rendered 0.25-second segment playback with 20ms overlaps, not direct volume adjustment of an already-playing sound handle. Gain changes take up to ~0.25s plus frame/timer delay; seams are possible. Global addon gain is multiplied and rounded to existing 10% variants; low master settings can silence the third voice. No shared game CVars are changed. At most three voice timelines schedule four segments per second each; no OnUpdate is used. Actual in-game listening quality, FPS and CPU load have not been measured. Full clips plus segments use roughly 3.9x normal export storage and more files. Switch to Stop previous if quality is unsuitable.

Re-export from v0.8 and fully restart WoW to add segment files. Segment-enabled exports default to newest priority unless a game playback preference was already saved. Legacy exports continue their old behavior until re-exported. Success variations also support **Random / Avoid repeats / Sequence**. `/vcs debug` toggles a bounded 60-entry in-memory trace; `/vcs diagnostics` prints settings and recent playback/condition results.

Voice packs support author/description, selected-voice preview and selective import. They carry full finished takes (or explicitly selected editable originals), not the game's generated segment files. Close older editor versions before upgrading: they do not participate in the new project lock.


## v0.8.1: A/B fade test / 音量の下げ方を比較

最新版の「ゲームへ書き出す」を行い、WoWを完全に終了して再起動してください。`/vcs` → 最新優先 → 下げ方の **一気に下げる / なだらかに下げる（0.20秒）** で切り替えます。設定はゲームに保存され、方式変更時には再生中の追加音声を止めます。コマンドは `/vcs fade step` と `/vcs fade smooth`。以前の区間だけの出力では smooth 用の再書き出しが必要です。

- 一気に：次の0.25秒区切りで、20msの短いクロスフェードで目標音量へ。
- なだらかに：同じ区切りから、200ms（0.20秒）のクロスフェードで目標音量へ。100%→50%なら、中間の約0.10秒で約75%、0.20秒で50%になります。
- 次のアビリティで声が追加されてから、まず最大約0.25秒＋フレーム/タイマー遅延の待ちがあります。その後に上記の変化が始まります。smooth は新しい技から必ず0.20秒以内に完了する方式ではありません。追加の意図的な0.20秒待ちはありません。0.25秒待ち＋0.20秒フェードで最大約0.45秒＋処理遅延が目安です。
- フェードは下がる時だけでなく、先行する声が終了して順位が上がる時にも使います。最新100%・前50%・前々20%・それ以前停止は共通です。4声目で古い声を停止する時や、明示的な中断/ミュートの停止フェードはこの選択とは別です。
- 両方の区間データを事前生成します。通常出力と比較した容量の目安は合計約3.9倍（短い音声・重複排除・ヘッダで変わります）。元録音は保持します。ゲーム中のDSPや共有音量CVarの変更はありません。実ゲームの継ぎ目・聴感・FPS/CPU負荷はまだ未検証です。

比較は同じ声・同じ音量・同じ技順で行ってください。「声の継ぎ目」「新しい声の聞き取りやすさ」「音量変更の遅さ」「カクつき」を記録すると調整しやすくなります。録音を5秒程度にすると、次の技が使える時点でも声が残るため比較しやすくなります。

English: Re-export with v0.8.1, fully restart WoW, open `/vcs`, choose Newest priority, then **Step down** or **Smooth down (0.20s)**. `/vcs fade step|smooth` also works. Both wait for the next 0.25s boundary (plus frame/timer delay). Step uses a ~20ms crossfade; smooth transitions over 200ms starting at that boundary, with no additional intentional wait. A 100→50 change is ~75 halfway through the 200ms transition. Worst nominal event-to-target timing is ~0.45s plus scheduling delay for smooth. Mode changes stop current added voices. Fade applies to rank promotions too; explicit stops/fourth-voice removal use their own short stop fade. Both pre-rendered banks increase total export storage to roughly 3.9x ordinary full-clip volume variants. Actual live-game quality and performance are unverified. Compare the same voices, master gain and ability sequence; report seams, intelligibility, response delay and stutter.
