"""HGSS message-archive (NARC a/0/2/7 = msgdata/msg) decode + single-entry re-encode.

Format (per NARC member), from decomp tools/msgenc/MessagesConverter.h:
  u16 count, u16 key
  count * { u32 offset(bytes), u32 length(u16 units) }   -- XOR-encrypted per entry
  then u16 string data (each string ends 0xFFFF)          -- XOR-encrypted per entry
Alloc key:  ak=(765*i*key)&0xFFFF; ak|=ak<<16; offset^=ak; length^=ak       (i = 1-based)
String key: k=(i*596947)&0xFFFF; for code: code^=k; k=(k+18749)&0xFFFF
Chars via charmap.txt (`HEXCODE=<char>`).  0xFFFE=command, 0xF100=trname, 0xFFFF=end.
"""
import os, struct, re

REFS = os.path.join(os.path.dirname(__file__), "..", "refs", "pokeheartgold")
CHARMAP = os.path.join(REFS, "charmap.txt")
MSG_NARC = "a/0/2/7"

def load_charmap():
    # Prefer the baked charmap (self-contained; ships in the .exe). Fall back to the decomp
    # refs file only in a dev checkout where charmap_data.py hasn't been regenerated.
    code2s = None
    try:
        from charmap_data import CODE2S as _baked
        code2s = dict(_baked)                     # preserves insertion (file) order
    except ImportError:
        code2s = {}
        for line in open(CHARMAP, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("//"):
                continue
            m = re.match(r"\s*([0-9A-Fa-f]{4})=(.*)$", line)
            if m:
                code2s[int(m.group(1), 16)] = m.group(2)
    s2code = {}
    for code, s in code2s.items():                # single-char forward map, first occurrence wins
        if len(s) == 1 and s not in s2code:
            s2code[s] = code
    return code2s, s2code

CODE2S, S2CODE = load_charmap()

def _alloc_key(key, i):
    ak = (765 * i * key) & 0xFFFF
    return ak | (ak << 16)

def parse_member(data):
    """-> (key, [ (offset,length,[u16 codes incl 0xFFFF]) , ...])."""
    count, key = struct.unpack_from("<HH", data, 0)
    entries = []
    for idx in range(count):
        i = idx + 1
        off, length = struct.unpack_from("<II", data, 4 + idx * 8)
        ak = _alloc_key(key, i)
        off ^= ak; length ^= ak
        codes = list(struct.unpack_from(f"<{length}H", data, off))
        sk = (i * 596947) & 0xFFFF
        dec = []
        for c in codes:
            dec.append(c ^ sk)
            sk = (sk + 18749) & 0xFFFF
        entries.append((off, length, dec))
    return key, entries

def codes_to_text(codes):
    out = []
    for c in codes:
        if c == 0xFFFF:
            break
        if c == 0xFFFE:
            out.append("{CMD}"); continue
        if c == 0xF100:
            out.append("{TRNAME}"); continue
        out.append(CODE2S.get(c, f"\\u{c:04X}"))
    return "".join(out)

LINEBREAK = 0xE000   # charmap '\n' — line break within a message box

def text_to_codes(text):
    """Encode a plain string -> u16 codes + 0xFFFF terminator. A real newline in `text` becomes
    the 0xE000 line-break code; every other char must be a single-char charmap entry."""
    codes = []
    for ch in text:
        if ch == "\n":
            codes.append(LINEBREAK)
        elif ch in S2CODE:
            codes.append(S2CODE[ch])
        else:
            raise ValueError(f"char {ch!r} not in charmap")
    codes.append(0xFFFF)
    return codes

def build_member(key, entries):
    """entries = list of [u16 codes] (each incl 0xFFFF). Re-encrypt and pack a full member."""
    count = len(entries)
    table_off = 4 + count * 8
    # recompute offsets/lengths, then encrypt
    blob = bytearray()
    raw_allocs = []
    cur = table_off
    for idx, codes in enumerate(entries):
        raw_allocs.append((cur, len(codes)))
        cur += len(codes) * 2
    out = bytearray(struct.pack("<HH", count, key))
    for idx, (off, length) in enumerate(raw_allocs):
        ak = _alloc_key(key, idx + 1)
        out += struct.pack("<II", off ^ ak, length ^ ak)
    for idx, codes in enumerate(entries):
        i = idx + 1
        sk = (i * 596947) & 0xFFFF
        enc = []
        for c in codes:
            enc.append(c ^ sk)
            sk = (sk + 18749) & 0xFFFF
        out += struct.pack(f"<{len(enc)}H", *enc)
    return bytes(out)

if __name__ == "__main__":
    import sys
    from ndspy import rom as ndsrom, narc as ndsnarc, codeCompression
    rompath = sys.argv[1] if len(sys.argv) > 1 else "Pokemon Heart Gold.nds"
    mapId = int(sys.argv[2]) if len(sys.argv) > 2 else 33
    rom = ndsrom.NintendoDSRom.fromFile(rompath)
    a9 = codeCompression.decompress(bytes(rom.arm9))
    hdr = 0xF6BE0 + mapId * 24
    msgBank = struct.unpack_from("<H", a9, hdr + 0x0A)[0]
    print(f"mapId {mapId}: msgBank = {msgBank}  (a/0/2/7[{msgBank}])")
    member = ndsnarc.NARC(rom.getFileByName(MSG_NARC)).files[msgBank]
    key, entries = parse_member(member)
    print(f"key=0x{key:04X}  count={len(entries)}\n")
    for idx, (off, length, codes) in enumerate(entries):
        print(f"[{idx:3}] {codes_to_text(codes)!r}")
