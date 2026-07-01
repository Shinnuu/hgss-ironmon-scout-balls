"""Verify a randomizer output is compatible + actually randomized, before patching."""
import sys, struct
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from ndspy import rom as ndsrom
from ndspy import narc as ndsnarc
from ndspy import codeCompression
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

BASE = 0x02000000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
CLEAN = "Pokemon Heart Gold.nds"
RAND = sys.argv[1] if len(sys.argv) > 1 else "Pokemon Heart Gold - random2.nds"

def grass_species(rom):
    d = ndsnarc.NARC(rom.getFileByName("a/0/3/7")).files[1]  # Route 29
    def u16s(o): return list(struct.unpack_from("<12H", d, o))
    return sorted(set(s for s in (u16s(0x14) + u16s(0x2C) + u16s(0x44)) if s))

def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u16(b, o): return struct.unpack_from("<H", b, o)[0]

def find_tbl(a9):
    off = 0
    while off + 4 <= len(a9):
        if 0x02000000 <= (u32(a9, off) & ~1) <= 0x023FFFFF:
            j, c = off, 0
            while j + 4 <= len(a9) and 0x02000000 <= (u32(a9, j) & ~1) <= 0x023FFFFF:
                c += 1; j += 4
            if 800 < c < 900:
                return off
            off = j
        else:
            off += 4

def find_hdr(a9):
    HDR = 24
    def ok(i):
        return (i+HDR <= len(a9) and (a9[i] < 142 or a9[i] == 0xFF)
                and u16(a9, i+4) < 1200 and u16(a9, i+0xA) < 829 and u16(a9, i+0x10) < 491)
    best = (None, 0); i = 0
    while i <= len(a9)-HDR:
        if not ok(i): i += 1; continue
        j, cnt, me = i, 0, 0
        while j+HDR <= len(a9) and ok(j):
            me = max(me, u16(a9, j+0x10)); cnt += 1; j += HDR
        if cnt > best[1] and me > 100: best = (i, cnt)
        i += 1
    return best[0]

clean = ndsrom.NintendoDSRom.fromFile(CLEAN)
rand = ndsrom.NintendoDSRom.fromFile(RAND)

cg, rg = grass_species(clean), grass_species(rand)
print(f"Route 29 grass species:")
print(f"  clean (vanilla): {cg}")
print(f"  randomized     : {rg}")
print(f"  => RANDOMIZED: {'YES (species changed)' if cg != rg else 'NO (identical!)'}")

a9 = codeCompression.decompress(bytes(rand.arm9))
tbl = find_tbl(a9)
H = u32(a9, tbl + 0x24D*4) & ~1
seq = [f"{i.mnemonic} {i.op_str}" for i in md.disasm(a9[H-BASE:H-BASE+0x14], H)]
print(f"\nopcode 0x24D -> 0x{H:08X}; winFlag(0x18) read: {any('#0x18' in s for s in seq)}")
ht = find_hdr(a9)
r29 = [k for k in range((len(a9)-ht)//24) if a9[ht+k*24] == 1]
print(f"header table @0x{BASE+ht:08X}; Route 29 (encBank==1) mapIds: {r29[:4]}")
for k in r29[:2]:
    o = ht + k*24
    print(f"  mapId {k}: scriptsBank={u16(a9,o+6)} eventsBank={u16(a9,o+0x10)}")
