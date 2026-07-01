-- HGSS wild-battle execution trace (DeSmuME Lua).
-- Load: Tools > Lua Scripting > New Lua Script Window > Browse to this file > Run.
-- Watch the script's Output box while you (1) walk into grass, then (2) press each ball.
--
-- Addresses recovered from arm9 (US/IPKE, clean-based prototype):
--   0x02049950 ScrCmd_WildBattle      (opcode 0x24C)  -- our ball B / D
--   0x02044BE8 ScrCmd_Fateful         (opcode 0x2AD)  -- our ball C
--   0x02043D78 ScrCmd_RocketTrap      (opcode 0xF8)
--   0x02049618 ScrCmd_TrainerBattle   (opcode 0xD4)   -- KNOWN-WORKING battle-from-script
--   0x02055218 encounter transition   (Task_StartEncounter state 0 = battle IS starting)
--   0x02050724 post-battle cleanup    (Task_StartEncounter state 3 = battle finished)

-- Step-by-step pipeline of SetupAndStartWildBattle. Wherever the log STOPS = the culprit.
local hooks = {
  {0x02049950, "1. ScrCmd_WildBattle          (command entered)"},
  {0x02044BE8, "1. ScrCmd_Fateful             (command entered)"},
  {0x02052574, "2. SetupAndStartWildBattle    (setup reached)"},
  {0x02028F94, "2a. BattleSetup_New           (alloc battle setup)"},
  {0x02028F54, "2b. BattleSetup_InitFromField (init from field state)"},
  {0x02002028, "3. GenerateSingleWildPokemon  (generating the mon)"},
  {0x0201C2D8, "4. CallTask_StartEncounter    (launching battle task)"},
  {0x02055218, "5. >> encounter TRANSITION    (battle actually launching)"},
  {0x02050724, "6. << post-battle cleanup     (battle finished)"},
}

local function mkcb(name)
  return function()
    local fc = 0
    if emu and emu.framecount then fc = emu.framecount() end
    print(string.format("[frame %d] %s", fc, name))
  end
end

local armed, failed = 0, 0
for _, h in ipairs(hooks) do
  local ok, err = pcall(function() memory.registerexec(h[1], mkcb(h[2])) end)
  if ok then armed = armed + 1
  else failed = failed + 1; print("!! could not hook 0x"..string.format("%08X", h[1])..": "..tostring(err)) end
end

print("=== wild-battle trace armed: "..armed.." hooks ("..failed.." failed) ===")
print("Now: 1) walk into grass (expect TRANSITION + cleanup), 2) press ball B, then ball C.")

-- keep the script (and its hooks) alive
while true do
  if emu and emu.frameadvance then emu.frameadvance() else break end
end
