# IronMON Scout Balls — Pokémon HeartGold / SoulSilver

Adds interactable **"scout balls"** to the start of each early (pre‑Falkner) wild area in a
randomized HeartGold/SoulSilver ROM. Each ball represents one wild species available there — press
**A** on it to start a normal wild battle with that species at a random level in its real range
(IVs / nature / ability / gender / shiny all rolled exactly like a real grass encounter).

It lets an IronMON player scout a route's pivot options without grinding rare encounter rates. The
balls are read **live from each freshly randomized ROM**, so they always match that seed's real
encounters (species *and* level band).

**Areas covered:** Route 29, Route 30, Route 31, Route 32, Route 46, Dark Cave (Violet City
entrance), and Sprout Tower.

---

## For players

The tool plugs into the **NDS Ironmon Tracker** on BizHawk. After a one‑time install, your normal
"new run" hotkey automatically adds the scout balls to each generated ROM — nothing about how you
play changes.

1. Download the latest release zip and extract it.
2. Put `scout_patcher.exe`, `install_scout_balls.bat`, and `uninstall_scout_balls.bat` into your
   Ironmon Tracker folder (the one containing `ironmon_tracker/QuickLoader.lua`).
3. Double‑click **`install_scout_balls.bat`**.

That's it — no Python or other installs required. Re‑run the installer if you move/update the
Tracker; run `uninstall_scout_balls.bat` to remove. Full player notes: [packaging/README.txt](packaging/README.txt).

## How it works

The Tracker's new‑run command randomizes a fresh ROM (PokéRandoZX) and loads it. The installer adds
one line to `QuickLoader.lua` that runs `scout_patcher.exe` on the freshly randomized ROM, in place,
before it loads. For each target area the patcher:

1. Reads the walking‑encounter species + levels from the encounter NARC (`a/0/3/7`).
2. Builds a random‑level `wildbattle` script per unique species and appends it to the scripts NARC
   (`a/0/1/2`) — using a **private script member + arm9 map‑header repoint** for cave/tower maps
   whose script bank is a stub shared by many maps.
3. Injects a Poké‑Ball object event pointing at that script (`a/0/3/2`).

Byte‑level formats and the reverse‑engineering notes are in [docs/rom-formats.md](docs/rom-formats.md).

## Building from source

The released `scout_patcher.exe` is built with [PyInstaller](https://pyinstaller.org/) from the
Python in `src/` (only dependency: [ndspy](https://github.com/RoadrunnerWMC/ndspy)):

```sh
pip install ndspy pyinstaller
pyinstaller --onefile --name scout_patcher \
  --hidden-import charmap_data --hidden-import species_ow_sprite \
  --collect-submodules ndspy src/scout_route.py
```

`scout_route.py` is the entry point and has three modes:

| Command | Does |
|---------|------|
| `scout_patcher <rom.nds>` | patch that ROM in place (what the Tracker hook calls) |
| `scout_patcher install [tracker_dir]` | add the hook to the Tracker's `QuickLoader.lua` |
| `scout_patcher uninstall [tracker_dir]` | remove the hook |

Other `src/` tools: `coord_reader.lua` (live BizHawk/DeSmuME position reader used to pick placement
tiles), `find_fieldsys_ptr.py` (derives the reader's pointer chain), `enum_areas.py`,
`verify_random.py`, and the `gen_*.py` scripts that bake the charmap / overworld‑sprite tables from
the [pret/pokeheartgold](https://github.com/pret/pokeheartgold) decompilation (reference only).

## License

Free/open‑source under the **GNU GPL v3** (see [LICENSE](LICENSE)) — the tool statically bundles
ndspy, which is GPLv3+. Third‑party credits: [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

© 2026 Fazlic Software.
