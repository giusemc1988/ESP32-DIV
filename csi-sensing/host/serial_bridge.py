#!/usr/bin/env python3
"""
serial_bridge.py - forward CSI JSON lines from the RX board to the server.

The csi_rx board prints one JSON object per line over USB serial. Docker
containers cannot easily read a host serial port, so this tiny bridge runs on
the host, reads the serial port, and forwards each line over TCP to the
sensing server's ingest port (default 5006, published by docker compose).

Usage:
    pip install pyserial
    python serial_bridge.py --port /dev/ttyACM0
    python serial_bridge.py --port COM5 --baud 921600 --server 127.0.0.1:5006

Tip: find the port with `ls /dev/ttyACM* /dev/ttyUSB*` (Linux/mac) or Device
Manager (Windows). The ESP32-C6 usually enumerates as ttyACM0 / COMx.
"""
import argparse
import socket
import sys
import time

try:
    import serial  # pyserial
except ImportError:
    sys.exit("pyserial not installed. Run: pip install pyserial")


def connect_server(host, port):
    while True:
        try:
            s = socket.create_connection((host, port), timeout=5)
            s.settimeout(None)
            print(f"[bridge] connected to server {host}:{port}")
            return s
        except OSError as e:
            print(f"[bridge] server {host}:{port} not ready ({e}); retry in 2s")
            time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="serial port, e.g. /dev/ttyACM0 or COM5")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--server", default="127.0.0.1:5006", help="host:port of server ingest")
    args = ap.parse_args()

    host, _, port = args.server.partition(":")
    port = int(port or 5006)

    ser = serial.Serial(args.port, args.baud, timeout=1)
    print(f"[bridge] reading {args.port} @ {args.baud}")
    sock = connect_server(host, port)

    lines = 0
    t0 = time.time()
    while True:
        try:
            raw = ser.readline()
        except serial.SerialException as e:
            print(f"[bridge] serial error: {e}; exiting")
            return
        if not raw:
            continue
        # Only forward lines that look like our JSON CSI records.
        if not raw.lstrip().startswith(b"{"):
            continue
        try:
            sock.sendall(raw if raw.endswith(b"\n") else raw + b"\n")
        except OSError as e:
            print(f"[bridge] server dropped ({e}); reconnecting")
            sock = connect_server(host, port)
            continue
        lines += 1
        if lines % 500 == 0:
            rate = lines / (time.time() - t0)
            print(f"[bridge] forwarded {lines} records ({rate:.0f}/s)")


if __name__ == "__main__":
    main()
