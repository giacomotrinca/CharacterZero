"""
build_dataset.py — Unisce canon + catalog + spells nel dataset servito all'app.

Output:
- web/data/dnd5e.json   : manuali, classi (con sottoclassi per-manuale + livello sottoclasse),
                          background per-manuale. Consumato dal creator (DndCache).
- web/data/spells.json  : indice incantesimi pulito e deduplicato (per Fase 5: selezione incantesimi).

Niente dipendenze esterne. Rigenerabile: python3 tools/build_dataset.py
"""

import json
import re
import sys
import pathlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dnd5e_canon as canon  # noqa: E402

IDX = ROOT / "manuals" / "_index"
CATALOG = IDX / "catalog.json"
CHUNKS_FILE = IDX / "chunks.jsonl"
SPELLS_IN = IDX / "spells.json"
WEB_DATA = ROOT / "web" / "data"

DATASET_VERSION = 15

# mappa manual_id usati in dnd5e.json → source string nei chunks
MANUAL_ID_TO_SOURCE = {
    "d_d_5th_manuale_del_giocatore": "D&D 5th Manuale del Giocatore",
    "tasha_italiano": "tasha italiano",
    "guida_omnicomprensiva_di_xanathar_5e": "Guida Omnicomprensiva di Xanathar 5e",
    "d_d_5th_guida_degli_avventurieri_alla_costa_della_spada":
        "D&D 5th Guida degli Avventurieri alla Costa della Spada",
}

# Cache chunks per source (lazy)
_chunks_by_source = None


def _get_chunks_by_source():
    global _chunks_by_source
    if _chunks_by_source is not None:
        return _chunks_by_source
    _chunks_by_source = {}
    if not CHUNKS_FILE.exists():
        return _chunks_by_source
    by: dict[str, list] = {}
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = c.get("source", "")
            if src:
                by.setdefault(src, []).append(c)
    _chunks_by_source = by
    return _chunks_by_source


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_feat_desc(feat_name, sources):
    """
    Cerca la descrizione del talento nei chunks dei manuali indicati.
    - Nomi a parola singola: solo match esatto dell'heading (evita false corrispondenze tipo
      "implacabile" per "Abile" o righe di tabella "Abile 2 mo al giorno").
    - Nomi multi-parola: match a word-boundary (gestisce artefatti OCR tipo "INCANTATORE | RITUALE È").
    """
    n = _norm(feat_name)
    is_single_word = " " not in n
    n_re = re.compile(r"\b" + re.escape(n) + r"\b") if not is_single_word else None

    def _matches(hn):
        if hn == n:
            return True
        if is_single_word:
            return False
        return bool(n_re.search(hn))

    by_source = _get_chunks_by_source()
    for src in sources:
        chunks = by_source.get(src, [])
        matched = []
        for c in chunks:
            hp = c.get("heading_path", [])
            if not isinstance(hp, list):
                continue
            for i, h in enumerate(hp):
                if _matches(_norm(h)):
                    continuation = " ".join(
                        part for part in hp[i + 1:] if part and len(part) > 3
                    )
                    chunk_text = c.get("text", "").strip()
                    full = (continuation + " " + chunk_text).strip() if continuation else chunk_text
                    matched.append((c.get("page_start", 0), full))
                    break
        if matched:
            matched.sort(key=lambda x: x[0])
            combined = " ".join(t for _, t in matched)
            combined = re.sub(r"CAPITOLO\s+\d+[^\n]*", "", combined, flags=re.IGNORECASE)
            combined = re.sub(r"Offrimi un caff[eè][^\n]*paypal\S*", "", combined, flags=re.IGNORECASE)
            combined = re.sub(r"\s{2,}", " ", combined).strip()
            if len(combined) > 20:
                return combined[:900] if len(combined) > 900 else combined
    return ""


# Parser livello incantesimo da level_text (es. "Trasmutazione di 2° livello", "Divinazione (rituale)")
RE_LEVEL = re.compile(r"(\d)\s*°\s*livello", re.IGNORECASE)
RE_CANTRIP = re.compile(r"trucchetto|livello\s*0|cantrip", re.IGNORECASE)
SCHOOLS = [
    "abiurazione", "ammaliamento", "divinazione", "evocazione",
    "illusione", "invocazione", "necromanzia", "trasmutazione",
]


def parse_level(level_text):
    if not level_text:
        return None
    if RE_CANTRIP.search(level_text):
        return 0
    m = RE_LEVEL.search(level_text)
    if m:
        return int(m.group(1))
    return None


def parse_school(level_text):
    if not level_text:
        return None
    lt = level_text.lower()
    for s in SCHOOLS:
        if s in lt:
            return s
    return None


def is_ritual(spell):
    lt = (spell.get("level_text") or "").lower()
    return "rituale" in lt


def manual_values_of(entries):
    """Da [{manual,page,...}] -> lista ordinata e deduplicata di valori manuale."""
    seen = []
    for e in entries:
        mv = e["manual"]
        if mv not in seen:
            seen.append(mv)
    return seen


def build_classes(catalog):
    cat_by_value = {c["value"]: c for c in catalog["classes"]}
    out = []
    for cls in canon.CLASSES:
        cc = cat_by_value.get(cls["value"], {"subclasses": []})
        canon_order = {canon.normalize(n): i for i, n in enumerate(cls["subclasses"])}

        def sort_key(s):
            if s["canonical"]:
                return (0, canon_order.get(canon.normalize(s["name"]), 999), "")
            return (1, 0, canon.normalize(s["name"]))

        subs = []
        for s in sorted(cc["subclasses"], key=sort_key):
            sub_entry = {
                "name": s["name"],
                "canonical": s["canonical"],
                "manuals": manual_values_of(s["manuals"]),
            }
            # Aggiunge spellcasting di sottoclasse (es. Cavaliere Mistico, Mistificatore Arcano).
            sub_sc = canon.SUBCLASS_SPELLCASTING.get(canon.normalize_subclass_name(s["name"]))
            if sub_sc:
                sub_entry["spellcasting"] = dict(sub_sc)
            subs.append(sub_entry)
        entry = {
            "value": cls["value"],
            "label": cls["label"],
            "subclass_level": cls["subclass_level"],
            "group_label": cls["group_label"],
            "caster": cls["caster"],
            "asi_levels": canon.asi_levels_for(cls["value"]),
            "save_profs": canon.SAVE_PROFS.get(cls["value"], []),
            "subclasses": subs,
        }
        sc = canon.SPELLCASTING.get(cls["value"])
        if sc:
            entry["spellcasting"] = dict(sc)
            if cls["value"] in canon.CANTRIPS_KNOWN:
                entry["spellcasting"]["cantrips_known"] = canon.CANTRIPS_KNOWN[cls["value"]]
            if cls["value"] in canon.SPELLS_KNOWN:
                entry["spellcasting"]["spells_known"] = canon.SPELLS_KNOWN[cls["value"]]
        sk = canon.CLASS_SKILL_CHOICES.get(cls["value"])
        if sk:
            entry["skill_choices"] = sk
        out.append(entry)
    return out


def build_backgrounds(catalog):
    out = []
    for b in catalog["backgrounds"]:
        rec = {"name": b["name"], "manuals": manual_values_of(b["manuals"])}
        skills = canon.BACKGROUND_SKILLS.get(b["name"])
        if skills:
            rec["skill_grants"] = skills
        out.append(rec)
    return out


def build_races(catalog):
    # indicizza i metadati canonici (stat_bonuses, half_elf_special, variant_human) per nome
    meta_by_name = {r["name"]: r for r in canon.RACES}
    out = []
    for r in catalog.get("races", []):
        meta = meta_by_name.get(r["name"], {})
        rec = {
            "name": r["name"],
            "manuals": manual_values_of(r["manuals"]),
            "stat_bonuses": meta.get("stat_bonuses", {}),
        }
        if meta.get("half_elf_special"):
            rec["half_elf_special"] = True
        if meta.get("variant_human"):
            rec["variant_human"] = True
        sk = canon.RACE_SKILLS.get(r["name"])
        if sk:
            if "fixed" in sk:   rec["skill_grants"] = sk["fixed"]
            if "choices" in sk: rec["skill_choices"] = sk["choices"]
        out.append(rec)
    return out


def build_feats(catalog):
    out = []
    for f in catalog.get("feats", []):
        rec = {"name": f["name"], "manuals": manual_values_of(f["manuals"])}
        meta = canon.FEAT_META.get(f["name"])
        if meta:
            if "stat_bonus_value" in meta:
                rec["stat_bonus_value"] = meta["stat_bonus_value"]
                rec["stat_options"] = meta.get("stat_options", [])
            if meta.get("save_prof"):
                rec["save_prof"] = True
        # Descrizione: cerca nei chunks dei manuali in cui appare, fallback curato
        sources = [
            MANUAL_ID_TO_SOURCE[mid]
            for mid in rec["manuals"]
            if mid in MANUAL_ID_TO_SOURCE
        ]
        # Aggiungi sempre PHB come fallback
        phb_src = MANUAL_ID_TO_SOURCE["d_d_5th_manuale_del_giocatore"]
        if phb_src not in sources:
            sources.append(phb_src)
        desc = _extract_feat_desc(f["name"], sources)
        if not desc:
            desc = canon.FEAT_DESCRIPTIONS_FALLBACK.get(f["name"], "")
        if desc:
            rec["description"] = desc
        out.append(rec)
    return out


def load_spell_translation_map():
    """Carica tools/spell_name_map_it_en.json + tools/spell_classes_en_5etools.json"""
    here = pathlib.Path(__file__).parent
    mp_path = here / "spell_name_map_it_en.json"
    en_path = here / "spell_classes_en_5etools.json"
    mp = json.load(open(mp_path, encoding="utf-8"))
    mp = {k: v for k, v in mp.items() if not k.startswith("_")}
    en_data = json.load(open(en_path, encoding="utf-8"))
    return mp, en_data.get("base", {}), en_data.get("extended", {})


def clean_description(text):
    """Pulisce la description estratta dall'OCR: rimuove header del prossimo spell incollati in coda."""
    if not text:
        return ""
    text = text.strip()
    # taglia se compare un pattern tipo "NOME SPELL\nTrucchetto di X" o "NOME SPELL\nIncantesimo di N° livello"
    lines = text.split("\n")
    cut = len(lines)
    for i in range(1, len(lines)):
        ln = lines[i].strip()
        # next-spell header heuristic: la riga successiva contiene "di livello", "Trucchetto di", "incantesimo"
        nxt = lines[i+1].strip() if i+1 < len(lines) else ""
        if nxt and (
            nxt.lower().startswith("trucchetto di ")
            or "° livello" in nxt.lower()
            or nxt.lower().startswith("incantesimo di ")
        ):
            # ln è probabilmente il nome dello spell successivo (ALL CAPS o Title Case)
            if ln and (ln.isupper() or (len(ln) < 60 and ln == ln.title())):
                cut = i
                break
    return "\n".join(lines[:cut]).strip()


_DAMAGE_TYPES = [
    "acido", "contundente", "energia negativa", "energia radiante", "fulmine", "fuoco",
    "freddo", "gelo", "forza", "necrotici", "perforante", "psichici", "radianti",
    "taglienti", "tonante", "tuono", "veleno",
]
_CONTROL_KEYWORDS = [
    "paralizzat", "spaventat", "affascinat", "incapacitat", "trattenut", "stordit",
    "addormentat", "prono", "trasformat in", "non può muoversi", "non può compiere",
    "terreno difficile", "afferrat",
]
_HEAL_KEYWORDS = [
    "recupera ", "guarisce", "punti ferita", "ripristina", "rimuove una malattia",
    "rimuove un veleno",
]
_BUFF_KEYWORDS = [
    "vantaggio ai tiri", "vantaggio ai propri tiri", "ottiene vantaggio", "ottiene un bonus",
    "aumenta di", "+ 1 alla", "+1 alla", "bonus di", "resistenza ai danni",
]
_DEBUFF_KEYWORDS = [
    "svantaggio ai tiri", "svantaggio ai propri tiri", "subisce svantaggio", "riduce",
    "vulnerabilità ai danni",
]
_SUMMON_KEYWORDS = [
    "evoca ", "convoca ", "fa apparire", "crea un servitore",
]
_MOVEMENT_KEYWORDS = [
    "velocità di volare", "velocità aumenta", "teletraspor", "si teletrasporta",
    "velocità di nuotare", "si sposta istantaneamente",
]
_UTILITY_KEYWORDS = [
    "comunicare", "rileva", "individua", "vede attraverso", "puoi conoscere",
    "puoi vedere", "puoi sentire", "scrutare", "messaggio",
]
_PROTECTION_KEYWORDS = [
    "+ 5 alla ca", "+5 alla ca", "non può essere ber", "immune ", "immunità",
    "scudo", "resistenza a tutti", "annulla",
]


def derive_target(rec, desc):
    """
    Tipo di bersaglio (euristica): 'self' | 'contatto' | 'creatura' | 'oggetto'
    | 'area' | 'punto'. Restituisce una lista di tag (un incantesimo può
    coinvolgere più tipi, es. 'creatura' + 'area').
    """
    out = set()
    rng = (rec.get("range") or "").strip().lower()
    text = (desc or "").lower()
    cmp_ = (rec.get("components") or "").lower()
    name = (rec.get("name") or "").lower()

    if rng in ("incantatore", "personale", "se stesso"):
        out.add("self")
    if "contatto" in rng:
        out.add("contatto")

    # area
    area_kws = [
        "cubo", "sfera del raggio", "sfera di raggio", "sfera con raggio",
        "raggio di", "linea lunga", "cono", "cilindro", "ogni creatura entro",
        "ogni creatura nell'area", "tutte le creature entro",
        "ogni creatura situata", "area",
    ]
    if any(k in text for k in area_kws):
        out.add("area")

    # creatura
    creature_kws = [
        "una creatura", "un bersaglio", "il bersaglio", "una bestia",
        "tocca una creatura", "creatura entro gittata", "tiro salvezza",
        "creatura consenziente", "umanoide", "non morto", "celestiale",
        "immondo", "draghi", "elementali", "folletti",
    ]
    if any(k in text for k in creature_kws):
        out.add("creatura")

    # oggetto
    object_kws = [
        "un oggetto", "tocca un oggetto", "l'oggetto", "oggetto non magico",
        "oggetto entro gittata", "arma non magica",
    ]
    if any(k in text for k in object_kws):
        out.add("oggetto")

    # punto: spell con range ma senza creatura/oggetto specifico
    if "in un punto" in text or "punto situato" in text or "in uno spazio libero" in text:
        out.add("punto")

    # buff caster-only nei trucchetti utility (mage hand, light)
    if not out and rng in ("incantatore", "personale", "se stesso"):
        out.add("self")

    if not out:
        # fallback: distanza numerica → punto/area, altrimenti utilità
        import re as _re
        if _re.search(r"\d+\s*metri", rng):
            out.add("punto")

    return sorted(out)


_PROTECTION_KEYWORDS_2 = []  # placeholder per evitare riassegnazione


_DAMAGE_FALLBACK = []


def derive_tags(rec, desc):
    """Restituisce un set di tag (categorie) per uno spell, basato su scuola + keyword nella descrizione."""
    tags = set()
    school = (rec.get("school") or "").lower()
    text = (desc or "").lower()
    name = (rec.get("name") or "").lower()

    # danno: presenza esplicita di tipi di danno o "danni N d M"
    if any(t in text for t in _DAMAGE_TYPES) or re.search(r"\b\d+d\d+\s+danni", text) or "subisce" in text and "danni" in text:
        tags.add("danno")
    if any(k in text for k in _HEAL_KEYWORDS):
        tags.add("cura")
    if any(k in text for k in _CONTROL_KEYWORDS):
        tags.add("controllo")
    if any(k in text for k in _BUFF_KEYWORDS):
        tags.add("potenziamento")
    if any(k in text for k in _DEBUFF_KEYWORDS):
        tags.add("indebolimento")
    if any(k in text for k in _SUMMON_KEYWORDS) or "evoc" in name:
        tags.add("evocazione")
    if any(k in text for k in _MOVEMENT_KEYWORDS):
        tags.add("movimento")
    if any(k in text for k in _UTILITY_KEYWORDS) or school in ("divinazione",):
        tags.add("utilità")
    if any(k in text for k in _PROTECTION_KEYWORDS) or school == "abiurazione":
        tags.add("protezione")

    # fallback: scuola implica tag se nulla è stato trovato
    if not tags:
        SCHOOL_TAG = {
            "abiurazione": "protezione",
            "ammaliamento": "controllo",
            "divinazione": "utilità",
            "evocazione": "evocazione",
            "illusione": "utilità",
            "invocazione": "danno",
            "necromanzia": "danno",
            "trasmutazione": "utilità",
        }
        t = SCHOOL_TAG.get(school)
        if t:
            tags.add(t)

    return sorted(tags)


def add_ritual_tag(rec, tags_list):
    """Aggiunge 'rituale' ai tag se lo spell è un rituale."""
    if is_ritual(rec):
        return sorted(set(tags_list) | {"rituale"})
    return tags_list


def build_spells():
    raw = json.load(open(SPELLS_IN, encoding="utf-8"))
    try:
        tr_map, en_base, en_ext = load_spell_translation_map()
    except FileNotFoundError:
        tr_map, en_base, en_ext = {}, {}, {}
    best = {}
    skipped = 0
    for s in raw:
        name = (s.get("name") or "").strip()
        if not name:
            continue
        # applica mappa di pulizia/traduzione
        tr = tr_map.get(name)
        if tr is not None:
            if tr.get("en") is None:
                skipped += 1
                continue
            display_it = tr.get("canon_it") or name
            name_en = tr.get("en")
            classes = en_base.get(name_en, [])
            classes_ext = en_ext.get(name_en, [])
            classes_sub_only = sorted(set(classes_ext) - set(classes))
        else:
            display_it = name
            name_en = None
            classes = []
            classes_sub_only = []

        key = canon.normalize(display_it)
        lvl_text = s.get("level_text")
        desc = clean_description(s.get("description"))
        rec = {
            "name": display_it,
            "name_en": name_en,
            "classes": classes,
            "classes_subclass_only": classes_sub_only,
            "level": parse_level(lvl_text),
            "school": parse_school(lvl_text),
            "ritual": is_ritual(s),
            "level_text": lvl_text,
            "casting_time": s.get("casting_time"),
            "range": s.get("range"),
            "components": s.get("components"),
            "duration": s.get("duration"),
            "description": desc,
            "source": s.get("source"),
            "page": s.get("page"),
            "complete": bool(s.get("complete")),
        }
        rec["tags"] = add_ritual_tag(rec, derive_tags(rec, desc))
        rec["target"] = derive_target(rec, desc)
        prev = best.get(key)
        if prev is None or (rec["complete"] and not prev["complete"]):
            best[key] = rec
    out = sorted(best.values(), key=lambda r: (r["level"] is None, r["level"] or 0, canon.normalize(r["name"])))
    if skipped:
        print(f"[dataset] scartate {skipped} entry non-spell dal catalogo OCR")
    no_class = sum(1 for r in out if not r["classes"])
    print(f"[dataset] spell senza class-assignment: {no_class}/{len(out)}")
    return out


def main():
    catalog = json.load(open(CATALOG, encoding="utf-8"))
    WEB_DATA.mkdir(parents=True, exist_ok=True)

    # ordine manuali per UX: prima i sourcebook dei giocatori più usati
    order = [
        "manuale_del_giocatore", "xanathar", "tasha",
        "guida_degli_avventurieri", "manuale_del_master", "manuale_dei_mostri",
    ]

    def mrank(m):
        for i, key in enumerate(order):
            if key in m["value"]:
                return i
        return len(order)

    manuals_sorted = sorted(catalog["manuals"], key=mrank)

    dataset = {
        "__v": DATASET_VERSION,
        "manuals": [{"value": m["value"], "label": m["label"]} for m in manuals_sorted],
        "skills": canon.SKILLS,
        "classes": build_classes(catalog),
        "backgrounds": build_backgrounds(catalog),
        "races": build_races(catalog),
        "feats": build_feats(catalog),
        "spell_slots": {
            "full_caster": canon.FULL_CASTER_SLOTS,
            "half_caster": canon.HALF_CASTER_SLOTS,
            "third_caster": canon.THIRD_CASTER_SLOTS,
            "pact": [{"slots": s[0], "slot_level": s[1]} for s in canon.PACT_SLOTS],
        },
    }
    spells = build_spells()
    (WEB_DATA / "spells.json").write_text(
        json.dumps(spells, ensure_ascii=False), encoding="utf-8"
    )

    # Liste ampliate del Calderone di Tasha (cap. 1) — incorporate nel dataset.
    tasha_expansions_path = ROOT / "tools" / "tasha_expanded_lists.json"
    if tasha_expansions_path.exists():
        dataset["tasha_expanded"] = json.loads(tasha_expansions_path.read_text(encoding="utf-8"))
    (WEB_DATA / "dnd5e.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("[dataset] scritto web/data/dnd5e.json e web/data/spells.json")
    print(f"  manuali:     {len(dataset['manuals'])}")
    print(f"  classi:      {len(dataset['classes'])}")
    tot_sub = sum(len(c['subclasses']) for c in dataset['classes'])
    print(f"  sottoclassi: {tot_sub}")
    print(f"  background:  {len(dataset['backgrounds'])}")
    print(f"  razze:       {len(dataset['races'])}")
    print(f"  talenti:     {len(dataset['feats'])}")
    print(f"  incantesimi: {len(spells)} (deduplicati)")


if __name__ == "__main__":
    main()
