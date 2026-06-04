#!/usr/bin/env python3
"""
extract_manuals.py — Pipeline di estrazione dei manuali D&D 5e (italiano).

Obiettivo: trasformare i PDF in `manuals/` in una knowledge base strutturata,
ottimizzata per essere usata come fonte (RAG + estrazioni specializzate) per
privilegi, incantesimi, razze, mostri ecc.

Backend torch-free (questa macchina è Intel macOS x86_64, dove Miner/torch>=2.6
non hanno wheel): testo via `pdftext`, OCR via `pypdfium2` + Tesseract.

Flusso a 3 fasi (sottocomandi):

  1) probe    Analizza il layer di testo di ogni PDF e decide il metodo:
              - 'txt' se il testo incorporato è pulito e affidabile (veloce);
              - 'ocr' se il PDF è di fatto immagine / font cifrata (lento).
              Scrive un piano editabile in OUT/_plan.json.

  2) extract  Estrae ogni PDF secondo il piano.
              - method 'txt' -> pdftext (titoli dedotti dalla dimensione font);
              - method 'ocr' -> render pagina + Tesseract (lingua 'ita');
              - Lavora UN PDF alla volta, a BATCH di pagine (RAM-friendly su 8GB);
              - È RESUMABILE: salta i batch già completati (a meno di --force);
              - Output grezzo in OUT/<stem>/batch_<NNNNN>/<stem>/<method>/.

  3) index    Scansiona tutti i *_content_list.json e genera:
              - INDEX/chunks.jsonl   chunk RAG con gerarchia di heading + pagina;
              - INDEX/spells.json    incantesimi (grammatica blocco 5e italiano);
              - INDEX/sections.json  albero dei titoli per manuale;
              - INDEX/manifest.json  riepilogo.

  all         probe -> extract -> index.

Esempi:
  python tools/extract_manuals.py probe
  python tools/extract_manuals.py extract --only "Xanathar"        # testo, veloce
  python tools/extract_manuals.py extract --only "Manuale dei Mostri"  # OCR
  python tools/extract_manuals.py extract                          # tutti, dal piano
  python tools/extract_manuals.py index
  python tools/extract_manuals.py all

Prerequisiti OCR (solo per i PDF immagine):
  brew install tesseract tesseract-lang
  ~/miniconda3/bin/python -m pip install pytesseract pillow
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ----------------------------------------------------------------------------
# Percorsi e configurazione di default
# ----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = ROOT / "manuals"
OUT_DIR = ROOT / "manuals" / "_extracted"   # output grezzo (content_list per batch)
INDEX_DIR = ROOT / "manuals" / "_index"     # output strutturato

PYTHON_BIN = sys.executable

DEFAULT_BATCH = 40          # pagine per batch (RAM-friendly)
PROBE_SAMPLE = 12           # pagine campionate nel probe
TXT_MIN_AVG = 5             # soglia: hit medi/parola per considerare 'txt'
TXT_MIN_COVERAGE = 0.7      # frazione minima di pagine "leggibili" per 'txt'

# Parole italiane frequenti nei manuali: segnale di testo reale (non cifrato).
ITALIAN_MARKERS = re.compile(
    r"\b("
    r"di|il|la|che|un|una|per|con|del|della|nel|come|"
    r"incantesim\w*|livello|azione|bonus|tiro|salvezza|dado|danni|"
    r"creatura|punti|ferita|riposo|privilegi\w*|competenz\w*|"
    r"personaggio|round|metri|velocit\w*|attacco|armatura"
    r")\b",
    re.IGNORECASE,
)


# ----------------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"[extract] {msg}", flush=True)


def find_pdfs() -> list[Path]:
    return sorted(p for p in MANUALS_DIR.glob("*.pdf"))


def pdf_page_count(pdf: Path) -> int:
    import pypdf
    return len(pypdf.PdfReader(str(pdf)).pages)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w]+", "_", name, flags=re.UNICODE).strip("_")
    return s or "manual"


# ----------------------------------------------------------------------------
# FASE 1 — PROBE
# ----------------------------------------------------------------------------

@dataclass
class ProbeResult:
    pdf: str
    pages: int
    avg_hits: float
    coverage: float
    method: str          # 'txt' | 'ocr'
    lang: str = "ita"

    def to_dict(self) -> dict:
        return {
            "pdf": self.pdf,
            "pages": self.pages,
            "avg_hits": round(self.avg_hits, 2),
            "coverage": round(self.coverage, 2),
            "method": self.method,
            "lang": self.lang,
        }


def probe_pdf(pdf: Path, sample: int = PROBE_SAMPLE) -> ProbeResult:
    import pypdf

    reader = pypdf.PdfReader(str(pdf))
    n = len(reader.pages)
    if n == 0:
        return ProbeResult(pdf.name, 0, 0.0, 0.0, "ocr")

    # Campiona pagine distribuite uniformemente, saltando le prime/ultime
    # (copertine/indici spesso vuoti o atipici).
    lo, hi = int(n * 0.05), int(n * 0.95)
    hi = max(hi, lo + 1)
    idxs = sorted({int(lo + (hi - lo) * i / max(sample - 1, 1)) for i in range(sample)})

    total_hits = 0
    readable_pages = 0
    sampled = 0
    for i in idxs:
        if i >= n:
            continue
        sampled += 1
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            text = ""
        hits = len(ITALIAN_MARKERS.findall(text))
        total_hits += hits
        if hits >= 3:
            readable_pages += 1

    avg = total_hits / sampled if sampled else 0.0
    coverage = readable_pages / sampled if sampled else 0.0
    method = "txt" if (avg >= TXT_MIN_AVG and coverage >= TXT_MIN_COVERAGE) else "ocr"
    return ProbeResult(pdf.name, n, avg, coverage, method)


def cmd_probe(args) -> dict:
    pdfs = find_pdfs()
    if not pdfs:
        log(f"Nessun PDF in {MANUALS_DIR}")
        return {}

    results = [probe_pdf(p) for p in pdfs]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = {r.pdf: r.to_dict() for r in results}
    plan_path = OUT_DIR / "_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"Piano scritto in {plan_path}")
    print()
    print(f"{'MANUALE':46} {'PAG':>5} {'AVG':>6} {'COV':>5}  METODO")
    print("-" * 74)
    for r in results:
        print(f"{r.pdf[:46]:46} {r.pages:5} {r.avg_hits:6.1f} {r.coverage:5.2f}  {r.method.upper()}")
    print()
    log("Modifica _plan.json per forzare manualmente 'txt'/'ocr' se necessario.")
    return plan


def load_plan() -> dict:
    plan_path = OUT_DIR / "_plan.json"
    if plan_path.exists():
        return json.loads(plan_path.read_text(encoding="utf-8"))
    return {}


# ----------------------------------------------------------------------------
# FASE 2 — EXTRACT  (torch-free: pdftext per il testo, Tesseract per l'OCR)
# ----------------------------------------------------------------------------
#
# Nota: MinerU 3.x non è utilizzabile su questa macchina (Intel macOS x86_64):
# il suo backend 'pipeline' richiede torch>=2.6, che non ha più wheel per questa
# piattaforma. Usiamo quindi un percorso senza torch che produce lo STESSO
# formato `<stem>_content_list.json` consumato dalla fase di index:
#   - method 'txt' -> pdftext (estrae span con font-size; i titoli si deducono
#     dalla dimensione del carattere rispetto al corpo del testo);
#   - method 'ocr' -> render pagina con pypdfium2 + Tesseract (lingua 'ita'),
#     raggruppando le parole in righe/blocchi e deducendo i titoli dall'altezza.

def batch_dir(stem: str, start: int) -> Path:
    return OUT_DIR / stem / f"batch_{start:05d}"


def content_list_path(stem: str, start: int, method: str) -> Path:
    d = batch_dir(stem, start) / stem / method
    return d / f"{stem}_content_list.json"


def batch_done(stem: str, start: int, method: str) -> bool:
    """Un batch è completo se è stato scritto il content_list.json."""
    return content_list_path(stem, start, method).exists()


def write_content_list(stem: str, start: int, method: str,
                       items: list[dict]) -> None:
    p = content_list_path(stem, start, method)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def _line_text(line: dict) -> str:
    return "".join(s.get("text", "") for s in line.get("spans", [])).strip()


def _line_size(line: dict) -> float:
    sizes = [s.get("font", {}).get("size", 0) or 0 for s in line.get("spans", [])]
    return max(sizes) if sizes else 0.0


def _line_bold(line: dict) -> bool:
    for s in line.get("spans", []):
        if (s.get("font", {}).get("weight", 0) or 0) >= 600:
            return True
    return False


def _heading_level(size: float, body: float, bold: bool) -> Optional[int]:
    """Deduci un text_level (1..3) dalla dimensione relativa del carattere."""
    if body <= 0:
        return None
    ratio = size / body
    if ratio >= 1.6:
        return 1
    if ratio >= 1.3:
        return 2
    if ratio >= 1.15 or (bold and ratio >= 1.08):
        return 3
    return None


def extract_txt_batch(pdf: Path, start: int, end: int) -> list[dict]:
    """Estrae blocchi/testo via pdftext. page_idx è relativo al batch."""
    from pdftext.extraction import dictionary_output
    pages = dictionary_output(str(pdf), page_range=list(range(start, end + 1)),
                              sort=True)
    items: list[dict] = []
    for rel_idx, pg in enumerate(pages):
        lines = []
        for block in pg.get("blocks", []):
            for line in block.get("lines", []):
                txt = _line_text(line)
                if txt:
                    lines.append((txt, _line_size(line), _line_bold(line)))
        if not lines:
            continue
        # dimensione "corpo" = mediana delle dimensioni di riga
        sizes = sorted(s for _, s, _ in lines)
        body = sizes[len(sizes) // 2] if sizes else 0.0
        for txt, size, bold in lines:
            lvl = _heading_level(size, body, bold)
            # i titoli sono righe brevi; evita di promuovere paragrafi lunghi
            if lvl is not None and len(txt) > 90:
                lvl = None
            item = {"type": "title" if lvl else "text", "text": txt,
                    "page_idx": rel_idx}
            if lvl:
                item["text_level"] = lvl
            items.append(item)
    return items


def extract_ocr_batch(pdf: Path, start: int, end: int, lang: str,
                      dpi: int) -> list[dict]:
    """Render + Tesseract. Raggruppa le parole in righe per block/par/line."""
    import pypdfium2 as pdfium
    import pytesseract
    from pytesseract import Output
    from PIL import Image

    doc = pdfium.PdfDocument(str(pdf))
    scale = dpi / 72.0
    items: list[dict] = []
    try:
        for rel_idx, page_no in enumerate(range(start, end + 1)):
            if page_no >= len(doc):
                break
            page = doc[page_no]
            bitmap = page.render(scale=scale)
            pil: Image.Image = bitmap.to_pil()
            data = pytesseract.image_to_data(pil, lang=lang,
                                             output_type=Output.DICT)
            # raggruppa le parole per (block, par, line)
            lines: dict[tuple, dict] = {}
            n = len(data["text"])
            for k in range(n):
                word = (data["text"][k] or "").strip()
                if not word:
                    continue
                try:
                    conf = float(data["conf"][k])
                except (ValueError, TypeError):
                    conf = -1
                if conf < 30:
                    continue
                key = (data["block_num"][k], data["par_num"][k],
                       data["line_num"][k])
                ln = lines.setdefault(key, {"words": [], "h": 0})
                ln["words"].append(word)
                ln["h"] = max(ln["h"], data["height"][k])
            if not lines:
                continue
            ordered = [lines[k] for k in sorted(lines.keys())]
            heights = sorted(l["h"] for l in ordered)
            body_h = heights[len(heights) // 2] if heights else 0
            for ln in ordered:
                txt = " ".join(ln["words"]).strip()
                if not txt:
                    continue
                lvl = _heading_level(ln["h"], body_h, False)
                if lvl is not None and len(txt) > 90:
                    lvl = None
                item = {"type": "title" if lvl else "text", "text": txt,
                        "page_idx": rel_idx}
                if lvl:
                    item["text_level"] = lvl
                items.append(item)
            page.close()
    finally:
        doc.close()
    return items


def check_ocr_available() -> Optional[str]:
    """Ritorna None se l'OCR è pronto, altrimenti un messaggio d'aiuto."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return ("pytesseract non installato. Esegui: "
                "~/miniconda3/bin/python -m pip install pytesseract pillow")
    try:
        import pytesseract
        langs = pytesseract.get_languages(config="")
    except Exception as e:
        return (f"Tesseract non trovato ({e}). Installa con: "
                "brew install tesseract tesseract-lang")
    if "ita" not in langs:
        return ("Modello lingua 'ita' assente. Installa con: "
                "brew install tesseract-lang")
    return None


def extract_pdf(pdf: Path, method: str, lang: str, batch: int,
                dpi: int, force: bool, dry_run: bool,
                start_page: Optional[int], end_page: Optional[int]) -> None:
    stem = pdf.stem
    total = pdf_page_count(pdf)
    lo = start_page if start_page is not None else 0
    hi = end_page if end_page is not None else total - 1
    hi = min(hi, total - 1)

    if method == "ocr":
        err = check_ocr_available()
        if err:
            log(f"{pdf.name}: OCR non disponibile -> {err}")
            return

    log(f"{pdf.name}: {total} pagine, metodo={method.upper()}, batch={batch}, "
        f"range={lo}-{hi}" + (f", dpi={dpi}" if method == "ocr" else ""))

    b = lo
    while b <= hi:
        bend = min(b + batch - 1, hi)
        if batch_done(stem, b, method) and not force:
            log(f"  batch {b}-{bend}: già fatto, skip")
            b = bend + 1
            continue
        log(f"  batch {b}-{bend}: estrazione ({method})...")
        if dry_run:
            log(f"  (dry-run) -> {content_list_path(stem, b, method)}")
            b = bend + 1
            continue
        try:
            if method == "txt":
                items = extract_txt_batch(pdf, b, bend)
            else:
                items = extract_ocr_batch(pdf, b, bend, lang, dpi)
        except Exception as e:
            log(f"  batch {b}-{bend}: ERRORE ({e}). Mi fermo su questo PDF.")
            return
        write_content_list(stem, b, method, items)
        log(f"  batch {b}-{bend}: {len(items)} blocchi scritti.")
        b = bend + 1
    log(f"{pdf.name}: completato.")


def cmd_extract(args) -> None:
    pdfs = find_pdfs()
    if not pdfs:
        log(f"Nessun PDF in {MANUALS_DIR}")
        return

    plan = load_plan()
    if not plan:
        log("Nessun _plan.json: eseguo prima il probe.")
        plan = cmd_probe(args)

    if args.only:
        needle = args.only.lower()
        pdfs = [p for p in pdfs if needle in p.name.lower()]
        if not pdfs:
            log(f"Nessun PDF corrisponde a --only '{args.only}'")
            return

    for pdf in pdfs:
        entry = plan.get(pdf.name, {})
        method = args.method or entry.get("method", "ocr")
        lang = args.lang or "ita"
        extract_pdf(
            pdf, method=method, lang=lang, batch=args.batch,
            dpi=args.dpi, force=args.force, dry_run=args.dry_run,
            start_page=args.start, end_page=args.end,
        )


# ----------------------------------------------------------------------------
# FASE 3 — INDEX
# ----------------------------------------------------------------------------

# Etichette dei campi del blocco-incantesimo (5e, italiano).
SPELL_FIELDS = ["tempo di lancio", "gittata", "componenti", "durata"]

# Scuole di magia (italiano 5e) — usate per riconoscere la riga "scuola/livello".
SPELL_SCHOOLS = (
    "abiurazione", "ammaliamento", "divinazione", "evocazione",
    "illusione", "invocazione", "necromanzia", "trasmutazione",
)

# Riga scuola/livello dei manuali reali, es:
#   "Trasmutazione di 1° livello"  /  "Trucchetto di evocazione"
#   "Abiurazione di livello 3"     /  "Incantesimo di 2° livello"
RE_LEVEL = re.compile(
    r"(trucchetto(?:\s+di\s+\w+)?"
    r"|(?:" + "|".join(SPELL_SCHOOLS) + r")(?:\s+di)?(?:\s+\w+){0,3}\s+livello"
    r"|\d\s*[°ºo]?\s*livello"
    r"|livello\s+\d"
    r"|incantesimo\s+di\s+\d)",
    re.IGNORECASE,
)

# Una riga è "riga-scuola" se contiene una scuola, 'trucchetto' o 'livello'.
RE_SCHOOL_LINE = re.compile(
    r"\b(trucchetto|livello|" + "|".join(SPELL_SCHOOLS) + r")\b",
    re.IGNORECASE,
)

RE_FIELD = {
    # forma canonica + OCR senza spazio + fallback "Tempo X azione|..."
    "casting_time": re.compile(
        r"tempo\s*(?:di\s*lancio|dilancio)\s*[:.]?\s*([^\n]+)"
        r"|tempo\s+(\S{1,5}\s+(?:azione|reazione|minut|ora|bonus|round)[^\n]*)",
        re.IGNORECASE),
    "range":       re.compile(r"gittata\s*[:.]?\s*(.+)", re.IGNORECASE),
    "components":  re.compile(r"componenti\s*[:.]?\s*(.+)", re.IGNORECASE),
    "duration":    re.compile(r"durata\s*[:.]?\s*(.+)", re.IGNORECASE),
}


@dataclass
class Block:
    text: str
    level: Optional[int]   # text_level (heading) o None
    page: int
    btype: str             # 'text' | 'title' | 'table' | 'image' | 'equation' | ...


def load_content_lists() -> dict[str, list[Block]]:
    """
    Ritorna {nome_manuale: [Block,...]} aggregando tutti i batch di un PDF,
    ricostruendo il numero di pagina globale dall'offset del batch.
    """
    manuals: dict[str, list[Block]] = {}
    if not OUT_DIR.exists():
        return manuals

    # Cerca tutti i content_list, ovunque sotto _extracted/.
    for cl_path in sorted(OUT_DIR.rglob("*_content_list.json")):
        # path: _extracted/<stem>/batch_<start>/<stem>/<method>/<stem>_content_list.json
        offset = 0
        for part in cl_path.parts:
            m = re.fullmatch(r"batch_(\d+)", part)
            if m:
                offset = int(m.group(1))
                break
        # nome manuale = primo segmento sotto _extracted
        try:
            rel = cl_path.relative_to(OUT_DIR)
            stem = rel.parts[0]
        except ValueError:
            stem = cl_path.parent.name

        try:
            items = json.loads(cl_path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"  ! impossibile leggere {cl_path}: {e}")
            continue

        blocks = manuals.setdefault(stem, [])
        for it in items:
            if not isinstance(it, dict):
                continue
            btype = it.get("type", "text")
            text = (it.get("text") or "").strip()
            if btype == "table" and not text:
                text = (it.get("table_body") or "").strip()
            page = int(it.get("page_idx", 0)) + offset
            level = it.get("text_level")
            level = int(level) if isinstance(level, int) else None
            if not text and btype not in ("image", "table"):
                continue
            blocks.append(Block(text=text, level=level, page=page, btype=btype))

    # Ordina i blocchi di ciascun manuale per pagina (i batch arrivano sparsi).
    for stem in manuals:
        manuals[stem].sort(key=lambda b: b.page)
    return manuals


def pretty_manual_name(stem: str) -> str:
    # I batch usano lo stem del file; ripuliamo per leggibilità.
    return stem.replace("_", " ").strip()


# ---- Chunking RAG -----------------------------------------------------------

def build_chunks(stem: str, blocks: list[Block], max_chars: int = 1200) -> list[dict]:
    chunks: list[dict] = []
    heading_stack: list[tuple[int, str]] = []
    buf: list[str] = []
    buf_pages: list[int] = []
    source = pretty_manual_name(stem)
    cid = 0

    def flush():
        nonlocal cid, buf, buf_pages
        text = "\n".join(buf).strip()
        if not text:
            buf, buf_pages = [], []
            return
        chunks.append({
            "id": f"{slugify(source)}::{cid:05d}",
            "source": source,
            "page_start": min(buf_pages) if buf_pages else None,
            "page_end": max(buf_pages) if buf_pages else None,
            "heading_path": [h for _, h in heading_stack],
            "text": text,
            "n_chars": len(text),
        })
        cid += 1
        buf, buf_pages = [], []

    for b in blocks:
        if b.level is not None:
            # nuovo heading: chiudi il chunk corrente e aggiorna lo stack
            flush()
            while heading_stack and heading_stack[-1][0] >= b.level:
                heading_stack.pop()
            heading_stack.append((b.level, b.text))
            continue
        chunk_text = b.text if b.btype != "table" else f"\n{b.text}\n"
        buf.append(chunk_text)
        buf_pages.append(b.page)
        if sum(len(x) for x in buf) >= max_chars:
            flush()
    flush()
    return chunks


# ---- Estrazione incantesimi -------------------------------------------------

RE_ANCHOR = re.compile(
    # forma canonica (anche con OCR senza spazio): "tempo di lancio: ..."
    r"tempo\s*(?:di\s*lancio|dilancio)\b"
    r"|"
    # forma OCR rotta: "Tempo X azione|reazione|..." dove X è breve
    r"tempo\s+\S{1,5}\s+(?:azione|reazione|minut|ora|bonus|round)",
    re.IGNORECASE)
RE_HAS_DURATA = re.compile(r"\bdurata\b", re.IGNORECASE)

# Parole/etichette che un vero nome di incantesimo non contiene.
# NOTA: 'incantesim' deve essere parola intera per non scartare 'CONTROINCANTESIMO'.
RE_NAME_REJECT = re.compile(
    r"(tempo di lancio|gittata|componenti|\bdurata\b|\bincantesim[oi]?\b|"
    r"^elenco|^degli\b|^lista\b)", re.IGNORECASE)


def is_valid_spell_name(text: str) -> bool:
    """Euristica: un nome plausibile è breve, non è un'etichetta/frammento.
    Accetta sia MAIUSCOLO (Xanathar) sia Title Case (altri manuali)."""
    t = (text or "").strip()
    if not (0 < len(t) <= 50) or "\n" in t:
        return False
    if RE_NAME_REJECT.search(t):
        return False
    if t.endswith((".", ",", ";", ":")):       # frammento di frase
        return False
    if len(t.split()) > 6:                       # i nomi sono brevi
        return False
    first = next((c for c in t if c.isalpha()), "")
    return first.isupper()                       # inizia con maiuscola


def parse_spell_fields(text: str) -> dict:
    out = {}
    for key, rx in RE_FIELD.items():
        m = rx.search(text)
        if m:
            val = (m.group(1) or (m.lastindex and m.group(m.lastindex)) or "").strip()
            # taglia alla prossima etichetta se più campi sono sulla stessa riga
            val = re.split(r"\s+(?:Gittata|Componenti|Durata|Tempo di lancio)\s*[:.]",
                           val, flags=re.IGNORECASE)[0].strip()
            out[key] = val.rstrip(". ").strip() or None
    return {k: v for k, v in out.items() if v}


def extract_spells(stem: str, blocks: list[Block]) -> list[dict]:
    """
    Ancora ogni incantesimo sulla riga "Tempo di lancio:" (primo campo canonico
    del blocco-stat 5e). Da lì raccoglie i 4 campi (anche se distribuiti su più
    blocchi, fino a trovare la 'Durata'), il nome (heading precedente più vicino)
    e la descrizione (blocchi tra la statline corrente e la statline successiva,
    escludendo nome+riga-scuola del prossimo incantesimo).
    """
    spells: list[dict] = []
    source = pretty_manual_name(stem)
    n = len(blocks)
    consumed = -1

    # Pre-calcola le posizioni di tutte le ancore "Tempo di lancio".
    anchor_positions = [k for k in range(n) if RE_ANCHOR.search(blocks[k].text)]

    for i in range(n):
        if i <= consumed:
            continue
        if not RE_ANCHOR.search(blocks[i].text):
            continue

        # 1) raccogli i blocchi della statline fino alla 'Durata' (max 6 blocchi).
        #    Non interrompere se il blocco è un sotto-campo (Gittata/Componenti/
        #    Durata) anche quando l'OCR gli ha assegnato un text_level.
        field_parts = [blocks[i].text]
        j = i + 1
        while j < n and not RE_HAS_DURATA.search(" ".join(field_parts)) and (j - i) <= 6:
            t = blocks[j].text
            is_field = bool(
                RE_FIELD["range"].search(t) or RE_FIELD["components"].search(t)
                or RE_FIELD["duration"].search(t) or RE_ANCHOR.search(t)
            )
            if blocks[j].level is not None and not is_field:
                break
            field_parts.append(t)
            j += 1
        joined = " ".join(field_parts)
        fields = parse_spell_fields(joined)
        if len(fields) < 2:
            continue

        # 2) riga "scuola/livello": cercala tra l'ancora e i ~4 blocchi precedenti.
        #    Nei manuali reali sta tra il NOME e "Tempo di lancio".
        #    Preferiamo il blocco che contiene una SCUOLA o 'trucchetto'; se il
        #    numero di livello è in un blocco adiacente, lo ricomponiamo.
        level_text = None
        school_idx = None
        RE_SCHOOL_WORD = re.compile(
            r"\b(trucchetto|" + "|".join(SPELL_SCHOOLS) + r")\b", re.IGNORECASE)
        for k in range(i - 1, max(i - 5, -1), -1):
            t = blocks[k].text.strip()
            if RE_SCHOOL_WORD.search(t) and len(t) <= 60:
                parts = [t]
                # ricomponi "... di 1° livello" se è spezzato sul blocco seguente
                if "livello" not in t.lower():
                    for m in (k + 1, k + 2):
                        if m < i and "livello" in blocks[m].text.lower() \
                                and len(blocks[m].text) <= 30:
                            parts.append(blocks[m].text.strip())
                            break
                level_text = " ".join(parts)
                level_text = re.sub(r"\s+", " ", level_text).replace(" °", "°").strip()
                school_idx = k
                break
        if level_text is None:  # fallback: qualunque riga con 'livello'
            for k in range(i - 1, max(i - 5, -1), -1):
                t = blocks[k].text.strip()
                if RE_SCHOOL_LINE.search(t) and len(t) <= 60:
                    level_text = t
                    school_idx = k
                    break

        # 3) nome = heading/riga breve subito PRIMA della riga-scuola
        #    (se non trovata, prima dell'ancora). Evita di prendere la riga-scuola
        #    VERA (cioè quella che ha anche 'livello'/'trucchetto', via RE_LEVEL).
        #    NB: RE_SCHOOL_LINE matcha anche nomi come 'ILLUSIONE MINORE' o
        #    'DIVINAZIONE', quindi qui usiamo RE_LEVEL, più specifico.
        name = None
        name_anchor = school_idx if school_idx is not None else i
        for k in range(name_anchor - 1, max(name_anchor - 6, -1), -1):
            if blocks[k].level is not None and not RE_LEVEL.search(blocks[k].text):
                cand = blocks[k].text.strip()
                if is_valid_spell_name(cand):
                    name = cand
                    break
        if name is None:
            for k in range(name_anchor - 1, max(name_anchor - 4, -1), -1):
                t = blocks[k].text.strip()
                if is_valid_spell_name(t) and not RE_LEVEL.search(t):
                    name = t
                    break

        # 4) descrizione: blocchi tra fine statline (j) e inizio del prossimo
        #    incantesimo. Cerchiamo il prossimo anchor "Tempo di lancio" e
        #    risaliamo per escludere nome+riga-scuola del prossimo spell.
        next_anchor = None
        for ap in anchor_positions:
            if ap > i:
                next_anchor = ap
                break
        if next_anchor is None:
            desc_end = min(j + 50, n)  # ultimo spell del manuale: prendi fino a ~50 blocchi
        else:
            # risali dal next_anchor per trovare la riga-scuola del prossimo spell
            ns_school = next_anchor
            for k in range(next_anchor - 1, max(next_anchor - 5, j - 1), -1):
                t = blocks[k].text.strip()
                if RE_SCHOOL_LINE.search(t) and len(t) <= 60:
                    ns_school = k
                    break
            # poi indietro per il nome (heading o riga breve)
            ns_name = ns_school
            for k in range(ns_school - 1, max(ns_school - 6, j - 1), -1):
                t = blocks[k].text.strip()
                if is_valid_spell_name(t) and not RE_LEVEL.search(t):
                    ns_name = k
                    break
            desc_end = ns_name

        desc: list[str] = []
        d = j
        while d < desc_end and d < n:
            t = blocks[d].text
            # salta blocchi tabella/immagine
            if blocks[d].btype in ("table", "image", "equation"):
                d += 1
                continue
            # evita doppioni della statline che possono finire qui
            if RE_ANCHOR.search(t) or RE_FIELD["duration"].search(t):
                d += 1
                continue
            desc.append(t)
            if sum(len(x) for x in desc) > 4000:
                break
            d += 1
        consumed = max(j, d) - 1

        spells.append({
            "name": (name or "").strip() or None,
            "source": source,
            "page": blocks[i].page,
            "level_text": level_text,
            "casting_time": fields.get("casting_time"),
            "range": fields.get("range"),
            "components": fields.get("components"),
            "duration": fields.get("duration"),
            "description": "\n".join(desc).strip() or None,
            "complete": len(fields) == 4 and bool(name),
        })
    return spells


# ---- Albero delle sezioni ---------------------------------------------------

def build_sections(stem: str, blocks: list[Block]) -> list[dict]:
    sections = []
    for b in blocks:
        if b.level is not None:
            sections.append({"level": b.level, "title": b.text, "page": b.page})
    return sections


def cmd_index(args) -> None:
    manuals = load_content_lists()
    if not manuals:
        log(f"Nessun output MinerU in {OUT_DIR}. Esegui prima 'extract'.")
        return

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    chunks_path = INDEX_DIR / "chunks.jsonl"
    spells_all: list[dict] = []
    sections_all: dict[str, list[dict]] = {}
    manifest: dict = {"manuals": {}, "totals": {}}

    n_chunks = 0
    with chunks_path.open("w", encoding="utf-8") as fh:
        for stem, blocks in sorted(manuals.items()):
            name = pretty_manual_name(stem)
            chunks = build_chunks(stem, blocks)
            for c in chunks:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
            n_chunks += len(chunks)

            spells = extract_spells(stem, blocks)
            spells_all.extend(spells)

            sections = build_sections(stem, blocks)
            sections_all[name] = sections

            pages = (max((b.page for b in blocks), default=-1) + 1)
            manifest["manuals"][name] = {
                "blocks": len(blocks),
                "chunks": len(chunks),
                "spells": len(spells),
                "sections": len(sections),
                "max_page": pages,
            }
            log(f"  {name}: {len(blocks)} blocchi -> {len(chunks)} chunk, "
                f"{len(spells)} incantesimi, {len(sections)} sezioni")

    (INDEX_DIR / "spells.json").write_text(
        json.dumps(spells_all, ensure_ascii=False, indent=2), encoding="utf-8")
    (INDEX_DIR / "sections.json").write_text(
        json.dumps(sections_all, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest["totals"] = {
        "manuals": len(manuals),
        "chunks": n_chunks,
        "spells": len(spells_all),
        "spells_complete": sum(1 for s in spells_all if s["complete"]),
    }
    (INDEX_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"Indice scritto in {INDEX_DIR}")
    log(f"  chunks.jsonl : {n_chunks} chunk")
    log(f"  spells.json  : {len(spells_all)} incantesimi "
        f"({manifest['totals']['spells_complete']} completi)")
    log(f"  sections.json: {sum(len(v) for v in sections_all.values())} titoli")


def cmd_all(args) -> None:
    cmd_probe(args)
    cmd_extract(args)
    cmd_index(args)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Estrazione manuali D&D 5e (pdftext + Tesseract) -> knowledge base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("probe", help="Analizza i PDF e scrivi il piano.")
    sp.set_defaults(func=cmd_probe)

    se = sub.add_parser("extract", help="Estrai testo/OCR secondo il piano.")
    se.add_argument("--only", help="Filtra i PDF per sottostringa del nome.")
    se.add_argument("--method", choices=["txt", "ocr"],
                    help="Forza il metodo (altrimenti dal piano).")
    se.add_argument("--lang", help="Lingua Tesseract per l'OCR (default: ita).")
    se.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                    help=f"Pagine per batch (default {DEFAULT_BATCH}).")
    se.add_argument("--dpi", type=int, default=200,
                    help="Risoluzione di render per l'OCR (default 200).")
    se.add_argument("--start", type=int, help="Pagina iniziale (0-based).")
    se.add_argument("--end", type=int, help="Pagina finale (0-based, inclusa).")
    se.add_argument("--force", action="store_true",
                    help="Riesegui anche i batch già completati.")
    se.add_argument("--dry-run", action="store_true",
                    help="Stampa cosa farebbe senza eseguire.")
    se.set_defaults(func=cmd_extract)

    si = sub.add_parser("index", help="Costruisci chunk + incantesimi + sezioni.")
    si.set_defaults(func=cmd_index)

    sa = sub.add_parser("all", help="probe -> extract -> index.")
    # eredita gli stessi argomenti di extract
    for action in se._actions:
        if action.dest in ("help",):
            continue
        sa._add_action(action)
    sa.set_defaults(func=cmd_all)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
