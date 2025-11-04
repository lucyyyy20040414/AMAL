#!/usr/bin/env python3
"""
Simplified script to analyze tactile contact data without OCR.
Paste your contact data matrices directly when prompted.
"""

import numpy as np
import matplotlib.pyplot as plt

# -------------------------- Config --------------------------
ROWS, COLS = 16, 16

# Define your force levels (in Newtons) - update these to match your actual weights
FORCE_LEVELS = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]  # Add/modify as needed

# Choose reduction metric
def sum_positive(M: np.ndarray) -> float:
    """Sum of all positive values (good for total contact intensity)"""
    return np.sum(M[M > 0])

def mean_positive(M: np.ndarray) -> float:
    """Mean of positive values (good for average intensity)"""
    vals = M[M > 0]
    return float(vals.mean()) if vals.size else 0.0

def max_value(M: np.ndarray) -> float:
    """Maximum value (good for peak contact)"""
    return float(np.max(M))

def count_positive(M: np.ndarray) -> float:
    """Count of positive taxels (good for contact area)"""
    return float(np.sum(M > 0))

# Select metric here
REDUCE = sum_positive   # <-- Change to mean_positive, max_value, or count_positive

# -------------------- Parsing utilities ---------------------
def parse_matrix_from_text(text: str) -> np.ndarray:
    """
    Parse a 16x16 matrix from pasted terminal output.
    Extracts numbers, ignoring header/footer lines.
    """
    lines = [ln.strip() for ln in text.strip().split('\n')]
    
    # Filter out header/footer lines
    lines = [ln for ln in lines if not ln.startswith('Frame #')]
    lines = [ln for ln in lines if not set(ln) <= set('= -')]  # Remove separator lines
    
    # Extract all numbers
    numbers = []
    for ln in lines:
        parts = ln.split()
        for p in parts:
            try:
                numbers.append(float(p))
            except ValueError:
                continue
    
    # Try to reshape to 16x16
    if len(numbers) >= ROWS * COLS:
        return np.array(numbers[:ROWS*COLS]).reshape(ROWS, COLS)
    else:
        raise ValueError(f"Expected {ROWS*COLS} numbers, found {len(numbers)}")

# -------------------- Main pipeline -------------------------
forces = []
signals = []
matrices = []

print("="*70)
print("Tactile Contact Data Analysis")
print("="*70)
print(f"Reduction metric: {REDUCE.__name__}")
print(f"\nYou will be prompted to paste contact data for each force level.")
print("After pasting the matrix, press Enter twice (empty line) to continue.\n")

for force in FORCE_LEVELS:
    print("="*70)
    print(f"Force level: {force} N")
    print("="*70)
    print("Paste the contact data matrix below (then press Enter twice):")
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "":
                if len(lines) > 0:  # Empty line after data
                    break
            else:
                lines.append(line)
        except EOFError:
            break
    
    if len(lines) == 0:
        print(f"  → Skipped (no data)")
        continue
    
    text = "\n".join(lines)
    
    try:
        M = parse_matrix_from_text(text)
        matrices.append(M)
        forces.append(force)
        signal = REDUCE(M)
        signals.append(signal)
        print(f"  ✓ Parsed {M.shape} matrix | Signal = {signal:.2f}")
    except Exception as e:
        print(f"  ✗ Parse error: {e}")

# -------------------- Save & Plot ---------------------------
if len(signals) >= 2:
    import csv
    
    # Save results
    out_csv = "tactile_signal_vs_force.csv"
    with open(out_csv, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["Force_N", f"Signal_{REDUCE.__name__}"])
        for f, s in zip(forces, signals):
            writer.writerow([f, s])
    
    np.save("matrices_16x16.npy", np.array(matrices, dtype=float))
    
    print("\n" + "="*70)
    print(f"✓ Saved: {out_csv} and matrices_16x16.npy")
    print("="*70)
    
    # Sort by force for plotting
    order = np.argsort(forces)
    F = np.array(forces)[order]
    S = np.array(signals)[order]
    
    # Print summary
    print("\nSummary:")
    print(f"{'Force (N)':<12} {'Signal':<15}")
    print("-" * 27)
    for f, s in zip(F, S):
        print(f"{f:<12.1f} {s:<15.2f}")
    
    # Plot
    plt.figure(figsize=(8, 6))
    plt.plot(F, S, marker='o', linewidth=2, markersize=8)
    plt.xlabel("Force (N)", fontsize=12)
    plt.ylabel(f"Tactile Signal ({REDUCE.__name__})", fontsize=12)
    plt.title("Tactile Signal vs Applied Force", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("tactile_force_calibration.png", dpi=150)
    print("\n✓ Saved plot: tactile_force_calibration.png")
    plt.show()
else:
    print("\n✗ Not enough data points to plot (need at least 2)")

