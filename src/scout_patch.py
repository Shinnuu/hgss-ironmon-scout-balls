"""
scout_patch.py - IronMON scout-ball injector (Route 29 prototype).

Injects interactable Pokeball objects into a route's event file, each wired to a new
script that starts a wild battle with a specific species. Reusable pieces (event-file
edit, script append, wildbattle bytecode) will seed the full 4-route patcher.

Prototype target: Route 29 (mapId 33) -> events a/0/3/2[30], scripts a/0/1/2[225].
"""
import sys, struct, os
from ndspy import rom as ndsrom
from ndspy import narc as ndsnarc

EVENTS_NARC = "a/0/3/2"
SCRIPTS_NARC = "a/0/1/2"
R29_EVENT_MEMBER = 30
R29_SCRIPT_MEMBER = 225

BALL_SPRITE = 87          # SPRITE_MONSTARBALL
DIR_SOUTH = 1             # global_fieldmap.h: N=0,S=1,W=2,E=3. South = faces down toward player.
OP_WILDBATTLE = 0x024C
OP_END = 0x0002

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]

# ---------------- event file ----------------
def split_event_file(data):
    """Return (n_bg, bg, objs(list of 32B), n_warp_bytes_block, coord_block) as raw slices."""
    p = 0
    n_bg = u32(data, p); p += 4
    bg = data[p:p + n_bg * 20]; p += n_bg * 20
    n_obj = u32(data, p); p += 4
    obj_block = data[p:p + n_obj * 32]; p += n_obj * 32
    objs = [obj_block[i*32:(i+1)*32] for i in range(n_obj)]
    rest = data[p:]  # warp count + warps + coord count + coords, kept verbatim
    return n_bg, bg, objs, rest

def build_event_file(n_bg, bg, objs, rest):
    out = bytearray()
    out += struct.pack("<I", n_bg) + bg
    out += struct.pack("<I", len(objs)) + b"".join(objs)
    out += rest
    return bytes(out)

def make_ball_object(template, obj_id, script_id, x, z, y=0, event_flag=0, sprite_id=BALL_SPRITE,
                     facing=DIR_SOUTH):
    """Copy a known-good 32B ObjectEvent template, override the ball-specific fields.
    sprite_id defaults to the Poke Ball (87); pass a follower OW sprite id to show the species.
    facing defaults to south so mon sprites face the player (balls ignore it)."""
    o = bytearray(template)
    struct.pack_into("<H", o, 0, obj_id & 0xFFFF)     # id
    struct.pack_into("<H", o, 2, sprite_id)            # spriteId (87 ball, or species OW sprite)
    struct.pack_into("<H", o, 4, 0)                    # movement = static
    struct.pack_into("<H", o, 8, event_flag)           # eventFlag (0 = always visible)
    struct.pack_into("<H", o, 10, script_id)           # scriptId
    struct.pack_into("<h", o, 12, facing)              # facingDirection (1 = south / toward player)
    struct.pack_into("<H", o, 24, x)                   # x
    struct.pack_into("<H", o, 26, z)                   # z
    struct.pack_into("<i", o, 28, y)                   # y (s32)
    return bytes(o)

# ---------------- script file ----------------
def build_wildbattle_script(species, level, shiny=0):
    return struct.pack("<HHHBH", OP_WILDBATTLE, species, level, shiny, OP_END)

def read_pointer_count(data):
    """K = number of leading u32 relative-offset entries (pointer table size)."""
    ptrs = []
    i = 0
    min_t = None
    while i + 4 <= len(data):
        w = u32(data, i)
        t = i + 4 + w
        if min_t is not None and i >= min_t:
            break
        if not (0 <= t <= len(data)):
            break
        ptrs.append(w)
        min_t = t if min_t is None else min(min_t, t)
        i += 4
    return ptrs  # len(ptrs) = K, values = original words

def append_scripts(data, new_scripts):
    """Append scripts, returning (new_data, first_new_index). Existing scripts untouched:
    each old word += 4*M (code block shifts down); new entries point past the old block."""
    old_words = read_pointer_count(data)
    K = len(old_words)
    M = len(new_scripts)
    blob = data[4 * K:]                 # gap + all existing code, treated opaquely
    new_table = bytearray()
    for w in old_words:
        new_table += struct.pack("<I", w + 4 * M)
    base = 4 * (K + M) + len(blob)      # absolute offset where new code begins
    new_code = bytearray()
    for j, sc in enumerate(new_scripts):
        idx = K + j
        target = base + len(new_code)
        word = target - (4 * idx + 4)
        new_table += struct.pack("<I", word)
        new_code += sc
    return bytes(new_table) + blob + bytes(new_code), K

# ---------------- prototype patch ----------------
def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "Pokemon Heart Gold.nds"
    out = sys.argv[2] if len(sys.argv) > 2 else "ironmon-scout/out/Route29_scout_proto.nds"

    rom = ndsrom.NintendoDSRom.fromFile(src)
    ev_narc = ndsnarc.NARC(rom.getFileByName(EVENTS_NARC))
    sc_narc = ndsnarc.NARC(rom.getFileByName(SCRIPTS_NARC))

    ev = ev_narc.files[R29_EVENT_MEMBER]
    sc = sc_narc.files[R29_SCRIPT_MEMBER]

    n_bg, bg, objs, rest = split_event_file(ev)
    template = objs[8]  # existing item-ball object (sprite 87) = known-good template
    max_id = max(u16(o, 0) for o in objs)

    # Test balls near the east (New Bark) entrance / existing walkable objects.
    # (species, level, x, z) -- distinct species so each ball is identifiable in-game.
    test_balls = [
        (16,  5, 626, 392),   # Pidgey   - just inside east entrance
        (19,  5, 620, 400),   # Rattata  - near the NPC cluster
        (161, 5, 655, 388),   # Sentret  - beside the existing item ball (654,386)
    ]

    K = len(read_pointer_count(sc))     # existing script count (expect 9)
    new_scripts = [build_wildbattle_script(sp, lv) for (sp, lv, x, z) in test_balls]

    new_objs = list(objs)
    print(f"Route 29: {len(objs)} existing objects, {K} existing scripts.")
    for j, (sp, lv, x, z) in enumerate(test_balls):
        table_index = K + j
        script_id = table_index + 1     # HYPOTHESIS: scriptId is 1-based (index+1)
        obj_id = max_id + 1 + j
        new_objs.append(make_ball_object(template, obj_id, script_id, x, z))
        print(f"  ball[{j}] species={sp} lvl={lv} pos=({x},{z}) "
              f"-> scriptId={script_id} (table idx {table_index}), objId={obj_id}")

    new_ev = build_event_file(n_bg, bg, new_objs, rest)
    new_sc, _ = append_scripts(sc, new_scripts)

    assert len(new_ev) < 0x800, f"event file {len(new_ev)} >= 2048 byte limit!"
    print(f"  event file: {len(ev)} -> {len(new_ev)} bytes (limit 2048)")
    print(f"  script file: {len(sc)} -> {len(new_sc)} bytes")

    ev_narc.files[R29_EVENT_MEMBER] = new_ev
    sc_narc.files[R29_SCRIPT_MEMBER] = new_sc
    rom.setFileByName(EVENTS_NARC, ev_narc.save())
    rom.setFileByName(SCRIPTS_NARC, sc_narc.save())

    os.makedirs(os.path.dirname(out), exist_ok=True)
    rom.saveToFile(out)
    print(f"\nWrote {out}")

if __name__ == "__main__":
    main()
