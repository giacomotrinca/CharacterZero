#!/usr/bin/env python3
"""
paddle_ocr_phb.py — Worker OCR PaddleOCR per UNA pagina del Manuale del Giocatore.

Eseguito come sottoprocesso isolato (un processo per pagina) per evitare
accumulo di RAM/OOM durante il batch lungo. Resumabile: se l'output esiste,
non rifà nulla.

Ricostruisce l'ordine di lettura a 2 colonne usando i bounding box:
divisori a tutta larghezza separano "bande"; dentro ogni banda si legge
prima la colonna sinistra (dall'alto), poi la destra.

Uso:
    python tools/paddle_ocr_phb.py <pdf_page_index_0based>
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("OMP_NUM_THREADS", "2")

ROOT = Path(__file__).parent.parent
PDF_PATH = ROOT / "manuals/D&D 5th Manuale del Giocatore.pdf"
OUT_DIR = ROOT / "manuals/_index/phb_ocr"
DPI = 150
DET_SIDE = 960  # limita il lato lungo per la detection (RAM-friendly)


def render_page(page_index: int):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(PDF_PATH))
    page = pdf[page_index]
    img = page.render(scale=DPI / 72).to_pil().convert("RGB")
    return img


def numpy_img(img):
    import numpy as np
    # PaddleOCR si aspetta BGR (come OpenCV)
    arr = np.asarray(img)[:, :, ::-1]
    return np.ascontiguousarray(arr)


def bbox_from_poly(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def reading_order(boxes, page_w):
    """boxes: list of (x1,y1,x2,y2,text). Ritorna lista ordinata di testo."""
    split_x = page_w / 2.0
    fw_thresh = 0.55 * page_w

    dividers = []  # (y_top, text)
    normals = []   # (x1,y1,x2,y2,text)
    for (x1, y1, x2, y2, t) in boxes:
        if (x2 - x1) >= fw_thresh:
            dividers.append((y1, t))
        else:
            normals.append((x1, y1, x2, y2, t))

    divider_ys = sorted(d[0] for d in dividers)

    def band_of(y):
        return sum(1 for dy in divider_ys if dy < y)

    items = []  # (band, col, y_top, text)
    for (x1, y1, x2, y2, t) in normals:
        cx = (x1 + x2) / 2.0
        col = 0 if cx < split_x else 1
        items.append((band_of(y1), col, y1, t))
    for i, (y, t) in enumerate(sorted(dividers)):
        # il divisore apre la sua banda: col=-1 per venire prima dei box
        items.append((i, -1, y, t))

    items.sort(key=lambda it: (it[0], it[1], it[2]))
    return [it[3] for it in items]


def main():
    if len(sys.argv) < 2:
        print("uso: paddle_ocr_phb.py <pdf_page_index>", file=sys.stderr)
        sys.exit(2)
    page_index = int(sys.argv[1])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"page_{page_index:03d}.json"
    if out_path.exists():
        print(f"[skip] page {page_index} già fatto")
        return

    img = render_page(page_index)
    page_w, page_h = img.size

    from paddleocr import PaddleOCR
    ocr = PaddleOCR(
        lang="it",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_det_limit_side_len=DET_SIDE,
        text_det_limit_type="max",
        text_rec_score_thresh=0.3,
    )
    res = ocr.predict(numpy_img(img))
    r = res[0]
    texts = r["rec_texts"]
    polys = r.get("rec_polys") or r.get("dt_polys")

    boxes = []
    for t, poly in zip(texts, polys):
        t = (t or "").strip()
        if not t:
            continue
        x1, y1, x2, y2 = bbox_from_poly([[float(p[0]), float(p[1])] for p in poly])
        boxes.append((x1, y1, x2, y2, t))

    ordered = reading_order(boxes, page_w)

    out = {
        "pdf_page_index": page_index,
        "page_label": page_index + 1,
        "width": page_w,
        "height": page_h,
        "n_lines": len(boxes),
        "lines": [
            {"x1": round(b[0], 1), "y1": round(b[1], 1),
             "x2": round(b[2], 1), "y2": round(b[3], 1), "text": b[4]}
            for b in boxes
        ],
        "reading_text": "\n".join(ordered),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[ok] page {page_index} -> {out_path.name} ({len(boxes)} righe)")


if __name__ == "__main__":
    main()
