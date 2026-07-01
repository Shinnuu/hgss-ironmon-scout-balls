"""Enumerate maps with walking (grass/cave/floor) encounters + their file banks, flagging
pre-Falkner candidates by species. Caves & building floors use the same 'walking' slots as grass.
"""
import struct
from ndspy import rom as ndsrom
from ndspy import narc as ndsnarc
from ndspy import codeCompression

HDR_FILE_OFF = 0xF6BE0   # map header table, decompressed arm9

# early-Johto walking pool (National dex) for flagging pre-Falkner areas
EARLY = {16,19,161,163,10,13,11,14,165,167,69,41,42,74,21,92,179,187,194,60,
         23,27,56,231,95,206,163,133,84,198}
NAMES = {16:"Pidgey",19:"Rattata",161:"Sentret",163:"Hoothoot",10:"Caterpie",13:"Weedle",
         11:"Metapod",14:"Kakuna",165:"Ledyba",167:"Spinarak",69:"Bellsprout",41:"Zubat",
         42:"Golbat",74:"Geodude",21:"Spearow",92:"Gastly",179:"Mareep",187:"Hoppip",
         194:"Wooper",60:"Poliwag",23:"Ekans",27:"Sandshrew",56:"Mankey",231:"Phanpy",
         95:"Onix",206:"Dunsparce",133:"Eevee",84:"Doduo",198:"Murkrow"}

rom = ndsrom.NintendoDSRom.fromFile("Pokemon Heart Gold.nds")
enc = ndsnarc.NARC(rom.getFileByName("a/0/3/7"))
a9 = codeCompression.decompress(bytes(rom.arm9))

def u16(o): return struct.unpack_from("<H", a9, o)[0]
def walking_species(bank):
    if bank >= len(enc.files): return []
    d = enc.files[bank]
    if len(d) < 0x5C: return []
    def a(o): return struct.unpack_from("<12H", d, o)
    return sorted(set(s for s in (a(0x14)+a(0x2C)+a(0x44)) if s))

n_maps = (len(a9) - HDR_FILE_OFF) // 24
print(f"{n_maps} map headers. Pre-Falkner CANDIDATES (walking species mostly early-Johto):\n")
print(f"{'mapId':>5} {'enc':>3} {'events':>6} {'scripts':>7}  species")
for mid in range(n_maps):
    o = HDR_FILE_OFF + mid*24
    encBank = a9[o]
    if encBank == 0xFF or encBank >= len(enc.files):
        continue
    sp = walking_species(encBank)
    if not sp:
        continue
    early_frac = sum(1 for s in sp if s in EARLY) / len(sp)
    if early_frac >= 0.6:   # flag pre-Falkner-ish
        names = ", ".join(NAMES.get(s, str(s)) for s in sp)
        print(f"{mid:>5} {encBank:>3} {u16(o+0x10):>6} {u16(o+0x6):>7}  {names}")
