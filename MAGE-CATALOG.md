# Mage catalog snapshot

- Built from the locally installed `WhatsTraining/Classes/Camelot/Mage.lua` trainer data.
- Included each trainer spell ID, `requiredIds` prerequisite, and `requiredTalentId` root ID. Added Fireball and Frost Armor starting IDs plus Arcane Power, Presence of Mind, Ice Block, and Cold Snap after matching their names in the Forever tooltip response.
- Resolved English names and cast duration from Wowhead's Forever tooltip endpoint. All 185 requested IDs resolved. No account or character data was sent to this provider.
- Grouped exact English spell names into 55 Mage rows. Rank IDs are unique within the class. The existing 50 Paladin rows are preserved unchanged.
- Added descriptive Japanese `name_ja` labels to all 55 Mage rows. These are convenience translations, not official Japanese localization.
- Added `channeled: true` to channel spells. Their `cast_seconds` remains the actual tooltip cast time (usually zero); the UI should select its start phase when `cast_seconds > 0` **or** `channeled` is true.
- This is an initial spell catalog, not a claim that every future, quest-granted, item-granted, or build-specific ability is present. The game's spellbook import remains the route for the player's current spells and later changes.

Rebuild with `python build_mage_catalog.py`. Cached tooltip JSON is saved under `tooltip-cache-mage/`; `mage-catalog-report.json` records coverage and validation. The script does not execute addon code or change game files.
