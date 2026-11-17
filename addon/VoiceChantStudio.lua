-- Voice Chant Studio: additive audio only. Never mutes or casts spells.
local cfg = VoiceChantConfig or {bindings={}, gap=.2, stopOnCancel=true}
local byID, byName, active, lastPlayed = {}, {}, nil, -100
local volumeFiles = {}
local durations={}
local segmentedFiles={}
local voices,selectionState,trace = {},{},{}
local function mode() return VoiceChantStudioDB and VoiceChantStudioDB.playbackMode or (cfg.ducking and 'duck' or 'replace') end
local function fadeMode() return VoiceChantStudioDB and VoiceChantStudioDB.duckFade or 'step' end
local function log(text)
    if not (VoiceChantStudioDB and VoiceChantStudioDB.debug) then return end
    trace[#trace+1]=string.format('%.2f %s',GetTime(),text)
    if #trace>60 then table.remove(trace,1) end
end
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
local function bindRow(target,row)
    if not row.condition then bind(target,row.event,row.file);return end
    target.rules=target.rules or {}
    local rule
    for _,r in ipairs(target.rules) do if r.condition.tag==row.condition.tag then rule=r;break end end
    if not rule then rule={condition=row.condition};target.rules[#target.rules+1]=rule end
    bind(rule,row.event,row.file)
end
if UnitClass then _, playerClass = UnitClass("player") end
for _, row in ipairs(cfg.bindings or {}) do
    -- Older exports did not include class. Keep those working as well.
    if not row.class or not playerClass or row.class == playerClass then
    durations[row.file]=tonumber(row.duration) or 600
    if row.segments then segmentedFiles[row.file]={segments=row.segments,smoothSegments=row.smoothSegments,step=row.segmentStep or .25,overlap=row.segmentOverlap or .02,smoothOverlap=row.smoothOverlap or .20,duration=durations[row.file]} end
    for _,path in pairs(row.volumes or {}) do durations[path]=durations[row.file] end
    if row.volumes then volumeFiles[row.file] = row.volumes end
    for _, id in ipairs(row.ids) do
        byID[id] = byID[id] or {}; bindRow(byID[id],row)
        if C_Spell and C_Spell.GetSpellName then
            local name = C_Spell.GetSpellName(id)
            if readable(name) and name then byName[name] = byName[name] or {}; bindRow(byName[name],row) end
        end
    end
    end
end
if VoiceChantConditions then VoiceChantConditions.Initialize(cfg.bindings) end
local function lookup(id,context)
    if not readable(id) or type(id) ~= "number" then return end
    local binding=byID[id]
    if not binding then
        local name = C_Spell and C_Spell.GetSpellName and C_Spell.GetSpellName(id)
        if readable(name) and name then binding=byName[name] end
    end
    if not binding or not context or not binding.rules or not VoiceChantConditions then return binding end
    local chosen={start=binding.start,success=binding.success,cancel=binding.cancel}
    for _,phase in ipairs({'start','success','cancel'}) do
        for _,rule in ipairs(binding.rules) do
            if rule[phase] and VoiceChantConditions.Matches(rule.condition,context) then chosen[phase]=rule[phase];chosen.matchedTag=rule.condition.tag;break end
        end
    end
    return chosen
end
local function stop(cast)
    for i=#voices,1,-1 do
        if not cast or voices[i].cast==cast then
            local voice=voices[i];voice.ended=true
            if voice.handles then for handle in pairs(voice.handles) do StopSound(handle,20) end
            elseif voice.handle then StopSound(voice.handle,100) end
            table.remove(voices,i)
        end
    end
    active=voices[#voices]
end
local function duckVoice(file,id,guid,phase,cast)
    local source=segmentedFiles[file]
    if not source then say('Ducking needs segmented audio. Export again from editor v0.8.');log('SKIP missing duck segments');return end
    if fadeMode()=='smooth' then
        if not source.smoothSegments then say('Smooth ducking needs new audio. Export again from editor v0.8.1.');log('SKIP missing smooth segments');return end
        source={segments=source.smoothSegments,step=source.step,overlap=source.smoothOverlap,duration=source.duration}
    end
    if cast then stop(cast) end
    while #voices>=3 do
        local oldest=table.remove(voices,1);oldest.ended=true
        if oldest.handles then for handle in pairs(oldest.handles) do StopSound(handle,20) end
        elseif oldest.handle then StopSound(oldest.handle,20) end
    end
    local voice={id=id,guid=guid,phase=phase,cast=cast,handles={},started=GetTime()};voices[#voices+1]=voice;active=voice
    local tick
    tick=function(nextIndex)
        if voice.ended then return end
        local index=math.max(nextIndex,math.floor((GetTime()-voice.started)/source.step+.0001)+1)
        local chunk=source.segments[index]
        if not chunk then
            voice.ended=true
            for i=#voices,1,-1 do if voices[i]==voice then table.remove(voices,i) end end
            active=voices[#voices];return
        end
        local rank
        for i,v in ipairs(voices) do if v==voice then rank=#voices-i+1 end end
        if not rank then return end
        local factors={1,.5,.2};local level=math.floor(getVolume()*(factors[rank] or 0)/10+.5)*10
        if level>0 then
            local path=level==100 and chunk.file or chunk.volumes and chunk.volumes[level]
            if path then
                local ok,handle=PlaySoundFile(path,'Dialog')
                if ok and handle then
                    voice.handles[handle]=true
                    C_Timer.After(source.step+(source.overlap or .02)+.04,function() voice.handles[handle]=nil end)
                else log('SEGMENT FAILED '..tostring(index)) end
            end
        end
        local due=voice.started+index*source.step
        C_Timer.After(math.max(.001,due-GetTime()),function() tick(index+1) end)
    end
    tick(1);lastPlayed=GetTime();log('DUCK PLAY '..tostring(id));return true
end
local function play(file, id, guid, phase, cast)
    if VoiceChantStudioDB and VoiceChantStudioDB.muted then log('SKIP muted');return end
    if not file then log('SKIP no voice for '..tostring(phase));return end
    if GetTime()-lastPlayed < (cfg.gap or .2) and phase ~= 'cancel' then log('SKIP minimum interval');return end
    local volume = getVolume()
    if volume == 0 then log('SKIP volume 0');return end
    if type(file)=='table' then
        if #file==0 then return end
        local choices=file;local previous=selectionState[choices] or 0;local index=1
        local selection=VoiceChantStudioDB and VoiceChantStudioDB.selectionMode or 'random'
        if #choices>1 then
            if selection=='sequence' then index=previous%#choices+1
            elseif selection=='norepeat' and previous>0 then index=math.random(#choices-1);if index>=previous then index=index+1 end
            else index=math.random(#choices) end
        end
        selectionState[choices]=index;file=choices[index]
    end
    if mode()=='duck' then return duckVoice(file,id,guid,phase,cast) end
    if volume < 100 then
        local choices = volumeFiles[file]
        if not choices or not choices[volume] then
            say("Export this voice pack again to enable independent volume control.")
            return
        end
        file = choices[volume]
    end
    if GetTime()-lastPlayed < (cfg.gap or .2) and phase ~= "cancel" then return end
    if mode()=='overlap' and cast then stop(cast) else stop() end
    if #voices>=8 then StopSound(voices[1].handle,100);table.remove(voices,1) end
    local ok, handle = PlaySoundFile(file, "Dialog")
    if ok then
        active = {handle=handle, id=id, guid=guid, phase=phase, cast=cast}
        voices[#voices+1]=active
        local value=active
        C_Timer.After((durations[file] or 600)+.1,function()
            for i=#voices,1,-1 do if voices[i]==value then table.remove(voices,i) end end
            active=voices[#voices]
        end)
        log('PLAY '..tostring(id)..' '..tostring(phase)..' '..file)
        lastPlayed = GetTime()
        return true
    else
        log('PLAY FAILED '..file)
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
frame:RegisterUnitEvent('UNIT_SPELLCAST_SENT','player')
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
    if cfg.stopOnCancel then stop(cast) end
    play(binding.cancel, cast.id, cast.guid, "cancel", cast)
end
frame:SetScript("OnEvent", function(_, event, unit, guid, id, extra)
    if event == "ADDON_LOADED" then
        if unit == "VoiceChantStudio" then
            VoiceChantStudioDB = VoiceChantStudioDB or {}
            VoiceChantStudioDB.volume = getVolume()
            if VoiceChantStudioOptions then VoiceChantStudioOptions.Initialize() end
        end
        return
    end
    if event=='UNIT_SPELLCAST_SENT' then
        if readable(unit) and unit=='player' and VoiceChantConditions then VoiceChantConditions.Sent(extra,id,guid) end
        return
    end
    if not readable(unit) or unit ~= "player" or not readable(id) or not readable(guid) then return end
    log(event..' '..tostring(id))
    if mode()=='replace' and active and (event=='UNIT_SPELLCAST_START' or event=='UNIT_SPELLCAST_CHANNEL_START' or event=='UNIT_SPELLCAST_SUCCEEDED') and ((guid and active.guid~=guid) or (not guid and active.id~=id)) then stop() end
    local binding = lookup(id)
    if not binding then
        log('NO VOICE '..tostring(id))
        if event=='UNIT_SPELLCAST_SUCCEEDED' and VoiceChantConditions then VoiceChantConditions.Complete(id,guid) end
        return
    end
    local cast = castFor(id, guid, event)
    if VoiceChantConditions then
        cast.context=cast.context or VoiceChantConditions.Snapshot(id,guid)
        binding=lookup(id,cast.context)
        if binding.matchedTag then log('LINK '..binding.matchedTag) end
    end
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
        if VoiceChantConditions then VoiceChantConditions.Complete(id,guid) end
        channelEnd(cast)
        if binding.success then
            -- A completion clip deliberately replaces this addon's preparation clip only.
            local same=false
            for _,voice in ipairs(voices) do if voice.cast==cast then same=true end end
            if same then stop(cast); lastPlayed=-100 end
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
local function setPlayback(value)
    if value~='replace' and value~='overlap' and value~='duck' then return false end
    VoiceChantStudioDB=VoiceChantStudioDB or {};VoiceChantStudioDB.playbackMode=value;stop();return true
end
local function setSelection(value)
    if value~='random' and value~='norepeat' and value~='sequence' then return false end
    VoiceChantStudioDB=VoiceChantStudioDB or {};VoiceChantStudioDB.selectionMode=value;selectionState={};return true
end
local function setFade(value)
    if value~='step' and value~='smooth' then return false end
    VoiceChantStudioDB=VoiceChantStudioDB or {};VoiceChantStudioDB.duckFade=value;stop();return true
end
local function diagnostics()
    say('Mode: '..mode()..' / '..(VoiceChantStudioDB.selectionMode or 'random')..' / Volume '..getVolume()..'%')
    say('Ducking: '..fadeMode()..'; wait <=0.25s + timer delay, then '..(fadeMode()=='smooth' and '0.20s ramp' or '~0.02s edge'))
    say('Debug '..(VoiceChantStudioDB.debug and 'ON' or 'OFF')..'; /vcs debug toggles capture. /vcs test previews a voice.')
    for i=math.max(1,#trace-11),#trace do say(trace[i]) end
end
VoiceChantStudioAPI = {GetVolume=getVolume, SetVolume=setVolume, Test=testVoice, Stop=function() stop() end, GetPlayback=mode, SetPlayback=setPlayback, GetFade=fadeMode, SetFade=setFade, SetSelection=setSelection, Diagnostics=diagnostics}
SlashCmdList.VOICECHANTSTUDIO = function(msg)
    msg = (msg or ""):lower():match("^%s*(.-)%s*$")
    VoiceChantStudioDB = VoiceChantStudioDB or {}
    if msg == "mute" then VoiceChantStudioDB.muted=true; stop(); say("Extra voice muted.")
    elseif msg=='debug' then VoiceChantStudioDB.debug=not VoiceChantStudioDB.debug;diagnostics()
    elseif msg=='diagnostics' then diagnostics()
    elseif msg:match('^mode%s+') then setPlayback(msg:match('^mode%s+(.+)$'));diagnostics()
    elseif msg:match('^fade%s+') then setFade(msg:match('^fade%s+(.+)$'));diagnostics()
    elseif msg:match('^variation%s+') then setSelection(msg:match('^variation%s+(.+)$'));diagnostics()
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
