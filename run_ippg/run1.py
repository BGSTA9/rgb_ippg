import time
import logging
from collections import deque
from dataclasses import dataclass
import cv2
import rppg

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ippg_monitor")


# ─── Configuration ────────────────────────────────────────────────────────────
@dataclass
class Config:
    camera_index: int = 0
    hr_poll_interval: float = 1.0          # seconds between HR requests
    hr_history_window: int = 10            # samples kept for rolling average
    hr_lookback_seconds: int = -10         # rPPG model lookback
    window_title: str = "iPPG Monitor"
    quit_key: str = "q"

    # HR zone thresholds (BPM)
    zone_resting_max: float = 60.0
    zone_normal_max: float = 100.0
    zone_elevated_max: float = 140.0

    # Overlay geometry
    overlay_x: int = 10
    overlay_y: int = 10
    bar_width: int = 160
    bar_height: int = 6

    # Font
    font: int = cv2.FONT_HERSHEY_SIMPLEX

    # Color Constants (Cached to prevent tuple re-allocation every frame)
    COLOR_RESTING: tuple[int, int, int] = (180, 180, 180)   # gray
    COLOR_NORMAL: tuple[int, int, int] = (80, 200, 80)      # green
    COLOR_ELEVATED: tuple[int, int, int] = (0, 165, 255)    # orange
    COLOR_HIGH: tuple[int, int, int] = (60, 60, 220)        # red
    COLOR_BG: tuple[int, int, int] = (20, 20, 20)           # dark grey
    COLOR_TEXT_DIM: tuple[int, int, int] = (130, 130, 130)  # dim text


CFG = Config()


# ─── HR Zone Helper ───────────────────────────────────────────────────────────
def hr_zone(bpm: float) -> tuple[str, tuple[int, int, int]]:
    """Return (label, BGR color) for a given BPM reading."""
    if bpm < CFG.zone_resting_max:
        return "Resting", CFG.COLOR_RESTING
    if bpm < CFG.zone_normal_max:
        return "Normal", CFG.COLOR_NORMAL
    if bpm < CFG.zone_elevated_max:
        return "Elevated", CFG.COLOR_ELEVATED
    return "High", CFG.COLOR_HIGH


# ─── Overlay Renderer ─────────────────────────────────────────────────────────
def draw_overlay(
    frame,
    hr_smooth: float | None,
    hr_raw: float | None,
    hr_history: deque,
    fps: float,
    box,
    face_detected: bool,
) -> None:
    h, w = frame.shape[:2]

    # ── Face bounding box + raw BPM label ──
    if box is not None and face_detected:
        y1, y2 = box[0]
        x1, x2 = box[1]
        color = hr_zone(hr_smooth)[1] if hr_smooth else CFG.COLOR_NORMAL
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        if hr_smooth is not None:
            label = f"{hr_smooth:.1f} BPM"
            (lw, lh), _ = cv2.getTextSize(label, CFG.font, 0.65, 2)
            # Background pill
            cv2.rectangle(frame, (x1 - 1, y1 - lh - 14), (x1 + lw + 6, y1 - 2), CFG.COLOR_BG, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 6), CFG.font, 0.65, color, 2)

    # ── Top-left info panel (Optimized ROI Blending) ──
    ox, oy = CFG.overlay_x, CFG.overlay_y
    panel_w, panel_h = 220, 130
    
    # Safely calculate bounds to prevent crashes if window is too small
    px1, py1 = max(0, ox - 4), max(0, oy - 4)
    px2, py2 = min(w, ox + panel_w), min(h, oy + panel_h)
    
    if px2 > px1 and py2 > py1:
        roi = frame[py1:py2, px1:px2]
        overlay_roi = roi.copy()
        cv2.rectangle(overlay_roi, (0, 0), (px2 - px1, py2 - py1), CFG.COLOR_BG, -1)
        cv2.addWeighted(overlay_roi, 0.55, roi, 0.45, 0, roi)

    # Status dot
    dot_color = CFG.COLOR_NORMAL if face_detected else CFG.COLOR_HIGH
    cv2.circle(frame, (ox + 8, oy + 10), 5, dot_color, -1)
    status_text = "Face detected" if face_detected else "Searching…"
    cv2.putText(frame, status_text, (ox + 20, oy + 15), CFG.font, 0.45, (200, 200, 200), 1)

    # Large BPM readout
    if hr_smooth is not None:
        zone_label, zone_color = hr_zone(hr_smooth)
        bpm_str = f"{hr_smooth:.0f}"
        cv2.putText(frame, bpm_str, (ox + 2, oy + 60), CFG.font, 1.8, zone_color, 3)
        cv2.putText(frame, "BPM", (ox + 90, oy + 60), CFG.font, 0.55, CFG.COLOR_RESTING, 1)

        # Zone badge
        cv2.putText(frame, zone_label, (ox + 2, oy + 80), CFG.font, 0.5, zone_color, 1)

        # Raw vs smoothed diff hint
        if hr_raw is not None and abs(hr_raw - hr_smooth) > 2:
            cv2.putText(frame, f"raw {hr_raw:.0f}", (ox + 80, oy + 80), CFG.font, 0.38, CFG.COLOR_TEXT_DIM, 1)
    else:
        cv2.putText(frame, "-- BPM", (ox + 2, oy + 60), CFG.font, 1.2, CFG.COLOR_TEXT_DIM, 2)

    # Mini history bar chart
    if len(hr_history) > 1:
        bar_y_base = oy + 105
        hr_min = min(hr_history)
        hr_max = max(hr_history)
        hr_range = max(hr_max - hr_min, 10)
        slot_w = CFG.bar_width // max(len(hr_history), 1)
        
        for i, val in enumerate(hr_history):
            bar_h_px = int(CFG.bar_height * (val - hr_min) / hr_range) + 2
            bx = ox + i * slot_w
            _, bc = hr_zone(val)
            cv2.rectangle(frame, (bx, bar_y_base - bar_h_px), (bx + max(slot_w - 2, 1), bar_y_base), bc, -1)

    # FPS — bottom-right corner
    fps_str = f"FPS {fps:.0f}"
    (fw, _), _ = cv2.getTextSize(fps_str, CFG.font, 0.4, 1)
    cv2.putText(frame, fps_str, (w - fw - 8, h - 8), CFG.font, 0.4, (120, 120, 120), 1)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    model = rppg.Model()
    hr_history: deque[float] = deque(maxlen=CFG.hr_history_window)
    last_poll_time: float = 0.0
    hr_raw: float | None = None
    hr_smooth: float | None = None

    fps_times: deque[float] = deque(maxlen=30)

    log.info("Starting iPPG monitor — press '%s' to quit.", CFG.quit_key)

    try:
        with model.video_capture(CFG.camera_index):
            for frame, box in model.preview:
                # ── Convert colour space ──────────────────────────────────────
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                face_detected = box is not None

                # ── FPS ───────────────────────────────────────────────────────
                now = time.perf_counter()
                fps_times.append(now)
                
                # Optimized FPS calculation logic
                elapsed_time = fps_times[-1] - fps_times[0]
                fps = len(fps_times) / elapsed_time if elapsed_time > 0 else 0.0

                # ── HR poll (throttled) ───────────────────────────────────────
                if now - last_poll_time >= CFG.hr_poll_interval:
                    try:
                        result = model.hr(start=CFG.hr_lookback_seconds)
                        if result and result.get("hr"):
                            hr_raw = float(result["hr"])
                            hr_history.append(hr_raw)
                            hr_smooth = sum(hr_history) / len(hr_history)
                            zone_label, _ = hr_zone(hr_smooth)
                            log.info("HR: %.1f BPM (smooth) | %.1f BPM (raw) | Zone: %s", hr_smooth, hr_raw, zone_label)
                    except Exception as exc:   # noqa: BLE001
                        log.warning("HR read failed: %s", exc)
                    last_poll_time = now

                # ── Draw overlay ──────────────────────────────────────────────
                draw_overlay(frame, hr_smooth, hr_raw, hr_history, fps, box, face_detected)

                # ── Display ───────────────────────────────────────────────────
                cv2.imshow(CFG.window_title, frame)
                if cv2.waitKey(1) & 0xFF == ord(CFG.quit_key):
                    log.info("Quit key pressed — exiting.")
                    break

    except KeyboardInterrupt:
        log.info("Interrupted — shutting down.")
    finally:
        cv2.destroyAllWindows()
        log.info("Done.")

if __name__ == "__main__":
    main()