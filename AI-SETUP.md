# Voice Chant Studio: setup for desktop AI assistants

User goal: record local voice clips and export an addon into the user's own WoW Forever installation. No AI, API key, server, or paid service is required to run the application.

1. On Windows, download the Windows release ZIP and extract it to a stable user-selected folder. Launch the versioned VoiceChantStudio EXE. Do not run the source .py unless the user wants development setup.
2. Close older editor instances before opening the same project. Do not overwrite a running user's project from scripts. Back up the complete project folder before migration.
3. The editor tries Blizzard registry entries and common folders on available drives. Never assume the publisher's drive letter, Windows username, account or character name.
4. If discovery fails, in Battle.net select WoW Forever and use its gear menu > Show in Explorer. Find `_forever_` containing `Wow.exe`. Use Browse in the editor and select `_forever_` (its parent World of Warcraft folder is accepted too). Retail `_retail_` is not a valid destination.
5. Choose a class, ability, playback phase. For Successful cast / Instant ability choose 1–5 Success voices, then a Voice slot. Record or import, trim and Save finished clip for each slot. Only saved, enabled slots are exported. Empty slots are skipped; recorded slots are selected with equal probability, and repeats are allowed. Start and interruption retain one voice each.
6. Export to game. Only Interface/AddOns/VoiceChantStudio is written. Do not modify game executables, data archives, other addons or account settings. If access is denied, create an addon ZIP and help the user copy its VoiceChantStudio folder into Interface/AddOns.
7. Fully restart WoW after adding files. Enable Voice Chant Studio - Voice Effects in AddOns. Enable Sound and Dialog in Options > Audio. Open `/vcs` for independent voice volume; `/voicechant test` previews a recorded voice. `/voicechant` alone exports spellbook text to import into the editor.
8. Saved editor data lives under `%LOCALAPPDATA%/VoiceChantStudio`. The default project folder is Projects/Paladin for historical compatibility and stores all supported classes. Original takes in originals/ are immutable. Preserve clips and success_variations when upgrading. Source takes and account directories must never be uploaded to GitHub without the user's explicit direction.

Verification: use synthetic audio and fake devices, `python -m unittest discover -v`. Real recording, listening quality and live WoW events require separate checks. Never claim live verification based only on unit tests. Pause before reloading if the user has unsaved HUD changes. Never automate authentication/security prompts.

Build: Python, dependencies in requirements.txt; `python -m PyInstaller --noconfirm VoiceChantStudio.spec`. Build helpers may require Pillow; Lua tests require lupa and luaparser. Build scripts referencing local trainer files require an installed Forever client. The shipped catalog works offline without running builders.

Publication: distribute the clean source archive and application ZIP; do not include Projects, originals, user Config.lua, WTF, caches, local logs, access tokens or any game installation. Bundled spell artwork is third-party game artwork; review its redistribution terms before public release. No redistribution license is granted by this document. Choose a repository/license and review source asset provenance before publishing.
