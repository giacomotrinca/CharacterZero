#!/usr/bin/env python3
"""
build_features.py
Genera web/data/features.json abbinando i dati canonici di classe/sottoclasse
con i testi reali estratti dai file PaddleOCR (manuals/_index/phb_ocr/).

Strategia:
  * Per ogni classe viene costruito un testo continuo dalle pagine OCR nel suo
    range di pagine (PDF index 0-based).
  * Per ogni privilegio canonico si cerca il nome nel testo (case-insensitive,
    normalizzato) e si estrae il testo dal match fino al privilegio successivo.
  * Solo le pagine della classe genitore vengono usate per le sottoclassi.
  * ASI e "Privilegio della <sottoclasse>" usano testi canonici.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OCR_DIR = ROOT / "manuals/_index/phb_ocr"
CHUNKS_FILE = ROOT / "manuals/_index/chunks.jsonl"
OUTPUT = ROOT / "web/data/features.json"

sys.path.insert(0, str(Path(__file__).parent))
from class_features_data import (
    CLASS_FEATURES, SUBCLASS_FEATURES, RACE_FEATURES, BACKGROUND_FEATURES
)

DATASET_VERSION = 6

# Range di pagine per classe [start, end) — PDF index 0-based, verificati sui file OCR.
CLASS_PDF_RANGE = {
    "barbaro":  (45, 50),
    "bardo":    (50, 55),
    "chierico": (55, 64),
    "druido":   (64, 70),
    "guerriero":(70, 76),
    "ladro":    (76, 80),
    "mago":     (80, 88),
    "monaco":   (88, 94),
    "paladino": (94, 102),
    "ranger":   (102, 106),
    "stregone": (106, 112),
    "warlock":  (112, 121),
}

# Mappa sottoclasse → classe genitore.
SUBCLASS_PARENT = {
    # Barbaro
    "Cammino del Berserker": "barbaro", "Cammino del Combattente Totemico": "barbaro",
    "Cammino del Combattente": "barbaro", "Cammino del Kensei": "barbaro",
    "Cammino della Bestia": "barbaro", "Cammino della Furia Combattente": "barbaro",
    "Cammino della Magia Selvaggia": "barbaro", "Cammino dello Zelota": "barbaro",
    # Bardo
    "Collegio della Sapienza": "bardo", "Collegio del Valore": "bardo",
    "Collegio dei Sussurri": "bardo", "Collegio dell Eloquenza": "bardo",
    "Collegio dell'Incanto": "bardo", "Collegio della Creazione": "bardo",
    "Collegio delle Spade": "bardo", "Collegio di Fochlucan": "bardo",
    "Collegio di Nuovo Olamn": "bardo",
    # Chierico
    "Dominio della Vita": "chierico", "Dominio della Luce": "chierico",
    "Dominio della Guerra": "chierico", "Dominio della Conoscenza": "chierico",
    "Dominio della Natura": "chierico", "Dominio della Tempesta": "chierico",
    "Dominio dell'Inganno": "chierico", "Dominio dell'Arcano": "chierico",
    "Dominio della Forgia": "chierico",
    # Druido
    "Circolo della Terra": "druido", "Circolo della Luna": "druido",
    "Circolo dei Sogni": "druido", "Circolo del Pastore": "druido",
    "Circolo della Fiamma": "druido", "Circolo delle Spore": "druido",
    "Circolo delle Stelle": "druido",
    # Guerriero
    "Campione": "guerriero", "Maestro di Battaglia": "guerriero",
    "Cavaliere Mistico": "guerriero", "Arciere Arcano": "guerriero",
    "Cavaliere Errante": "guerriero", "Samurai": "guerriero",
    "Cavaliere Runico": "guerriero", "Guerriero Psionico": "guerriero",
    # Ladro
    "Ladro": "ladro", "Assassino": "ladro", "Mistificatore Arcano": "ladro",
    "Esploratore": "ladro", "Indagatore": "ladro", "Pianificatore": "ladro",
    "Spadaccino": "ladro", "Fantasma": "ladro", "Lama Spirituale": "ladro",
    # Mago
    "Scuola di Abiurazione": "mago", "Scuola di Ammaliamento": "mago",
    "Scuola di Divinazione": "mago", "Scuola di Evocazione": "mago",
    "Scuola di Illusione": "mago", "Scuola di Invocazione": "mago",
    "Scuola di Necromanzia": "mago", "Scuola di Trasmutazione": "mago",
    "Magia della Guerra": "mago", "Canto della Lama": "mago",
    "Ordine degli Scribi": "mago",
    # Monaco
    "Via della Mano Aperta": "monaco", "Via dell'Ombra": "monaco",
    "Via dei Quattro Elementi": "monaco", "Via del Kensei": "monaco",
    "Via del Maestro Ubriaco": "monaco", "Via del Male": "monaco",
    "Via del Se Astrale": "monaco", "Via dell'Anima Solare": "monaco",
    "Via della Lunga Morte": "monaco", "Via della Misericordia Do": "monaco",
    # Paladino
    "Giuramento di Devozione": "paladino", "Giuramento degli Antichi": "paladino",
    "Giuramento di Vendetta": "paladino", "Giuramento della Corona": "paladino",
    "Giuramento delle Sentinelle": "paladino", "Giuramento di Conquista": "paladino",
    "Giuramento di Gloria": "paladino", "Giuramento di Inimicizia": "paladino",
    # Ranger
    "Cacciatore": "ranger", "Signore delle Bestie": "ranger",
    "Cacciatore delle Tenebre": "ranger", "Uccisore di Mostri": "ranger",
    "Custode degli Sciami": "ranger", "Viandante Fatato": "ranger",
    # Stregone
    "Discendenza Draconica": "stregone", "Magia Selvaggia": "stregone",
    "Anima Divina": "stregone", "Magia delle Ombre": "stregone",
    "Stregoneria della Tempesta": "stregone", "Anima Meccanica": "stregone",
    "Mente Aberrante": "stregone",
    # Warlock
    "L'Immondo": "warlock", "Il Grande Antico": "warlock",
    "Il Signore Fatato": "warlock", "Il Celestiale": "warlock",
    "La Lama del Sortilegio": "warlock", "Il Genio": "warlock",
    "L'Insondabile": "warlock",
    # Artefice (Tasha)
    "Alchimista": "artefice", "Artigliere": "artefice",
    "Forgia di Battaglia": "artefice", "Armaiolo": "artefice",
}

ASI_DESC = (
    "Puoi aumentare di 2 un punteggio di caratteristica a tua scelta, oppure "
    "di 1 due punteggi di caratteristica a tua scelta. Con questo privilegio "
    "non puoi portare un punteggio di caratteristica sopra il 20. In "
    "alternativa, puoi scegliere un talento."
)

SUBCLASS_GRANT_PREFIXES = (
    "privilegio del", "privilegio della", "privilegio dell",
)


# ─────────────────────────────────────────────────────────────────────────────
# Testo OCR per range di pagine
# ─────────────────────────────────────────────────────────────────────────────

_page_cache: dict[int, str] = {}


def load_page(idx: int) -> str:
    if idx in _page_cache:
        return _page_cache[idx]
    path = OCR_DIR / f"page_{idx:03d}.json"
    if not path.exists():
        return ""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    text = data.get("reading_text", "")
    _page_cache[idx] = text
    return text


def class_text(cls: str) -> str:
    if cls not in CLASS_PDF_RANGE:
        return ""
    lo, hi = CLASS_PDF_RANGE[cls]
    parts = []
    for idx in range(lo, hi):
        t = load_page(idx)
        if t:
            parts.append(t)
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Chunks Tasha / Xanathar / SCAG per descrizioni di sottoclassi/classi non-PHB
# ─────────────────────────────────────────────────────────────────────────────

# Mappa il "source" dei chunks → manual id usato in catalog.json
SOURCE_TO_MANUAL_ID = {
    "tasha italiano": "tasha_italiano",
    "Guida Omnicomprensiva di Xanathar 5e": "guida_omnicomprensiva_di_xanathar_5e",
    "D&D 5th Guida degli Avventurieri alla Costa della Spada":
        "d_d_5th_guida_degli_avventurieri_alla_costa_della_spada",
    "D&D 5th Manuale del Giocatore": "d_d_5th_manuale_del_giocatore",
}

# Sottoclassi non-PHB: in quale manuale cercare. Se non presente qui, fallback a PHB.
SUBCLASS_SOURCE = {
    # Tasha — sottoclassi nuove
    "Cammino del Combattente": "tasha italiano",
    "Cammino della Bestia": "tasha italiano",
    "Cammino della Magia Selvaggia": "tasha italiano",
    "Collegio della Creazione": "tasha italiano",
    "Collegio dell'Eloquenza": "tasha italiano",
    "Dominio dell'Arcano": "tasha italiano",  # Xanathar Arcana actually
    "Dominio della Forgia": "tasha italiano",
    "Circolo delle Spore": "tasha italiano",
    "Circolo delle Stelle": "tasha italiano",
    "Guerriero Psionico": "tasha italiano",
    "Cavaliere Runico": "tasha italiano",
    "Fantasma": "tasha italiano",
    "Lama Spirituale": "tasha italiano",
    "Pianificatore": "tasha italiano",
    "Ordine degli Scribi": "tasha italiano",
    "Via della Misericordia Do": "tasha italiano",
    "Via del Se Astrale": "tasha italiano",
    "Giuramento di Gloria": "tasha italiano",
    "Custode degli Sciami": "tasha italiano",
    "Viandante Fatato": "tasha italiano",
    "Anima Meccanica": "tasha italiano",
    "Mente Aberrante": "tasha italiano",
    "Il Genio": "tasha italiano",
    "L'Insondabile": "tasha italiano",
    # Xanathar — sottoclassi
    "Cammino del Combattente Totemico": "Guida Omnicomprensiva di Xanathar 5e",
    "Cammino dello Zelota": "Guida Omnicomprensiva di Xanathar 5e",
    "Collegio dei Sussurri": "Guida Omnicomprensiva di Xanathar 5e",
    "Collegio del Valore": "Guida Omnicomprensiva di Xanathar 5e",
    "Dominio della Tempesta": "Guida Omnicomprensiva di Xanathar 5e",
    "Circolo dei Sogni": "Guida Omnicomprensiva di Xanathar 5e",
    "Circolo del Pastore": "Guida Omnicomprensiva di Xanathar 5e",
    "Arciere Arcano": "Guida Omnicomprensiva di Xanathar 5e",
    "Cavaliere Errante": "Guida Omnicomprensiva di Xanathar 5e",
    "Samurai": "Guida Omnicomprensiva di Xanathar 5e",
    "Esploratore": "Guida Omnicomprensiva di Xanathar 5e",
    "Indagatore": "Guida Omnicomprensiva di Xanathar 5e",
    "Magia della Guerra": "Guida Omnicomprensiva di Xanathar 5e",
    "Via del Kensei": "Guida Omnicomprensiva di Xanathar 5e",
    "Via del Maestro Ubriaco": "Guida Omnicomprensiva di Xanathar 5e",
    "Via del Male": "Guida Omnicomprensiva di Xanathar 5e",
    "Via dell'Anima Solare": "Guida Omnicomprensiva di Xanathar 5e",
    "Via della Lunga Morte": "Guida Omnicomprensiva di Xanathar 5e",
    "Giuramento della Corona": "Guida Omnicomprensiva di Xanathar 5e",
    "Giuramento delle Sentinelle": "Guida Omnicomprensiva di Xanathar 5e",
    "Giuramento di Conquista": "Guida Omnicomprensiva di Xanathar 5e",
    "Cacciatore delle Tenebre": "Guida Omnicomprensiva di Xanathar 5e",
    "Uccisore di Mostri": "Guida Omnicomprensiva di Xanathar 5e",
    "Anima Divina": "Guida Omnicomprensiva di Xanathar 5e",
    "Magia delle Ombre": "Guida Omnicomprensiva di Xanathar 5e",
    "Stregoneria della Tempesta": "Guida Omnicomprensiva di Xanathar 5e",
    "Il Signore Fatato": "Guida Omnicomprensiva di Xanathar 5e",
    "Il Celestiale": "Guida Omnicomprensiva di Xanathar 5e",
    "Collegio di Fochlucan": "Guida Omnicomprensiva di Xanathar 5e",
    "Collegio di Nuovo Olamn": "Guida Omnicomprensiva di Xanathar 5e",
    "Giuramento di Inimicizia": "Guida Omnicomprensiva di Xanathar 5e",
    # SCAG — Canto della Lama (Bladesinger) e altre
    "Canto della Lama": "D&D 5th Guida degli Avventurieri alla Costa della Spada",
    "Spadaccino": "D&D 5th Guida degli Avventurieri alla Costa della Spada",
    "La Lama del Sortilegio": "D&D 5th Guida degli Avventurieri alla Costa della Spada",
    "Collegio delle Spade": "Guida Omnicomprensiva di Xanathar 5e",
    "Discendenza Draconica": "D&D 5th Manuale del Giocatore",  # PHB ma usa fallback chunks
    # Artefice subclasses (Tasha)
    "Alchimista": "tasha italiano",
    "Artigliere": "tasha italiano",
    "Forgia di Battaglia": "tasha italiano",
    "Armaiolo": "tasha italiano",
}

_chunks_by_source: dict[str, str] | None = None


def _load_chunks_text():
    """Concatena tutto il testo dei chunks per ogni manuale (lazy)."""
    global _chunks_by_source
    if _chunks_by_source is not None:
        return _chunks_by_source
    out: dict[str, list[str]] = {}
    if not CHUNKS_FILE.exists():
        _chunks_by_source = {}
        return _chunks_by_source
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = j.get("source", "")
            if not src:
                continue
            out.setdefault(src, []).append(j.get("text", ""))
    _chunks_by_source = {k: "\n".join(v) for k, v in out.items()}
    return _chunks_by_source


def chunks_text_for(source_name: str) -> str:
    return _load_chunks_text().get(source_name, "")


# ─────────────────────────────────────────────────────────────────────────────
# Normalizzazione e ricerca
# ─────────────────────────────────────────────────────────────────────────────

def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_text(text: str, max_len: int = 800) -> str:
    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    # Rimuovi artefatti comuni OCR (numeri di pagina isolati, header)
    text = re.sub(r"\bCAPITOLO\s+\d+\s*\|?\s*CLASSI\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    idx = cut.rfind(".")
    if idx > max_len // 2:
        return cut[:idx + 1]
    return cut.rstrip() + "…"


def canonical_override(name: str) -> str | None:
    n = norm(name)
    if n == "aumento dei punteggi di caratteristica":
        return ASI_DESC
    for pref in SUBCLASS_GRANT_PREFIXES:
        if n.startswith(norm(pref)):
            return (
                "Ottieni un privilegio concesso dalla tua sottoclasse al "
                "livello indicato. Consulta la voce della sottoclasse per i dettagli."
            )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Estrazione descrizioni dalla classe
# ─────────────────────────────────────────────────────────────────────────────

_TABLE_LINE_RE = re.compile(r"^[\d\+\-°©\s/]+$")


def _is_prose_context(lines: list[str], idx: int, lookahead: int = 3) -> bool:
    """Restituisce True se le righe successive al match sembrano prosa (non tabella)."""
    next_lines = [l.strip() for l in lines[idx + 1:idx + 1 + lookahead] if l.strip()]
    if not next_lines:
        return False
    # Se la maggioranza delle prossime righe sono corte/numeriche → tabella
    prose_count = sum(1 for l in next_lines if len(l) > 15 and not _TABLE_LINE_RE.match(l))
    return prose_count >= len(next_lines) // 2 + 1


def extract_descs(features: list, text: str) -> dict[str, str]:
    """
    Per ogni privilegio in `features`, trova il nome come riga isolata nel
    testo OCR (i titoli dei privilegi sono spesso ALL CAPS o bold → riga propria)
    e restituisce il testo fino al privilegio successivo.

    Preferisce match in contesto-prosa (non tabelle) iterando su tutte le occorrenze.
    """
    lines = text.split('\n')
    norm_lines = [norm(l) for l in lines]

    def find_line_idx(name: str) -> int | None:
        n = norm(name)
        if not n:
            return None
        candidates = []
        # Passata 1: match esatto su riga normalizzata
        for i, nl in enumerate(norm_lines):
            if nl == n:
                candidates.append(i)
        # Passata 2: la riga inizia con il nome (heading con continuazione)
        if not candidates:
            for i, nl in enumerate(norm_lines):
                if nl.startswith(n + " ") or nl.startswith(n + ","):
                    candidates.append(i)
        if not candidates:
            return None
        # Preferisce il match con contesto-prosa
        for c in candidates:
            if _is_prose_context(lines, c):
                return c
        return candidates[-1]  # Fallback: ultimo match

    # Raccoglie posizioni (indice riga) per ogni feature trovata
    hits: list[tuple[int, str]] = []
    for feat in features:
        name = feat["name"]
        if canonical_override(name) is not None:
            continue
        idx = find_line_idx(name)
        if idx is not None:
            hits.append((idx, name))
    hits.sort()

    out: dict[str, str] = {}
    for i, (line_idx, name) in enumerate(hits):
        nxt_line = hits[i + 1][0] if i + 1 < len(hits) else len(lines)
        # Il testo parte dalla riga dopo il titolo fino al prossimo titolo
        snippet_lines = lines[line_idx + 1:nxt_line]
        snippet = " ".join(l.strip() for l in snippet_lines if l.strip())
        # Rimuovi artefatti OCR comuni
        snippet = re.sub(r"\bCAPITOLO\s+\d+\s*[|/]?\s*CLASSI\b", "", snippet, flags=re.IGNORECASE)
        snippet = re.sub(r"Offrimi un caff[eè][^\n]*paypal\.me/\S*", "", snippet, flags=re.IGNORECASE)
        snippet = re.sub(r"\s{2,}", " ", snippet).strip()
        out[name] = clean_text(snippet) if len(snippet) > 20 else ""
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────

def build_class_features() -> dict:
    # Per classi PHB usa l'OCR PHB; come fallback, prova chunks del PHB
    phb_chunks = chunks_text_for("D&D 5th Manuale del Giocatore")
    result = {}
    for cls, features in CLASS_FEATURES.items():
        text = class_text(cls)
        descs = extract_descs(features, text) if text else {}
        # Per Artefice (non in PHB) usa chunks Tasha
        if cls == "artefice":
            tasha_chunks = chunks_text_for("tasha italiano")
            descs = extract_descs(features, tasha_chunks) if tasha_chunks else {}
        # Fallback chunks PHB per features non trovate
        descs_fb = extract_descs(features, phb_chunks) if (cls != "artefice" and phb_chunks) else {}
        out = []
        for feat in features:
            name = feat["name"]
            desc = canonical_override(name)
            if desc is None:
                desc = descs.get(name) or descs_fb.get(name) or ""
            out.append({"name": name, "level": feat["level"], "desc": desc or ""})
        out.sort(key=lambda x: (x["level"], x["name"]))
        result[cls] = out
    return result


def build_subclass_features() -> dict:
    result = {}
    for sub, features in SUBCLASS_FEATURES.items():
        # Sorgente primaria: chunks del manuale assegnato, fallback su PHB OCR
        chunk_src = SUBCLASS_SOURCE.get(sub)
        text_primary = chunks_text_for(chunk_src) if chunk_src else ""
        parent = SUBCLASS_PARENT.get(sub)
        text_phb = class_text(parent) if parent else ""

        descs_primary = extract_descs(features, text_primary) if text_primary else {}
        descs_phb = extract_descs(features, text_phb) if text_phb else {}

        out = []
        for feat in features:
            name = feat["name"]
            desc = canonical_override(name)
            if desc is None:
                # Priorità: chunks del manuale specifico > PHB OCR
                desc = descs_primary.get(name) or descs_phb.get(name) or ""
            out.append({"name": name, "level": feat["level"], "desc": desc or ""})
        out.sort(key=lambda x: x["level"])
        result[sub] = out
    return result


def build_race_features() -> dict:
    return {
        race: [{"name": f["name"], "desc": f.get("desc", "")} for f in feats]
        for race, feats in RACE_FEATURES.items()
    }


def build_background_features() -> dict:
    return {
        bg: [{"name": f["name"], "desc": f.get("desc", "")} for f in feats]
        for bg, feats in BACKGROUND_FEATURES.items()
    }


def main():
    if not OCR_DIR.exists():
        print(f"[features] ERRORE: {OCR_DIR} non trovata. Esegui prima run_phb_ocr_batch.py.")
        sys.exit(1)

    pages_found = len(list(OCR_DIR.glob("page_*.json")))
    print(f"[features] Pagine OCR disponibili: {pages_found}")

    print("[features] Build privilegi classe…")
    class_features = build_class_features()
    print("[features] Build privilegi sottoclasse…")
    subclass_features = build_subclass_features()
    race_features = build_race_features()
    background_features = build_background_features()

    def coverage(d):
        tot = sum(len(v) for v in d.values())
        withdesc = sum(1 for v in d.values() for f in v if f["desc"])
        return withdesc, tot

    cw, ct = coverage(class_features)
    sw, st = coverage(subclass_features)
    print(f"[features] Privilegi classe:      {cw}/{ct} con descrizione")
    print(f"[features] Privilegi sottoclasse: {sw}/{st} con descrizione")

    output = {
        "__v": DATASET_VERSION,
        "class_features": class_features,
        "subclass_features": subclass_features,
        "race_features": race_features,
        "background_features": background_features,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[features] Scritto {OUTPUT} (v{DATASET_VERSION})")


if __name__ == "__main__":
    main()
