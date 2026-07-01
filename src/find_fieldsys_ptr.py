"""Locate the arm9 static `sFieldSysPtr` (FieldSystem**) so a Lua coord-reader can chase
the live player grid position:

    sFieldSysPtr -> FieldSystem +0x40 -> PlayerAvatar +0x30 -> LocalMapObject
    LocalMapObject +0x64 = currentX (u32 grid tile), +0x6C = currentZ (u32 grid tile)

Grid tile units == ObjectEvent x/z units (map_object.c: currentX = (posVec.x>>4)/FX32_ONE).

Method: disassemble the no-arg accessors that touch sFieldSysPtr and read the PC-relative
literal they load. sub_0203E324 = `if (sFieldSysPtr->unk4==NULL) return 0; return ...->unk14;`
so it does: ldr r0,=sFieldSysPtr ; ldr r0,[r0] ; ldr r0,[r0,#4] ; ...  The first literal is
&sFieldSysPtr.  Also confirms struct base offsets match the real retail bytes (the decomp has
bitten us before with the +1 opcode shift).

Usage: ironmon-scout/.venv/Scripts/python.exe ironmon-scout/tools/find_fieldsys_ptr.py [rom]
"""
import sys, struct
from ndspy import rom as ndsrom
from ndspy import codeCompression
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

BASE = 0x02000000
rompath = sys.argv[1] if len(sys.argv) > 1 else "Pokemon Heart Gold.nds"
a9 = codeCompression.decompress(bytes(ndsrom.NintendoDSRom.fromFile(rompath).arm9))
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True

def u32(o): return struct.unpack_from("<I", a9, o)[0]

def litval(insn):
    """If insn is `ldr rX,[pc,#imm]`, return (dest_reg_str, literal_address, value_at_literal)."""
    if insn.mnemonic != "ldr" or "[pc" not in insn.op_str:
        return None
    imm = int(insn.op_str.split("#")[-1].rstrip("]"), 0)
    lit_addr = ((insn.address + 4) & ~3) + imm
    return insn.op_str.split(",")[0].strip(), lit_addr, u32(lit_addr - BASE)

def dump(addr, n, label):
    print(f"\n=== {label}  0x{addr:08X} ===")
    off = addr - BASE
    found = []
    for insn in md.disasm(a9[off:off + n], addr):
        lit = ""
        lv = litval(insn)
        if lv:
            _, la, val = lv
            lit = f"   ; [0x{la:08X}] = 0x{val:08X}"
            found.append((la, val))
        print(f"  0x{insn.address:08X}: {insn.mnemonic:7} {insn.op_str}{lit}")
        if insn.mnemonic in ("pop", "bx") and ("pc" in insn.op_str or "lr" in insn.op_str):
            break
    return found

# The three no-arg accessors in field_system.c that dereference sFieldSysPtr.
lits = []
lits += dump(0x0203E2F4, 0x24, "sub_0203E2F4  sFieldSysPtr->unk0->isPaused=TRUE")
lits += dump(0x0203E30C, 0x24, "sub_0203E30C  sFieldSysPtr->unk0->isPaused=FALSE")
lits += dump(0x0203E324, 0x2C, "sub_0203E324  sFieldSysPtr->unk4->unk14")

# The VALUE these accessors load (not the pool slot) is &sFieldSysPtr — it recurs across all
# three functions. Count loaded values.
from collections import Counter
c = Counter(val for _, val in lits)
print("\n--- literal VALUES loaded (candidate pointers) ---")
for val, n in c.most_common():
    print(f"  0x{val:08X}  x{n}")
if c:
    best = c.most_common(1)[0][0]
    print(f"\n>>> sFieldSysPtr (FieldSystem**) is at RAM 0x{best:08X}")
    print( "    Live chain: [0x%08X] -> +0x40 (PlayerAvatar) -> +0x30 (LocalMapObject)" % best)
    print( "                -> +0x64 currentX (u32), +0x68 currentY (s32), +0x6C currentZ (u32)")
