"""
app.py - CSI sensing server.

Responsibilities:
  * TCP ingest (port 5006): accepts newline-delimited CSI JSON from the host
    serial bridge (or directly from a Wi-Fi-streaming RX board).
  * DSP: feeds every record into CSIProcessor (dsp.py).
  * WebSocket /ws: pushes the current sensing state to the dashboard ~15x/s.
  * REST: GET /api/state, GET/POST /api/config, POST /api/recalibrate.
  * Serves the static dashboard from ../web at /.

Run locally:   uvicorn app:app --host 0.0.0.0 --port 8000
In Docker:     see docker-compose.yml
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from dsp import CSIProcessor, Config

INGEST_PORT = int(os.environ.get("CSI_INGEST_PORT", "5006"))
WEB_DIR = os.environ.get("CSI_WEB_DIR", os.path.join(os.path.dirname(__file__), "..", "web"))

proc = CSIProcessor(Config())
_clients: set[WebSocket] = set()


async def handle_ingest(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    print(f"[ingest] source connected: {peer}")
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.strip()
            if not line or not line.startswith(b"{"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            proc.push(rec)
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        print(f"[ingest] source disconnected: {peer}")
        writer.close()


async def broadcaster():
    """Push the latest state to all websocket clients at a fixed cadence."""
    while True:
        await asyncio.sleep(1 / 15)
        if not _clients:
            continue
        msg = json.dumps(proc.snapshot())
        dead = []
        for ws in list(_clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _clients.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    server = await asyncio.start_server(handle_ingest, "0.0.0.0", INGEST_PORT)
    print(f"[server] CSI ingest listening on tcp/{INGEST_PORT}")
    task = asyncio.create_task(broadcaster())
    async with server:
        srv_task = asyncio.create_task(server.serve_forever())
        yield
        srv_task.cancel()
        task.cancel()


app = FastAPI(title="ESP32-DIV CSI Sensing", lifespan=lifespan)


@app.get("/api/state")
async def api_state():
    return proc.snapshot()


@app.get("/api/config")
async def api_get_config():
    return proc.config_dict()


@app.post("/api/config")
async def api_set_config(patch: dict):
    return proc.update_config(patch)


@app.post("/api/recalibrate")
async def api_recalibrate():
    proc.recalibrate()
    return JSONResponse({"ok": True, "msg": "baseline reset - keep the room empty for ~5s"})


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            # we only push; ignore inbound but keep the socket alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)


# Static dashboard LAST so /api and /ws take priority.
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
