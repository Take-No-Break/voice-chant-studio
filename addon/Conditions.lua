-- Optional conditional voices. No OnUpdate, combat-log polling or automated casts.
VoiceChantConditions = {}
local api=VoiceChantConditions
local watched={player={},target={}}
local cache={player={},target={}}
local pending={};local enabled=false
local targets={}
local previous,previousAt,lastGUID
local function readable(v) return not (issecretvalue and issecretvalue(v)) end
local function scan(unit)
 local found={}
 if not next(watched[unit]) then return found end
 local filter=unit=='player' and 'HELPFUL' or 'HARMFUL|PLAYER'
 for i=1,80 do
  local id
  if C_UnitAuras and C_UnitAuras.GetAuraDataByIndex then
   local aura=C_UnitAuras.GetAuraDataByIndex(unit,i,filter)
   if not aura then break end
   id=aura.spellId
  elseif UnitAura then
   local name,_,_,_,_,_,_,_,_,spellID=UnitAura(unit,i,filter)
   if not name then break end
   id=spellID
  else break end
  if readable(id) and type(id)=='number' and watched[unit][id] then found[id]=true end
 end
 return found
end
function api.Initialize(bindings)
 for _,row in ipairs(bindings or {}) do
  local c=row.condition
  if c then
   enabled=true
   for _,id in ipairs(row.ids or {}) do targets[id]=true end
   local unit=c.kind=='player_aura' and 'player' or c.kind=='target_aura' and 'target'
   if unit then for _,id in ipairs(c.ids or {}) do watched[unit][id]=true end end
  end
 end
 if not enabled then return end
 cache.player=scan('player');cache.target=scan('target')
 local frame=CreateFrame('Frame')
 frame:RegisterUnitEvent('UNIT_AURA','player','target')
 frame:RegisterEvent('PLAYER_TARGET_CHANGED');frame:RegisterEvent('PLAYER_ENTERING_WORLD')
 frame:SetScript('OnEvent',function(_,event,unit)
  if event=='UNIT_AURA' then
   if readable(unit) and watched[unit] then cache[unit]=scan(unit) end
  else cache.player=scan('player');cache.target=scan('target') end
 end)
end
local function snapshot()
 -- Tables are replaced, never mutated by aura updates. A cast retains its pre-cast state.
 return {player=cache.player,target=cache.target,previous=previous,previousAt=previousAt,time=GetTime()}
end
function api.Sent(id,guid,target)
 if not enabled or not readable(id) or type(id)~='number' or not targets[id] or not readable(guid) then return end
 cache.player=scan('player');cache.target=scan('target')
 local value=snapshot()
 if not readable(target) then value.target={}
 elseif target and UnitName then
  local name=UnitName('target')
  if not readable(name) or target~=name then value.target={} end
 end
 local key=guid or ('spell:'..id)
 pending[key]=value
 C_Timer.After(30,function() if pending[key]==value then pending[key]=nil end end)
end
function api.Snapshot(id,guid)
 if not enabled then return nil end
 return pending[guid or ('spell:'..id)] or snapshot()
end
function api.Complete(id,guid)
 if not enabled or not readable(id) or type(id)~='number' then return end
 if guid and guid==lastGUID then return end
 previous,previousAt,lastGUID=id,GetTime(),guid
end
function api.Matches(condition,value)
 if not condition or not value then return false end
 local kind=condition.kind
 if kind=='previous_spell' then
  if not value.previousAt or value.time-value.previousAt>(condition.seconds or 8) then return false end
  for _,id in ipairs(condition.ids or {}) do if id==value.previous then return true end end
 elseif kind=='player_aura' or kind=='target_aura' then
  local auras=value[kind=='player_aura' and 'player' or 'target'] or {}
  for _,id in ipairs(condition.ids or {}) do if auras[id] then return true end end
 end
 return false
end
