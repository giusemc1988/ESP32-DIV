# Running the REAL ruview on Windows (2 boards) — step by step

This sets up **ruvnet/ruview's own firmware + server + dashboard** on your
Windows PC with your 2 ESP32 boards. It fixes the bug that most likely broke
your count/location: **Docker Desktop on Windows silently drops all but one
ESP32's UDP data** (ruview issues #374 / #386). We apply ruview's official
relay workaround.

> Do this with me one step at a time — tell me the result of each step and I'll
> help with the next. Don't try to rush all of it at once.

---

## The 3 things that were probably wrong before
1. **Windows UDP drop** — with 2 boards, the server only ever saw ONE. → fixed
   by the UDP relay below. **This is the big one.**
2. **Old firmware** — firmware before v0.8.8 could show a person count in an
   empty room. → use the v0.8.8+ release bundles.
3. **No models mounted** — advanced features need the `.rvf` model file mounted
   into the server.

---

## Step 0 — Get the files
- Install **Docker Desktop** (open it, wait for "Engine running") and
  **Python 3** (tick "Add to PATH"), and **Git**.
- Clone ruview:
  ```powershell
  cd $HOME\Desktop
  git clone https://github.com/ruvnet/ruview
  cd ruview
  ```

## Step 1 — Download the official firmware bundles
Firmware source in the repo may be older. Get the **v0.8.8 (or newer) ESP32
release** here:
https://github.com/ruvnet/RuView/releases

Download the bundle that matches **each** board + its flash size, e.g.:
- ESP32-C6 → `esp32-csi-node-v0.8.8-c6-4mb-flash-bundle.zip`
- ESP32-S3 (if you use it) → `...-s3-8mb-...` or `...-s3-4mb-...`

Extract each zip. Each contains `bootloader.bin`, `partition-table.bin`,
`ota_data_initial.bin`, `esp32-csi-node.bin`, and a short flashing guide.
**Never flash an S3 bundle onto a C6 or vice-versa.**

## Step 2 — Flash each board (esptool)
Install esptool once: `pip install esptool`

Plug in **Board 1 (C6)**, find its COM port (Device Manager → Ports), then from
inside that board's extracted bundle folder:
```powershell
python -m esptool --chip esp32c6 --port COM5 --baud 460800 `
  write_flash --flash_mode dio --flash_size 4MB `
  0x0     bootloader.bin `
  0x8000  partition-table.bin `
  0xf000  ota_data_initial.bin `
  0x20000 esp32-csi-node.bin
```
Repeat for **Board 2** (swap `--chip`/`--flash_size` to match that board and
its bundle). Use the exact offsets from the guide inside each bundle.

## Step 3 — Provision each board (WiFi + server address)
Each node needs: your WiFi SSID + password, a unique `node_id`, and the
**server address = your PC's LAN IP** (find it with `ipconfig` → IPv4 Address).

Depending on the firmware build, provisioning is one of:
- **SoftAP setup:** on first boot the board makes a WiFi network (e.g.
  `ruview-c6-...`). Join it from your phone/PC and open the setup page to enter
  WiFi + server IP, **or**
- **config_push.py** (in the ruview repo) once the board is on WiFi:
  ```powershell
  python config_push.py --node <board-ip> --set wifi_ssid=YOURWIFI
  python config_push.py --node <board-ip> --set wifi_password=YOURPASS
  python config_push.py --node <board-ip> --set node_id=1   # 2 for the other
  ```
Point both boards at **your PC's IP on UDP 5005**. (Follow the exact method in
the bundle's flashing guide — tell me which it uses and I'll give exact keys.)

## Step 4 — ⭐ Apply the Windows UDP relay fix (the important one)
Without this, Windows Docker drops one board's data.

1. Start the relay (keep this window open):
   ```powershell
   python scripts\udp-relay.py --listen-port 5005 --forward-port 5006
   ```
2. Edit `docker\docker-compose.yml` — change the ESP32 UDP line from
   `- "5005:5005/udp"` to `- "5006:5005/udp"`.

## Step 5 — Start the server with real CSI + models
```powershell
# tell it to use real ESP32 data and where the model lives
$env:CSI_SOURCE="esp32"
$env:MODELS_DIR="/app/models"
docker compose -f docker\docker-compose.yml up --build
```
If models aren't auto-mounted, add this under `sensing-server:` in the compose
file and restart:
```yaml
    volumes:
      - ./docker:/app/models      # contains wifi-densepose-v1.rvf
```

## Step 6 — Open the dashboard
- REST API: http://localhost:3000
- WebSocket: ws://localhost:3001
- (Python UI variant, if you run that service: http://localhost:8080)

Check http://localhost:3000/api/v1/sensing/latest — you should now see **both**
node IDs appearing (not just one). That confirms the UDP fix worked.

## Step 7 — Calibrate
Leave the room empty for the ambient-learning window (~60 s), then test. With
both nodes feeding data and the models mounted, count/location should be far
better than before.

---

## Honest expectations
- The Windows UDP fix + both nodes + v0.8.8 firmware should fix most of your
  "wrong amount / only one body" problem.
- Full **body-pose and precise (x,y)** still improve a lot with **more than 2
  receivers** — ruview's best demos use 4–6 nodes. Your S3 can be a 3rd node.
- "Experimental" features (heart rate, pose) are labelled experimental by
  ruview too — treat them as such.

## If you get stuck
Tell me the exact step number and paste the error or what you see. The two most
common Windows issues are: (a) wrong COM port / esptool can't connect (hold the
BOOT button while it starts), and (b) forgetting the UDP relay (Step 4) — then
only one board shows up.
