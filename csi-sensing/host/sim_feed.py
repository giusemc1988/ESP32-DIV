#!/usr/bin/env python3
"""
sim_feed.py - test Ruview WITHOUT any ESP32 hardware.

Generates synthetic CSI and streams it to the server's ingest port, so you can
see the dashboard come alive (presence, motion, count, breathing) before your
boards are ready. It cycles: empty room -> 1 person -> 2 people -> empty, so you
can watch the readouts and tune the sliders.

Usage (while `docker compose up` is running):
    python sim_feed.py
    python sim_feed.py --server 127.0.0.1:5006 --rate 100
"""
import argparse
import json
import math
import random
import socket
import time


def make_record(level: float, t: float, n: int = 64) -> dict:
    """level: 0 = empty, higher = more motion. Adds a slow breathing wiggle."""
    base = 20.0 + (2.0 * math.sin(2 * math.pi * 0.3 * t) if level > 0 else 0.0)
    csi = []
    for _ in range(n):
        amp = base + random.gauss(0, 0.5) + level * random.gauss(0, 20)
        amp = max(1.0, min(120.0, amp))
        phase = random.random() * 2 * math.pi
        i = int(max(-127, min(127, amp * math.cos(phase))))
        q = int(max(-127, min(127, amp * math.sin(phase))))
        csi.extend([i, q])
    return {"t": int(t * 1e6), "rssi": -45, "n": n, "csi": csi}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="127.0.0.1:5006")
    ap.add_argument("--rate", type=int, default=100, help="records per second")
    args = ap.parse_args()
    host, _, port = args.server.partition(":")
    port = int(port or 5006)

    print(f"[sim] connecting to {host}:{port} ...")
    sock = socket.create_connection((host, port))
    print("[sim] connected. Streaming fake CSI. Ctrl+C to stop.")
    print("[sim] cycle: ~8s empty -> 8s one person -> 8s two people -> repeat")

    # scenario levels and how long each lasts (seconds)
    scenario = [(0.0, 8, "EMPTY"), (0.5, 8, "ONE PERSON"), (1.1, 8, "TWO PEOPLE")]
    dt = 1.0 / args.rate
    t = 0.0
    try:
        while True:
            for level, dur, label in scenario:
                print(f"[sim] --> {label}")
                end = t + dur
                while t < end:
                    rec = make_record(level, t)
                    sock.sendall((json.dumps(rec) + "\n").encode())
                    t += dt
                    time.sleep(dt)
    except KeyboardInterrupt:
        print("\n[sim] stopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
