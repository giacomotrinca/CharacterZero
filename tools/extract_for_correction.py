#!/usr/bin/env python3
"""
extract_for_correction.py — Prepara dati di confronto per agente AI di correzione.

Obiettivo: produrre file intermedi che un agente AI possa consumare per correggere
le descrizioni degli incantesimi e dei privilegi nei dataset di produzione
(web/data/spells.json, web/data/features.json).

Strategia:
  1) Ricostruisce il testo pagina-per-pagina dai content_list.json già estratti
     (nessuna riesecuzione di OCR/pdftext).
  2) Allinea ogni entry di web/data/spells.json con il testo grezzo delle pagine
     del manuale di origine.
  3) Allinea ogni privilegio di web/data/features.json con le pagine OCR della
     classe di appartenenza nel PHB.

Output (sotto manuals/_index/):
  pages/<manual>.jsonl         — una riga JSON per pagina: {source, page, text}
  spell_context.json           — allineamento incantesimi: {name, source, pages, current, raw_pages, online_ref}
  feature_context.json         — allineamento privilegi: {type, class, subclass?, name, level, current, source, pages, raw_pages}

Usage:
  python3 tools/extract_for_correction.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACTED = ROOT / "manuals" / "_extracted"
INDEX = ROOT / "manuals" / "_index"
PAGES_DIR = INDEX / "pages"
WEB_DATA = ROOT / "web" / "data"

SOURCE_LOOKUP = {
    "D&D 5th Manuale del Giocatore": "Manuale del Giocatore",
    "Guida Omnicomprensiva di Xanathar 5e": "Guida di Xanathar",
    "tasha italiano": "Calderone di Tasha",
    "D&D 5th Guida degli Avventurieri alla Costa della Spada": "Guida degli Avventurieri",
    "D&D 5th Manuale del Master": "Manuale del Master",
    "D&D 5th Manuale dei Mostri": "Manuale dei Mostri",
}

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

SUBCLASS_PARENT = {
    "Cammino del Berserker": "barbaro", "Cammino del Combattente Totemico": "barbaro",
    "Cammino del Combattente": "barbaro", "Cammino del Kensei": "barbaro",
    "Cammino della Bestia": "barbaro", "Cammino della Furia Combattente": "barbaro",
    "Cammino della Magia Selvaggia": "barbaro", "Cammino dello Zelota": "barbaro",
    "Collegio della Sapienza": "bardo", "Collegio del Valore": "bardo",
    "Collegio dei Sussurri": "bardo", "Collegio dell Eloquenza": "bardo",
    "Collegio dell'Incanto": "bardo", "Collegio della Creazione": "bardo",
    "Collegio delle Spade": "bardo", "Collegio di Fochlucan": "bardo",
    "Collegio di Nuovo Olamn": "bardo",
    "Dominio della Vita": "chierico", "Dominio della Luce": "chierico",
    "Dominio della Guerra": "chierico", "Dominio della Conoscenza": "chierico",
    "Dominio della Natura": "chierico", "Dominio della Tempesta": "chierico",
    "Dominio dell'Inganno": "chierico", "Dominio dell'Arcano": "chierico",
    "Dominio della Forgia": "chierico",
    "Circolo della Terra": "druido", "Circolo della Luna": "druido",
    "Circolo dei Sogni": "druido", "Circolo del Pastore": "druido",
    "Circolo della Fiamma": "druido", "Circolo delle Spore": "druido",
    "Circolo delle Stelle": "druido",
    "Campione": "guerriero", "Maestro di Battaglia": "guerriero",
    "Cavaliere Mistico": "guerriero", "Arciere Arcano": "guerriero",
    "Cavaliere Errante": "guerriero", "Samurai": "guerriero",
    "Cavaliere Runico": "guerriero", "Guerriero Psionico": "guerriero",
    "Ladro": "ladro", "Assassino": "ladro", "Mistificatore Arcano": "ladro",
    "Esploratore": "ladro", "Indagatore": "ladro", "Pianificatore": "ladro",
    "Scassinatore": "ladro", "Tagliagole": "ladro",
    "Scuola di Abiurazione": "mago", "Scuola di Ammaliamento": "mago",
    "Scuola di Divinazione": "mago", "Scuola di Evocazione": "mago",
    "Scuola di Illusione": "mago", "Scuola di Invocazione": "mago",
    "Scuola di Necromanzia": "mago", "Scuola di Trasmutazione": "mago",
    "Via del Signore del Vento": "monaco", "Via dell'Ombra": "monaco",
    "Via del Guerriero Eterno": "monaco", "Via della Mano Aperta": "monaco",
    "Via del Sole Radioso": "monaco", "Via della Morte Silenziosa": "monaco",
    "Via dei Quattro Elementi": "monaco", "Via del Cielo Nascosto": "monaco",
    "Via del Kensei": "monaco", "Via del Drago": "monaco",
    "Via della Rinascita": "monaco", "Via della Giusta Furia": "monaco",
    "Giuramento di Fedeltà": "paladino", "Giuramento del Mare": "paladino",
    "Giuramento del Conquistatore": "paladino",
    "Giuramento dei Sacri Carpentieri": "paladino",
    "Giuramento del Tradimento": "paladino",
    "Giuramento di Devozione": "paladino",
    "Giuramento dei Vendicatori": "paladino",
    "Giuramento della Corona": "paladino",
    "Giuramento del Sepolcro": "paladino",
    "Giuramento del Redentore": "paladino",
    "Giuramento della Luce": "paladino",
    "Giuramento della Sapienza": "paladino",
    "Giuramento dell'Anziano": "paladino",
    "Giuramento del Cacciatore": "paladino",
    "Giuramento della Gloria": "paladino",
    "Giuramento della Vendetta": "paladino", "Giuramento del Cielo": "paladino",
    "Inseguitore della Bestia": "ranger", "Inseguitore delle Ombre": "ranger",
    "Inseguitore Orizzonte": "ranger", "Inseguitore Fatato": "ranger",
    "Inseguitore Draconico": "ranger", "Maestro delle Bestie": "ranger",
    "Inseguitore del Cacciatore": "ranger", "Senza Sfondo": "ranger",
    "Arpista": "ranger", "Esploratore delle Paludi": "ranger",
    "Linea di Sangue Draconica": "stregone",
    "Magia Selvaggia": "stregone", "Anima Divina": "stregone",
    "Mente di Gelatina": "stregone", "Ombra": "stregone",
    "Tempesta": "stregone", "Fato del Ghiaccio": "stregone",
    "Accordo del Guardiano": "warlock", "Accordo del Fabbro": "warlock",
    "Accordo del Demone": "warlock", "Accordo dell'Antico": "warlock",
    "Accordo del Gatto del Cielo": "warlock", "Accordo del Genio": "warlock",
    "Accordo del Paladino Oscuro": "warlock", "Accordo del Raccolto": "warlock",
    "Accordo del Seppellitore": "warlock", "Accordo della Fata": "warlock",
    "Accordo della Lama": "warlock", "Accordo della Madre": "warlock",
    "Accordo della Sfinge": "warlock", "Accordo della Sguardo": "warlock",
    "Accordo della Sorellanza": "warlock", "Accordo della Strega": "warlock",
    "Accordo della Tempesta": "warlock", "Accordo del Kraken": "warlock",
    "Accordo dell’Impulso": "warlock", "Accordo dell'Unicorno": "warlock",
    "Accordo Immortale": "warlock", "Accordo della Morte": "warlock",
    "Hexblade": "warlock",
}

RACE_SECTION_NAMES = [
    "Nano", "Elfo", "Halfling", "Umano", "Gnomo", "Mezzelfo", "Mezzorco",
    "Tiefling", "Draconide",
]

BACKGROUND_SECTION_NAMES = [
    "Adepto", "Artigiano", "Criminale", "Eroe del Popolo", "Accolito",
    "Eremita", "Insolita", "Intrattenitore", "Marinaio", "Mercenario",
    "Nobile", "Saggio", "Soldato", "Viandante",
]


def log(msg: str) -> None:
    print(f"[extract_for_correction] {msg}", flush=True)


###############################################################################
# FASE 1 — Ricostruzione pagina-per-pagina dai content_list.json
###############################################################################

def _extract_batch_offset(cl_path: Path) -> int:
    for part in cl_path.parts:
        m = re.fullmatch(r"batch_(\d+)", part)
        if m:
            return int(m.group(1))
    return 0


def _stem_from_path(cl_path: Path) -> str:
    try:
        rel = cl_path.relative_to(EXTRACTED)
        return rel.parts[0]
    except ValueError:
        return cl_path.parent.name


def build_pages() -> dict[str, dict[int, str]]:
    """
    Scansiona tutti i *_content_list.json sotto _extracted/ e ricostruisce
    il testo per pagina per ogni manuale.

    Ritorna {source_name: {page_number: text_body, ...}}
    """
    all_pages: dict[str, dict[int, str]] = {}

    for cl_path in sorted(EXTRACTED.rglob("*_content_list.json")):
        offset = _extract_batch_offset(cl_path)
        stem = _stem_from_path(cl_path)
        try:
            items = json.loads(cl_path.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"  ! impossibile leggere {cl_path}: {e}")
            continue

        pages = all_pages.setdefault(stem, {})
        for it in items:
            text = (it.get("text") or "").strip()
            if not text:
                continue
            rel_page = it.get("page_idx", 0)
            page_num = rel_page + offset
            prev = pages.get(page_num, "")
            pages[page_num] = (prev + "\n" + text).strip()

    # Ricostruisci i nomi lunghi dei manuali dagli stem delle directory
    # Lo stem è il nome del PDF senza .pdf
    return all_pages


def _pretty_name(stem: str) -> str:
    # I nomi delle directory sono il nome del PDF senza .pdf
    return stem


def write_pages_jsonl(pages: dict[str, dict[int, str]]) -> None:
    """
    Scrive manuals/_index/pages/<stem>.jsonl per ogni manuale.
    """
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    for stem, page_map in sorted(pages.items()):
        out_path = PAGES_DIR / f"{stem}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for p in sorted(page_map):
                f.write(json.dumps({
                    "page": p,
                    "text": page_map[p],
                }, ensure_ascii=False) + "\n")
        log(f"  {stem}: {len(page_map)} pagine -> {out_path}")


###############################################################################
# FASE 2 — Allineamento incantesimi
###############################################################################

def load_pages() -> dict[str, dict[int, str]]:
    """Carica i file pages/*.jsonl in memoria."""
    pages: dict[str, dict[int, str]] = {}
    if not PAGES_DIR.exists():
        return pages
    for p in sorted(PAGES_DIR.glob("*.jsonl")):
        stem = p.stem
        page_map: dict[int, str] = {}
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                page_map[item["page"]] = item["text"]
        pages[stem] = page_map
    return pages


def _normalize_source(source_key: str) -> str:
    """Converte un source key (stem di directory) in un nome umano."""
    source_key = source_key.replace("_", " ")
    source_key = re.sub(r"\.pdf$", "", source_key, flags=re.IGNORECASE)
    return source_key.strip()


def _match_source(stem: str, spell_source: str) -> bool:
    """True se lo stem della directory corrisponde alla fonte di uno spell."""
    s = stem.lower().replace("_", " ").replace("-", " ").strip()
    t = spell_source.lower().strip()
    return s == t or s in t or t in s


def load_online_ref() -> dict:
    """Carica il reference online inglese, indicizzato per name_en."""
    ref_path = INDEX / "online_reference.json"
    if not ref_path.exists():
        log("  online_reference.json non trovato, procedo senza")
        return {}
    try:
        return json.loads(ref_path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"  online_reference.json corrotto: {e}")
        return {}


def build_spell_context(pages: dict[str, dict[int, str]],
                        spells_path: Path) -> list[dict]:
    """
    Per ogni spell in web/data/spells.json, allinea le pagine del manuale
    di origine e produce un record con il dato corrente + il testo grezzo
    + la reference online inglese.
    """
    try:
        spells = json.loads(spells_path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"ERRORE: impossibile leggere {spells_path}: {e}")
        return []

    online_ref = load_online_ref()
    if online_ref:
        log(f"  online_ref caricato: {sum(1 for v in online_ref.values() if v)} spell trovate")

    context: list[dict] = []
    matched = 0
    no_source_pages = 0

    for sp in spells:
        name = sp.get("name", "").strip()
        source = sp.get("source", "")
        page = sp.get("page")

        # Reference inglese
        name_en = (sp.get("name_en") or "").strip()
        ref = online_ref.get(name_en) if name_en else None

        if not name or not source or page is None:
            context.append({
                "name": name,
                "source": source,
                "page": page,
                "current": sp,
                "raw_pages": {},
                "pages_available": False,
                "online_ref": ref,
            })
            continue

        # Trova le pagine nel manuale giusto
        raw_pages: dict[str, str] = {}
        for stem, page_map in pages.items():
            if _match_source(stem, source):
                # Prendi 3 pagine: la pagina dello spell + 2 successive
                for offset in range(3):
                    p = page + offset
                    if p in page_map:
                        raw_pages[str(p)] = page_map[p]
                if raw_pages:
                    matched += 1
                else:
                    no_source_pages += 1
                break

        context.append({
            "name": name,
            "source": source,
            "page": page,
            "current": sp,
            "raw_pages": raw_pages,
            "pages_available": bool(raw_pages),
            "online_ref": ref,
        })

    log(f"  spells: {len(spells)} totali, {matched} con pagine trovate, "
        f"{no_source_pages} senza pagine nel manuale")
    return context


###############################################################################
# FASE 3 — Allineamento privilegi
###############################################################################

def _class_range(class_name: str) -> tuple[int, int]:
    """Ritorna (start, end) per le pagine di una classe nel PHB."""
    return CLASS_PDF_RANGE.get(class_name, (0, 0))


def _class_from_subclass(subclass_name: str) -> str | None:
    return SUBCLASS_PARENT.get(subclass_name)


def build_feature_context(pages: dict[str, dict[int, str]],
                          features_path: Path) -> dict:
    """
    Per ogni privilegio in web/data/features.json, trova le pagine PHB
    della classe corrispondente e produce record con testo grezzo.
    """
    try:
        features = json.loads(features_path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"ERRORE: impossibile leggere {features_path}: {e}")
        return {}

    # Trova il manuale PHB tra le pagine
    phb_pages: dict[int, str] = {}
    for stem, page_map in pages.items():
        if "manuale del giocatore" in stem.lower():
            phb_pages = page_map
            log(f"  PHB trovato in stem: {stem}")
            break

    if not phb_pages:
        log("  ! PHB non trovato tra le pagine estratte!")
        return {}

    context: dict[str, list[dict]] = {
        "class_features": [],
        "subclass_features": [],
        "race_features": [],
        "background_features": [],
    }

    # — Class features
    for cls_name, flist in features.get("class_features", {}).items():
        start, end = _class_range(cls_name)
        raw_pages: dict[str, str] = {}
        for p in range(start, end):
            if p in phb_pages:
                raw_pages[str(p)] = phb_pages[p]

        for feat in flist:
            context["class_features"].append({
                "class": cls_name,
                "name": feat.get("name", ""),
                "level": feat.get("level"),
                "current": feat,
                "source": "D&D 5th Manuale del Giocatore",
                "pages": f"{start}-{end}",
                "raw_pages": raw_pages,
                "pages_available": bool(raw_pages),
            })

    # — Subclass features
    for sub_name, flist in features.get("subclass_features", {}).items():
        parent = _class_from_subclass(sub_name)
        if parent:
            start, end = _class_range(parent)
            raw_pages = {}
            for p in range(start, end):
                if p in phb_pages:
                    raw_pages[str(p)] = phb_pages[p]
        else:
            raw_pages = {}

        for feat in flist:
            context["subclass_features"].append({
                "class": sub_name,
                "subclass": sub_name,
                "name": feat.get("name", ""),
                "level": feat.get("level"),
                "current": feat,
                "source": "D&D 5th Manuale del Giocatore",
                "pages": f"{start}-{end}" if parent else "?",
                "raw_pages": raw_pages,
                "pages_available": bool(raw_pages),
            })

    # — Race features
    for race_name, flist in features.get("race_features", {}).items():
        # Razze nel PHB: capitolo 2, pagine 17-40 circa
        start, end = 17, 40
        raw_pages = {}
        for p in range(start, end):
            if p in phb_pages:
                raw_pages[str(p)] = phb_pages[p]

        for feat in flist:
            context["race_features"].append({
                "race": race_name,
                "name": feat.get("name", ""),
                "level": feat.get("level"),
                "current": feat,
                "source": "D&D 5th Manuale del Giocatore",
                "pages": f"{start}-{end}",
                "raw_pages": raw_pages,
                "pages_available": bool(raw_pages),
            })

    # — Background features
    for bg_name, flist in features.get("background_features", {}).items():
        # Background nel PHB: capitolo 4, pagine ~120-140
        start, end = 120, 140
        raw_pages = {}
        for p in range(start, end):
            if p in phb_pages:
                raw_pages[str(p)] = phb_pages[p]

        for feat in flist:
            context["background_features"].append({
                "background": bg_name,
                "name": feat.get("name", ""),
                "current": feat,
                "source": "D&D 5th Manuale del Giocatore",
                "pages": f"{start}-{end}",
                "raw_pages": raw_pages,
                "pages_available": bool(raw_pages),
            })

    totals = {k: len(v) for k, v in context.items()}
    log(f"  features: {totals}")
    return context


###############################################################################
# MAIN
###############################################################################

def main() -> None:
    # Fase 1: ricostruisci pagine dai content_list
    log("FASE 1: Ricostruzione pagine dai content_list...")
    all_pages = build_pages()
    log(f"  manuali trovati: {list(all_pages.keys())}")
    write_pages_jsonl(all_pages)

    # Fase 2: allineamento incantesimi
    log("FASE 2: Allineamento incantesimi...")
    pages = load_pages()
    spell_ctx = build_spell_context(pages, WEB_DATA / "spells.json")
    spell_out = INDEX / "spell_context.json"
    spell_out.write_text(
        json.dumps(spell_ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  -> {spell_out} ({len(spell_ctx)} entries)")

    # Fase 3: allineamento privilegi
    log("FASE 3: Allineamento privilegi...")
    feat_ctx = build_feature_context(pages, WEB_DATA / "features.json")
    feat_out = INDEX / "feature_context.json"
    feat_out.write_text(
        json.dumps(feat_ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    feat_total = sum(len(v) for v in feat_ctx.values())
    log(f"  -> {feat_out} ({feat_total} entries)")

    log("Fatto.")


if __name__ == "__main__":
    main()
