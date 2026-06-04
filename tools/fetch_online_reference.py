#!/usr/bin/env python3
"""
fetch_online_reference.py — Scarica descrizioni incantesimi in inglese da dnd5eapi.co.

Per ogni spell in web/data/spells.json, deriva lo slug dal campo name_en e
interroga l'API SRD di dnd5eapi.co per ottenere descrizione, higher_level,
range, components, material, duration, casting_time, school, classes.

Output: manuals/_index/online_reference.json
  { "<name_en>": { "desc": [...], "higher_level": [...], ... }, ... }

Cache: se il file esiste già, lo ricarica e salta gli spell già presenti.
Usa un rate limit di 0.3s tra le richieste per non sovraccaricare l'API.

Usage:
  python3 tools/fetch_online_reference.py
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web" / "data"
INDEX = ROOT / "manuals" / "_index"
OUT = INDEX / "online_reference.json"

API_BASE = "https://www.dnd5eapi.co/api/2014/spells"
USER_AGENT = "CharacterZero/1.0 (dataset correction tool)"
MAX_WORKERS = 8


def log(msg: str) -> None:
    print(f"[fetch_online] {msg}", flush=True)


def slugify(name_en: str) -> str:
    s = name_en.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def fetch_spell(slug: str) -> dict | None:
    url = f"{API_BASE}/{slug}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except HTTPError as e:
        if e.code == 404:
            return None
        log(f"  HTTP {e.code} per {slug}: {e.reason}")
        return None
    except URLError as e:
        log(f"  Errore di connessione per {slug}: {e.reason}")
        return None
    except json.JSONDecodeError:
        log(f"  JSON non valido per {slug}")
        return None

    return {
        "name": data.get("name"),
        "desc": data.get("desc", []),
        "higher_level": data.get("higher_level", []),
        "range": data.get("range"),
        "components": data.get("components", []),
        "material": data.get("material"),
        "ritual": data.get("ritual"),
        "duration": data.get("duration"),
        "concentration": data.get("concentration"),
        "casting_time": data.get("casting_time"),
        "level": data.get("level"),
        "school": data.get("school", {}).get("name"),
        "classes": [c["name"] for c in data.get("classes", [])],
        "subclasses": [s["name"] for s in data.get("subclasses", [])],
        "attack_type": data.get("attack_type"),
        "damage": data.get("damage"),
        "dc": data.get("dc"),
    }


def _save(refs: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(OUT)


def main() -> None:
    try:
        spells = json.loads((WEB_DATA / "spells.json").read_text(encoding="utf-8"))
    except Exception as e:
        log(f"ERRORE: impossibile leggere web/data/spells.json: {e}")
        sys.exit(1)

    log(f"Dataset letto: {len(spells)} spell")

    refs: dict = {}
    if OUT.exists():
        try:
            refs = json.loads(OUT.read_text(encoding="utf-8"))
            log(f"Cache caricata: {len(refs)} spell già presenti")
        except Exception:
            log("Cache corrotta, riparto da zero")

    # Costruisci lista dei nomi da fetchare
    todo: list[tuple[str, str]] = []
    for sp in spells:
        name_en = (sp.get("name_en") or "").strip()
        if not name_en:
            continue
        if name_en not in refs:
            todo.append((name_en, slugify(name_en)))

    if not todo:
        log("Tutti gli spell sono già in cache. Nothing to do.")
        n_found = sum(1 for v in refs.values() if v is not None)
        log(f"Totale: {n_found} found, {len(refs) - n_found} not found")
        return

    log(f"Da fetchare: {len(todo)} spell (con {MAX_WORKERS} workers)...")

    fetched = 0
    not_found = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fut = {pool.submit(fetch_spell, slug): name_en for name_en, slug in todo}
        for i, f in enumerate(as_completed(fut)):
            name_en = fut[f]
            data = f.result()
            if data:
                refs[name_en] = data
                fetched += 1
            else:
                refs[name_en] = None
                not_found += 1
            if (i + 1) % 50 == 0:
                _save(refs)
                log(f"  progresso: {i + 1}/{len(todo)}")

    _save(refs)
    n_found = sum(1 for v in refs.values() if v is not None)
    log(f"Fatto: {n_found} spell trovate, {not_found} non trovate, "
        f"{fetched} nuove fetch, {len(refs) - fetched - (0 if OUT.exists() else 0)} già in cache")
    log(f"Output: {OUT}")

    n_found = sum(1 for v in refs.values() if v is not None)
    log(f"Fatto: {n_found} spell trovate, {not_found} non trovate, "
        f"{fetched} nuove fetch, {skipped} già in cache")
    log(f"Output: {OUT}")


if __name__ == "__main__":
    main()
