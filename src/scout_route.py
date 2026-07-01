# scout_patcher — IronMON Scout Balls patcher for Pokemon HeartGold / SoulSilver.
# Copyright (C) 2026 Fazlic Software.
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. Distributed WITHOUT ANY WARRANTY. See LICENSE.txt
# (GPLv3) for details. Uses ndspy (GPLv3+, https://github.com/RoadrunnerWMC/ndspy).
"""Patch pre-Falkner areas with scout balls: one ball per unique walking species, each running a
random-level wild battle (random level within that species' real slot range on the route).
THE PATCHER. Usage: python scout_route.py <src.nds> <out.nds>

Multi-area: every area in AREAS whose `place` is set gets patched in one pass (all edits land in
the same event/script NARCs, saved once). Banks are randomizer-invariant, so the same indices work
on clean, 4787-base, and randomized ROMs. Placement (start tile + march direction) is dictated by
the user via the live coord reader (tools/coord_reader.lua); fill an area's `place` to enable it.
"""
import sys, os, struct, re
sys.path.insert(0, os.path.dirname(__file__))
import scout_patch as sp
import msgtool as mt                               # HGSS message-archive decode/re-encode
from species_ow_sprite import SPECIES_OW_SPRITE   # dex -> follower overworld sprite id
from ndspy import rom as ndsrom
from ndspy import narc as ndsnarc
from ndspy import codeCompression

HDR_FILE_OFF = 0xF6BE0   # map header table in decompressed arm9 (mapId -> 24B record)

# --- REAL retail opcodes (verified in-binary; NOT the decomp's +1-shifted indices) ---
OP_END, OP_WILD, OP_RANDOM, OP_ADDVAR = 0x0002, 0x024D, 0x017C, 0x0027
TMP = 0x4000  # temp scratch var (Save-backed, overwritten each use)

ENC_NARC = "a/0/3/7"

# A clean 32-byte ObjectEvent template. make_ball_object fills every field that matters
# (id, spriteId=87, movement=0, type=0, eventFlag=0, scriptId, x/z/y); all others stay 0.
# Proven byte-identical to the live-verified Route 29 balls (whose template's only nonzero
# non-overridden field, eventFlag, is overridden to 0 anyway).
BALL_TEMPLATE = bytes(32)

# Per-area config. enc/events/scripts = NARC member banks (from the arm9 map-header table,
# see tools/enum_areas.py). `place` is one of:
#   ((x0,z0),(dx,dz))  -> auto row: ball i at (x0+dx*i, z0+dz*i)   [tuple; good for open routes]
#   [(x,z), (x,z), ...] -> explicit per-ball tiles                [list;  good for caves/towers]
#   None                -> skip this area (no coords yet)
# All tiles are matrix-global grid coords straight from tools/coord_reader.lua (press M to mark).
# Optional `mon_sprite=True` shows each ball as its species' overworld (follower) sprite instead
# of a Poke Ball (SPIKE — watch the per-map overworld-sprite budget when many distinct species).
AREAS = {
    "Route 29":            dict(enc=1,  events=30,  scripts=225, place=((666, 396), (1, 0))),  # mon_sprite=True available; client wants plain Poke Balls
    "Route 30":            dict(enc=3,  events=31,  scripts=227, place=((546, 374), (0, 1))),
    "Route 31":            dict(enc=4,  events=32,  scripts=230, place=((524, 266), (1, 0))),
    "Route 32 (north)":    dict(enc=8,  events=33,  scripts=232, place=((464, 288), (1, 0))),
    "Route 46 (south)":    dict(enc=68, events=45,  scripts=259, place=((629, 373), (0, 1))),
    "Dark Cave (Violet)":  dict(mapId=176, enc=69, events=169, scripts=139, place=((4, 21), (0, 1)), private_script=True),  # 139 is a 90-map shared stub -> private member + arm9 repoint
    "Sprout Tower (155)":  dict(mapId=155, enc=6, events=150, scripts=17, place=((9, 9), (0, 1)), private_script=True),  # shared stub 17 -> private member + repoint
    "Sprout Tower (156)":  dict(mapId=156, enc=7, events=151, scripts=18, place=None, private_script=True),  # other floor; shared stub 18
}

# Optional message-archive text edits (reuse an existing sign instead of adding one).
# mapId -> { message_index: "new text"  ('\n' = line break inside the box) }.
# Route 29 (mapId 33) msg[15] is the "West to Cherrygrove City" direction sign.
SIGN_EDITS = {
    33: {15: "GL Clabe\n-Shinnu"},
}

def apply_sign_edits(rom):
    """Rewrite specific messages in NARC a/0/2/7 (map text). msgBank comes from the map header."""
    if not SIGN_EDITS:
        return
    a9 = codeCompression.decompress(bytes(rom.arm9))
    msg_narc = ndsnarc.NARC(rom.getFileByName(mt.MSG_NARC))
    for mapId, edits in SIGN_EDITS.items():
        msgBank = struct.unpack_from("<H", a9, HDR_FILE_OFF + mapId * 24 + 0x0A)[0]
        key, entries = mt.parse_member(msg_narc.files[msgBank])
        codes = [c for (_o, _l, c) in entries]
        for idx, text in edits.items():
            codes[idx] = mt.text_to_codes(text)
            print(f"Sign: mapId {mapId} a/0/2/7[{msgBank}] msg[{idx}] -> {text!r}")
        msg_narc.files[msgBank] = mt.build_member(key, codes)
    rom.setFileByName(mt.MSG_NARC, msg_narc.save())

def apply_arm9_repoints(rom, repoints):
    """Point each (mapId -> new scriptsBank) in the arm9 map-header table. arm9 is recompressed;
    ndspy's save(compress=True) round-trips byte-perfectly (verified)."""
    if not repoints:
        return
    mcf = rom.loadArm9()
    sec = mcf.sections[0]                          # ram 0x02000000; holds the header table @ 0xF6BE0
    assert sec.ramAddress == 0x02000000
    for mapId, new_bank in repoints:
        struct.pack_into("<H", sec.data, HDR_FILE_OFF + mapId * 24 + 0x06, new_bank)
        print(f"arm9: mapId {mapId} scriptsBank -> {new_bank}")
    rom.arm9 = mcf.save(compress=True)

def placement_tiles(place, n):
    """Resolve `place` to exactly n ball tiles (see AREAS doc for the two accepted forms)."""
    if isinstance(place, list):                       # explicit per-ball tiles
        if len(place) < n:
            raise SystemExit(f"!! only {len(place)} placement tiles for {n} balls")
        return [tuple(t) for t in place[:n]]
    (x0, z0), (dx, dz) = place                        # start tile + march direction -> auto row
    return [(x0 + dx * i, z0 + dz * i) for i in range(n)]

def grass_species_ranges(data):
    """species -> (minLevel, maxLevel) across morning/day/night slots (levels@0x08 shared)."""
    levels = list(data[0x08:0x08 + 12])
    def u16s(off): return list(struct.unpack_from("<12H", data, off))
    ranges = {}
    for arr in (u16s(0x14), u16s(0x2C), u16s(0x44)):   # morning, day, night
        for i, spec in enumerate(arr):
            if spec == 0:
                continue
            lv = levels[i]
            lo, hi = ranges.get(spec, (lv, lv))
            ranges[spec] = (min(lo, lv), max(hi, lv))
    return ranges

def random_level_script(species, lo, hi):
    """random tmp,(hi-lo+1); addvar tmp,lo; wildbattle species,tmp,0; end  (or fixed if lo==hi)"""
    lo = max(1, lo)
    if hi > lo:
        span = hi - lo + 1
        body = (struct.pack("<HHH", OP_RANDOM, TMP, span)
                + struct.pack("<HHH", OP_ADDVAR, TMP, lo)
                + struct.pack("<HHHB", OP_WILD, species, TMP, 0))   # level via var
    else:
        body = struct.pack("<HHHB", OP_WILD, species, lo, 0)        # fixed level immediate
    return body + struct.pack("<H", OP_END)

def patch_area(name, cfg, enc_narc, evn, scn, repoints):
    """Read one area's species, append scripts + inject ball objects. Mutates evn/scn in place.
    If cfg['private_script'] (scriptsBank is a shared stub), write scripts to a NEW narc member and
    queue an arm9 map-header repoint instead of overwriting the shared member."""
    encf = enc_narc.files[cfg["enc"]]
    ev, sc = evn.files[cfg["events"]], scn.files[cfg["scripts"]]

    ranges = grass_species_ranges(encf)
    species = sorted(ranges)
    row = placement_tiles(cfg["place"], len(species))
    use_mon = cfg.get("mon_sprite", False)
    private = cfg.get("private_script", False)
    print(f"{name}: {len(species)} unique species{'  [mon sprites]' if use_mon else ''}"
          f"{'  [private script member]' if private else ''}")

    n_bg, bg, objs, rest = sp.split_event_file(ev)
    max_id = max((struct.unpack_from("<H", o, 0)[0] for o in objs), default=0)
    K = len(sp.read_pointer_count(sc))

    new_scripts, new_objs = [], list(objs)
    for j, s in enumerate(species):
        lo, hi = ranges[s]
        x, z = row[j]
        sprite_id = SPECIES_OW_SPRITE.get(s, sp.BALL_SPRITE) if use_mon else sp.BALL_SPRITE
        new_scripts.append(random_level_script(s, lo, hi))
        script_id = K + 1 + j                     # 1-based local scriptId (index K+j in the member)
        new_objs.append(sp.make_ball_object(BALL_TEMPLATE, max_id + 1 + j, script_id, x, z,
                                            sprite_id=sprite_id))
        print(f"  species {s:4}  level {lo}-{hi}  -> ({x},{z})  scriptId={script_id}  sprite={sprite_id}")

    new_ev = sp.build_event_file(n_bg, bg, new_objs, rest)
    if len(new_ev) >= 0x800:
        raise SystemExit(f"!! {name}: event file {len(new_ev)} >= 2048 B limit "
                         f"({len(species)} balls too many for one member)")
    evn.files[cfg["events"]] = new_ev

    new_sc, _ = sp.append_scripts(sc, new_scripts)   # = stub (index 0) + our scripts (indices 1..)
    if private:
        new_idx = len(scn.files)
        scn.files.append(new_sc)                      # leave the shared stub untouched
        repoints.append((cfg["mapId"], new_idx))
        print(f"  event {len(ev)}->{len(new_ev)} B, scripts -> NEW member [{new_idx}] "
              f"(shared bank {cfg['scripts']} untouched; repoint mapId {cfg['mapId']})")
    else:
        scn.files[cfg["scripts"]] = new_sc
        print(f"  event {len(ev)}->{len(new_ev)} B, script {len(sc)}->{len(new_sc)} B")

def patch_rom(src, out):
    rom = ndsrom.NintendoDSRom.fromFile(src)
    enc_narc = ndsnarc.NARC(rom.getFileByName(ENC_NARC))
    evn = ndsnarc.NARC(rom.getFileByName(sp.EVENTS_NARC))
    scn = ndsnarc.NARC(rom.getFileByName(sp.SCRIPTS_NARC))

    todo = [(n, c) for n, c in AREAS.items() if c["place"]]
    if not todo:
        raise SystemExit("No areas have placement set (fill AREAS[...]['place']).")
    print(f"Patching {len(todo)} area(s): {', '.join(n for n, _ in todo)}\n")
    repoints = []
    for name, cfg in todo:
        patch_area(name, cfg, enc_narc, evn, scn, repoints)
        print()

    apply_sign_edits(rom)                          # reads arm9 (msgBank); writes msg narc
    rom.setFileByName(sp.EVENTS_NARC, evn.save())
    rom.setFileByName(sp.SCRIPTS_NARC, scn.save())
    apply_arm9_repoints(rom, repoints)             # writes arm9 (after sign edits' arm9 read)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rom.saveToFile(out)
    print(f"Wrote {out}")

# --- Tracker hook install/uninstall (edits ironmon_tracker/QuickLoader.lua) ---
HOOK_BEGIN = "-- [SCOUT-BALLS HOOK]"
HOOK_END   = "-- [/SCOUT-BALLS HOOK]"
ANCHOR     = 'MiscUtils.runExecuteCommand(command, "RomGenerationErrorLog.txt")'

def find_quickloader(hint=None):
    cands = []
    def add(base):
        if base:
            base = base.strip().rstrip('"')        # tolerate batch %~dp0 trailing-backslash mangling
            cands.extend([os.path.join(base, "ironmon_tracker", "QuickLoader.lua"),
                          os.path.join(base, "QuickLoader.lua")])
    # 1. the exe's OWN folder — most robust: the installer is placed in the Tracker folder, so this
    #    works regardless of working directory, batch quoting, or "Run as administrator".
    if getattr(sys, "frozen", False):
        add(os.path.dirname(os.path.abspath(sys.executable)))
    add(hint)                                       # 2. explicit hint (or its own dir)
    if hint and os.path.isfile(hint.strip().rstrip('"')):
        cands.insert(0, hint.strip().rstrip('"'))
    add(os.getcwd())                                # 3. current working directory
    for c in cands:
        if c and os.path.isfile(c):
            return c
    for root, _dirs, files in os.walk(os.getcwd()):  # 4. last resort: search downward from CWD
        if "QuickLoader.lua" in files and os.path.basename(root) == "ironmon_tracker":
            return os.path.join(root, "QuickLoader.lua")
    return None

def _hook_block():
    """Lua block that runs THIS program on the freshly randomized ROM, in place. Command is
    cmd/c-wrapped (validated) so paths with spaces survive os.execute."""
    if getattr(sys, "frozen", False):
        parts = [sys.executable]                    # the delivered .exe invokes itself
    else:
        parts = [sys.executable, os.path.abspath(__file__)]   # dev: python + this script
    fmt = 'cmd /c "' + '"%s" ' * len(parts) + '"%s""'         # -> cmd /c ""p".. "rom""
    partargs = ", ".join("[[%s]]" % p for p in parts)         # Lua [[...]] = literal backslashes
    call = "string.format('%s', %s, nextRomPath)" % (fmt, partargs)
    return ("    %s auto-generated by scout_patcher; patches the new ROM in place before it loads.\n"
            "    MiscUtils.runExecuteCommand(%s, \"ScoutPatchErrorLog.txt\")\n"
            "    %s" % (HOOK_BEGIN, call, HOOK_END))

def install_hook(hint=None, remove=False):
    ql = find_quickloader(hint)
    if not ql:
        raise SystemExit("Could not find ironmon_tracker/QuickLoader.lua. Run this from the "
                         "Tracker folder, or pass its path: scout_patcher install <tracker_dir>")
    text = open(ql, encoding="utf-8").read()
    # strip any existing hook block (makes install idempotent / re-runnable, and enables uninstall)
    pat = re.compile(r"\n?[ \t]*" + re.escape(HOOK_BEGIN) + r".*?" + re.escape(HOOK_END), re.S)
    text = pat.sub("", text)
    if not remove:
        idx = text.find(ANCHOR)
        if idx < 0:
            raise SystemExit(f"Anchor not found in {ql}; Tracker version may differ. Aborting.")
        eol = text.find("\n", idx)
        text = text[:eol + 1] + _hook_block() + "\n" + text[eol + 1:]
    open(ql + ".scoutbak", "w", encoding="utf-8").write(open(ql, encoding="utf-8").read())
    open(ql, "w", encoding="utf-8").write(text)
    print(("Uninstalled hook from:\n  " if remove else "Installed scout-ball hook into:\n  ") + ql)
    if not remove:
        print("Patcher: " + (sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)))
        print("Done. New runs in the Tracker will now auto-patch scout balls.")
        print("(Reload the tracker in BizHawk so the change takes effect.)")

def main():
    a = sys.argv[1:]
    if a and a[0].lower() in ("install", "uninstall"):
        return install_hook(a[1] if len(a) > 1 else None, remove=(a[0].lower() == "uninstall"))
    src = a[0] if a else "Pokemon Heart Gold.nds"
    out = a[1] if len(a) > 1 else src              # 1 arg => patch IN PLACE (the tracker hook)
    patch_rom(src, out)

if __name__ == "__main__":
    main()
