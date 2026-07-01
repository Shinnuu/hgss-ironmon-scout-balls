# HGSS ROM formats — working notes

Living record of the formats this project touches. Mark each **CONFIRMED** (validated
against real data / reference source) or **PENDING** (assumed, not yet verified). Don't
build the patcher on a PENDING format without validating it first.

Game: Pokémon HeartGold US (`IPKE`). Species IDs are National-Dex order (1–493).

---

## Wild grass encounters — NARC `a/0/3/7`  (CONFIRMED 2026-06-30)
142 subfiles, one per encounter area, each 196 (0xC4) bytes. Grass has separate species for
morning/day/night sharing one set of per-slot levels. 12 grass slots.

Grass layout (little-endian) — validated on clean ROM against Route 29:

| Offset | Size | Field |
|--------|------|-------|
| 0x00 | 1 | grass encounter rate |
| 0x01–0x07 | 7 | other-method rates + padding (all 0 when no surf/fishing; unused for grass) |
| 0x08 | 12 | grass slot levels (u8 × 12) |
| 0x14 | 24 | grass species — MORNING (u16 × 12) |
| 0x2C | 24 | grass species — DAY (u16 × 12) |
| 0x44 | 24 | grass species — NIGHT (u16 × 12) |
| 0x5C | … | (radio/surf/fishing/swarm — not needed for grass-only scope) |

Grass slot rate weights: `[20,20,10,10,10,10,5,5,4,4,1,1]` (sum 100).

**Unique scout set for a route** = `set(morning ∪ day ∪ night) \ {0}`.

Validated: clean ROM encounter file **index 1 = Route 29**, levels `[2,3,2,3,3,3,2,2,4,4,4,4]`,
union `{16 Pidgey, 19 Rattata, 161 Sentret, 163 Hoothoot}` = exactly vanilla Route 29.

> ⚠️ **Do NOT identify routes by species signature on the randomized ROM** — species are
> shuffled there. The encounter *file index* is randomizer-invariant (randomizer changes
> values, not file order), so map routes → encounter index via **map headers** (below), then
> read species from that index. The clean-ROM signature is only for validating the parser.

---

## Map headers — struct `MapHeader`, 24 bytes each  (CONFIRMED via decomp 2026-06-30)
Fixed 24-byte records, one per map id — the master index routing each map to its data.
On-ROM storage location (arm9 table vs a narc) still TBD (see checklist).

| Off | Type | Field | Use for us |
|-----|------|-------|------------|
| 0x00 | u8  | `wildEncounterBank` | index into encounter NARC `a/0/3/7` → species |
| 0x01 | u8  | areaDataBank | |
| 0x02 | u16 bitfields | moveModelBank:4, worldMapX:6, worldMapY:6 | |
| 0x04 | u16 | matrixId | |
| 0x06 | u16 | `scriptsBank` | index into scripts NARC (scr_seq) → add scripts |
| 0x08 | u16 | scriptHeaderBank | |
| 0x0A | u16 | msgBank | |
| 0x0C | u16 | dayMusicId | |
| 0x0E | u16 | nightMusicId | |
| 0x10 | u16 | `eventsBank` | index into events NARC (zone_event) → add objects |
| 0x12 | u16 bitfields | mapsec:8, areaIcon:4, momCallIntroParam:4 | |
| 0x14 | u32 bitfields | region/weather/mapType/camera/... | |

Route a map by reading these three banks: wildEncounterBank (species), eventsBank (place
balls), scriptsBank (battle scripts). All three are randomizer-invariant.

## Event file — NARC `fielddata/eventdata/zone_event` (CONFIRMED via decomp 2026-06-30)
One member per map (indexed by `MapHeader.eventsBank`). Read directly by pointer cast, so
compiler struct sizes == on-disk record sizes. **Whole member must stay < 0x800 (2048) bytes**
(engine buffer `event_data[0x800]`).

```
u32 num_bg_events
BG_EVENT    bg[num_bg_events]        # 20 bytes each
u32 num_object_events
ObjectEvent obj[num_object_events]   # 32 bytes each   <-- add scout balls here
u32 num_warp_events
WARP_EVENT  warp[num_warp_events]    # 12 bytes each
u32 num_coord_events
COORD_EVENT coord[num_coord_events]  # 16 bytes each
```

**ObjectEvent (32 bytes):** `id`u16, `spriteId`u16, `movement`u16, `type`u16, `eventFlag`u16,
`scriptId`u16, `facingDirection`s16, `param[3]`u16, `xRange`s16, `yRange`s16, `x`u16, `z`u16,
`y`s32. For a scout ball: `spriteId` = Pokéball OW sprite, `scriptId` = our battle script #,
`x/z/y` = a walkable tile near the route entrance.

Adding balls = bump `num_object_events`, insert 32-byte records; warp/coord sections shift
down. Rebuild the member and write it back via ndspy.

## Scripts — NARC `a/0/1/2` (scr_seq)  (CONFIRMED 2026-06-30)
Confirmed via the arm9 header table: `scriptsBank` values span 0..964 → this narc (965
members). `scriptHeaderBank` also indexes this narc (a separate member per map).

Container format (one member = one map's scripts):
- Starts with a **pointer table** of u32 relative offsets. Script `i` code lives at
  `4*i + 4 + word[i]` (offset relative to the position right after that 4-byte entry).
  Engine: `ScriptRunByIndex: script_ptr += 4*idx; script_ptr += ScriptReadWord()`.
- Route 29 (`a/0/1/2[225]`, 2580 B) = 9 scripts; table ends ~0x24, code begins 0x26.
- ⚠️ **scriptId ↔ index nuance (verify in prototype):** Route 29 object scriptIds are
  {3,4,7,8,9} against a 9-entry table (indices 0..8) → indexing is likely **1-based**
  (objectScriptId N → table index N-1; 0 = "no script"), possibly routed via scriptHeaderBank.
  Confirm empirically before finalizing new script indices.
- Special object scriptId ranges are engine-handled, NOT local scripts: Route 29 uses
  2800, 7000, 10000 (7000-range = item-ball "give item"). Scout balls must use a NORMAL
  local scriptId, never a special.
- Pointer-table format (decomp `asm/macros/script.inc`): N × `ScrDef` (u32 = target−here−4),
  terminated by `ScrDefEnd` = **u16 0xFD13**. The engine never reads the terminator at runtime
  (`ScriptRunByIndex` just jumps to `4*idx`), so it's a build-time marker; our append relocates it
  after the enlarged table and it's fine. Object scriptId N → `LoadScriptsAndMessagesByMapId`
  returns index **N−1** in the map's scriptsBank member (1-based CONFIRMED via `fieldmap.c`).

### ⚠️ Shared "empty stub" script members — need a PRIVATE member  (CONFIRMED live 2026-07-01)
Many maps (caves/towers) point `scriptsBank` at a **shared 8-byte empty stub** (just `End`).
Dark Cave (mapId 176) → member **139**, which is shared by **90 maps**. Appending scout scripts
to it is navigationally valid BUT **black-screens the map on entry** (89 other maps also read it;
don't disturb it). Fix that works live:
1. Build the new member = stub + our scripts (`append_scripts`), **append it to the narc** (new
   index, e.g. 965) — leave the shared stub byte-for-byte untouched.
2. **Repoint** that map's `scriptsBank` (arm9 header off 0x06) to the new index.
- arm9 edit via ndspy: `mcf = rom.loadArm9(); struct.pack_into('<H', mcf.sections[0].data,
  0xF6BE0 + mapId*24 + 0x06, newBank); rom.arm9 = mcf.save(compress=True)`. Recompression
  round-trips byte-perfect (verified: only the 2 edited bytes change; boots fine).
- Detect shared stubs by counting maps whose header `scriptsBank` == that bank (`>1` ⇒ shared).
  Routes 29/30/31/32/46 have **unique** members (plain append is safe). Sprout Tower (17/18) will
  also be shared ⇒ same private-member+repoint. Implemented as `private_script=True` in scout_route.

## Script commands — REAL RETAIL OPCODES  (RESOLVED 2026-07-01)
⚠️ **The decomp command-table order does NOT match this ROM.** Above a mid-table shift point,
retail opcode = decomp index **+1**. Confirmed live in the emulator. Derive real opcodes from
the ROM, not the decomp count. (`gScriptCmdTable` = decompressed arm9 @file 0xFAD00, 853
entries; `tools/find_battle_opcode.py` identifies handlers by what they call.)

| command | RETAIL opcode | operands | notes |
|---------|---------------|----------|-------|
| `end`        | **0x0002** | — | below shift point; matches decomp |
| `wildbattle` | **0x024D** | species u16, level u16, shiny u8 | decomp said 0x24C = actually `CheckBattleWon`! |
| `fateful`    | **0x02AE** | species u16, level u16 | no shiny byte |
| `rockettrap` | **0x00F9** | species u16, level u16 | can't-flee wild |

Minimal scout-ball script (9 bytes): `wildbattle(species, level, 0)` + `end`
= `4D 02 <sp16> <lv16> 00  02 00`. Species/level < 0x4000 are immediate literals (ScriptGetVar).
`shiny=0` = normal shiny odds (NOT forced off); IVs/nature/gender/ability all rolled randomly.
`setvar`/`lockall`/`releaseall` (decomp 0x29/0x60/0x61) are UNVERIFIED for this ROM — may also
be +1; re-derive from the binary before use. The prototype avoids them (immediate operands).

## Overworld object / sprite  (CONFIRMED 2026-06-30)
- **Pokéball ground sprite = 87** (`SPRITE_MONSTARBALL`). Route 29 object[8] uses it at
  (654,386). Scout balls mimic it: `spriteId=87, movement=0`, our scriptId, chosen x/z/y.
- ObjectEvent position order is (x, z, y). Route 29 walkable objects: x≈596-661, z≈386-410.
- **facingDirection** (ObjectEvent off 12, s16): N=0, S=1, W=2, E=3 (`global_fieldmap.h`).
  Use **S=1** so an object faces down toward the player (0 shows its back).

## Species overworld (follower) sprite — optional mon-shaped scout balls  (CONFIRMED live 2026-07-01)
A scout ball can display as its species' overworld sprite instead of a Poké Ball — HGSS ships a
follower OW sprite for every species. Just set the ObjectEvent `spriteId`:
```
spriteId(species) = 428 + sModelIndexLUT[species]
```
- 428 = `SPRITE_FOLLOWER_MON_BULBASAUR`; range 428–993. `sModelIndexLUT` (follow_mon.c) is indexed
  by dex# and holds `FOLLOWER_MON_*` offsets (follow_mon_idx.h); female/form variants shift later
  species (e.g. Venusaur=430, Charmander=432 — 431 is Venusaur_F). Base/male/form-0 sprite is what
  we want (wild gender/form rolled at battle).
- Baked map: `tools/species_ow_sprite.py` (regen with `tools/gen_species_ow.py`).
- **Verified live:** static ObjectEvents load these fine — no follower codepath / ASM needed.
  Interaction unchanged (scriptId drives the battle). Face them **south (facing=1)**.
- ⚠️ Open risk: per-map overworld-sprite VRAM budget with many *distinct* large species on one
  screen. 3 medium species (Golem/Slaking/Gorebyss) rendered clean; a pathological seed untested.
- Toggle: per-area `mon_sprite=True` in `scout_route.py` AREAS. **Pending client sign-off before ship.**

## Map header table  (CONFIRMED 2026-06-30)
- Location: **decompressed arm9**, offset **0xF6BE0**, 540 records × 24 bytes, index = mapId.
  arm9 is compressed on the ROM — decompress with `ndspy.codeCompression.decompress` first.
- READ-only for us (route → banks). All three banks are randomizer-invariant.

## Live player grid position — pointer chain  (CONFIRMED static 2026-07-01; PENDING live calibration)
For the placement coord-reader: read the player's current grid tile from RAM at runtime. The
tile units are **matrix-global** and **identical to ObjectEvent.x/z** (`map_object.c`:
`currentX = (positionVector.x >> 4) / FX32_ONE`), so whatever the reader shows is exactly what
the patcher writes into the event file.

```
[0x021D4158]  FieldSystem*   (sFieldSysPtr; 0 / stale when NOT in the overworld)
      +0x40   PlayerAvatar*
      +0x30   LocalMapObject*
      +0x64   currentX  (u32 grid tile)   == ObjectEvent.x
      +0x68   currentY  (s32 elevation)   == ObjectEvent.y  (0 on all flat grass routes)
      +0x6C   currentZ  (u32 grid tile)   == ObjectEvent.z
```
- `sFieldSysPtr` @ **0x021D4158** recovered by disassembling the no-arg field_system.c accessors
  (`sub_0203E2F4/30C/324`) — all load that literal (`tools/find_fieldsys_ptr.py`). Struct offsets
  cross-checked against the retail bytes (accessor writes `isPaused` at `[unk0]+8`, reads `unk4`
  at `+4` — both match the decomp `FieldSystem`/`PlayerAvatar`/`LocalMapObject` layouts).
- arm9 static → **same address on clean / 4787 base / randomized** ROMs (vanilla arm9, randomizer
  touches only NARC `a/0/3/7`).
- Reader: `tools/coord_reader.lua` (DeSmuME). **Calibration gate:** stand beside the Route 29 item
  ball (grid 654,386) — one tile west must read X=653 Z=386. Confirm before trusting for placement.

## Verified Route 29 data path (mapId 33)
| Data | NARC member | Status |
|------|-------------|--------|
| Grass species | `a/0/3/7[1]` | Pidgey/Sentret/Rattata/Hoothoot ✅ |
| Event file (add balls) | `a/0/3/2[30]` | 468 B, 11 objects, clean parse ✅ |
| Script file (add scripts) | `a/0/1/2[225]` | 2580 B, 9 scripts ✅ |

Routes 30/31/46: identify enc index by clean-ROM grass signature, find mapId via the header
table (record whose `wildEncounterBank` == that index), read its events/scripts banks. TODO.

## Battle trigger from a scout ball — ✅ RESOLVED (2026-07-01)
**Working end-to-end on Route 29.** Pressing a scout ball starts a real wild battle with the
chosen species; battle launches and completes cleanly. Verified via Lua exec-trace: for each
ball, `BattleSetup_New → InitFromField → GenerateSingleWildPokemon → encounter TRANSITION →
post-battle cleanup` all fire. IVs/nature/gender/ability rolled; shiny at normal odds.

Root cause of the multi-session debug: **wrong opcode** — 0x24C is `CheckBattleWon` in this ROM;
the real `wildbattle` is **0x24D** (see opcode table above). Everything else (ball injection,
event rebuild, script append, scriptId 1-based, sprite 87, placement beside the wandering NPC
at 622,392) was correct the whole time.

Runtime-debug setup (reusable): DeSmuME 0.9.13 x64 + `lua51.dll` (in the exe folder) +
`tools/trace_wildbattle.lua`. Key arm9 addresses (clean/IPKE): GenerateSingleWildPokemon
0x02002028, BattleSetup_New 0x02028F94, InitFromField 0x02028F54, encounter transition
0x02055218, post-battle 0x02050724, SetupAndStartWildBattle 0x02052580, cmd table 0x020FAD00.

## Map text / signs — message archive NARC `a/0/2/7`  (CONFIRMED live 2026-07-01)
Sign & NPC text. Map's text member = `MapHeader.msgBank` (header off 0x0A). Route 29 (mapId 33)
= `a/0/2/7[373]`; msg[15]="Rt. 29\nWest to Cherrygrove City", msg[16]=East sign. **Reusing an
existing sign (rewrite its message) is far cheaper than adding one** — no new event/script/opcodes.
Per-member format (from decomp `tools/msgenc/MessagesConverter.h`, ported in `tools/msgtool.py`):
- `u16 count, u16 key`, then `count × {u32 offset(bytes), u32 length(u16 units)}`, then u16 strings.
- Alloc table XOR-encrypted: `ak=(765*i*key)&0xFFFF; ak|=ak<<16; offset^=ak; length^=ak` (i 1-based).
- Each string XOR-encrypted: `k=(i*596947)&0xFFFF; per code: code^=k; k=(k+18749)&0xFFFF`. Ends `0xFFFF`.
- Chars via `refs/.../charmap.txt` (`HEXCODE=char`); line break = **0xE000** ("\n"); `0xFFFE`=cmd.
- ✅ Re-encode round-trips **byte-identical**; edited msg[15]→"GL Clabe\n-Shinnu", others intact.
  Toggle via `scout_route.py` `SIGN_EDITS = {mapId: {msgIndex: "text"}}`.

## Still to confirm (checklist)
- [x] **Validate the grass encounter parser** on the clean ROM (Route 29 signature). ✅ 2026-06-30
- [x] **Map header struct** (24 B; wildEncounterBank@0x00, scriptsBank@0x06, eventsBank@0x10). ✅ 2026-06-30
- [x] **Event file on-disk format** (counts + BG/Object/Warp/Coord arrays; ObjectEvent=32 B). ✅ 2026-06-30
- [x] **ROM narc paths**: events = `a/0/3/2`, scripts = `a/0/1/2`; header table in arm9 @0xF6BE0. ✅ 2026-06-30
- [x] **Script container format** (scr_seq): pointer table `4*i+4+word[i]`. ✅ 2026-06-30
      (scriptId↔index 1-based nuance to confirm in prototype.)
- [x] **Wild-battle command** = opcode `0x24D` (NOT 0x24C — decomp is +1); `end` = `0x0002`. ✅ 2026-07-01
- [x] **Battle fires from a scout ball** — verified live in DeSmuME, all 3 test balls battle. ✅ 2026-07-01
- [x] **Pokéball sprite** = 87 (`SPRITE_MONSTARBALL`); confirmed live on Route 29. ✅ 2026-06-30
- [ ] **scriptId ↔ table index** exact rule (1-based? via scriptHeaderBank?) — verify in prototype.
- [ ] **Per-map object cap** at runtime (MapObjectManager capacity). Event file must stay < 0x800 B.
- [ ] Placement coords for scout balls (have Route 29 reference coords; pick per route).
- [ ] Map routes 30/31/46 → mapId → event/script banks (via header table).

## Reference sources
- `pret/pokeheartgold` (decomp) — authoritative for all of the above.
- Project Pokémon HGSS format threads.
- DSPRE source — practical read/write implementations of these NARCs.
