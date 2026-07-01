-- HGSS live player-position reader (DeSmuME Lua).
-- Stand on the tile where you want a scout ball, read X / Z off the overlay, dictate them.
-- The X/Z shown are matrix-global GRID TILE coords -- the SAME units as ObjectEvent.x/z in the
-- event file, so whatever this reads goes straight into the patcher's placement list.
--
-- Load:  DeSmuME 0.9.13  ->  Tools > Lua Scripting > New Lua Script Window > Browse this file > Run.
--
-- Pointer chain (all offsets confirmed against the retail arm9, see tools/find_fieldsys_ptr.py):
--   [0x021D4158] = FieldSystem*        (0 / garbage outside the overworld: menus, battle, warps)
--        +0x40   = PlayerAvatar*
--        +0x30   = LocalMapObject*
--        +0x64   = currentX (u32 grid tile)
--        +0x68   = currentY (s32 elevation)
--        +0x6C   = currentZ (u32 grid tile)
--
-- CALIBRATION (do this once): walk next to the shiny item Poke Ball on Route 29 (it sits at grid
-- x=654, z=386). Standing one tile west of it should read X=653 Z=386; one tile south, X=654 Z=387.
-- If the numbers line up with (654,386), the reader is trustworthy for every route.

local SFIELDSYS = 0x021D4158
local OFF_AVATAR, OFF_MAPOBJ = 0x40, 0x30
local OFF_LOCATION = 0x20          -- FieldSystem -> Location* ; Location.mapId is first field
local OFF_X, OFF_Y, OFF_Z     = 0x64, 0x68, 0x6C

local function valid(p)            -- DS main RAM is 0x02000000..0x023FFFFF
  return p ~= nil and p >= 0x02000000 and p < 0x02400000
end

-- read a 32-bit pointer/word; DeSmuME memory.* uses full ARM9 addresses (same as our exec traces)
local function rd(addr) return memory.readdword(addr) end

-- sign-extend a 32-bit value read as unsigned (for currentY, which can be negative)
local function s32(v) if v >= 0x80000000 then return v - 0x100000000 else return v end end

local function readPlayer()
  local fs = rd(SFIELDSYS)
  if not valid(fs) then return nil, "no FieldSystem (not in overworld)" end
  local av = rd(fs + OFF_AVATAR)
  if not valid(av) then return nil, "no PlayerAvatar" end
  local mo = rd(av + OFF_MAPOBJ)
  if not valid(mo) then return nil, "no MapObject" end
  local loc = rd(fs + OFF_LOCATION)
  local mapId = valid(loc) and rd(loc) or -1
  return { x = rd(mo + OFF_X), y = s32(rd(mo + OFF_Y)), z = rd(mo + OFF_Z),
           mapId = mapId, fs = fs, mo = mo }
end

print("=== HGSS coord reader armed. Walk around; read X/Z off the top-left overlay. ===")
print("Calibrate vs the Route 29 item ball at grid (x=654, z=386).")
print("Press keyboard 'M' while standing on a tile to log a numbered MARK for that ball.")

-- Rising-edge keyboard 'M' detector (guarded: if input.get isn't available it just no-ops).
local function markPressed()
  local ok, keys = pcall(function() return input.get() end)
  if ok and type(keys) == "table" then return keys.M or keys.m end
  return false
end

local lastKey = nil
local lockedOnce = false
local markHeld = false
local markCount = 0
while true do
  local p, err = readPlayer()
  if p then
    if not lockedOnce then     -- one-time sanity dump so we can debug if calibration is off
      print(string.format("locked: FieldSystem=0x%08X  MapObject=0x%08X", p.fs, p.mo))
      lockedOnce = true
    end
    -- on-screen overlay (redrawn every frame)
    gui.text(2, 2,  string.format("map=%d  X=%d  Z=%d", p.mapId, p.x, p.z))
    gui.text(2, 11, string.format("Y=%d  marks=%d", p.y, markCount))
    -- console line only when you actually move to a new tile (keeps the log readable)
    local key = p.mapId .. ":" .. p.x .. "," .. p.z .. "," .. p.y
    if key ~= lastKey then
      print(string.format("map %-4d  X=%-4d Z=%-4d  Y=%-3d   (ball here -> place at x=%d, z=%d)",
                          p.mapId, p.x, p.z, p.y, p.x, p.z))
      lastKey = key
    end
    -- 'M' rising edge => log a numbered mark for this exact tile
    local m = markPressed()
    if m and not markHeld then
      markCount = markCount + 1
      print(string.format(">>> MARK #%d:  map=%d  x=%d, z=%d, y=%d", markCount, p.mapId, p.x, p.z, p.y))
    end
    markHeld = m
  else
    gui.text(2, 2, err)
    if err ~= lastKey then print("[" .. err .. "]"); lastKey = err end
  end
  emu.frameadvance()
end
