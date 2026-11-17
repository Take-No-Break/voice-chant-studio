-- Voice Chant Studio: additive audio only. Never mutes or casts spells.
local cfg = VoiceChantConfig or {bindings={}, gap=.2, stopOnCancel=true}
local byID, byName, active, lastPlayed = {}, {}, nil, -100
local volumeFiles = {}
local function getVolume()
    local value = tonumber(VoiceChantStudioDB and VoiceChantStudioDB.volume) or 100
    if value ~= value then value = 100 end
    return math.floor(math.max(0, math.min(100, value))/10+.5)*10
end
local function readable(v) return not (issecretvalue and issecretvalue(v)) end
local function say(s) print("|cff70dcc7Voice Chant|r: "..s) end
local _, playerClass = nil, nil
local function bind(target,event,file)
    if event~='success' then target[event]=file; return end
    local choices=target[event]
    if type(choices)~='table' then choices=choices and {choices} or {};target[event]=choices end
    for _,existing in ipairs(choices) do if existing==file then return end end
    if #choices<5 then choices[#choices+1]=file end
end
if UnitClass then _, playerClass = UnitClass("player") end
for _, row in ipairs(cfg.bindings or {}) do
    -- Older exports did not include class. Keep those working as well.
    if not row.class or not playerClass or row.class == playerClass then
    if row.volumes then volumeFiles[row.file] = row.volumes end
    for _, id in ipairs(row.ids) do
        byID[id] = byID[id] or {}; bind(byID[id],row.event,row.file)
        if C_Spell and C_Spell.GetSpellName then
            local name = C_Spell.GetSpellName(id)
            if readable(name) and name then byName[name] = byName[name] or {}; bind(byName[name],row.event,row.file) end
        end
    end
    end
end
local function lookup(id)
    if not readable(id) or type(id) ~= "number" then return end
    if byID[id] then return byID[id] end
    local name = C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(id)
    if readable(name) and name then return byName[name] end
end
local function stop()
    if active and active.handle then StopSound(active.handle, 100) end
    active = nil
end
local function play(file, id, guid, phase, cast)
    if VoiceChantStudioDB and VoiceChantStudioDB.muted then return end
    if not file then return end
    if GetTime()-lastPlayed < (cfg.gap or .2) and phase ~= 'cancel' then return end
    local volume = getVolume()
    if volume == 0 then return end
    if type(file)=='table' then
        if #file==0 then return end
        file=file[#file==1 and 1 or math.random(#file)]
    end
    if volume < 100 then
        local choices = volumeFiles[file]
        if not choices or not choices[volume] then
            say("Export this voice pack again to enable independent volume control.")
            return
        end
        file = choices[volume]
    end
    if GetTime()-lastPlayed < (cfg.gap or .2) and phase ~= "cancel" then return end
    stop()
    local ok, handle = PlaySoundFile(file, "Dialog")
    if ok then
        active = {handle=handle, id=id, guid=guid, phase=phase, cast=cast}
        lastPlayed = GetTime()
        return true
    else
        if GetCVar and (GetCVar("Sound_EnableAllSound") == "0" or GetCVar("Sound_EnableDialog") == "0") then
            say("Enable Sound and Dialog in Options > Audio. Voice Chant Studio uses Dialog.")
        else
            say("Cannot load audio. Fully restart WoW after exporting new sound files.")
        end
    end
end
local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
for _, event in ipairs({"UNIT_SPELLCAST_START", "UNIT_SPELLCAST_CHANNEL_START", "UNIT_SPELLCAST_CHANNEL_UPDATE", "UNIT_SPELLCAST_SUCCEEDED", "UNIT_SPELLCAST_FAILED", "UNIT_SPELLCAST_INTERRUPTED", "UNIT_SPELLCAST_STOP", "UNIT_SPELLCAST_CHANNEL_STOP"}) do
    frame:RegisterUnitEvent(event, "player")
end
-- Cast state is separate from audio state: a cancellation clip must also work
-- when no preparation clip was recorded, or its playback was throttled.
local casts, recentByID = {}, {}
local function castFor(id, guid, event)
    local key = guid or ("spell:"..id)
    local cast = (not guid and recentByID[id]) or casts[key]
    local starting = event == "UNIT_SPELLCAST_START" or event == "UNIT_SPELLCAST_CHANNEL_START"
    -- A client without cast GUIDs cannot deduplicate independent instant casts.
    -- Reuse its current cast for terminal events, but let the next activation run.
    local freshWithoutGUID = not guid and cast and ((starting and cast.ended)
        or (event == "UNIT_SPELLCAST_START" and cast.succeeded)
        or (event == "UNIT_SPELLCAST_SUCCEEDED" and cast.succeeded and not cast.channel))
    if not cast or cast.id ~= id or freshWithoutGUID then
        cast = {id=id, guid=guid}
        casts[key] = cast
        C_Timer.After(120, function()
            if casts[key] == cast then casts[key] = nil end
            if recentByID[id] == cast then recentByID[id] = nil end
        end)
    end
    recentByID[id] = cast
    return cast
end
local function channelEnd(cast)
    if not UnitChannelInfo then return end
    local _, _, _, _, ends, _, _, spellID = UnitChannelInfo("player")
    if readable(spellID) and spellID == cast.id and readable(ends) and type(ends) == "number" then
        cast.channel = true
        cast.channelEnd = ends / 1000
    end
end
local function cancel(cast, binding)
    if cast.cancelled then return end
    cast.cancelled, cast.ended = true, true
    if cfg.stopOnCancel and active and active.cast == cast then stop() end
    play(binding.cancel, cast.id, cast.guid, "cancel", cast)
end
frame:SetScript("OnEvent", function(_, event, unit, guid, id)
    if event == "ADDON_LOADED" then
        if unit == "VoiceChantStudio" then
            VoiceChantStudioDB = VoiceChantStudioDB or {}
            VoiceChantStudioDB.volume = getVolume()
            if VoiceChantStudioOptions then VoiceChantStudioOptions.Initialize() end
        end
        return
    end
    if not readable(unit) or unit ~= "player" or not readable(id) or not readable(guid) then return end
    local binding = lookup(id)
    if not binding then return end
    local cast = castFor(id, guid, event)
    if event == "UNIT_SPELLCAST_START" or event == "UNIT_SPELLCAST_CHANNEL_START" then
        if event == "UNIT_SPELLCAST_CHANNEL_START" then cast.channel = true; channelEnd(cast) end
        if cast.started or cast.cancelled or cast.ended then return end
        cast.started = true
        -- Some clients send a channel's SUCCEEDED before CHANNEL_START.
        -- Do not replace an activation clip already played for that same cast.
        if not cast.successPlayed then play(binding.start, id, guid, "start", cast) end
    elseif event == "UNIT_SPELLCAST_CHANNEL_UPDATE" then
        cast.channel = true; channelEnd(cast)
    elseif event == "UNIT_SPELLCAST_SUCCEEDED" then
        if cast.succeeded or cast.cancelled then return end
        cast.succeeded = true
        channelEnd(cast)
        if binding.success then
            -- A completion clip deliberately replaces this addon's preparation clip only.
            if active and active.cast == cast then stop(); lastPlayed=-100 end
            cast.successPlayed = play(binding.success, id, guid, "success", cast) or false
        end
    elseif event == "UNIT_SPELLCAST_FAILED" or event == "UNIT_SPELLCAST_INTERRUPTED" then
        -- A channel's activation succeeds at its beginning, so that success
        -- cannot be used to decide whether the channel was later interrupted.
        channelEnd(cast)
        if not cast.succeeded or cast.channel then cancel(cast, binding) end
    elseif event == "UNIT_SPELLCAST_CHANNEL_STOP" then
        cast.channel, cast.ended = true, true
        -- At a natural channel finish leave the voice tail intact. If the
        -- client has no readable end time, stop the preparation voice safely.
        if not cast.channelEnd or GetTime() < cast.channelEnd - .12 then
            cancel(cast, binding)
        end
    elseif event == "UNIT_SPELLCAST_STOP" then
        if cast.channel then return end
        cast.ended = true
        -- STOP can precede SUCCEEDED. Defer briefly, then only stop an unfinished cast.
        C_Timer.After(.15, function()
            if cast.started and not cast.succeeded and not cast.channel then cancel(cast, binding) end
        end)
    end
end)

local function escapeJSON(s)
    return '"'..s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('[%z\1-\31]', function(c) return string.format('\\u%04x', string.byte(c)) end)..'"'
end
local function spellbookJSON()
    local rows, seen = {}, {}
    local _, class = UnitClass("player")
    local function add(id, passive)
        if not readable(id) or type(id) ~= "number" or seen[id] then return end
        local info = C_Spell.GetSpellInfo(id)
        if not info or not readable(info.name) or not info.name then return end
        seen[id] = true
        local cast = readable(info.castTime) and tonumber(info.castTime) or 0
        rows[#rows+1] = '{"id":'..id..',"name":'..escapeJSON(info.name)..',"class":'..escapeJSON(class)..',"passive":'..(passive and "true" or "false")..',"cast_seconds":'..(cast/1000)..'}'
    end
    local bank = Enum.SpellBookSpellBank.Player
    for i=1,C_SpellBook.GetNumSpellBookSkillLines() do
        local line = C_SpellBook.GetSpellBookSkillLineInfo(i)
        if line then
            for slot=line.itemIndexOffset+1,line.itemIndexOffset+line.numSpellBookItems do
                local info = C_SpellBook.GetSpellBookItemInfo(slot, bank)
                if info then add(info.spellID, info.isPassive) end
            end
        end
    end
    if C_SpellBook.GetCurrentLevelSpells then
        for level=1,60 do
            local ok, ids = pcall(C_SpellBook.GetCurrentLevelSpells, level)
            if ok and type(ids) == "table" then for _, id in ipairs(ids) do add(id, false) end end
        end
    end
    if C_ClassTalents and C_Traits and C_ClassTalents.GetActiveConfigID then
        local ok, configID = pcall(C_ClassTalents.GetActiveConfigID)
        if ok and configID then
            local okInfo, config = pcall(C_Traits.GetConfigInfo, configID)
            if okInfo and config and config.treeIDs then
                for _, tree in ipairs(config.treeIDs) do
                    local okNodes, nodes = pcall(C_Traits.GetTreeNodes, tree)
                    if okNodes and nodes then for _, nodeID in ipairs(nodes) do
                        local okNode, node = pcall(C_Traits.GetNodeInfo, configID, nodeID)
                        if okNode and node and node.entryIDs then for _, entryID in ipairs(node.entryIDs) do
                            local okEntry, entry = pcall(C_Traits.GetEntryInfo, configID, entryID)
                            if okEntry and entry and entry.definitionID then
                                local okDef, definition = pcall(C_Traits.GetDefinitionInfo, entry.definitionID)
                                if okDef and definition then add(definition.spellID, false) end
                            end
                        end end
                    end end
                end
            end
        end
    end
    -- Include only the current class's bundled unlearned ranks.
    for _, row in ipairs(VoiceChantCatalog or {}) do
        if row.class == class or (not row.class and class == "PALADIN") then add(row.id, false) end
    end
    return '['..table.concat(rows, ',')..']'
end
local panel
local function showBook()
    if InCombatLockdown() then say("Open this panel after leaving combat."); return end
    if not panel then
        panel = CreateFrame("Frame", "VoiceChantBookExport", UIParent, "BasicFrameTemplateWithInset")
        panel:SetSize(620, 380); panel:SetPoint("CENTER"); panel:SetFrameStrata("DIALOG")
        panel.TitleText:SetText("Voice Chant Studio - Spellbook export")
        local label = panel:CreateFontString(nil,"OVERLAY","GameFontHighlight")
        label:SetPoint("TOPLEFT", 18,-40); label:SetWidth(580)
        label:SetText("Press Ctrl+A then Ctrl+C. Paste into the desktop app spellbook import.")
        local scroll = CreateFrame("ScrollFrame",nil,panel,"UIPanelScrollFrameTemplate")
        scroll:SetPoint("TOPLEFT",18,-80); scroll:SetPoint("BOTTOMRIGHT",-35,20)
        local edit = CreateFrame("EditBox",nil,scroll)
        edit:SetMultiLine(true); edit:SetFontObject(ChatFontNormal); edit:SetWidth(550); edit:SetAutoFocus(false)
        edit:SetScript("OnEscapePressed",function() panel:Hide() end)
        scroll:SetScrollChild(edit); panel.edit=edit
    end
    local ok, json = pcall(spellbookJSON)
    if not ok then say("Spellbook export failed: "..tostring(json)); return end
    panel:Show(); panel.edit:SetText(json); panel.edit:SetFocus(); panel.edit:HighlightText()
end
SLASH_VOICECHANTSTUDIO1 = "/voicechant"
local function testVoice()
    if VoiceChantStudioDB and VoiceChantStudioDB.muted then say("Extra voice is muted."); return end
    if getVolume() == 0 then say("Voice volume is 0%."); return end
    for _, row in ipairs(cfg.bindings or {}) do
        if not row.class or not playerClass or row.class == playerClass then
            lastPlayed=-100
            return play(row.file, row.ids[1], nil, "test")
        end
    end
    say("Export a recording for this class from the desktop app first.")
end
local function setVolume(value)
    value = tonumber(value)
    if not value or value ~= value or value < 0 or value > 100 then return false end
    VoiceChantStudioDB = VoiceChantStudioDB or {}
    VoiceChantStudioDB.volume = math.floor(value/10+.5)*10
    stop()
    if VoiceChantStudioOptions then VoiceChantStudioOptions.Refresh() end
    return true
end
VoiceChantStudioAPI = {GetVolume=getVolume, SetVolume=setVolume, Test=testVoice, Stop=stop}
SlashCmdList.VOICECHANTSTUDIO = function(msg)
    msg = (msg or ""):lower():match("^%s*(.-)%s*$")
    VoiceChantStudioDB = VoiceChantStudioDB or {}
    if msg == "mute" then VoiceChantStudioDB.muted=true; stop(); say("Extra voice muted.")
    elseif msg == "unmute" then VoiceChantStudioDB.muted=false; say("Extra voice enabled.")
    elseif msg == "test" then testVoice()
    elseif msg == "settings" or msg == "options" or msg == "volume" then
        if VoiceChantStudioOptions then VoiceChantStudioOptions.Open() end
    elseif msg:match("^volume%s+") then
        if setVolume(msg:match("^volume%s+(.+)$")) then say("Voice volume: "..getVolume().."%.")
        else say("Use /vcs volume 0 to 100 (10% steps).") end
    else showBook() end
end
SLASH_VOICECHANTSETTINGS1 = "/vcs"
SlashCmdList.VOICECHANTSETTINGS = function(msg)
    if not msg or msg:match("^%s*$") then msg = "settings" end
    SlashCmdList.VOICECHANTSTUDIO(msg)
end
