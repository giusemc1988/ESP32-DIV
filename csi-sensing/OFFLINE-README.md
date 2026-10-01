# Ruview Project — Offline Bundle (work without cloud credits)

This folder has everything to keep working offline, including with a **local**
Claude Code (`claude` CLI) on your own PC.

## What's inside
```
Ruview-Project/
├── OFFLINE-README.md          ← you are here
├── our-app/                   ← the lightweight app we built together
│   ├── QUICKSTART.md          ← how to run OUR app (start here, no boards needed)
│   ├── RUN-REAL-RUVIEW-WINDOWS.md ← how to run the REAL ruview on Windows
│   ├── START-HERE.md          ← project overview / recall notes
│   ├── firmware/ server/ web/ host/ docker-compose.yml README.md
└── ruview-source/             ← the REAL ruvnet/ruview source code (for study + local Claude)
```

## Run OUR app offline (easiest, works today)
1. Install **Docker Desktop** + **Python 3** once (while you still have internet).
2. In `our-app/`: `docker compose up --build` → open http://localhost:8000
3. Test with fake data: `python host\sim_feed.py`  (see `our-app/QUICKSTART.md`)
4. With your 2 boards: flash `firmware/csi_tx` + `firmware/csi_rx`, then
   `python host\serial_bridge.py --port COMx`.

## Run the REAL ruview
Follow `our-app/RUN-REAL-RUVIEW-WINDOWS.md`. The `ruview-source/` folder here is
the core source for reference. **The firmware `.bin` files and the `.rvf` model
are included** so you can flash and run without re-downloading.

> Note: `ruview-source/` has git history and some heavy/optional folders removed
> to keep the download small. To get the FULL repo WITH git history later
> (recommended for serious work with local Claude Code), run on your PC (needs
> internet, NOT cloud credits):
> ```
> git clone https://github.com/ruvnet/ruview
> ```

## Continue with LOCAL Claude Code (no cloud credits)
1. Install the Claude Code CLI on your PC (https://claude.ai/code → "install").
2. Open a terminal in this `Ruview-Project` folder and run: `claude`
3. Ask it things like: "read our-app/START-HERE.md and help me add a 3rd ESP32
   node for real location" — it can read every file here offline.

## The #1 fix for your old problem
On Windows, Docker silently dropped one of your two boards' data (ruview
#374/#386). The fix is the **UDP relay** — see
`our-app/RUN-REAL-RUVIEW-WINDOWS.md` Step 4. Without it, you only ever see one
board → wrong count and location.

## Where it also lives online
GitHub: `giusemc1988/ESP32-DIV`, branch `claude/esp32-human-detection-xdaf7g`,
folder `csi-sensing/`.
