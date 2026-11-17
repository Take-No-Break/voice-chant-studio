# WoW Forever catalog, v0.3

The catalog uses the installed **WhatsTraining/Classes/Camelot** data loaded for the Forever client, not its Vanilla or TBC class tables. The local Priest file explicitly checks `forClass("PRIEST")`.

- Priest: every trainer ID, prerequisite rank, required talent root, starting spells, all 12 Priest entries in Camelot/QuestSpells.lua, plus name-checked unranked active talents (Inner Focus, Power Infusion, Silence, Vampiric Embrace and Shadowform).
- Mage: existing 55 entries and keys retained; added quest-granted Polymorph (Pig, 28272) and Conjure Water rank 7 (10140). Existing trainer evidence is in MAGE-CATALOG.md.
- Paladin: existing entries and keys retained.
- Names, cast times and icon names use `https://nether.wowhead.com/forever/tooltip/spell/{ID}`. No character, account, or recording data is sent.

Lesser Heal, Smite, Flash Heal, Holy Fire and Holy Nova are **PRIEST**, as confirmed by the Forever class table and the Forever tooltips. The app now includes this class; they are not added as Mage spells.

The JSON report records exact local source hashes, IDs and per-spell source URLs. Japanese names are descriptive labels, not official localization. Icons are fetched by the tooltip's icon name, bundled for offline display, with sources in Icon-Sources.json.

This starter catalog includes unlearned, talented and race-specific abilities; it does not mean your current character knows them. Passive talent trees and every future/item/build-specific spell are not guaranteed. Import `/voicechant` from the actual client to add your own current spells. Unknown imported IDs have a fallback icon.

Rebuild with `python build_forever_catalog.py`, then `python build_icons.py`. Existing editor row keys/metadata remain intact and rank IDs are added. The builder never opens user projects or writes to the game installation.
