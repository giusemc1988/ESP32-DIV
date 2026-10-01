# Ruview — Quickstart (how to turn it on)

Two ways to run it. **Start with Path A** to see it working in ~5 minutes with
no hardware, then do Path B once your boards are ready.

Everything below is run from inside the `csi-sensing` folder.

---

## What you need installed (one time)
- **Docker Desktop** (Windows/Mac/Linux) — this runs the server + dashboard.
  Get it: https://www.docker.com/products/docker-desktop/  → install → open it
  once so it's running (whale icon in the menu bar/tray).
- **Python 3** (only needed for the simulator in Path A and the board bridge in
  Path B). Get it: https://www.python.org/downloads/ (tick "Add to PATH").

---

## Path A — Test it NOW, no ESP32 needed  ✅ do this first

This proves the whole app works and lets you play with the dashboard.

1. Open a terminal in the `csi-sensing` folder and start the server:
   ```bash
   docker compose up --build
   ```
   Wait until it prints `CSI ingest listening on tcp/5006`. Leave it running.

2. Open your browser to **http://localhost:8000** — you'll see the dashboard
   (it will say "connecting…" then "● live", everything at 0 for now).

3. Open a **second** terminal in the `csi-sensing` folder and run the simulator:
   ```bash
   pip install --upgrade pip
   python host/sim_feed.py
   ```
   (On Mac/Linux use `python3` if `python` doesn't work.)

4. Watch the dashboard. It cycles **EMPTY → ONE PERSON → TWO PEOPLE** every ~8s.
   Presence flips to OCCUPIED, the people count changes, the motion line moves,
   and breathing shows a number. Play with the **tuning sliders** and the
   **Recalibrate** button to see how they affect the readings.

5. To stop: press **Ctrl+C** in each terminal, then `docker compose down`.

> This is fake data — it just shows the software works and lets you learn the UI.

---

## Path B — Run it for real with your 2 ESP32-C6 boards

1. **Flash the firmware** (Arduino IDE, ESP32 core ≥ 3.0.x, board
   "ESP32C6 Dev Module"):
   - Board A → `firmware/csi_tx/csi_tx.ino`
   - Board B → `firmware/csi_rx/csi_rx.ino`
   - Power board A. Plug board B into your computer by USB.
   - (Defaults match already: SSID `csi-sense`, pass `csisense123`, channel 6.)

2. **Start the server** (same as Path A step 1):
   ```bash
   docker compose up --build
   ```

3. **Bridge the RX board to the server.** In a second terminal:
   ```bash
   pip install pyserial
   python host/serial_bridge.py --port /dev/ttyACM0      # Mac/Linux
   python host/serial_bridge.py --port COM5              # Windows
   ```
   Find the port: Mac/Linux `ls /dev/ttyACM* /dev/ttyUSB*`; Windows → Device
   Manager → Ports (COM & LPT).

4. Open **http://localhost:8000**. It should go "● live" and the `Hz` number
   should be ~100+. Now tune it for your room — see **README.md section 4
   "Fixing accuracy"** (calibrate empty first, then set the count thresholds).

---

## Common hiccups
- **Browser shows "disconnected":** the Docker server isn't running, or you're
  not on http://localhost:8000. Check the first terminal for errors.
- **`docker: command not found`:** Docker Desktop isn't installed or not open.
- **Simulator/bridge says "connection refused":** start `docker compose up`
  first and wait for the "listening" line before running them.
- **`python: command not found`:** try `python3` instead (Mac/Linux).
- **Wrong count with real boards:** that's expected with 2 boards — see
  README §4. Count is a tunable estimate; position is only a coarse hint.

Full details and the accuracy playbook are in **README.md**.
Project overview for a fresh start is in **START-HERE.md**.
