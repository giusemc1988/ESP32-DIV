# ESP32-DIV · Wi-Fi CSI Human Sensing (ruview-inspired)

A small, self-contained webapp that turns **two ESP32-C6 boards** into a
camera-free Wi-Fi sensor: it detects **presence**, **motion**, and
**breathing rate**, and shows it on a live dashboard — inspired by
[ruvnet/ruview](https://github.com/ruvnet/ruview).

```
[ESP32-C6 TX] ── Wi-Fi packets ──▶ [ESP32-C6 RX] ──USB serial──▶ host bridge ──TCP──▶ Docker server ──▶ browser dashboard
 "illuminator"   (CSI changes as        captures CSI                                  DSP + WebSocket
  SoftAP          people move/breathe)                                                 (FastAPI + numpy)
```

---

## ⚠️ Read this first — what 2 boards can and cannot do

This is the honest physics, and it explains why your current setup reports the
wrong **amount** and **location**:

| Capability | 2 nodes (1 TX + 1 RX) | Needs more |
|---|---|---|
| Presence (someone in the room) | ✅ reliable | — |
| Motion / activity level | ✅ reliable | — |
| Breathing rate (still, nearby subject) | ✅ works | — |
| **People count** | ⚠️ **estimate only**, tunable, 0/1/2/3+ | 3+ RX nodes |
| **Location (x,y)** | ❌ **not possible** — shown as coarse near/mid/far *hints* | 3+ RX nodes (triangulation) |

A single transmitter→receiver link is **one measurement**. You cannot solve for
*where* or *how many* from one number — that is a hardware limit, not a software
bug. ruview gets position from a **mesh of receivers**. So: trust presence,
motion, and breathing; treat count as a tunable gauge and zones as hints. If you
later add a 3rd/4th C6 as extra RX nodes, position becomes real (see *Roadmap*).

---

## Hardware

- 2× **ESP32-C6** (any dev board). C6 has the Wi-Fi 6 radio + CSI support.
- 1× USB cable for the **RX** board (data stream) — and power for the TX board.
- Place TX and RX **2–4 m apart** with the monitored area **between** them.
  Line-of-sight across the zone of interest works best.

## 1. Flash the firmware

Arduino IDE with **ESP32 core ≥ 3.0.x** (Boards Manager → "esp32" by Espressif).
Select board **"ESP32C6 Dev Module"**.

- Board **A → transmitter**: open `firmware/csi_tx/csi_tx.ino`, flash it.
- Board **B → receiver**: open `firmware/csi_rx/csi_rx.ino`, flash it.

The SSID/password/channel at the top of both sketches **must match** (defaults
`csi-sense` / `csisense123` / channel 6). Pick a quiet channel (1, 6, or 11).

Open the RX serial monitor at **921600 baud** — you should see JSON lines like:
```json
{"t":123456,"rssi":-43,"n":64,"csi":[12,-4,9,-7, ...]}
```
If you see those steadily (~100+/s), capture is working.

## 2. Start the server (Docker)

```bash
cd csi-sensing
docker compose up --build
```
This serves the dashboard at **http://localhost:8000** and listens for CSI on
**tcp/5006**.

## 3. Bridge the RX board to the server

The RX streams over USB serial; this forwards it into the container:
```bash
pip install pyserial
python host/serial_bridge.py --port /dev/ttyACM0      # Linux/mac
python host/serial_bridge.py --port COM5              # Windows
```
Find the port with `ls /dev/ttyACM* /dev/ttyUSB*` or Windows Device Manager.

Open **http://localhost:8000** — the dashboard should go **● live**.

---

## 4. Fixing accuracy (the important part)

Do these in order whenever the readings look wrong:

1. **Calibrate empty.** Click **Recalibrate** with the room **empty**. The
   baseline is the "resting" channel; everything is measured relative to it.
   Recalibrate again any time you move a board or furniture.
2. **Check the sample rate.** The dashboard shows `Hz`. You want **≥ 100 Hz**.
   If it's low: shorten the USB cable, keep TX/RX on a quiet channel, and make
   sure `PING_HZ` in `csi_tx.ino` is ≥ 120. Low/jittery rate wrecks breathing.
3. **Fix false presence / empty flapping.** Raise **Presence ON** until an empty
   room reads *empty*; lower **Presence OFF** a bit below it (hysteresis stops
   flicker).
4. **Fix the people count.** Put the *real* number of people in the room, watch
   **Motion energy**, then drag the matching **Count threshold** slider so the
   readout matches. Repeat for 1, 2, and 3 people. Raise **Count smoothing** if
   the number jitters. These are per-room — a big echoey room needs different
   numbers than a small one.
5. **Breathing** reads 0 until it's confident. It needs a **still** subject
   within ~2 m and a steady sample rate. Movement masks breathing — that's
   expected.

All sliders apply **live** on the server (`POST /api/config`); nothing to
restart.

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | current sensing state (JSON) |
| GET | `/api/config` | current DSP thresholds |
| POST | `/api/config` | patch thresholds (any subset) |
| POST | `/api/recalibrate` | reset the empty-room baseline |
| WS | `/ws` | live state stream (~15 Hz) used by the dashboard |

## How the DSP works (`server/dsp.py`)

raw int8 I/Q → amplitude per subcarrier → **Hampel** outlier clean → running
**baseline** (static removal) → normalized **motion energy** → presence
(with hysteresis), bucketed **count estimate**, **breathing** via band-limited
FFT (0.15–0.60 Hz → 9–36 BPM), and coarse subcarrier-group **zones**.

## No-serial (Wi-Fi) streaming — optional

The serial bridge is the reliable default. If you'd rather the RX push CSI over
Wi-Fi: have the **host/PC running Docker join the TX SoftAP**, give the RX a
TCP-client that connects to the PC's AP-subnet IP on port 5006 and sends the
same JSON lines. Then you can drop the serial bridge. (Firmware stub not
included by default to keep the CSI Wi-Fi link uncontended.)

## Roadmap to real location + robust counting

- Add a **3rd and 4th C6 as extra RX nodes** (same `csi_rx` sketch, separate
  serial bridges to the same `:5006`). Tag each stream with a node id.
- With ≥3 receivers you can estimate position by comparing per-node motion
  energy (centroid / trilateration), which is what makes counting robust.
- Swap the bucketed count for a small learned model (e.g. an MLP on the
  multi-node energy vector) once you have labeled data.

---

*Educational / research use. Sense only spaces you own or are permitted to
monitor. CSI sensing is privacy-sensitive even without a camera.*
