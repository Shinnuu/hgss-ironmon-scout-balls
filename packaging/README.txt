============================================================================
 IronMON Scout Balls  —  Pokemon HeartGold / SoulSilver
============================================================================

WHAT IT DOES
  Adds interactable "scout balls" at the start of each early (pre-Falkner)
  wild-Pokemon area. Each ball represents one wild species available there.
  Press A on a ball -> a normal wild battle with that species, at a random
  level in its real range (IVs / nature / ability / gender / shiny all rolled
  exactly like a real grass encounter). It lets you scout a route's pivot
  options without grinding rare encounter rates.

  Areas covered: Route 29, Route 30, Route 31, Route 32, Route 46,
  Dark Cave (Violet City entrance), and Sprout Tower.

----------------------------------------------------------------------------
SETUP  (do this once)
----------------------------------------------------------------------------
  1. Put these three files into your Ironmon Tracker folder -- the SAME folder
     that has "Ironmon-Tracker.lua" (the file you load in BizHawk):
         scout_patcher.exe
         install_scout_balls.bat
         uninstall_scout_balls.bat

     >> Put them in that TOP tracker folder -- the one that ALSO contains the
        "ironmon_tracker" sub-folder. Do NOT put them inside the
        "ironmon_tracker" sub-folder. <<

  2. Double-click  install_scout_balls.bat.
     It should print:  Installed scout-ball hook into: ...\ironmon_tracker\QuickLoader.lua
     (If it says it could NOT find QuickLoader.lua, the files are in the wrong
     folder -- move them next to Ironmon-Tracker.lua and run it again.)

  3. In BizHawk, reload the tracker (restart the Lua script, or restart BizHawk)
     so the change takes effect.

  Done. No Python or other installs are required.

----------------------------------------------------------------------------
HOW IT WORKS
----------------------------------------------------------------------------
  Your Tracker's normal "new run" hotkey already randomizes and loads a fresh
  ROM. After install, each new run ALSO auto-adds the scout balls (this adds a
  few seconds while it patches). Nothing about how you play changes.

  The balls always match THAT seed's real grass/cave species and levels --
  they are read live from each freshly randomized ROM.

----------------------------------------------------------------------------
NOTES
----------------------------------------------------------------------------
  * Each new run OVERWRITES the same generated ROM file -- no disk buildup.
    (To keep a specific seed, copy its .nds before your next new run.)
  * If you MOVE or UPDATE your Tracker, just double-click
    install_scout_balls.bat again.
  * To remove the feature: double-click uninstall_scout_balls.bat.
  * If a run ever loads without balls, look for "ScoutPatchErrorLog.txt" in
    your Tracker folder and send it over.

----------------------------------------------------------------------------
LICENSE
----------------------------------------------------------------------------
  Open source under the GNU GPL v3 (see LICENSE.txt). Full source is in the
  "src" folder; third-party credits are in THIRD-PARTY-NOTICES.txt.
  (Only scout_patcher.exe + the two .bat files are needed to run it; the
  LICENSE / NOTICES / src are included to satisfy the open-source license.)
============================================================================
