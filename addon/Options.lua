-- In-game settings for this addon's voice files only. No shared volume CVars.
VoiceChantStudioOptions = {}
local panel, category, slider, percent, mute, status, overlap, variation, playback
local syncing = false
local jp = GetLocale and GetLocale() == "jaJP"
local function L(ja,en) return jp and ja or en end
local api = VoiceChantStudioAPI
local function label(parent,text,x,y,font)
    local f=parent:CreateFontString(nil,"ARTWORK",font or "GameFontHighlight")
    f:SetPoint("TOPLEFT",x,y); f:SetText(text)
    return f
end
function VoiceChantStudioOptions.Refresh()
    if not panel then return end
    syncing=true
    local volume=api.GetVolume()
    slider:SetValue(volume); percent:SetText(volume.."%")
    mute:SetChecked(VoiceChantStudioDB and VoiceChantStudioDB.muted or false)
    if overlap then overlap:SetChecked(VoiceChantStudioDB and VoiceChantStudioDB.playbackMode=='overlap' or false) end
    if variation then variation:SetText(L('現在：','Current: ')..(VoiceChantStudioDB.selectionMode or 'random')) end
    if playback then playback:SetText(L('現在：','Current: ')..api.GetPlayback()..L('  最新100% / 前50% / 前々20% / それ以前は無音','  Newest 100% / previous 50% / third 20% / older silent')) end
    local enabled=not GetCVar or (GetCVar("Sound_EnableAllSound")~="0" and GetCVar("Sound_EnableDialog")~="0")
    status:SetText(enabled and L("Dialog: オン","Dialog: enabled") or L("Options > Audio で Sound と Dialog をオンにしてください。","Enable Sound and Dialog in Options > Audio to hear your voice."))
    syncing=false
end
function VoiceChantStudioOptions.Initialize()
    if panel then return end
    panel=CreateFrame("Frame","VoiceChantStudioSettings",UIParent)
    panel.name="Voice Chant Studio"
    panel:Hide()
    label(panel,"Voice Chant Studio",20,-20,"GameFontNormalLarge")
    label(panel,L("自分の声による詠唱・効果音","Your recorded spell chants and voice effects"),20,-50)
    label(panel,L("このアドオンの声の音量","Voice Chant Studio volume"),20,-90,"GameFontNormal")
    slider=CreateFrame("Slider","VoiceChantStudioVolumeSlider",panel,"OptionsSliderTemplate")
    slider:SetPoint("TOPLEFT",24,-125); slider:SetSize(300,20)
    slider:SetMinMaxValues(0,100); slider:SetValueStep(10); slider:SetObeyStepOnDrag(true)
    _G[slider:GetName().."Low"]:SetText("0%")
    _G[slider:GetName().."High"]:SetText("100%")
    _G[slider:GetName().."Text"]:SetText("")
    percent=label(panel,"100%",345,-125,"GameFontNormalLarge")
    slider:SetScript("OnValueChanged",function(_,value)
        if not syncing then api.SetVolume(value) end
    end)
    label(panel,L("10%刻み。ゲームの効果音やNPCの音量は変わりません。","10% steps. Does not change game effects or NPC voice volume."),20,-175)
    mute=CreateFrame("CheckButton",nil,panel,"UICheckButtonTemplate")
    mute:SetPoint("TOPLEFT",18,-205)
    label(panel,L("このアドオンの声をミュート","Mute Voice Chant Studio"),54,-214)
    mute:SetScript("OnClick",function(self)
        VoiceChantStudioDB=VoiceChantStudioDB or {}
        VoiceChantStudioDB.muted=self:GetChecked() and true or false
        api.Stop(); VoiceChantStudioOptions.Refresh()
    end)
    local test=CreateFrame("Button",nil,panel,"UIPanelButtonTemplate")
    test:SetPoint("TOPLEFT",20,-255); test:SetSize(200,28)
    test:SetText(L("録音した声を試聴","Test recorded voice")); test:SetScript("OnClick",api.Test)
    local reset=CreateFrame("Button",nil,panel,"UIPanelButtonTemplate")
    reset:SetPoint("LEFT",test,"RIGHT",12,0); reset:SetSize(160,28)
    reset:SetText(L("音量を100%に戻す","Reset to 100%")); reset:SetScript("OnClick",function() api.SetVolume(100) end)
    status=label(panel,"",20,-310)
    local note=label(panel,L("0%は無音です。録音元ファイルは変更しません。\n書き出し時の音量が100%の基準になります。\n新しい音声を書き出した後はWoWを完全に再起動してください。","0% is silent. Original recordings are preserved.\n100% uses the volume saved when the clip was exported.\nFully restart WoW after exporting new audio files."),20,-345)
    note:SetJustifyH("LEFT")
    local modeLabels={L('前の声を止める','Stop previous'),L('通常の重ね再生','Overlap'),L('最新優先（試験）','Newest priority (beta)')}
    local modeValues={'replace','overlap','duck'}
    for i,text in ipairs(modeLabels) do
        local button=CreateFrame('Button',nil,panel,'UIPanelButtonTemplate');button:SetPoint('TOPLEFT',20+(i-1)*175,-410);button:SetSize(165,26);button:SetText(text)
        button:SetScript('OnClick',function() api.SetPlayback(modeValues[i]);VoiceChantStudioOptions.Refresh() end)
    end
    playback=label(panel,'',20,-445)
    label(panel,L('成功音声の選び方：','Success variation selection:'),20,-470)
    local labels={L('均等ランダム','Random'),L('連続重複を避ける','Avoid repeats'),L('順番に再生','Sequence')}
    local values={'random','norepeat','sequence'}
    for i,text in ipairs(labels) do
        local button=CreateFrame('Button',nil,panel,'UIPanelButtonTemplate');button:SetPoint('TOPLEFT',20+(i-1)*175,-495);button:SetSize(165,26);button:SetText(text)
        button:SetScript('OnClick',function() api.SetSelection(values[i]);VoiceChantStudioOptions.Refresh() end)
    end
    variation=label(panel,'',20,-535)
    local diag=CreateFrame('Button',nil,panel,'UIPanelButtonTemplate');diag:SetPoint('TOPLEFT',20,-565);diag:SetSize(230,26);diag:SetText(L('再生状態・ログをチャットへ表示','Print playback diagnostics'));diag:SetScript('OnClick',api.Diagnostics)
    label(panel,'/vcs debug | /vcs diagnostics',20,-605,'GameFontNormal')
    panel:SetScript("OnShow",VoiceChantStudioOptions.Refresh)
    if Settings and Settings.RegisterCanvasLayoutCategory and Settings.RegisterAddOnCategory then
        category=Settings.RegisterCanvasLayoutCategory(panel,"Voice Chant Studio")
        Settings.RegisterAddOnCategory(category)
    elseif InterfaceOptions_AddCategory then
        InterfaceOptions_AddCategory(panel)
    end
    VoiceChantStudioOptions.Refresh()
end
function VoiceChantStudioOptions.Open()
    if InCombatLockdown and InCombatLockdown() then
        print("Voice Chant Studio: "..L("戦闘が終わってから設定を開いてください。","Open settings after leaving combat.")); return
    end
    VoiceChantStudioOptions.Initialize()
    if category and Settings and Settings.OpenToCategory then
        Settings.OpenToCategory(category:GetID())
    elseif InterfaceOptionsFrame_OpenToCategory then
        InterfaceOptionsFrame_OpenToCategory(panel)
    end
end
