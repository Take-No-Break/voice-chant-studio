# Voice Chant Studio

Read AI-SETUP.md and README.en.md before assisting users. This is a local Windows audio editor with a WoW Forever Lua addon. No AI runtime is required.

- Preserve original recordings and existing clip keys. Slot 1 success remains `ability:success`; slots 2–5 are `ability:success:N`. Enabled count lives in `success_variations[ability]`, defaults to 1. Lowering the count excludes slots from export but never deletes recordings.
- Never seed the game's global random generator. Pick once per accepted success event, uniformly from saved enabled files. Deduplicate repeated game events. No continuous polling or audio preloading for variation selection.
- Volume variants affect only this addon's files, never shared game sound CVars. Save game volume in VoiceChantStudioDB.
- Tests must use temporary projects, synthetic audio and simulated game events. Run unittest discover; do not record a real microphone without a user-driven recording request.
- Do not publish user audio, account files, local paths or secrets. Public release is a separate action from preparing source archives. Preserve third-party notices and verify asset redistribution rights.

- Preserve link base_key/condition and clip effects fields. Conditional rows must stay separate from normal abilities during migration/import. Effects render offline, never in Lua. Read LINK-EXAMPLES.md before explaining links.
