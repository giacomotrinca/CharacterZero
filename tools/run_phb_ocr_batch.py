#!/usr/bin/env python3
"""
run_phb_ocr_batch.py — Driver resumabile per l'OCR PaddleOCR dei capitoli classe
del Manuale del Giocatore.

Lancia un sottoprocesso isolato per ogni pagina (RAM-safe). Se un sottoprocesso
crasha (OOM/segfault) viene loggato e si prosegue con la pagina successiva.
È resumabile: rilanciandolo, salta le pagine già completate.

Uso:
    ~/miniconda3/bin/python tools/run_phb_ocr_batch.py [start_idx] [end_idx]
default: 44..121 (capitoli classe, indici PDF 0-based, end incluso)
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORKER = ROOT / "tools/paddle_ocr_phb.py"
OUT_DIR = ROOT / "manuals/_index/phb_ocr"
PYTHON = sys.executable

START = int(sys.argv[1]) if len(sys.argv) > 1 else 44
END = int(sys.argv[2]) if len(sys.argv) > 2 else 121  # incluso


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = list(range(START, END + 1))
    total = len(pages)
    print(f"[batch] {total} pagine (idx {START}..{END}) → {OUT_DIR}")
    t0 = time.time()
    done = 0
    for i, p in enumerate(pages, 1):
        out = OUT_DIR / f"page_{p:03d}.json"
        if out.exists():
            print(f"[batch] ({i}/{total}) page {p} già fatto, skip")
            done += 1
            continue
        ts = time.time()
        print(f"[batch] ({i}/{total}) page {p} … ", flush=True)
        try:
            r = subprocess.run(
                [PYTHON, str(WORKER), str(p)],
                timeout=1800,
                capture_output=True, text=True,
            )
            if r.returncode == 0 and out.exists():
                done += 1
                print(f"[batch]   ok in {time.time()-ts:.0f}s")
            else:
                print(f"[batch]   FALLITA (rc={r.returncode}) "
                      f"stderr_tail={r.stderr.strip()[-200:]!r}")
        except subprocess.TimeoutExpired:
            print(f"[batch]   TIMEOUT page {p}")
        elapsed = time.time() - t0
        avg = elapsed / i
        eta = avg * (total - i)
        print(f"[batch]   progress {done}/{total} done, "
              f"elapsed {elapsed/60:.1f}m, ETA {eta/60:.1f}m")

    print(f"[batch] FINITO: {done}/{total} pagine in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
