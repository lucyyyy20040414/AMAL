import re
import os
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageOps, ImageFilter

# -------------------------- Config --------------------------
# Image paths (in the exact order you described)
paths = [
    (10.0, "/mnt/data/1000.png"),
    (8.0,  "/mnt/data/800.png"),
    (7.0,  "/mnt/data/700.png"),
    (6.0,  "/mnt/data/600.png"),
    (5.0,  "/mnt/data/500.png"),
    (4.5,  "/mnt/data/450.png"),
    (3.0,  "/mnt/data/300.png"),
    (2.0,  "/mnt/data/200.png"),
    (1.0,  "/mnt/data/100.png"),
]

ROWS, COLS = 16, 16

# Choose how to reduce a 16x16 matrix to a single scalar
# Options below—pick ONE by setting REDUCE to its function name.
def sum_positive(M: np.ndarray) -> float:
    return np.sum(M[M > 0])

def mean_positive(M: np.ndarray) -> float:
    vals = M[M > 0]
    return float(vals.mean()) if vals.size else 0.0

def l1_abs_mean(M: np.ndarray) -> float:
    return float(np.mean(np.abs(M)))

def p95_positive(M: np.ndarray) -> float:
    vals = M[M > 0]
    return float(np.percentile(vals, 95)) if vals.size else 0.0

REDUCE = sum_positive   # <-- default metric

# -------------------- OCR (pytesseract) ---------------------
# We’ll try pytesseract; if unavailable or OCR fails, we’ll prompt for manual text paste in console.
try:
    import pytesseract
    TESS_AVAILABLE = True
except Exception:
    TESS_AVAILABLE = False

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    # Crop margins a bit, convert to grayscale, boost contrast, sharpen and upscale for better OCR
    w, h = img.size
    img = img.crop((int(0.02*w), int(0.10*h), int(0.98*w), int(0.92*h)))  # trim headers/footers & borders
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    # Upscale
    scale = 2
    img = img.resize((img.width*scale, img.height*scale), Image.BICUBIC)
    return img

def ocr_matrix_from_image(path: str) -> str:
    img = Image.open(path)
    img = preprocess_for_ocr(img)
    if not TESS_AVAILABLE:
        raise RuntimeError("pytesseract not available")
    cfg = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.-'
    return pytesseract.image_to_string(img, config=cfg)

# -------------------- Parsing utilities ---------------------
def normalize_minus_signs(text: str) -> str:
    # Replace Unicode minus/dash variants with ASCII hyphen
    return (text
            .replace('−', '-')  # Unicode minus
            .replace('–', '-')  # en dash
            .replace('—', '-')  # em dash
            .replace('·', '.')  # stray middots to dots if any
            )

def extract_matrix_from_text(text: str, expect_shape=(ROWS, COLS)) -> np.ndarray:
    """
    Accepts raw OCRed text, returns a 16x16 float array.
    We look for rows of numbers (including negatives and decimals).
    """
    text = normalize_minus_signs(text)
    lines = [ln.strip() for ln in text.splitlines()]
    # Remove obvious header/footer lines (e.g., 'Frame #xxxx – Contact Data (median-subtracted)')
    lines = [ln for ln in lines if not re.search(r'Frame\s*#?\d+', ln)]
    lines = [ln for ln in lines if not set(ln) <= set('= -')]  # drop ruler lines like "====", "----"

    rows = []
    num_re = re.compile(r'[-+]?\d+(?:\.\d+)?')

    for ln in lines:
        nums = [float(x) for x in num_re.findall(ln)]
        if len(nums) >= 8:   # heuristically keep lines that look like matrix rows
            rows.append(nums)

    # If lines are wrapped, we might have too many columns; try to fold to COLS
    cleaned = []
    for r in rows:
        # If too few numbers, skip
        if len(r) < 4:
            continue
        cleaned.extend(r)

    # Strategy:
    # 1) If we collected exactly ROWS lines and each looks near COLS, try line-wise trim/pad
    # 2) Otherwise, fall back to flat reshape if total count matches ROWS*COLS

    # Try reshape directly first
    total_needed = expect_shape[0]*expect_shape[1]
    if len(cleaned) >= total_needed:
        arr = np.array(cleaned[:total_needed], dtype=float).reshape(expect_shape)
        return arr

    # Fallback: try to assemble per-line if it looks like 16 rows
    if len(rows) >= ROWS:
        candidate = []
        for r in rows[:ROWS]:
            if len(r) >= COLS:
                candidate.append(r[:COLS])
            else:
                # right-pad with zeros if a short OCR row
                candidate.append(r + [0.0]*(COLS-len(r)))
        return np.array(candidate, dtype=float)

    raise ValueError("Could not parse a {}x{} matrix from text".format(*expect_shape))

# -------------------- Main pipeline -------------------------
forces = []
signals = []
matrices = []

for f, p in paths:
    print(f"\nProcessing {p} (Force = {f} N)")
    text = None
    # Try OCR first
    if TESS_AVAILABLE:
        try:
            text = ocr_matrix_from_image(p)
        except Exception as e:
            print(f"  OCR failed: {e}")

    # If OCR not available or failed, ask for manual paste
    if not text:
        print("  Please paste the matrix text for this image (end with an empty line):")
        lines = []
        while True:
            try:
                ln = input()
            except EOFError:
                break
            if ln.strip() == "":
                break
            lines.append(ln)
        text = "\n".join(lines)

    try:
        M = extract_matrix_from_text(text, expect_shape=(ROWS, COLS))
        matrices.append(M)
        forces.append(f)
        sig = REDUCE(M)
        signals.append(sig)
        print(f"  Parsed {M.shape} | signal={sig:.3f} (metric={REDUCE.__name__})")
    except Exception as e:
        print(f"  Parse error for {p}: {e}")

# -------------------- Save & Plot ---------------------------
if len(signals) >= 2:
    # Save CSV of signals and a separate npy of full matrices
    import csv
    out_csv = "tactile_signal_vs_force.csv"
    with open(out_csv, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["Force_N", f"Signal_{REDUCE.__name__}"])
        for f, s in zip(forces, signals):
            writer.writerow([f, s])
    np.save("matrices_16x16.npy", np.array(matrices, dtype=float))
    print(f"\nSaved: {out_csv} and matrices_16x16.npy")

    # Sort by force (descending to match your order, or ascending if you prefer)
    order = np.argsort(forces)
    F = np.array(forces)[order]
    S = np.array(signals)[order]

    plt.figure()
    plt.plot(F, S, marker='o')   # (per UI rules: single-plot, no style/colors specified)
    plt.xlabel("Force (N)")
    plt.ylabel(f"Tactile Signal ({REDUCE.__name__})")
    plt.title("Tactile Signal vs Force")
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()
else:
    print("\nNot enough valid points to plot.")
