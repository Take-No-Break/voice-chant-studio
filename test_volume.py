"""Independent volume and settings regression tests; no live mic/game access."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
import test_addon_v02 as lifecycle
from core import Project, load_audio

BASE=Path(__file__).parent

class VoiceVolumeTests(unittest.TestCase):
    def runtime(self):
        return lifecycle.AddonLifecycleTests().runtime('''{{class="MAGE",ids={133},event="success",file="full.wav",volumes={[10]="ten.wav",[50]="half.wav",[90]="ninety.wav"}}}''')

    def test_independent_gain_mute_rounding_and_no_shared_cvar_writes(self):
        lua=self.runtime()
        lua.execute('''
SetCVar=function() error("Shared game volume must not be changed") end
assert(VoiceChantStudioAPI.GetVolume()==100)
assert(VoiceChantStudioAPI.SetVolume(51))
assert(VoiceChantStudioDB.volume==50)
event("UNIT_SPELLCAST_SUCCEEDED","a",133)
assert(plays[1].file=="half.wav" and plays[1].channel=="Dialog")
assert(VoiceChantStudioAPI.SetVolume(0))
now=1; event("UNIT_SPELLCAST_SUCCEEDED","b",133); assert(#plays==1 and #stops==1)
assert(not VoiceChantStudioAPI.SetVolume(-1))
assert(not VoiceChantStudioAPI.SetVolume(101))
assert(not VoiceChantStudioAPI.SetVolume(0/0))
assert(not VoiceChantStudioAPI.SetVolume("junk"))
SlashCmdList.VOICECHANTSTUDIO("volume 90")
now=2; event("UNIT_SPELLCAST_SUCCEEDED","c",133); assert(plays[2].file=="ninety.wav")
SlashCmdList.VOICECHANTSTUDIO("mute")
now=3; event("UNIT_SPELLCAST_SUCCEEDED","d",133); assert(#plays==2)
SlashCmdList.VOICECHANTSTUDIO("unmute")
VoiceChantStudioAPI.SetVolume(100); VoiceChantStudioAPI.Test()
assert(plays[3].file=="full.wav")
''')

    def test_volume_saved_values_survive_addon_load_and_missing_variants_are_explicit(self):
        lua=self.runtime()
        lua.execute('''VoiceChantStudioDB.volume=50; event("ADDON_LOADED",nil,nil,"VoiceChantStudio")
assert(VoiceChantStudioAPI.GetVolume()==50)
VoiceChantStudioDB.volume="invalid"; assert(VoiceChantStudioAPI.GetVolume()==100)
''')
        lua=lifecycle.AddonLifecycleTests().runtime('{{class="MAGE",ids={133},event="success",file="legacy.wav"}}')
        lua.execute('''
messages={}; print=function(msg) table.insert(messages,msg) end
VoiceChantStudioAPI.SetVolume(50); VoiceChantStudioAPI.Test()
assert(#plays==0 and messages[1]:find("Export this voice pack again"))
''')

    def test_settings_panel_registration_slider_commands_and_test_button(self):
        lua=self.runtime()
        lua.execute('''
widgets={}; function GetLocale() return "enUS" end
function GetCVar() return "1" end
function CreateFrame(kind,name,parent,template)
 local w={scripts={},name=name,kind=kind}; table.insert(widgets,w)
 local noop=function() end
 setmetatable(w,{__index=function(_,key)
  if key=="SetScript" then return function(self,n,fn) self.scripts[n]=fn end end
  if key=="CreateFontString" then return function() return CreateFrame("Font") end end
  if key=="GetName" then return function(self) return self.name end end
  if key=="SetText" then return function(self,t) self.text=t end end
  if key=="SetChecked" then return function(self,v) self.checked=v end end
  if key=="GetChecked" then return function(self) return self.checked end end
  if key=="SetValue" then return function(self,v) self.value=v; if self.scripts.OnValueChanged then self.scripts.OnValueChanged(self,v) end end end
  return noop
 end})
 if name then _G[name]=w end
 if template=="OptionsSliderTemplate" then for _,tail in ipairs({"Low","High","Text"}) do _G[name..tail]=CreateFrame("Font") end end
 return w
end
Settings={RegisterCanvasLayoutCategory=function(panel,name) registeredName=name; return {GetID=function() return 321 end} end,
 RegisterAddOnCategory=function(c) registeredID=c:GetID() end,
 OpenToCategory=function(id) openedID=id end}
''')
        lua.execute((BASE/'addon/Options.lua').read_text(encoding='utf8'))
        lua.execute('''
VoiceChantStudioDB.volume=50
event("ADDON_LOADED",nil,nil,"VoiceChantStudio")
assert(registeredName=="Voice Chant Studio" and registeredID==321)
assert(VoiceChantStudioVolumeSlider.value==50)
SlashCmdList.VOICECHANTSETTINGS(""); assert(openedID==321)
VoiceChantStudioVolumeSlider.scripts.OnValueChanged(VoiceChantStudioVolumeSlider,90)
assert(VoiceChantStudioDB.volume==90)
for _,w in ipairs(widgets) do if w.text=="Test recorded voice" then w.scripts.OnClick(w) end end
assert(plays[1].file=="ninety.wav")
VoiceChantStudioOptions.Initialize(); assert(VoiceChantStudioDB.volume==90)
local smooth,step=false,false
for _,w in ipairs(widgets) do if w.text=='Smooth down (0.20s)' then w.scripts.OnClick(w);smooth=true end end
assert(smooth and VoiceChantStudioDB.duckFade=='smooth')
for _,w in ipairs(widgets) do if w.text=='Step down' then w.scripts.OnClick(w);step=true end end
assert(step and VoiceChantStudioDB.duckFade=='step')
''')

    def test_export_has_real_pcm_gain_variants_preserves_sources_and_ready_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            p=Project(root/'project',[{'key':'fire','class':'MAGE','name':'Fireball','ids':[133]}])
            data=np.sin(np.arange(4410)*.05).astype('float32')*.6
            source=p.add_audio(data,44100); before=p.asset(source).read_bytes()
            p.data['clips']['fire:start']={'source':source,'start':0,'end':.1,'gain':1,'ready':True}
            target,count=p.export(root/'export',BASE/'addon',game=False)
            self.assertEqual(count,1)
            from lupa import LuaRuntime
            lua=LuaRuntime(); lua.execute((target/'Config.lua').read_text(encoding='utf8'))
            row=lua.globals().VoiceChantConfig.bindings[1]
            full,_=load_audio(target/'Audio'/row.file.split('\\')[-1])
            for level in range(10,100,10):
                scaled,rate=load_audio(target/'Audio'/row.volumes[level].split('\\')[-1])
                self.assertEqual(rate,44100)
                np.testing.assert_allclose(scaled,full*(level/100),atol=.00004)
            self.assertEqual(p.asset(source).read_bytes(),before)
            self.assertEqual(len(list((target/'Audio').glob('*.wav'))),10)
            self.assertIn('Options.lua',(target/'VoiceChantStudio.toc').read_text())

if __name__=='__main__':unittest.main()
