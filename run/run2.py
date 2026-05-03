"""
rPPG Real-Time Heart Rate Monitor
----------------------------------
v3 fixes:
  - Latency: model.hr() moved to a daemon thread — main loop never blocks
  - Face detection: OpenCV DNN face detector runs every frame independently
    from the rPPG signal box (no more missing/jittery boxes)
  - EMA box smoothing: bounding box glides instead of jumping
  - Thread-safe shared state via threading.Lock
  - All v2 features retained: smoothing, zones, FPS, history bars, logging
"""

import threading
import time
import logging
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np
import rppg

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rppg_monitor")


# ─── Configuration ────────────────────────────────────────────────────────────
@dataclass
class Config:
    camera_index: int = 0
    hr_poll_interval: float = 1.5       # seconds between background HR calls
    hr_history_window: int = 10         # rolling average window
    hr_lookback_seconds: int = -10      # rPPG model lookback window 

    # Face detector
    face_scale_factor: float = 1.1      # Haar cascade scale step
    face_min_neighbors: int = 5         # detection strictness
    face_min_size: tuple = (80, 80)     # ignore tiny detections
    box_ema_alpha: float = 0.25         # EMA smoothing (0=frozen, 1=raw)

    # HR zone thresholds (BPM)
    zone_resting_max: float = 60.0
    zone_normal_max: float = 100.0
    zone_elevated_max: float = 140.0

    # Overlay
    overlay_x: int = 10
    overlay_y: int = 10
    bar_width: int = 160
    bar_height: int = 6
    window_title: str = "rPPG Monitor"
    quit_key: str = "q"
    font: int = cv2.FONT_HERSHEY_SIMPLEX


CFG = Config()


# ─── HR Zone ──────────────────────────────────────────────────────────────────
def hr_zone(bpm: float) -> tuple[str, tuple[int, int, int]]:
    if bpm < CFG.zone_resting_max:
        return "Resting",  (180, 180, 180)
    if bpm < CFG.zone_normal_max:
        return "Normal",   (80, 200, 80)
    if bpm < CFG.zone_elevated_max:
        return "Elevated", (0, 165, 255)
    return     "High",     (60, 60, 220)


# ─── Face Detector ────────────────────────────────────────────────────────────
class FaceDetector:
    """
    OpenCV Haar cascade face detector.
    Runs on every frame independently of the rPPG model's own face tracking,
    so a bounding box is always available even when the rPPG box is None.
    Box coordinates are EMA-smoothed to remove jitter.
    """

    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError(f"Failed to load Haar cascade from {cascade_path}")
        self._smooth_box: np.ndarray | None = None  # [x, y, w, h] floats

    def detect(self, frame_bgr: np.ndarray) -> tuple[int, int, int, int] | None:
        """
        Returns (x1, y1, x2, y2) of the largest detected face, or None.
        EMA-smoothed so the box doesn't jump between frames.
        """
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)   # helps in varied lighting

        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=CFG.face_scale_factor,
            minNeighbors=CFG.face_min_neighbors,
            minSize=CFG.face_min_size,
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        if len(faces) == 0:
            self._smooth_box = None
            return None

        # Pick largest face by area
        face = max(faces, key=lambda f: f[2] * f[3]).astype(float)

        if self._smooth_box is None:
            self._smooth_box = face.copy()
        else:
            a = CFG.box_ema_alpha
            self._smooth_box = a * face + (1 - a) * self._smooth_box

        x, y, w, h = self._smooth_box.astype(int)
        return x, y, x + w, y + h          # (x1, y1, x2, y2)


# ─── Background HR Thread ─────────────────────────────────────────────────────
class HRWorker:
    """
    Calls model.hr() in a daemon thread on a fixed interval.
    The main render loop reads results through a Lock — zero blocking.
    """

    def __init__(self, model: rppg.Model) -> None:
        self._model = model
        self._lock = threading.Lock()
        self._hr_raw: float | None = None
        self._hr_smooth: float | None = None
        self._history: deque[float] = deque(maxlen=CFG.hr_history_window)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="hr-worker")

    def start(self) -> None:
        self._thread.start()
        log.info("HR worker thread started (poll every %.1fs)", CFG.hr_poll_interval)

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                result = self._model.hr(start=CFG.hr_lookback_seconds)
                if result and result.get("hr"):
                    raw = float(result["hr"])
                    with self._lock:
                        self._hr_raw = raw
                        self._history.append(raw)
                        self._hr_smooth = sum(self._history) / len(self._history)
                    zone_label, _ = hr_zone(self._hr_smooth)
                    log.info(
                        "HR: %.1f BPM (smooth) | %.1f BPM (raw) | Zone: %s",
                        self._hr_smooth, raw, zone_label,
                    )
            except Exception as exc:    # noqa: BLE001
                log.warning("HR read error: %s", exc)

            elapsed = time.perf_counter() - t0
            self._stop.wait(max(0.0, CFG.hr_poll_interval - elapsed))

    @property
    def state(self) -> tuple[float | None, float | None, list[float]]:
        """Thread-safe snapshot: (hr_smooth, hr_raw, history_list)."""
        with self._lock:
            return self._hr_smooth, self._hr_raw, list(self._history)


# ─── Overlay ──────────────────────────────────────────────────────────────────
def draw_overlay(
    frame: np.ndarray,
    hr_smooth: float | None,
    hr_raw: float | None,
    hr_history: list[float],
    fps: float,
    face_box: tuple[int, int, int, int] | None,
) -> None:
    h, w = frame.shape[:2]
    face_detected = face_box is not None

    # ── Face bounding box ──
    if face_box is not None:
        x1, y1, x2, y2 = face_box
        color = hr_zone(hr_smooth)[1] if hr_smooth else (80, 200, 80)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        if hr_smooth is not None:
            label = f"{hr_smooth:.1f} BPM"
            (lw, lh), _ = cv2.getTextSize(label, CFG.font, 0.65, 2)
            cv2.rectangle(frame, (x1 - 1, y1 - lh - 14), (x1 + lw + 6, y1 - 2), (20, 20, 20), -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 6), CFG.font, 0.65, color, 2)

    # ── Semi-transparent info panel ──
    ox, oy = CFG.overlay_x, CFG.overlay_y
    panel_w, panel_h = 220, 130
    slab = frame.copy()
    cv2.rectangle(slab, (ox - 4, oy - 4), (ox + panel_w, oy + panel_h), (20, 20, 20), -1)
    cv2.addWeighted(slab, 0.55, frame, 0.45, 0, frame)

    # Status dot
    dot_color = (80, 200, 80) if face_detected else (60, 60, 220)
    cv2.circle(frame, (ox + 8, oy + 10), 5, dot_color, -1)
    cv2.putText(
        frame,
        "Face detected" if face_detected else "No face — searching…",
        (ox + 20, oy + 15), CFG.font, 0.42, (200, 200, 200), 1,
    )

    # Large BPM readout
    if hr_smooth is not None:
        zone_label, zone_color = hr_zone(hr_smooth)
        cv2.putText(frame, f"{hr_smooth:.0f}", (ox + 2, oy + 62), CFG.font, 1.9, zone_color, 3)
        cv2.putText(frame, "BPM", (ox + 95, oy + 62), CFG.font, 0.55, (180, 180, 180), 1)
        cv2.putText(frame, zone_label, (ox + 2, oy + 82), CFG.font, 0.5, zone_color, 1)
        if hr_raw is not None and abs(hr_raw - hr_smooth) > 2:
            cv2.putText(frame, f"raw {hr_raw:.0f}", (ox + 82, oy + 82), CFG.font, 0.38, (130, 130, 130), 1)
    else:
        cv2.putText(frame, "-- BPM", (ox + 2, oy + 62), CFG.font, 1.2, (130, 130, 130), 2)
        cv2.putText(frame, "Collecting signal…", (ox + 2, oy + 82), CFG.font, 0.38, (130, 130, 130), 1)

    # Mini history bar chart
    if len(hr_history) > 1:
        bar_y_base = oy + 108
        hr_min, hr_max = min(hr_history), max(hr_history)
        hr_range = max(hr_max - hr_min, 10)
        slot_w = CFG.bar_width // len(hr_history)
        for i, val in enumerate(hr_history):
            bar_h_px = int(CFG.bar_height * (val - hr_min) / hr_range) + 2
            bx = ox + i * slot_w
            _, bc = hr_zone(val)
            cv2.rectangle(frame, (bx, bar_y_base - bar_h_px), (bx + max(slot_w - 2, 1), bar_y_base), bc, -1)

    # FPS — bottom-right
    fps_str = f"FPS {fps:.0f}"
    (fw, _), _ = cv2.getTextSize(fps_str, CFG.font, 0.4, 1)
    cv2.putText(frame, fps_str, (w - fw - 8, h - 8), CFG.font, 0.4, (120, 120, 120), 1)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    model = rppg.Model()
    detector = FaceDetector()
    hr_worker = HRWorker(model)
    fps_times: deque[float] = deque(maxlen=30)

    log.info("Starting rPPG monitor — press '%s' to quit.", CFG.quit_key)
    hr_worker.start()

    try:
        with model.video_capture(CFG.camera_index):
            for frame, _ in model.preview:         # _ = rPPG's own box, unused
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # FPS
                now = time.perf_counter()
                fps_times.append(now)
                fps = (len(fps_times) / (fps_times[-1] - fps_times[0] + 1e-9)
                       if len(fps_times) > 1 else 0.0)

                # Independent face detection — every frame, non-blocking
                face_box = detector.detect(frame)

                # HR state from background thread — non-blocking lock read
                hr_smooth, hr_raw, hr_history = hr_worker.state

                draw_overlay(frame, hr_smooth, hr_raw, hr_history, fps, face_box)

                cv2.imshow(CFG.window_title, frame)
                if cv2.waitKey(1) & 0xFF == ord(CFG.quit_key):
                    log.info("Quit key pressed — exiting.")
                    break

    except KeyboardInterrupt:
        log.info("Interrupted — shutting down.")
    finally:
        hr_worker.stop()
        cv2.destroyAllWindows()
        log.info("Done.")


if __name__ == "__main__":
    main()