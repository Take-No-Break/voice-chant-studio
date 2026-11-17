"""Run addon lifecycle tests in Lua without opening WoW or using a microphone."""
from pathlib import Path
import json
import sys
import unittest

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parent / 'lua-test'))


class AddonLifecycleTests(unittest.TestCase):
    def runtime(self, bindings, *, player_class='MAGE', catalog='{}'):
        from lupa import LuaRuntime
        lua = LuaRuntime()
        lua.globals().testPlayerClass = player_class
        lua.execute('''
VoiceChantStudioDB = {}; SlashCmdList = {}; plays = {}; stops = {}
now = 0; timers = {}; channelID = nil; channelEndMS = nil
function UnitClass() return "Test class", testPlayerClass end
function UnitChannelInfo()
    if channelID then return "Channel", nil, nil, 0, channelEndMS, nil, false, channelID end
end
function GetTime() return now end
function PlaySoundFile(file, channel)
    table.insert(plays, {file=file, channel=channel})
    return true, #plays
end
function StopSound(handle) table.insert(stops, handle) end
function print() end
function issecretvalue(v) return v == "SECRET" end
C_Timer = {After=function(delay, fn) table.insert(timers, {at=now+delay, fn=fn}) end}
function advanceTo(t)
    now = t
    local pending = timers
    timers = {}
    for _, timer in ipairs(pending) do
        if timer.at <= now then timer.fn() else table.insert(timers, timer) end
    end
end
local function widget()
    local w = {}
    local nothing = function() end
    w.TitleText = {SetText=nothing}
    setmetatable(w, {__index=function(_, key)
        if key == "SetScript" then return function(_, name, fn) if name == "OnEvent" then handler = fn end end end
        if key == "SetText" then return function(_, text) lastText = text end end
        if key == "CreateFontString" then return function() return widget() end end
        return nothing
    end})
    return w
end
function CreateFrame() return widget() end
function InCombatLockdown() return false end
UIParent = {}; ChatFontNormal = {}; Enum = {SpellBookSpellBank={Player=0}}
C_SpellBook = {GetNumSpellBookSkillLines=function() return 0 end,
              GetCurrentLevelSpells=function() return {} end}
C_Spell = {GetSpellName=function(id) return "Spell " .. id end,
           GetSpellInfo=function(id) return {name="Spell " .. id, castTime=0} end}
function event(name, guid, id, unit) handler(nil, name, unit or "player", guid, id) end
''')
        lua.execute('VoiceChantConfig={gap=.2,stopOnCancel=true,bindings=' + bindings + '}')
        lua.execute('VoiceChantCatalog=' + catalog)
        lua.execute((BASE / 'addon' / 'VoiceChantStudio.lua').read_text(encoding='utf8'))
        return lua

    def test_normal_completion_survives_reordered_stop_and_duplicate_success(self):
        lua = self.runtime('''{
            {class="MAGE",ids={133},event="start",file="prepare.wav"},
            {class="MAGE",ids={133},event="success",file="finish.wav"},
            {class="MAGE",ids={133},event="cancel",file="cancel.wav"}}''')
        lua.execute('''
event("UNIT_SPELLCAST_START", "fire-1", 133)
event("UNIT_SPELLCAST_STOP", "fire-1", 133)
now=.05; event("UNIT_SPELLCAST_SUCCEEDED", "fire-1", 133)
advanceTo(.3)
assert(#plays == 2 and plays[2].file == "finish.wav")
assert(#stops == 1)
now=1; event("UNIT_SPELLCAST_SUCCEEDED", "fire-1", 133)
event("UNIT_SPELLCAST_STOP", "fire-1", 133); advanceTo(2)
assert(#plays == 2 and #stops == 1)
''')

    def test_completed_start_only_clip_keeps_its_tail(self):
        lua = self.runtime('{{ids={133},event="start",file="prepare.wav"}}')
        lua.execute('''
event("UNIT_SPELLCAST_START", "fire-2", 133)
now=1; event("UNIT_SPELLCAST_SUCCEEDED", "fire-2", 133)
event("UNIT_SPELLCAST_STOP", "fire-2", 133); advanceTo(2)
assert(#plays == 1 and #stops == 0)
''')

    def test_cancel_only_clip_plays_without_an_active_preparation_and_deduplicates(self):
        lua = self.runtime('{{ids={133},event="cancel",file="cancel.wav"}}')
        lua.execute('''
event("UNIT_SPELLCAST_START", "fire-3", 133)
event("UNIT_SPELLCAST_INTERRUPTED", "fire-3", 133)
event("UNIT_SPELLCAST_FAILED", "fire-3", 133)
event("UNIT_SPELLCAST_STOP", "fire-3", 133); advanceTo(1)
assert(#plays == 1 and plays[1].file == "cancel.wav" and #stops == 0)
''')

    def test_short_and_long_channel_cancellation_ignores_initial_success(self):
        for cancelled_at in (1, 4):
            with self.subTest(cancelled_at=cancelled_at):
                lua = self.runtime('''{
                    {ids={5143},event="start",file="missiles.wav"},
                    {ids={5143},event="cancel",file="cancel.wav"}}''')
                lua.globals().cancelledAt = cancelled_at
                lua.execute('''
channelID=5143; channelEndMS=8000
event("UNIT_SPELLCAST_CHANNEL_START", "missiles-1", 5143)
event("UNIT_SPELLCAST_SUCCEEDED", "missiles-1", 5143)
advanceTo(cancelledAt); channelID=nil
event("UNIT_SPELLCAST_CHANNEL_STOP", "missiles-1", 5143)
event("UNIT_SPELLCAST_INTERRUPTED", "missiles-1", 5143)
assert(#plays == 2 and plays[2].file == "cancel.wav" and #stops == 1)
''')

    def test_natural_channel_completion_and_channel_time_updates(self):
        lua = self.runtime('{{ids={5143},event="start",file="missiles.wav"}}')
        lua.execute('''
channelID=5143; channelEndMS=5000
event("UNIT_SPELLCAST_CHANNEL_START", "missiles-2", 5143)
event("UNIT_SPELLCAST_SUCCEEDED", "missiles-2", 5143)
now=1; channelEndMS=7000
event("UNIT_SPELLCAST_CHANNEL_UPDATE", "missiles-2", 5143)
advanceTo(7); channelID=nil
event("UNIT_SPELLCAST_CHANNEL_STOP", "missiles-2", 5143)
assert(#plays == 1 and #stops == 0)
''')

    def test_success_before_channel_start_still_allows_start_only_voice(self):
        lua = self.runtime('{{ids={5143},event="start",file="missiles.wav"}}')
        lua.execute('''
channelID=5143; channelEndMS=8000
event("UNIT_SPELLCAST_SUCCEEDED", "missiles-3", 5143)
event("UNIT_SPELLCAST_CHANNEL_START", "missiles-3", 5143)
assert(#plays == 1)
now=1; event("UNIT_SPELLCAST_INTERRUPTED", "missiles-3", 5143)
channelID=nil; event("UNIT_SPELLCAST_CHANNEL_STOP", "missiles-3", 5143)
assert(#stops == 1)
''')

    def test_late_old_cast_stop_does_not_stop_new_cast_of_same_spell(self):
        lua = self.runtime('{{ids={133},event="start",file="prepare.wav"}}')
        lua.execute('''
event("UNIT_SPELLCAST_START", "old", 133)
now=1; event("UNIT_SPELLCAST_START", "new", 133)
event("UNIT_SPELLCAST_STOP", "old", 133); advanceTo(2)
assert(#plays == 2 and #stops == 1)
event("UNIT_SPELLCAST_INTERRUPTED", "new", 133)
assert(#stops == 2)
''')

    def test_secret_values_and_non_player_events_are_ignored(self):
        lua = self.runtime('{{ids={133},event="success",file="fire.wav"}}')
        lua.execute('''
event("UNIT_SPELLCAST_SUCCEEDED", "SECRET", 133)
event("UNIT_SPELLCAST_SUCCEEDED", "a", "SECRET")
event("UNIT_SPELLCAST_SUCCEEDED", "a", 133, "SECRET")
event("UNIT_SPELLCAST_SUCCEEDED", "a", 133, "target")
assert(#plays == 0 and #timers == 0)
event("UNIT_SPELLCAST_SUCCEEDED", "a", 133)
assert(#plays == 1 and plays[1].channel == "Dialog")
''')

    def test_client_without_cast_guids_can_repeat_an_instant_spell(self):
        lua = self.runtime('{{ids={133},event="success",file="fire.wav"}}')
        lua.execute('''
event("UNIT_SPELLCAST_SUCCEEDED", nil, 133)
now=1; event("UNIT_SPELLCAST_SUCCEEDED", nil, 133)
assert(#plays == 2)
''')

    def test_class_scopes_bindings_and_unlearned_spellbook_entries(self):
        lua = self.runtime('''{
            {class="MAGE",ids={133},event="success",file="mage.wav"},
            {class="PALADIN",ids={133},event="success",file="paladin.wav"}}''',
            catalog='{{id=133,class="MAGE"},{id=635,class="PALADIN"}}')
        lua.execute('''
event("UNIT_SPELLCAST_SUCCEEDED", "mage-1", 133)
assert(#plays == 1 and plays[1].file == "mage.wav")
SlashCmdList.VOICECHANTSTUDIO("")
''')
        rows = json.loads(lua.globals().lastText)
        self.assertEqual(rows, [{'id': 133, 'name': 'Spell 133', 'class': 'MAGE',
                                 'passive': False, 'cast_seconds': 0}])

    def test_slash_test_skips_recordings_for_other_classes(self):
        lua = self.runtime('''{
            {class="PALADIN",ids={635},event="start",file="paladin.wav"},
            {class="MAGE",ids={133},event="start",file="mage.wav"}}''')
        lua.execute('''
SlashCmdList.VOICECHANTSTUDIO("test")
assert(#plays == 1 and plays[1].file == "mage.wav")
''')
        lua = self.runtime('{{class="PALADIN",ids={635},event="start",file="paladin.wav"}}')
        lua.execute('''
SlashCmdList.VOICECHANTSTUDIO("test")
assert(#plays == 0)
''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
