"""
AMAL Display Web Demo
version: 0.0.1
Reads serial data of the 3d vitact sensors and display via web.
"""
import numpy as np
import serial
import cv2
import time
from scipy.ndimage import gaussian_filter
import logging
from typing import Optional
import os

# Flask must be installed and imported directly (no optional import)
from flask import Flask, Response

# here we go

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

contact_data_norm = np.zeros((16,16), dtype=np.float32)
THRESHOLD = 12
NOISE_SCALE = 60

# Optional terminal printing
# Set PRINT_TO_TERMINAL=True to print readings periodically
PRINT_TO_TERMINAL = True
# Choose 'stats' for summary or 'matrix' to print the whole 16x16 grid (heavy)
PRINT_MODE = 'stats'  # 'stats' | 'matrix'
# Print every N frames
PRINT_EVERY_N = 10

# Force/pressure calibration and output
# Linear force model per taxel: force_N = max(0, FORCE_GAIN * counts + FORCE_BIAS)
FORCE_GAIN = float(os.getenv('AMAL_FORCE_GAIN', '0.02'))  # N per sensor count
FORCE_BIAS = float(os.getenv('AMAL_FORCE_BIAS', '0.0'))   # N offset
# Taxel area for pressure computation (m^2). Example: (3 mm)^2 = 9e-6 m^2
TAXEL_AREA_M2 = float(os.getenv('AMAL_TAXEL_AREA_M2', '9e-6'))
# Pressure unit for terminal output: 'pa' or 'kpa'
PRESSURE_UNIT = os.getenv('AMAL_PRESSURE_UNIT', 'kPa').strip().lower()
# Toggle printing of force/pressure stats
PRINT_FORCE_PRESSURE = os.getenv('AMAL_PRINT_FORCE_PRESSURE', '1').strip().lower() in {'1','true','yes'}

# Optional web UI configuration
ENABLE_WEB_UI = True  # set False to disable the web dashboard
WEB_HOST = "127.0.0.1"
WEB_PORT = 6900

# Visualization options
# MIRROR_VERTICAL mirrors across the horizontal axis (top-bottom flip)
# MIRROR_HORIZONTAL mirrors left-right across the vertical axis
MIRROR_VERTICAL = True
MIRROR_HORIZONTAL = False

# Image enhancement options
ENABLE_MEDIAN = True
MEDIAN_KSIZE = 3  # must be odd; typical: 3 or 5
ENABLE_GAUSSIAN = True
GAUSS_SIGMA = 0.6  # small smoothing
ENABLE_UNSHARP = True
UNSHARP_AMOUNT = 0.6  # 0..2 typical; 0 disables

# Output scaling (to improve clarity on large screens)
SCALE_UP = True
SCALE_SIZE = 512  # output width/height in pixels for square image
SCALE_INTERP = 'nearest'  # 'nearest' (crisp blocks), 'cubic' (smooth), 'linear'

# Global serial device handle (initialized in __main__)
serDev = None

def _parse_line_to_row(line: str, width: int) -> Optional[np.ndarray]:
    try:
        row = np.fromstring(line, dtype=np.int16, sep=' ')
        if row.size == width:
            return row
    except Exception as e:
        logging.error(f"Error parsing line to row: {e}")
    return None

## Serial port is specified manually by the user in __main__

# Flask application; website code starts
app = Flask(__name__)


def apply_gaussian_blur(contact_map, sigma=0.1):
    return gaussian_filter(contact_map, sigma=sigma)

def temporal_filter(new_frame, prev_frame, alpha=0.2):
    """
    Apply temporal smoothing filter.
    'alpha' determines the blending factor.
    A higher alpha gives more weight to the current frame, while a lower alpha gives more weight to the previous frame.
    """
    return alpha * new_frame + (1 - alpha) * prev_frame

# Initialize previous frame buffer
prev_frame = np.zeros_like(contact_data_norm)


# ---- Optional Web UI (MJPEG stream) ----
def _make_mjpeg_stream(calibration_frames: int = 30, rows_per_frame: int = 16):
    """Single-threaded MJPEG stream generator that also reads and processes sensor data.
    Calibrates on first use for each client connection.
    """
    global serDev
    if serDev is None:
        raise RuntimeError("Serial device not initialized.")

    # Calibration
    calib_buffer = np.zeros((calibration_frames, rows_per_frame, rows_per_frame), dtype=np.int16)
    collected = 0
    row_buffer = []
    logging.info("Starting calibration...")
    while collected < calibration_frames:
        try:
            raw = serDev.readline()
            if not raw:
                # no data available yet (non-blocking/short-timeout)
                time.sleep(0.001)
                continue
            line = raw.decode('utf-8', errors='ignore').strip()
        except Exception as e:
            logging.error(f"Error reading calibration data: {e}")
            continue
        if len(line) < 2:
            if len(row_buffer) == rows_per_frame:
                try:
                    calib_buffer[collected] = np.vstack(row_buffer)
                    collected += 1
                except Exception:
                    pass
            row_buffer = []
            continue
        row = _parse_line_to_row(line, rows_per_frame)
        if row is not None:
            row_buffer.append(row)

    median = np.median(calib_buffer, axis=0)
    logging.info("Calibration complete. Streaming frames...")

    # Streaming loop
    prev_frame = np.zeros((rows_per_frame, rows_per_frame), dtype=np.float32)
    target_fps = 30.0
    min_interval = 1.0 / target_fps
    last_send = 0.0

    boundary = b'--frame\r\n'
    headers = b'Content-Type: image/jpeg\r\n\r\n'

    row_buffer = []
    try:
        frame_counter = 0
        while True:
            try:
                raw = serDev.readline()
                if not raw:
                    time.sleep(0.001)
                    continue
                line = raw.decode('utf-8', errors='ignore').strip()
            except Exception as e:
                logging.error(f"Error reading stream data: {e}")
                # end generator gracefully to avoid 500s
                return
            if len(line) < 2:
                if len(row_buffer) == rows_per_frame:
                    frame = np.vstack(row_buffer).astype(np.float32)
                    # Process frame
                    contact = frame - median - THRESHOLD
                    np.clip(contact, 0, 100, out=contact)
                    max_val = float(contact.max(initial=0.0))
                    denom = NOISE_SCALE if max_val < THRESHOLD else max_val
                    norm = contact / (denom if denom != 0 else 1.0)

                    # Force (N) and pressure stats for terminal
                    if PRINT_FORCE_PRESSURE and TAXEL_AREA_M2 > 0:
                        force_map = np.maximum(0.0, FORCE_GAIN * contact + FORCE_BIAS)
                        total_force_N = float(force_map.sum())
                        peak_force_N = float(force_map.max(initial=0.0))
                        mean_force_N = float(force_map.mean())

                        pressure_map_pa = force_map / TAXEL_AREA_M2
                        if PRESSURE_UNIT == 'pa':
                            peak_pressure = float(pressure_map_pa.max(initial=0.0))
                            mean_pressure = float(pressure_map_pa.mean())
                            pressure_unit_label = 'Pa'
                        else:
                            peak_pressure = float((pressure_map_pa / 1000.0).max(initial=0.0))
                            mean_pressure = float((pressure_map_pa / 1000.0).mean())
                            pressure_unit_label = 'kPa'

                    # Optional terminal output
                    frame_counter += 1
                    if PRINT_TO_TERMINAL and (frame_counter % PRINT_EVERY_N == 0):
                        if PRINT_MODE == 'stats':
                            logging.info(f"frame stats: max={max_val:.1f}, mean={float(norm.mean()):.3f}")
                            if PRINT_FORCE_PRESSURE and TAXEL_AREA_M2 > 0:
                                logging.info(
                                    f"force: total={total_force_N:.3f} N, peak={peak_force_N:.3f} N, mean={mean_force_N:.3f} N; "
                                    f"pressure: peak={peak_pressure:.2f} {pressure_unit_label}, mean={mean_pressure:.2f} {pressure_unit_label}"
                                )
                        elif PRINT_MODE == 'matrix':
                            try:
                                arr8 = (np.clip(norm, 0.0, 1.0) * 255).astype(np.uint8)
                                print(np.array_str(arr8, max_line_width=120))
                            except Exception:
                                pass

                    # temporal smoothing
                    alpha = 0.2
                    prev_frame = alpha * norm + (1 - alpha) * prev_frame

                    img = np.clip(prev_frame, 0.0, 1.0)

                    # Denoise / enhance
                    if ENABLE_MEDIAN and MEDIAN_KSIZE and (MEDIAN_KSIZE % 2 == 1):
                        _img8 = (img * 255).astype(np.uint8)
                        _img8 = cv2.medianBlur(_img8, MEDIAN_KSIZE)
                        img = _img8.astype(np.float32) / 255.0
                    if ENABLE_GAUSSIAN and GAUSS_SIGMA > 0:
                        img = gaussian_filter(img, sigma=GAUSS_SIGMA)
                    if ENABLE_UNSHARP and UNSHARP_AMOUNT > 0:
                        blur_for_unsharp = gaussian_filter(img, sigma=max(0.001, GAUSS_SIGMA)) if ENABLE_GAUSSIAN else gaussian_filter(img, sigma=0.8)
                        img = np.clip(img + UNSHARP_AMOUNT * (img - blur_for_unsharp), 0.0, 1.0)

                    img8 = (img * 255).astype(np.uint8)
                    colormap = cv2.applyColorMap(img8, cv2.COLORMAP_VIRIDIS)
                    flip_code = None
                    if MIRROR_HORIZONTAL and MIRROR_VERTICAL:
                        flip_code = -1
                    elif MIRROR_HORIZONTAL:
                        flip_code = 1
                    elif MIRROR_VERTICAL:
                        flip_code = 0
                    if flip_code is not None:
                        colormap = cv2.flip(colormap, flip_code)
                    if SCALE_UP and SCALE_SIZE > 0:
                        interp_map = {
                            'nearest': cv2.INTER_NEAREST,
                            'linear': cv2.INTER_LINEAR,
                            'cubic': cv2.INTER_CUBIC,
                            'area': cv2.INTER_AREA,
                        }
                        inter = interp_map.get(SCALE_INTERP, cv2.INTER_NEAREST)
                        colormap = cv2.resize(colormap, (SCALE_SIZE, SCALE_SIZE), interpolation=inter)

                    colormap = cv2.copyMakeBorder(colormap, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=(0,0,0))

                    # Encode JPEG and yield
                    now = time.time()
                    if now - last_send >= min_interval:
                        last_send = now
                        try:
                            ok, jpg = cv2.imencode('.jpg', colormap, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                            if ok:
                                yield boundary + headers + jpg.tobytes() + b"\r\n"
                        except Exception as e:
                            logging.debug(f"JPEG encode skipped: {e}")
                row_buffer = []
                continue
            row = _parse_line_to_row(line, rows_per_frame)
            if row is not None:
                row_buffer.append(row)
    except GeneratorExit:
        logging.info("Client disconnected from stream.")
        return


@app.route('/')
def index():
    return (
        """
        <html>
            <head>
                <meta charset='utf-8' />
                <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
                <title>AMAL Web Demo</title>
                <style>
                    html, body { height: 100%; margin: 0; background:#111; color:#ddd; font-family: Arial, sans-serif; }
                    .wrap { min-height: 100vh; display:flex; flex-direction:column; justify-content:center; align-items:center; gap: 12px; padding: 8px; }
                    .info { opacity: 0.8; font-size: 0.95rem; }
                    /* Make the image fill the screen while preserving aspect ratio */
                    .frame { border:1px solid #333; background:#000; object-fit: contain; display:block; }
                    /* Prefer the smaller viewport side to keep square aspect */
                    @media (max-aspect-ratio: 1/1) { .frame { width: 96vw; height: 96vw; } }
                    @media (min-aspect-ratio: 1/1) { .frame { width: 96vh; height: 96vh; } }
                </style>
            </head>
            <body>
                <div class="wrap">
                    <h2 style="margin:0">AMAL Web Demo</h2>
                    <img class="frame" src="/stream" alt="Contact Map" />
                    <div class="info">Local server running locally. Press Ctrl+C in the terminal to stop.</div>
                </div>
            </body>
        </html>
        """
    )


@app.route('/stream')
def stream():
    return Response(_make_mjpeg_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        # Initialize serial only when running the app
        # Set your serial port here manually, e.g.:
        # - On Windows: "COM18"
        # - On macOS: "/dev/cu.usbmodemXXXX" or "/dev/cu.usbserialXXXX"
        # - On Linux: "/dev/ttyACM0" or "/dev/ttyUSB0"
        PORT = "/dev/cu.usbserial-AQ02VE0X"  # TODO: replace with your actual device path
        BAUD = 2000000
        # Use a small timeout to avoid busy-waiting and Windows ClearCommError
        serDev = serial.Serial(PORT, BAUD, timeout=0.1)
        serDev.flush()
        logging.info(f"Serial device opened on {PORT} @ {BAUD} baud")

        if ENABLE_WEB_UI:
            logging.info(f"Starting web UI at http://{WEB_HOST}:{WEB_PORT}")
            app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False, threaded=False)
            
        else:
            logging.info("Web UI disabled. Enable ENABLE_WEB_UI to serve the dashboard.")
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Exiting...")
    finally:
        try:
            if serDev is not None:
                serDev.close()
                logging.info("Serial device closed.")
        except Exception:
            pass