"""
╔══════════════════════════════════════════════════════════════════════╗
║  rPPG CRIMSON — Real-Time Cardiac Telemetry Interface                ║
║  ─────────────────────────────────────────────────────              ║
║  Model:  ME-flow  (arXiv 2025 · state-space · low-latency)          ║
║  Theme:  Crimson / Black  HUD  ·  Octagonal panels  ·  Scan lines   ║
║                                                                      ║
║  CONTROLS                                                            ║
║    q / ESC  quit               s  save snapshot + CSV               ║
║    p        pause / resume     r  reset buffer                       ║
║    g        toggle BVP plot    h  toggle HR history                  ║
║    f        toggle face box    m  cycle models                       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import csv
import os
import math
import time
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import rppg


# ═══════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════

MODEL_ZOO = [
    "ME-flow",
    "ME-chunk",
    "RhythmMamba",
    "PhysMamba",
    "FacePhys",
    "EfficientPhys",
    "PhysFormer",
    "TSCAN",
    "PhysNet",
]
DEFAULT_MODEL    = "ME-flow"
HR_UPDATE_PERIOD = 1.0
HR_WINDOW        = 10
BVP_WINDOW       = 8
HR_HIST_LEN      = 120

# ── CRIMSON / BLACK PALETTE (BGR) ────────────────────────────────────
BG          = ( 4,  4,  8)           # near-black canvas
PANEL       = (14, 10, 18)           # panel fill
PANEL_EDGE  = (40, 20, 55)           # panel border base
RED_HOT     = (20, 20, 220)          # vivid crimson  #DC1414
RED_DIM     = (16, 10, 140)          # muted crimson
CRIMSON     = (30, 12, 180)          # medium crimson
AMBER       = (18, 160, 255)         # amber warning
GREEN_ACQ   = (40, 200, 40)          # signal-ok green
BLUE_COLD   = (200, 80, 40)          # cold blue accent
TEXT_HI     = (230, 220, 240)        # bright text
TEXT_MID    = (160, 148, 168)        # mid text
TEXT_LOW    = ( 90,  80,  98)        # dim label
GRID_LINE   = (28, 16, 32)           # very dark grid


# ═══════════════════════════════════════════════════════════════════
#  LAYOUT  (1400 × 880)
# ═══════════════════════════════════════════════════════════════════

W, H = 1400, 880

# camera viewport (left column)
CAM_X, CAM_Y   = 16, 56
CAM_W, CAM_H   = 700, 525

# HR card (right column, top)
HR_X, HR_Y     = 736, 56
HR_W, HR_H     = 648, 280

# metric row
MET_Y          = 356
MET_H          = 130
MET_SNR_X      = 736
MET_HRV_X      = 986
MET_W          = 230

# status card
STAT_X, STAT_Y = 1228, 356
STAT_W, STAT_H = 156, 130

# BVP full-width bottom
BVP_X, BVP_Y   = 16,  600
BVP_W, BVP_H   = 700, 130

# HR history
HIST_X, HIST_Y = 736, 600
HIST_W, HIST_H = 648, 130

# header / footer heights
HDR_H = 50
FTR_H = 30


# ═══════════════════════════════════════════════════════════════════
#  DRAWING PRIMITIVES
# ═══════════════════════════════════════════════════════════════════

def _oct_pts(x, y, w, h, cut=12):
    """Return octagon polygon points for a rectangle with corner cuts."""
    return np.array([
        [x + cut,     y         ],
        [x + w - cut, y         ],
        [x + w,       y + cut   ],
        [x + w,       y + h - cut],
        [x + w - cut, y + h     ],
        [x + cut,     y + h     ],
        [x,           y + h - cut],
        [x,           y + cut   ],
    ], dtype=np.int32)


def oct_fill(img, x, y, w, h, color, cut=12, alpha=0.80):
    pts = _oct_pts(x, y, w, h, cut)
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)


def oct_stroke(img, x, y, w, h, color, thickness=1, cut=12):
    pts = _oct_pts(x, y, w, h, cut)
    cv2.polylines(img, [pts], True, color, thickness, cv2.LINE_AA)


def oct_card(img, x, y, w, h, title="", cut=10, fill_alpha=0.75):
    """Draw a filled octagonal card with a title bar stripe."""
    oct_fill(img, x, y, w, h, PANEL, cut=cut, alpha=fill_alpha)
    # crimson title bar stripe
    if title:
        bar_h = 24
        bar_pts = np.array([
            [x + cut,     y          ],
            [x + w - cut, y          ],
            [x + w,       y + cut    ],
            [x + w,       y + bar_h  ],
            [x,           y + bar_h  ],
            [x,           y + cut    ],
        ], dtype=np.int32)
        overlay = img.copy()
        cv2.fillPoly(overlay, [bar_pts], CRIMSON)
        cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)
        txt_x = x + cut + 8
        cv2.putText(img, title.upper(), (txt_x, y + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, TEXT_HI, 1, cv2.LINE_AA)
    oct_stroke(img, x, y, w, h, PANEL_EDGE, thickness=1, cut=cut)
    # bright corner accents
    _corner_ticks(img, x, y, w, h, RED_HOT, cut=cut)


def _corner_ticks(img, x, y, w, h, color, cut=10, length=14):
    """Draw short bright tick marks at each octagon corner."""
    lw = 2
    # top-left
    cv2.line(img, (x + cut, y), (x + cut + length, y), color, lw, cv2.LINE_AA)
    cv2.line(img, (x, y + cut), (x, y + cut + length), color, lw, cv2.LINE_AA)
    # top-right
    cv2.line(img, (x + w - cut, y), (x + w - cut - length, y), color, lw, cv2.LINE_AA)
    cv2.line(img, (x + w, y + cut), (x + w, y + cut + length), color, lw, cv2.LINE_AA)
    # bottom-left
    cv2.line(img, (x + cut, y + h), (x + cut + length, y + h), color, lw, cv2.LINE_AA)
    cv2.line(img, (x, y + h - cut), (x, y + h - cut - length), color, lw, cv2.LINE_AA)
    # bottom-right
    cv2.line(img, (x + w - cut, y + h), (x + w - cut - length, y + h), color, lw, cv2.LINE_AA)
    cv2.line(img, (x + w, y + h - cut), (x + w, y + h - cut - length), color, lw, cv2.LINE_AA)


def txt(img, text, ox, oy, scale=0.5, color=TEXT_HI, thick=1):
    cv2.putText(img, text, (ox, oy), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thick, cv2.LINE_AA)


def txt_mono(img, text, ox, oy, scale=0.55, color=TEXT_HI, thick=1):
    cv2.putText(img, text, (ox, oy), cv2.FONT_HERSHEY_PLAIN,
                scale, color, thick, cv2.LINE_AA)


def draw_grid(img, x, y, w, h, step=20):
    for xi in range(x, x + w, step):
        cv2.line(img, (xi, y), (xi, y + h), GRID_LINE, 1)
    for yi in range(y, y + h, step):
        cv2.line(img, (x, yi), (x + w, yi), GRID_LINE, 1)


def hr_color(hr):
    if hr is None:
        return TEXT_LOW
    if 50 <= hr <= 110:
        return RED_HOT
    if 40 <= hr < 50 or 110 < hr <= 140:
        return AMBER
    return BLUE_COLD


def blink(phase, period=1.2, duty=0.5):
    """Returns True during the 'on' phase of a blink cycle."""
    return (phase % period) < (period * duty)


# ═══════════════════════════════════════════════════════════════════
#  SCAN LINE
# ═══════════════════════════════════════════════════════════════════

def draw_scanline(img, phase, region_y=0, region_h=None):
    """Faint horizontal glow band that scrolls down the camera region."""
    rh = region_h or img.shape[0]
    pos = int((phase * 60) % rh) + region_y
    for offset, alpha in [(0, 0.18), (1, 0.10), (-1, 0.10)]:
        ry = pos + offset
        if 0 <= ry < img.shape[0]:
            row = img[ry].astype(np.float32)
            row[:, 2] = np.clip(row[:, 2] + 55, 0, 255)   # red channel boost
            img[ry] = row.astype(np.uint8)


# ═══════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════

def draw_header(img, model_name, fps, session_secs, frame_count):
    # dark bar
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (W, HDR_H), (8, 4, 12), -1)
    cv2.addWeighted(overlay, 0.92, img, 0.08, 0, img)
    cv2.line(img, (0, HDR_H - 1), (W, HDR_H - 1), RED_DIM, 1)

    # ● REC blinker
    now = time.time()
    rec_color = RED_HOT if blink(now) else RED_DIM
    cv2.circle(img, (22, 25), 6, rec_color, -1, cv2.LINE_AA)
    txt(img, "REC", 34, 30, 0.45, rec_color)

    txt(img, "CARDIAC TELEMETRY SYSTEM  //  rPPG CRIMSON",
        80, 30, 0.55, TEXT_HI, 1)

    # right side: model, fps, session timer, frame count
    elapsed = int(session_secs)
    hh, mm, ss = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
    timer_str  = f"{hh:02d}:{mm:02d}:{ss:02d}"
    info = (f"MDL:{model_name}   {fps:4.1f}fps   "
            f"T:{timer_str}   F:{frame_count:06d}")
    (tw, _), _ = cv2.getTextSize(info, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    txt(img, info, W - tw - 16, 30, 0.42, TEXT_MID)

    # bottom left: date
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    txt(img, ts, 80, 45, 0.38, TEXT_LOW)


# ═══════════════════════════════════════════════════════════════════
#  CAMERA VIEWPORT
# ═══════════════════════════════════════════════════════════════════

def draw_cam_viewport(img, cam_frame, phase):
    """Paste the camera frame, apply scan line, octagonal HUD frame."""
    if cam_frame is not None:
        resized = cv2.resize(cam_frame, (CAM_W, CAM_H))
        img[CAM_Y:CAM_Y + CAM_H, CAM_X:CAM_X + CAM_W] = resized
        draw_scanline(img, phase, region_y=CAM_Y, region_h=CAM_H)
    else:
        cv2.rectangle(img, (CAM_X, CAM_Y),
                      (CAM_X + CAM_W, CAM_Y + CAM_H), (12, 8, 16), -1)
        txt(img, "NO SIGNAL", CAM_X + CAM_W // 2 - 50,
            CAM_Y + CAM_H // 2, 0.8, RED_DIM, 2)

    # animated dashed border
    _animated_border(img, CAM_X, CAM_Y, CAM_W, CAM_H, phase)

    # corner labels
    txt(img, "CAM:00", CAM_X + 8, CAM_Y + CAM_H - 8, 0.38, TEXT_LOW)
    txt(img, f"RES:{CAM_W}x{CAM_H}", CAM_X + CAM_W - 95,
        CAM_Y + CAM_H - 8, 0.38, TEXT_LOW)


def _animated_border(img, x, y, w, h, phase, seg=18, gap=10):
    """Scrolling dashed border around a rectangle."""
    perimeter = 2 * (w + h)
    offset = int(phase * 40) % (seg + gap)
    color_a = RED_HOT
    color_b = RED_DIM

    def draw_dash_line(p1, p2, o):
        x1, y1 = p1; x2, y2 = p2
        length = int(math.hypot(x2 - x1, y2 - y1))
        if length == 0:
            return
        steps = length
        for i in range(0, steps, seg + gap):
            start = (i - o) % (seg + gap)
            if start >= seg:
                continue
            t0 = (i + start)      / steps
            t1 = min((i + start + seg) / steps, 1.0)
            pa = (int(x1 + t0 * (x2 - x1)), int(y1 + t0 * (y2 - y1)))
            pb = (int(x1 + t1 * (x2 - x1)), int(y1 + t1 * (y2 - y1)))
            cv2.line(img, pa, pb, color_a, 2, cv2.LINE_AA)

    draw_dash_line((x, y), (x + w, y), offset)
    draw_dash_line((x + w, y), (x + w, y + h), offset)
    draw_dash_line((x + w, y + h), (x, y + h), offset)
    draw_dash_line((x, y + h), (x, y), offset)
    _corner_ticks(img, x, y, w, h, RED_HOT, cut=0, length=20)


# ═══════════════════════════════════════════════════════════════════
#  FACE RETICLE
# ═══════════════════════════════════════════════════════════════════

def draw_reticle(img, box, hr, hr_fresh, phase):
    if box is None:
        msg = "[ NO FACE DETECTED — CENTER AND HOLD STILL ]"
        (mw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cx = CAM_X + (CAM_W - mw) // 2
        cy = CAM_Y + CAM_H // 2
        txt(img, msg, cx, cy, 0.5, RED_DIM)
        return

    (y1, y2), (x1, x2) = box
    color = hr_color(hr) if hr_fresh else AMBER

    # main box
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)

    # crosshair center
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    cv2.line(img, (cx - 12, cy), (cx + 12, cy), color, 1, cv2.LINE_AA)
    cv2.line(img, (cx, cy - 12), (cx, cy + 12), color, 1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 4, color, 1, cv2.LINE_AA)

    # pulsing outer ring  (radius oscillates with phase)
    pulse_r = int(6 + 3 * math.sin(phase * math.pi * 2))
    cv2.circle(img, (cx, cy), pulse_r, color, 1, cv2.LINE_AA)

    # corner brackets (inside face box)
    bl = 10
    for bx, by, dx, dy in [(x1, y1, 1, 1), (x2, y1, -1, 1),
                             (x1, y2, 1, -1), (x2, y2, -1, -1)]:
        cv2.line(img, (bx, by), (bx + dx * bl, by), color, 2, cv2.LINE_AA)
        cv2.line(img, (bx, by), (bx, by + dy * bl), color, 2, cv2.LINE_AA)

    # HR label above box
    label = f"HR {hr:.1f} BPM" if hr else "ACQUIRING…"
    (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    lx = x1
    cv2.rectangle(img, (lx, y1 - lh - 10), (lx + lw + 10, y1), color, -1)
    cv2.putText(img, label, (lx + 5, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


# ═══════════════════════════════════════════════════════════════════
#  HEART RATE CARD (right top)
# ═══════════════════════════════════════════════════════════════════

def draw_hr_card(img, hr, hrv, snr, hr_fresh, phase):
    oct_card(img, HR_X, HR_Y, HR_W, HR_H, title="CARDIAC RATE", cut=14)

    base_y = HR_Y + 30

    # big HR number
    hr_txt  = f"{hr:.1f}" if hr else "---"
    color   = hr_color(hr) if hr_fresh else TEXT_LOW
    scale   = 2.8
    (tw, th), _ = cv2.getTextSize(hr_txt, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)
    num_x = HR_X + (HR_W - tw) // 2
    cv2.putText(img, hr_txt, (num_x, base_y + 110),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 3, cv2.LINE_AA)

    txt(img, "BPM", HR_X + HR_W // 2 + tw // 2 + 8, base_y + 100,
        0.7, TEXT_LOW)

    # signal quality bar
    quality = min(1.0, max(0.0, (snr + 3) / 20.0)) if snr is not None else 0.0
    _quality_bar(img, HR_X + 30, base_y + 125, HR_W - 60, 10, quality, hr_fresh)

    # zone label
    zone, zone_col = _hr_zone(hr)
    txt(img, f"ZONE: {zone}", HR_X + 30, base_y + 158, 0.48, zone_col)

    # SNR / HRV inline
    snr_t = f"SNR {snr:+.1f}dB" if snr is not None else "SNR ---"
    hrv_t = f"HRV {hrv:.0f}ms"  if hrv else "HRV ---"
    txt(img, snr_t, HR_X + 30,            base_y + 180, 0.45, TEXT_MID)
    txt(img, hrv_t, HR_X + HR_W - 130,    base_y + 180, 0.45, TEXT_MID)

    # pulsing heart icon (right side of card)
    hx = HR_X + HR_W - 70
    hy = base_y + 80
    _draw_heart(img, hx, hy, color, phase if hr_fresh else None)


def _quality_bar(img, x, y, w, h, quality, active):
    # background track
    cv2.rectangle(img, (x, y), (x + w, y + h), (30, 15, 35), -1)
    if quality > 0:
        fill_w = int(w * quality)
        col = RED_HOT if active else RED_DIM
        cv2.rectangle(img, (x, y), (x + fill_w, y + h), col, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), RED_DIM, 1)
    txt(img, f"SIG {int(quality * 100):3d}%", x + w + 6, y + h, 0.38, TEXT_LOW)


def _hr_zone(hr):
    if hr is None:
        return "UNKNOWN", TEXT_LOW
    if hr < 50:
        return "BRADYCARDIA", BLUE_COLD
    if hr <= 60:
        return "RESTING-LOW", TEXT_MID
    if hr <= 100:
        return "NORMAL", GREEN_ACQ
    if hr <= 140:
        return "ELEVATED", AMBER
    return "TACHYCARDIA", RED_HOT


def _draw_heart(img, cx, cy, color, phase=None, size=28):
    """Draw a simple heart using two arcs + a V."""
    r = size // 3
    # two circle tops
    cv2.circle(img, (cx - r, cy - r // 2), r, color, 2, cv2.LINE_AA)
    cv2.circle(img, (cx + r, cy - r // 2), r, color, 2, cv2.LINE_AA)
    # V bottom
    pts = np.array([[cx - size, cy - r // 2],
                    [cx, cy + size],
                    [cx + size, cy - r // 2]], dtype=np.int32)
    cv2.polylines(img, [pts], False, color, 2, cv2.LINE_AA)

    if phase is not None:
        pulse = 0.7 + 0.3 * abs(math.sin(phase * math.pi * 1.2))
        outer = int(size * pulse * 1.4)
        cv2.circle(img, (cx, cy), outer, (*color[:2], max(0, color[2] - 80)), 1, cv2.LINE_AA)


# ═══════════════════════════════════════════════════════════════════
#  METRIC CARDS  (SNR bar, HRV)
# ═══════════════════════════════════════════════════════════════════

def draw_metric_card(img, x, y, w, h, title, value_str, unit, sub="", color=TEXT_HI):
    oct_card(img, x, y, w, h, title=title, cut=8)
    base_y = y + 28
    cv2.putText(img, value_str, (x + 18, base_y + 64),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, color, 2, cv2.LINE_AA)
    txt(img, unit, x + 18, base_y + 84, 0.38, TEXT_LOW)
    if sub:
        txt(img, sub, x + 18, base_y + 100, 0.38, TEXT_MID)


def draw_snr_card(img, snr):
    val = f"{snr:+.1f}" if snr is not None else "---"
    col = RED_HOT if snr and snr > 5 else AMBER if snr and snr > 0 else RED_DIM
    draw_metric_card(img, MET_SNR_X, MET_Y, MET_W, MET_H,
                     "SIGNAL·NOISE", val, "dB", "Signal quality index", col)

    # horizontal SNR gauge
    if snr is not None:
        gx, gy = MET_SNR_X + 16, MET_Y + MET_H - 22
        gw = MET_W - 32
        nrm = min(1.0, max(0.0, (snr + 5) / 25.0))
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + 8), (30, 14, 35), -1)
        cv2.rectangle(img, (gx, gy), (gx + int(gw * nrm), gy + 8), col, -1)
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + 8), RED_DIM, 1)


def draw_hrv_card(img, hrv):
    val = f"{hrv:.0f}" if hrv else "---"
    col = GREEN_ACQ if hrv and 20 <= hrv <= 80 else AMBER
    draw_metric_card(img, MET_HRV_X, MET_Y, MET_W, MET_H,
                     "HEART·RATE·VAR", val, "ms RMSSD",
                     "Autonomic indicator", col)


def draw_status_card(img, face_ok, sig_ok, paused, phase):
    oct_card(img, STAT_X, STAT_Y, STAT_W, STAT_H, title="STATUS", cut=8)
    base_y = STAT_Y + 32

    def led(bx, by, on, label, blink_it=False):
        on_now = on and (not blink_it or blink(phase))
        col = RED_HOT if on_now else (RED_DIM if on else (24, 12, 28))
        cv2.circle(img, (bx, by), 5, col, -1, cv2.LINE_AA)
        txt(img, label, bx + 12, by + 4, 0.38, TEXT_MID if on else TEXT_LOW)

    led(STAT_X + 18, base_y + 0,  face_ok,  "FACE", blink_it=not face_ok)
    led(STAT_X + 18, base_y + 22, sig_ok,   "SIGNAL")
    led(STAT_X + 18, base_y + 44, not paused, "LIVE", blink_it=True)
    led(STAT_X + 18, base_y + 66, paused,   "PAUSED")

    txt(img, "SYS:OK" if face_ok and sig_ok else "SYS:WAIT",
        STAT_X + 14, base_y + 96,
        0.4, GREEN_ACQ if face_ok and sig_ok else AMBER)


# ═══════════════════════════════════════════════════════════════════
#  BVP WAVEFORM
# ═══════════════════════════════════════════════════════════════════

def draw_bvp_panel(img, signal):
    oct_card(img, BVP_X, BVP_Y, BVP_W, BVP_H, title="BLOOD·VOLUME·PULSE", cut=8)
    inner_x, inner_y = BVP_X + 14, BVP_Y + 28
    inner_w, inner_h = BVP_W - 28, BVP_H - 40

    draw_grid(img, inner_x, inner_y, inner_w, inner_h, step=25)

    if signal is None or len(signal) < 4:
        txt(img, "WAITING FOR SIGNAL…", inner_x + 20, inner_y + inner_h // 2,
            0.5, RED_DIM)
        return

    s = np.asarray(signal, dtype=np.float32)
    s -= s.mean()
    rng = float(np.max(np.abs(s))) or 1.0
    s /= rng

    n = len(s)
    xs = np.linspace(inner_x, inner_x + inner_w, n).astype(np.int32)
    ys = (inner_y + inner_h / 2 - s * (inner_h / 2 - 8)).astype(np.int32)

    # glow: draw multiple passes with decreasing opacity
    for thick, alpha_mul in [(4, 0.15), (2, 0.4), (1, 1.0)]:
        color = RED_HOT if thick == 1 else RED_DIM
        if thick > 1:
            overlay = img.copy()
            cv2.polylines(overlay, [np.stack([xs, ys], axis=1)],
                          False, color, thick, cv2.LINE_AA)
            cv2.addWeighted(overlay, alpha_mul, img, 1 - alpha_mul, 0, img)
        else:
            cv2.polylines(img, [np.stack([xs, ys], axis=1)],
                          False, color, thick, cv2.LINE_AA)

    # axis labels
    txt(img, "+1", BVP_X + BVP_W - 26, inner_y + 10, 0.35, TEXT_LOW)
    txt(img, " 0", BVP_X + BVP_W - 26, inner_y + inner_h // 2, 0.35, TEXT_LOW)
    txt(img, "-1", BVP_X + BVP_W - 26, inner_y + inner_h - 4, 0.35, TEXT_LOW)
    txt(img, f"{BVP_WINDOW}s", inner_x, inner_y + inner_h + 12, 0.35, TEXT_LOW)
    txt(img, "0s", inner_x + inner_w - 12, inner_y + inner_h + 12, 0.35, TEXT_LOW)


# ═══════════════════════════════════════════════════════════════════
#  HR HISTORY
# ═══════════════════════════════════════════════════════════════════

def draw_history_panel(img, history):
    oct_card(img, HIST_X, HIST_Y, HIST_W, HIST_H, title="CARDIAC·RATE·HISTORY", cut=8)
    inner_x, inner_y = HIST_X + 14, HIST_Y + 28
    inner_w, inner_h = HIST_W - 28, HIST_H - 40

    draw_grid(img, inner_x, inner_y, inner_w, inner_h, step=25)

    if len(history) < 2:
        txt(img, "ACCUMULATING…", inner_x + 20, inner_y + inner_h // 2,
            0.5, RED_DIM)
        return

    hr = np.asarray(history, dtype=np.float32)
    lo = max(40.0,  float(hr.min()) - 5.0)
    hi = min(180.0, float(hr.max()) + 5.0)
    span = max(hi - lo, 1.0)

    n = len(hr)
    xs = np.linspace(inner_x, inner_x + inner_w, n).astype(np.int32)
    ys = (inner_y + inner_h - (hr - lo) / span * (inner_h - 16) - 4).astype(np.int32)

    col = hr_color(hr[-1])
    # glow pass
    overlay = img.copy()
    cv2.polylines(overlay, [np.stack([xs, ys], axis=1)], False, col, 3, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
    cv2.polylines(img, [np.stack([xs, ys], axis=1)], False, col, 1, cv2.LINE_AA)

    txt(img, f"{hi:.0f}", inner_x + inner_w + 4, inner_y + 10, 0.35, TEXT_LOW)
    txt(img, f"{lo:.0f}", inner_x + inner_w + 4, inner_y + inner_h - 4, 0.35, TEXT_LOW)
    txt(img, f"LAST:{hr[-1]:.1f}bpm", inner_x + 4, inner_y + inner_h + 12,
        0.38, col)


# ═══════════════════════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════════════════════

def draw_footer(img, paused, last_error):
    y = H - FTR_H
    cv2.line(img, (0, y), (W, y), RED_DIM, 1)
    overlay = img.copy()
    cv2.rectangle(overlay, (0, y), (W, H), (8, 4, 12), -1)
    cv2.addWeighted(overlay, 0.88, img, 0.12, 0, img)

    status = "  ■ PAUSED  " if paused else "  ▶ LIVE  "
    s_col  = AMBER if paused else RED_HOT
    txt(img, status, 8, H - 8, 0.42, s_col)

    keys = ("q quit  ·  s save  ·  p pause  ·  r reset  ·  "
            "g waveform  ·  h history  ·  f face  ·  m model")
    txt(img, keys, 110, H - 8, 0.38, TEXT_LOW)

    if last_error:
        err = f"ERR: {last_error[:100]}"
        txt(img, err, W - 620, H - 8, 0.36, RED_DIM)


# ═══════════════════════════════════════════════════════════════════
#  MONITOR CLASS
# ═══════════════════════════════════════════════════════════════════

class RPPGMonitor:
    def __init__(self,
                 model_name: str = DEFAULT_MODEL,
                 camera: int = 0,
                 log_dir: str = "rppg_logs"):
        self.model_name = model_name
        self.model      = self._load_model(model_name)
        self.camera     = camera
        self.log_dir    = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.hr_history     = deque(maxlen=HR_HIST_LEN)
        self.last_hr_time   = 0.0
        self.last_hr_update = None
        self.last_face_seen = None
        self.last_error     = None
        self.current_hr     = None
        self.current_hrv    = None
        self.current_snr    = None
        self.frame_count    = 0
        self.start_time     = time.time()

        self.show_bvp  = True
        self.show_hist = True
        self.show_box  = True
        self.paused    = False

    @staticmethod
    def _load_model(name):
        print(f"[rPPG] loading '{name}'…")
        try:
            return rppg.Model(name)
        except Exception as exc:
            print(f"[rPPG] '{name}' unavailable ({exc}); using default.")
            return rppg.Model()

    def cycle_model(self):
        idx = (MODEL_ZOO.index(self.model_name) + 1) % len(MODEL_ZOO) \
            if self.model_name in MODEL_ZOO else 0
        self.model_name = MODEL_ZOO[idx]
        self.model = self._load_model(self.model_name)
        self.reset(quiet=True)

    @staticmethod
    def _to_float(v, prefer=("value", "rmssd", "sdnn", "mean", "median",
                              "db", "snr", "hr")):
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            for k in prefer:
                if k in v:
                    out = RPPGMonitor._to_float(v[k])
                    if out is not None:
                        return out
            for sub in v.values():
                out = RPPGMonitor._to_float(sub)
                if out is not None:
                    return out
            return None
        if isinstance(v, (list, tuple)) and v:
            return RPPGMonitor._to_float(v[-1])
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def update_metrics(self):
        try:
            res = self.model.hr(start=-HR_WINDOW)
        except Exception as exc:
            self.last_error = f"hr(): {exc!r}"
            return
        if not res:
            return
        hr = self._to_float(res.get("hr"))
        if hr and hr > 0:
            self.current_hr = hr
            self.hr_history.append(hr)
            self.last_hr_update = time.time()
        hrv = self._to_float(res.get("hrv") or res.get("rmssd"))
        if hrv:
            self.current_hrv = hrv
        snr = self._to_float(res.get("snr") or res.get("snr_db"))
        if snr is not None:
            self.current_snr = snr

    def bvp_window(self, seconds=BVP_WINDOW):
        try:
            bvp, _ = self.model.bvp(start=-seconds)
            return bvp
        except Exception:
            return None

    def save_session(self, frame):
        ts  = datetime.now().strftime("%Y%m%d-%H%M%S")
        png = self.log_dir / f"snapshot-{ts}.png"
        csv_path = self.log_dir / f"session-{ts}.csv"
        cv2.imwrite(str(png), frame)
        try:
            bvp, t = self.model.bvp()
            with open(csv_path, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["t_seconds", "bvp"])
                for ti, bi in zip(t, bvp):
                    w.writerow([f"{ti:.4f}", f"{bi:.6f}"])
            print(f"[rPPG] saved → {png}  |  {csv_path}")
        except Exception as exc:
            print(f"[rPPG] CSV failed ({exc}); image → {png}")

    def reset(self, quiet=False):
        try:
            self.model.reset()
        except Exception:
            pass
        self.hr_history.clear()
        self.current_hr = self.current_hrv = self.current_snr = None
        self.frame_count = 0
        self.start_time = time.time()
        if not quiet:
            print("[rPPG] buffer reset.")

    # ── render ─────────────────────────────────────────────────────
    def render(self, cam_frame, box):
        canvas = np.full((H, W, 3), BG, dtype=np.uint8)

        now      = time.time()
        phase    = (now % 100.0)          # general animation phase (seconds)
        blink_ph = now                    # fast blink phase

        face_ok  = self.last_face_seen and (now - self.last_face_seen) < 1.5
        hr_fresh = (self.last_hr_update and
                    (now - self.last_hr_update) < HR_UPDATE_PERIOD * 3)

        if box is not None:
            self.last_face_seen = now

        elapsed = now - self.start_time

        # ── background subtle grid across full canvas ──────────────
        draw_grid(canvas, 0, HDR_H, W, H - HDR_H - FTR_H, step=40)

        # ── header ─────────────────────────────────────────────────
        draw_header(canvas, self.model_name,
                    self.frame_count / max(elapsed, 1),
                    elapsed, self.frame_count)

        # ── camera viewport ────────────────────────────────────────
        draw_cam_viewport(canvas, cam_frame, phase)

        # ── face reticle ───────────────────────────────────────────
        if self.show_box:
            try:
                draw_reticle(canvas, box, self.current_hr, hr_fresh, phase)
            except Exception as exc:
                self.last_error = f"reticle: {exc!r}"

        # ── HR card ────────────────────────────────────────────────
        draw_hr_card(canvas, self.current_hr, self.current_hrv,
                     self.current_snr, hr_fresh, phase)

        # ── metric cards ───────────────────────────────────────────
        draw_snr_card(canvas, self.current_snr)
        draw_hrv_card(canvas, self.current_hrv)
        draw_status_card(canvas, face_ok, hr_fresh, self.paused, blink_ph)

        # ── BVP ────────────────────────────────────────────────────
        if self.show_bvp:
            try:
                draw_bvp_panel(canvas, self.bvp_window())
            except Exception as exc:
                self.last_error = f"bvp: {exc!r}"

        # ── HR history ─────────────────────────────────────────────
        if self.show_hist:
            try:
                draw_history_panel(canvas, list(self.hr_history))
            except Exception as exc:
                self.last_error = f"history: {exc!r}"

        # ── footer ─────────────────────────────────────────────────
        draw_footer(canvas, self.paused, self.last_error)

        return canvas

    # ── main loop ──────────────────────────────────────────────────
    def run(self):
        win = "rPPG CRIMSON"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, W, H)
        last_good_frame = None
        exit_reason = "user quit"

        try:
            with self.model.video_capture(self.camera):
                preview_iter = iter(self.model.preview)

                while True:
                    try:
                        frame, box = next(preview_iter)
                    except StopIteration:
                        exit_reason = "stream ended"
                        break
                    except Exception as exc:
                        traceback.print_exc()
                        exit_reason = f"preview error: {exc!r}"
                        break

                    if frame is None:
                        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                            break
                        continue

                    try:
                        cam_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    except cv2.error:
                        continue

                    self.frame_count += 1
                    last_good_frame = cam_bgr

                    if not self.paused:
                        now = time.time()
                        if now - self.last_hr_time > HR_UPDATE_PERIOD:
                            try:
                                self.update_metrics()
                            except Exception as exc:
                                self.last_error = str(exc)
                            self.last_hr_time = now
                            if self.current_hr:
                                snr_s = (f"  SNR {self.current_snr:+.1f}dB"
                                         if self.current_snr is not None else "")
                                print(f"[rPPG] HR {self.current_hr:6.1f} BPM{snr_s}")

                    try:
                        canvas = self.render(cam_bgr, box)
                    except Exception as exc:
                        print(f"[rPPG] render error: {exc}")
                        canvas = np.zeros((H, W, 3), dtype=np.uint8)

                    cv2.imshow(win, canvas)

                    try:
                        if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                            exit_reason = "window closed"
                            break
                    except cv2.error:
                        exit_reason = "window destroyed"
                        break

                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break
                    elif key == ord("s") and last_good_frame is not None:
                        self.save_session(last_good_frame)
                    elif key == ord("r"):
                        self.reset()
                    elif key == ord("p"):
                        self.paused = not self.paused
                        print(f"[rPPG] {'paused' if self.paused else 'resumed'}.")
                    elif key == ord("g"):
                        self.show_bvp = not self.show_bvp
                    elif key == ord("h"):
                        self.show_hist = not self.show_hist
                    elif key == ord("f"):
                        self.show_box = not self.show_box
                    elif key == ord("m"):
                        try:
                            self.cycle_model()
                        except Exception as exc:
                            self.last_error = f"model switch: {exc!r}"

        except KeyboardInterrupt:
            exit_reason = "Ctrl+C"
        except Exception as exc:
            traceback.print_exc()
            exit_reason = f"fatal: {exc!r}"
        finally:
            cv2.destroyAllWindows()
            print(f"[rPPG] exit — {exit_reason}.")


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description="rPPG CRIMSON — cardiac telemetry HUD.")
    p.add_argument("--model",   default=DEFAULT_MODEL,
                   help=f"model name (default {DEFAULT_MODEL}). "
                        f"Options: {', '.join(MODEL_ZOO)}.")
    p.add_argument("--camera",  type=int, default=0,
                   help="camera index (default 0)")
    p.add_argument("--log-dir", default="rppg_logs",
                   help="directory for snapshots and CSVs")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    RPPGMonitor(model_name=args.model,
                camera=args.camera,
                log_dir=args.log_dir).run()