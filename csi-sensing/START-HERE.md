# Ruview — ESP32-C6 Wi-Fi CSI Human-Sensing Webapp (START HERE)

> One-page handoff so any new chat can continue without re-explaining.
> Last updated: 2026-10-01

## Start here
**Ruview** is a camera-free human-sensing webapp: two **ESP32-C6** boards use
Wi-Fi **CSI** (Channel State Information) to detect **presence, motion, and
breathing**, shown on a live browser dashboard. Inspired by
[ruvnet/ruview](https://github.com/ruvnet/ruview).

All code lives in **`csi-sensing/`** on GitHub:
- Repo: `giusemc1988/ESP32-DIV`
- Branch: **`claude/esp32-human-detection-xdaf7g`**
- Layout: `firmware/csi_tx` (TX illuminator), `firmware/csi_rx` (RX capture),
  `host/serial_bridge.py` (serial→TCP), `server/` (FastAPI + numpy DSP),
  `web/index.html` (dashboard), `docker-compose.yml`, `README.md`.

## Goal and requirements (user's words)
"Build a webapp like ruview with esp32… it detects human but not the right
amount and location." Hardware: **2× ESP32-C6**. Wanted a new webapp in this
repo, ruview-inspired, runnable with Docker. Keep it honest about limits.

## Current version and features
- TX board = SoftAP "illuminator" sending steady 120 Hz UDP packets.
- RX board = joins TX AP, captures CSI, streams JSON over USB serial @921600.
- Server = TCP ingest (:5006), DSP, WebSocket + REST, serves dashboard (:8000).
- DSP: amplitude → Hampel clean → static-baseline removal → motion energy →
  presence (hysteresis), bucketed people-count estimate, FFT breathing
  (9–36 BPM), coarse near/mid/far zones. All thresholds tunable live.
- Dashboard: presence, count, breathing, motion timeline, zone bars, live
  tuning sliders, recalibrate button.

## Decisions and why
- **Serial bridge is the default** (not Wi-Fi streaming): most reliable, no
  network reconfig, never competes with the CSI link.
- **Count is a labeled ESTIMATE; location is "hints," not coordinates.** With
  only 1 TX→RX link you physically CANNOT triangulate position or cleanly
  separate N people — that needs 3+ receivers. This is the root cause of the
  "wrong amount and location" the user saw. Documented, not hidden.
- Runs **100% local** (Docker on PC + 2 boards over USB + a private board-to-board
  Wi-Fi link). No internet/cloud needed to operate. GitHub is only code backup.

## How to install and run
1. Arduino IDE, ESP32 core ≥3.0.x, board "ESP32C6 Dev Module".
   Flash `csi_tx.ino` to board A, `csi_rx.ino` to board B (SSID/pass/channel
   must match; defaults `csi-sense`/`csisense123`/ch6).
2. `cd csi-sensing && docker compose up --build`  → dashboard at
   http://localhost:8000 , ingest on tcp/5006.
3. `pip install pyserial` then
   `python host/serial_bridge.py --port /dev/ttyACM0` (or `COM5` on Windows).
4. Open http://localhost:8000 → should show "● live".

## Troubleshooting (hit so far)
- **GitHub push 403 / "could not read Username":** the git CLI in a cloud
  session has no push credential if GitHub was connected AFTER the session
  started. Fix: install Claude GitHub App on the repo, then either start a NEW
  session, or push via the GitHub MCP tools (`push_files`) — which is how this
  project was uploaded.
- **Wrong count / position:** expected with 2 boards. Recalibrate empty, then
  tune the count-threshold sliders against the real number of people. See
  README §4 "Fixing accuracy".
- **Breathing shows 0:** needs a still subject <~2 m and steady ≥100 Hz rate.

## Status (2026-10-01)
- ✅ All code written, DSP + server smoke-tested with simulated CSI (presence,
  count 1→2, REST/WS verified).
- ✅ Pushed to GitHub branch `claude/esp32-human-detection-xdaf7g`.
- ⚠️ NOT yet tested on real ESP32-C6 hardware by the user.
- Last thing user was doing: asking to save the project for later recall.

## Next steps and ideas
- Flash both boards, run the stack, tune thresholds for the real room.
- Open a PR from the branch if desired (not yet created).
- **Roadmap to real location + robust counting:** add a 3rd/4th C6 as extra RX
  nodes (same `csi_rx` sketch, one serial bridge each to :5006, tag node id),
  then estimate position by comparing per-node motion energy; later swap the
  bucketed count for a small learned model.

## To resume
Open a new chat on this repo and say: **"continue Ruview"** (or point it at
`csi-sensing/START-HERE.md` on branch `claude/esp32-human-detection-xdaf7g`).
