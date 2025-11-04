import numpy as np
import serial
import threading
import cv2
import time
from scipy.ndimage import gaussian_filter
from flask import Flask, Response
import socket

# -------------------- CONFIG --------------------
MATRIX_SIZE = 16
THRESHOLD = 12
NOISE_SCALE = 60
ALPHA = 0.2
GAUSS_SIGMA = 0.0
BAUD = 2000000
WEB_HOST = "0.0.0.0"
WEB_PORT = 6900
CLEAR_THRESHOLD_COUNTS = 2
IDLE_BASELINE_BETA = 0.2

# Absolute force-based normalization (maps Newtons to colors)
USE_FORCE_NORM = False           # True → normalize by MAX_FORCE_N (Newtons)
MAX_FORCE_N = 10.0               # top of color scale (N)
FORCE_GAIN = 0.02                # N per contact count (auto-calibrated if enabled)
AUTO_CALIBRATE_FORCE_GAIN = False # compute FORCE_GAIN from a known load on first strong frame
KNOWN_FORCE_N = 10.0             # N; used if AUTO_CALIBRATE_FORCE_GAIN

# ✅ Fixed absolute scale (fallback if USE_FORCE_NORM=False)
ABSOLUTE_MAX = 100   # counts that map to full brightness

# Mac serial port (use "ls /dev/tty.*" to find yours)
PORT = '/dev/cu.usbserial-AQ02VE0X'

# ------------------------------------------------
contact_data_norm = np.zeros((MATRIX_SIZE, MATRIX_SIZE))
flag = False
app = Flask(__name__)
_prev_frame = None  # set in main
_force_gain_calibrated = False

# Terminal stats configuration
ENABLE_STATS = True
STATS_PERIOD_SEC = 1.0


# -------------------- SERIAL READING THREAD --------------------
def readThread(serDev):
    global contact_data_norm, flag

    data_tac = []
    num = 0
    backup = None
    current = None
    flag = False

    print("Collecting baseline frames...")

    # ---------- BASELINE CAPTURE ----------
    while True:
        if serDev.in_waiting > 0:
            try:
                line = serDev.readline().decode('utf-8', errors='ignore').strip()
            except:
                line = ""
            if len(line) < 10:
                if current is not None and len(current) == MATRIX_SIZE:
                    backup = np.array(current)
                    data_tac.append(backup)
                    num += 1
                    print(f"Baseline frame {num}/30", end='\r')
                    if num >= 30:
                        break
                current = []
                continue
            if current is not None:
                try:
                    int_values = [int(val) for val in line.split()]
                    current.append(int_values)
                except ValueError:
                    continue

    data_tac = np.array(data_tac)
    median = np.median(data_tac, axis=0)
    flag = True
    print("\nBaseline initialization complete ✅")

    # ---------- MAIN LOOP ----------
    while True:
        if serDev.in_waiting > 0:
            try:
                line = serDev.readline().decode('utf-8', errors='ignore').strip()
            except:
                line = ""

            if len(line) < 10:
                if current is not None and len(current) == MATRIX_SIZE:
                    backup = np.array(current)
                current = []
                if backup is not None:
                    # Remove baseline and noise floor
                    contact_data = backup - median - THRESHOLD
                    contact_data = np.clip(contact_data, 0, None)

                    # Remove tiny ghost values
                    if CLEAR_THRESHOLD_COUNTS > 0:
                        contact_data[contact_data < CLEAR_THRESHOLD_COUNTS] = 0

                    # Absolute force-based normalization or absolute counts
                    if USE_FORCE_NORM:
                        global _force_gain_calibrated, FORCE_GAIN
                        if AUTO_CALIBRATE_FORCE_GAIN and not _force_gain_calibrated and KNOWN_FORCE_N > 0:
                            peak_counts = float(contact_data.max())
                            if peak_counts >= 1.0:
                                FORCE_GAIN = KNOWN_FORCE_N / peak_counts
                                _force_gain_calibrated = True
                                print(f"Calibrated FORCE_GAIN={FORCE_GAIN:.5f} N/count from peak={peak_counts:.1f} for {KNOWN_FORCE_N} N")
                        force_map = contact_data * float(FORCE_GAIN)
                        contact_data_norm = np.clip(force_map / float(MAX_FORCE_N), 0, 1)
                    else:
                        contact_data_norm = np.clip(contact_data / float(ABSOLUTE_MAX), 0, 1)

                    # When idle (no contact), slowly adapt baseline to remove drift
                    if float(contact_data.sum()) == 0.0 and 0.0 < IDLE_BASELINE_BETA <= 1.0:
                        median = (1.0 - IDLE_BASELINE_BETA) * median + IDLE_BASELINE_BETA * backup

                continue

            if current is not None:
                try:
                    int_values = [int(val) for val in line.split()]
                    current.append(int_values)
                except ValueError:
                    continue


# -------------------- FILTERS --------------------
def apply_gaussian_blur(contact_map, sigma=GAUSS_SIGMA):
    return gaussian_filter(contact_map, sigma=sigma)


def temporal_filter(new_frame, prev_frame, alpha=ALPHA):
    return alpha * new_frame + (1 - alpha) * prev_frame


# -------------------- WEB STREAM --------------------
def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _mjpeg_generator(target_fps: float = 30.0):
    global _prev_frame
    min_interval = 1.0 / max(1.0, target_fps)
    last_send = 0.0
    boundary = b'--frame\r\n'
    headers = b'Content-Type: image/jpeg\r\n\r\n'
    last_stats = 0.0
    while True:
        if flag:
            if _prev_frame is None:
                _prev_frame = np.zeros_like(contact_data_norm)

            _prev_frame = contact_data_norm

            # Visualize absolute-normalized data
            vis = (np.clip(contact_data_norm, 0.0, 1.0) * 255).astype(np.uint8)
            colormap = cv2.applyColorMap(vis, cv2.COLORMAP_VIRIDIS)
            colormap = cv2.resize(colormap, (512, 512), interpolation=cv2.INTER_NEAREST)

            # Periodic terminal output
            now = time.time()
            if ENABLE_STATS and (now - last_stats) >= STATS_PERIOD_SEC:
                if USE_FORCE_NORM:
                    avg_counts = float(_prev_frame.mean() * (MAX_FORCE_N / max(FORCE_GAIN, 1e-9)))
                    avg_force_n = float(_prev_frame.mean() * MAX_FORCE_N)
                    print(f"avg_counts: {avg_counts:.2f}, avg_force_N: {avg_force_n:.3f}")
                else:
                    avg_counts = float(_prev_frame.mean() * float(ABSOLUTE_MAX))
                    peak_counts = float(_prev_frame.max() * float(ABSOLUTE_MAX))
                    print(f"avg_counts: {avg_counts:.2f}, peak_counts: {peak_counts:.2f}")
                last_stats = now

            if now - last_send >= min_interval:
                last_send = now
                ok, jpg = cv2.imencode('.jpg', colormap, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if ok:
                    yield boundary + headers + jpg.tobytes() + b"\r\n"
        time.sleep(0.005)


@app.route('/')
def index():
    return (
        """
        <html>
            <head>
                <meta charset='utf-8' />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>VITAC Web (Absolute Scale)</title>
                <style>
                    html, body { height:100%; margin:0; background:#111; color:#ddd; font-family:Arial, sans-serif; }
                    .wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; }
                    img { width:96vmin; height:96vmin; object-fit:contain; border:1px solid #333; background:#000;
                          image-rendering: pixelated; image-rendering: crisp-edges; }
                </style>
            </head>
            <body>
                <div class="wrap">
                    <img src="/stream" alt="VITAC" />
                </div>
            </body>
        </html>
        """
    )


@app.route('/stream')
def stream():
    return Response(_mjpeg_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


# -------------------- MAIN --------------------
def main():
    global contact_data_norm, flag, _prev_frame

    try:
        serDev = serial.Serial(PORT, BAUD, timeout=0.05)
    except Exception as e:
        print(f"⚠️ Could not open serial port {PORT}: {e}")
        print("Use `ls /dev/tty.*` to find your sensor device.")
        return

    serDev.flush()

    serialThread = threading.Thread(target=readThread, args=(serDev,))
    serialThread.daemon = True
    serialThread.start()

    _prev_frame = np.zeros_like(contact_data_norm)
    lan_ip = _get_local_ip()
    print(f"🌐 Web server started at: http://{WEB_HOST}:{WEB_PORT} (LAN: http://{lan_ip}:{WEB_PORT})")

    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False, threaded=False)


if __name__ == '__main__':
    main()