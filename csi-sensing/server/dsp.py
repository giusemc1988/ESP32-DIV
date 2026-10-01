"""
dsp.py - Wi-Fi CSI signal processing for human sensing.

Design goals (and honest limits) for a TWO-node setup (1 TX + 1 RX):
  * Presence / motion  -> reliable. A person moving changes CSI amplitude.
  * Breathing rate      -> works when the subject is fairly still and close.
  * "Zones"             -> COARSE only. With a single TX->RX link we cannot
                           triangulate (x,y). We expose a near/far motion split
                           derived from subcarrier groups; treat it as a hint,
                           not a floor-plan coordinate.
  * People count        -> an ESTIMATE bucketed from motion energy, with a
                           runtime-tunable threshold. One link CANNOT cleanly
                           separate N people; 3+ receivers are required for that.

Pipeline per CSI record:
  raw int8 I/Q  ->  amplitude per subcarrier  ->  drop pilot/null carriers
  ->  Hampel outlier clean  ->  running baseline (static removal)
  ->  motion energy, presence, breathing FFT, coarse zones, count estimate.

Everything that affects results is a field in Config so the UI can tune it live.
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from threading import Lock

import numpy as np


@dataclass
class Config:
    # --- calibration ---
    baseline_alpha: float = 0.01      # EMA rate for the static channel baseline
    # --- presence / motion ---
    presence_on: float = 0.35         # motion energy to declare presence
    presence_off: float = 0.20        # lower threshold (hysteresis) to clear
    motion_gain: float = 1.0          # scales normalized motion energy
    # --- people count (ESTIMATE, single-link) ---
    count_thresholds: list = field(default_factory=lambda: [0.20, 0.60, 1.20])
    #   energy < t0        -> 0 people
    #   t0 <= energy < t1  -> 1
    #   t1 <= energy < t2  -> 2
    #   energy >= t2       -> 3+   (cannot resolve further on one link)
    dedup_smoothing: float = 0.30     # EMA on the count to stop it flickering
    # --- breathing ---
    breath_window_s: float = 20.0     # analysis window length
    breath_min_hz: float = 0.15       # 9  BPM
    breath_max_hz: float = 0.60       # 36 BPM


def _amplitude(csi: list[int]) -> np.ndarray:
    """int8 I/Q interleaved -> amplitude per subcarrier."""
    a = np.asarray(csi, dtype=np.float32)
    if a.size < 2:
        return np.zeros(0, dtype=np.float32)
    i = a[0::2]
    q = a[1::2]
    n = min(i.size, q.size)
    return np.sqrt(i[:n] * i[:n] + q[:n] * q[:n])


def _hampel(x: np.ndarray, k: int = 2, nsig: float = 3.0) -> np.ndarray:
    """Cheap Hampel filter: replace subcarrier outliers with the local median.
    Removes the sparse spikes ESP32 CSI is notorious for."""
    if x.size < 2 * k + 1:
        return x
    out = x.copy()
    for idx in range(x.size):
        lo = max(0, idx - k)
        hi = min(x.size, idx + k + 1)
        window = x[lo:hi]
        med = np.median(window)
        mad = np.median(np.abs(window - med)) + 1e-6
        if abs(x[idx] - med) > nsig * 1.4826 * mad:
            out[idx] = med
    return out


class CSIProcessor:
    """Stateful processor. Feed CSI records; read the latest state."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self._lock = Lock()

        self.baseline: np.ndarray | None = None    # per-subcarrier static level
        self.n_sub = 0

        # rolling history for motion + breathing (timestamp, mean_amp, energy)
        self._amp_hist: deque = deque(maxlen=4000)   # (t, mean_amplitude)
        self._energy_ema = 0.0
        self._count_ema = 0.0
        self._present = False
        self._last_rate_t = time.time()
        self._rate_count = 0
        self._rate = 0.0

        self.state = {
            "present": False,
            "motion": 0.0,        # 0..~2 normalized motion energy
            "count": 0,           # estimated people (bucketed, see Config)
            "breathing_bpm": 0.0, # 0 when not confidently measurable
            "zones": [0.0, 0.0, 0.0],  # coarse near/mid/far motion hint
            "spectrum": [],       # per-subcarrier normalized variation (for waterfall)
            "rssi": 0,
            "rate_hz": 0.0,       # actual CSI sample rate reaching the server
            "subcarriers": 0,
            "ts": time.time(),
            "calibrating": True,
        }

    # ---- runtime tuning ----
    def update_config(self, patch: dict) -> dict:
        with self._lock:
            for k, v in patch.items():
                if hasattr(self.cfg, k):
                    cur = getattr(self.cfg, k)
                    if isinstance(cur, list) and isinstance(v, list):
                        setattr(self.cfg, k, [float(x) for x in v])
                    else:
                        setattr(self.cfg, k, type(cur)(v))
            return asdict(self.cfg)

    def config_dict(self) -> dict:
        with self._lock:
            return asdict(self.cfg)

    def recalibrate(self):
        """Forget the static baseline - call with the room EMPTY."""
        with self._lock:
            self.baseline = None
            self.state["calibrating"] = True

    # ---- ingest ----
    def push(self, rec: dict):
        csi = rec.get("csi")
        if not csi:
            return
        amp = _amplitude(csi)
        if amp.size == 0:
            return
        amp = _hampel(amp)

        with self._lock:
            cfg = self.cfg
            now = time.time()

            # sample-rate meter
            self._rate_count += 1
            if now - self._last_rate_t >= 1.0:
                self._rate = self._rate_count / (now - self._last_rate_t)
                self._rate_count = 0
                self._last_rate_t = now

            # (re)initialise baseline
            if self.baseline is None or self.baseline.size != amp.size:
                self.baseline = amp.copy()
                self.n_sub = amp.size
                self.state["calibrating"] = True
                return

            # Static removal: how far is the live channel from its resting state?
            delta = amp - self.baseline
            # normalize by baseline magnitude so RSSI/distance don't dominate
            norm = np.abs(delta) / (self.baseline + 1e-3)
            energy = float(np.mean(norm)) * cfg.motion_gain

            # Slowly track the static baseline ONLY when the room looks quiet,
            # so a person standing still doesn't get absorbed into "empty".
            if energy < cfg.presence_off:
                self.baseline += cfg.baseline_alpha * delta
                self.state["calibrating"] = False

            # motion energy EMA (smooth)
            self._energy_ema = 0.6 * self._energy_ema + 0.4 * energy

            # presence with hysteresis
            if self._energy_ema >= cfg.presence_on:
                self._present = True
            elif self._energy_ema <= cfg.presence_off:
                self._present = False

            # coarse zones: split subcarriers into 3 groups. Different carriers
            # are affected differently by reflectors at different ranges, so the
            # group with the most variation is a WEAK near/far hint only.
            g = np.array_split(norm, 3)
            zones = [float(np.mean(x)) for x in g]

            # people-count estimate (bucketed motion energy + smoothing)
            t = cfg.count_thresholds
            raw_count = 0
            e = self._energy_ema
            if e >= t[0]:
                raw_count = 1 + int(e >= t[1]) + int(e >= t[2])
            self._count_ema = ((1 - cfg.dedup_smoothing) * self._count_ema
                               + cfg.dedup_smoothing * raw_count)
            count = int(round(self._count_ema)) if self._present else 0

            # history for breathing (use mean amplitude of a stable sub-band)
            self._amp_hist.append((now, float(np.mean(amp))))
            bpm = self._breathing(now)

            self.state.update({
                "present": self._present,
                "motion": round(self._energy_ema, 4),
                "count": count,
                "breathing_bpm": round(bpm, 1),
                "zones": [round(z, 4) for z in zones],
                "spectrum": [round(float(x), 3) for x in norm],
                "rssi": int(rec.get("rssi", 0)),
                "rate_hz": round(self._rate, 1),
                "subcarriers": int(amp.size),
                "ts": now,
                "calibrating": self.state["calibrating"],
            })

    def _breathing(self, now: float) -> float:
        """Estimate breathing rate via FFT of the amplitude time series."""
        cfg = self.cfg
        win = [(t, v) for (t, v) in self._amp_hist if now - t <= cfg.breath_window_s]
        if len(win) < 64:
            return 0.0
        ts = np.array([t for t, _ in win])
        vs = np.array([v for _, v in win], dtype=np.float64)
        dur = ts[-1] - ts[0]
        if dur < cfg.breath_window_s * 0.5:
            return 0.0
        fs = len(win) / dur
        if fs < 2 * cfg.breath_max_hz:      # Nyquist guard
            return 0.0

        # resample to uniform grid, detrend, window
        grid = np.linspace(ts[0], ts[-1], len(win))
        v = np.interp(grid, ts, vs)
        v = v - np.mean(v)
        v *= np.hanning(len(v))

        spec = np.abs(np.fft.rfft(v))
        freqs = np.fft.rfftfreq(len(v), d=1.0 / fs)
        band = (freqs >= cfg.breath_min_hz) & (freqs <= cfg.breath_max_hz)
        if not np.any(band):
            return 0.0
        bspec = spec[band]
        bfreqs = freqs[band]
        peak = int(np.argmax(bspec))
        # confidence: peak must stand out from the band's mean energy
        if bspec[peak] < 3.0 * (np.mean(bspec) + 1e-9):
            return 0.0
        return float(bfreqs[peak] * 60.0)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)
