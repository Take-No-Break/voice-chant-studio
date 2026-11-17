# User-created spell links / ユーザー連携リンク

Links change this addon's voice only. They never cast spells, change combat effects, or guarantee a talent/build is available. The user chooses both spells and the condition; no presets are silently enabled.

## How to use

1. Select a class, then **Create spell link / 連携リンクを作成**.
2. Spell 1 is the condition; Spell 2 is the ability whose voice changes.
3. Choose one condition: **Buff on player**, **Your debuff on target**, or **Previous successful spell** within 1–30 seconds (default 8). Previous means the immediately preceding successful spell, not any spell used during that interval.
4. Record/import on the new **[LINK: ...]** row. It supports the existing three phases and 1–5 success voice slots, plus Voice FX/EQ.
5. Save finished clip, export and restart the game. If no link matches, or a linked phase has no assigned voice, the normal ability voice is used. If multiple links match, the first exported matching link with a voice for that phase wins. One selected voice plays; normal and linked voices are not stacked.

技1・技2をユーザーが選ぶ方式です。効果中を選ぶ場合は、実際にバフ／デバフとして付与される技を選択してください。条件となるオーラのIDと発動技のIDが異なる場合、ゲームから取得した実際のオーラIDを持つ項目が必要です。パッシブの習得だけや、敵の行動・装備・HP・コンボポイントなどは現在の条件には含みません。

## Retained research and examples

These are setup ideas, not preconfigured rules or a complete list of game interactions. Verify the actual learned spellbook and aura IDs in the client. Sequence examples are voice choreography; they do not claim a game damage bonus.

| Class | Candidate condition → replacement ability | Evidence / scope |
|---|---|---|
| Paladin | Each active Seal → Judgement | Blizzard confirms the Seal/Judgement system; **Forever Judgement no longer consumes the active Seal**. Source 1. |
| Paladin | Righteous Fury active → Holy Strike | Official Iron Creed interaction; talent required for the game damage-reduction effect. The voice link merely tests the active buff. Source 1. |
| Paladin | Light's Vigil → Holy Shock | Official follow-up interaction. Friendly-target aura conditions are not currently supported; a Previous successful spell link is an alternative voice sequence, not exact aura detection. Source 1. |
| Mage | Presence of Mind active → Fireball; Frost Nova → Frostbolt | Player-aura or previous-spell voice conditions. Freeze/crit results depend on actual target state/talents. Source 2. |
| Shaman | Nature's Swiftness active → Healing Wave; Lightning Mastery active → Lightning Bolt | Forever spell names/IDs come from its tooltip provider; do not substitute Classic Elemental Mastery naming blindly. Source 2 and all-classes-report.json. |
| Rogue | Stealth active → Ambush; Cold Blood active → Eviscerate | Official Stealth/finisher/Cold Blood toolkit. Consumed effects are captured before the cast where supported. Source 3. |
| Warlock | Immolate on target → Conflagrate; Fel Domination active → summon | Build/learned-spell dependent. Curses and Banes differ in Forever. Source 3. |
| Hunter | Hunter's Mark on target → Aimed Shot | User-chosen target-debuff voice rule, not a claim of an extra Aimed Shot effect. Source 4. |
| Druid | Prowl active → Ravage; Cat Form active → Shred | Form/Stealth conditions rely on the actual player aura being exposed by the client. Source 4. |
| Priest | Power Infusion active → Smite; Shadowform active → Mind Blast | User-chosen buff-dependent voice branches. Source 5. |
| Warrior | Battle Stance active → Overpower; Defensive Stance active → Shield Slam | The link tests the exposed aura only, not dodge/shield/cooldown requirements. Source 5. |

1. https://news.blizzard.com/en-us/article/24302099/world-of-warcraft-forever-class-deep-dives-paladin
2. https://worldofwarcraft.blizzard.com/en-us/news/24302097/world-of-warcraft-forever-class-deep-dives-mage-and-shaman
3. https://news.blizzard.com/en-us/article/24310968/world-of-warcraft-forever-class-deep-dives-rogue-and-warlock
4. https://news.blizzard.com/en-us/article/24301515/world-of-warcraft-forever-class-deep-dives-hunter-and-druid
5. https://worldofwarcraft.blizzard.com/en-us/news/24301514/

## Performance / limitations

Only exported links with finished audio activate the optional condition engine. There is no OnUpdate or combat-log polling. Aura events update only player/target caches; only watched spell IDs are retained, and only linked casts request a pre-cast snapshot. The previous successful spell is stored as one ID/time pair. Target snapshots are captured against the current target; mouseover/focus casts targeting somebody else are deliberately not matched to that target cache. Unreadable/secret IDs are ignored, causing normal-voice fallback.

No exact game FPS or memory claim is made: final live-client behavior must be verified separately. The code does not resolve hypothetical buffs that do not appear as readable auras. Effects are offline DSP in the editor, never realtime game processing.

## Voice FX / EQ

Select a recorded clip, open **Voice FX / EQ**: pitch ±12 semitones (duration preserved), low/mid/high EQ ±12 dB, vibrato depth/rate, tremolo depth/rate. Preview, Apply, then Save finished clip. Reset effects returns neutral settings. Originals stay unchanged. Strong pitch shifts can produce phase-vocoder artifacts; this is a basic offline voice editor, not a multitrack/VST DAW.
