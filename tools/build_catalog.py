"""
build_catalog.py — Estrae il CATALOGO per-manuale (parte algoritmica dell'ibrido).

Per ogni manuale estratto determina QUALI sottoclassi (note + scoperte) e QUALI background
compaiono, ancorando al dizionario canonico (`dnd5e_canon`) con fuzzy match su testo OCR.

Output: manuals/_index/catalog.json
"""

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dnd5e_canon as canon  # noqa: E402

IDX = Path(__file__).resolve().parent.parent / "manuals" / "_index"
CHUNKS = IDX / "chunks.jsonl"
SECTIONS = IDX / "sections.json"
MANIFEST = IDX / "manifest.json"
OUT = IDX / "catalog.json"

FUZZY_MIN = 0.86      # soglia SequenceMatcher per match "noto"
DISCOVER_MAX_WORDS = 6
MANUAL_LABELS = {
    "D&D 5th Manuale del Giocatore": "Manuale del Giocatore",
    "D&D 5th Manuale del Master": "Manuale del Master",
    "D&D 5th Manuale dei Mostri": "Manuale dei Mostri",
    "D&D 5th Guida degli Avventurieri alla Costa della Spada": "Guida degli Avventurieri",
    "Guida Omnicomprensiva di Xanathar 5e": "Guida di Xanathar",
    "tasha italiano": "Calderone di Tasha",
}


def manual_value(src: str) -> str:
    return canon.normalize(src).replace(" ", "_")


def short_lines(text: str):
    for ln in text.split("\n"):
        ln = ln.strip()
        if 3 <= len(ln) <= 70:
            yield ln


def load_corpus():
    """Per ogni manuale: (entries, token_index).

    entries = lista di (norm_text, raw, page); token_index = token -> set(indici entries).
    L'indice serve a limitare il fuzzy match alle sole righe che condividono un token raro.
    """
    raw_corpus = {}

    sections = json.load(open(SECTIONS, encoding="utf-8"))
    for src, lst in sections.items():
        bucket = raw_corpus.setdefault(src, [])
        for s in lst:
            raw = s["title"].strip()
            nt = canon.normalize(raw)
            if nt:
                bucket.append((nt, raw, s["page"], "h"))

    with open(CHUNKS, encoding="utf-8") as fh:
        for line in fh:
            c = json.loads(line)
            src = c["source"]
            bucket = raw_corpus.setdefault(src, [])
            p = c.get("page_start", 0)
            for ln in short_lines(c["text"]):
                nt = canon.normalize(ln)
                if nt:
                    bucket.append((nt, ln, p, "b"))

    corpus = {}
    for src, entries in raw_corpus.items():
        index = {}
        for i, (nt, _raw, _page, _kind) in enumerate(entries):
            for tok in set(nt.split()):
                if len(tok) >= 4:
                    index.setdefault(tok, set()).add(i)
        corpus[src] = (entries, index)
    return corpus


def _candidate_indices(target_norm, entries, index):
    toks = [t for t in set(target_norm.split()) if len(t) >= 4]
    if not toks:
        return range(len(entries))
    # parti dal token più raro per ridurre i candidati
    toks.sort(key=lambda t: len(index.get(t, ())))
    cand = set(index.get(toks[0], set()))
    return cand


def best_match(target_norm, corpus_entry, heading_only=False):
    """Miglior candidato (score, raw, page) per target_norm nel manuale.

    heading_only=True: considera solo heading e accetta solo match "stretti" (riga ≈ nome),
    per nomi-comuni come i background che altrimenti matchano testo di corpo.
    """
    entries, index = corpus_entry
    best = (0.0, None, None)
    tlen = len(target_norm)
    for i in _candidate_indices(target_norm, entries, index):
        nt, raw, page, kind = entries[i]
        if heading_only:
            if kind != "h":
                continue
            # match stretto: la riga è (quasi) solo il nome
            if target_norm in nt and len(nt) <= tlen + 4:
                score = 0.97
            else:
                score = SequenceMatcher(None, target_norm, nt).ratio()
                if score < 0.90:
                    continue
        else:
            if target_norm in nt and tlen >= 6:
                score = 0.97 if len(nt) <= tlen + 8 else 0.90
            else:
                score = SequenceMatcher(None, target_norm, nt).ratio()
        if score > best[0]:
            best = (score, raw, page)
            if score >= 0.999:
                break
    return best


# Parole che segnalano un heading NON-sottoclasse (liste incantesimi, privilegi, riferimenti…)
NOISE_TOKENS = {
    "incantesimi", "incantesimo", "privilegi", "privilegio", "vedi", "tabella",
    "capitolo", "esempi", "esempio", "rappresenta", "descritti", "descritto",
    "barbaro", "bardo", "chierico", "druido", "druida", "guerriero", "ladro",
    "mago", "monaco", "paladino", "ranger", "stregone", "warlock",
}
# Articoli/preposizioni ammessi come SECONDA parola (grammatica del nome di sottoclasse)
LINK_WORDS = {
    "del", "della", "dello", "dell", "dei", "degli", "delle", "di",
}
# Radice attesa come PRIMA parola, derivata dall'anchor della classe
ANCHOR_ROOT = {
    "barbaro": "cammino", "bardo": "collegio", "chierico": "dominio",
    "druido": "circolo", "mago": "scuola", "monaco": "via", "paladino": "giuramento",
}


def discover_subclasses(cls, corpus_entry, known_norms):
    """Scopre sottoclassi non in canon via anchor regex, con filtri severi anti-rumore."""
    root = ANCHOR_ROOT.get(cls["value"])
    if not root:
        return []
    entries, _index = corpus_entry
    found = {}
    for nt, raw, page, _kind in entries:
        toks = nt.split()
        # 1) deve iniziare con la radice e avere grammatica "Radice <link> Nome"
        if len(toks) < 3 or toks[0] != root or toks[1] not in LINK_WORDS:
            continue
        if not (3 <= len(toks) <= 5):
            continue
        # 2) niente parole-rumore
        if any(t in NOISE_TOKENS for t in toks):
            continue
        # 3) raw pulito: lettere/spazi/apostrofi, niente parentesi/cifre/punteggiatura strana
        if re.search(r"[0-9(){}\[\]<>.:;]|\.\.\.|…", raw):
            continue
        if not re.fullmatch(r"[A-Za-zÀ-ÿ' ]+", raw.strip()):
            continue
        # 4) non già noto (fuzzy contro canon)
        if any(SequenceMatcher(None, nt, kn).ratio() >= 0.85 for kn in known_norms):
            continue
        # normalizza capitalizzazione: Radice + articoli minuscoli + Nome in Maiuscolo
        clean = titlecase_subclass(raw.strip())
        key = canon.normalize(clean)
        if key not in found:
            found[key] = {"name": clean, "page": page}
    return list(found.values())


def _cap_token(tok: str) -> str:
    """Capitalizza un token gestendo apostrofi (dell'arcano -> dell'Arcano)."""
    for ap in ("'", "\u2019"):
        if ap in tok:
            head, tail = tok.split(ap, 1)
            head_l = head.lower()
            head_out = head_l if head_l in LINK_WORDS else head.capitalize()
            return head_out + ap + tail.capitalize()
    return tok.lower() if tok.lower() in LINK_WORDS else tok.capitalize()


def titlecase_subclass(raw: str) -> str:
    words = raw.split()
    if not words:
        return raw
    out = [words[0].capitalize()]
    out += [_cap_token(w) for w in words[1:]]
    return " ".join(out)


def main():
    corpus = load_corpus()
    manuals_in_index = list(json.load(open(MANIFEST, encoding="utf-8"))["manuals"].keys())

    # Manuale del Giocatore = fonte canonica garantita per sottoclassi/background base PHB
    phb_src = next((s for s in manuals_in_index if "Manuale del Giocatore" in s), None)
    phb_value = manual_value(phb_src) if phb_src else None

    def ensure_phb(present):
        """Garantisce la presenza del PHB (dato curato a mano), senza duplicarlo."""
        if phb_value and not any(p["manual"] == phb_value for p in present):
            present.insert(0, {"manual": phb_value, "page": None, "score": 1.0})
        return present

    manuals_out = []
    for src in manuals_in_index:
        manuals_out.append({
            "value": manual_value(src),
            "label": MANUAL_LABELS.get(src, src),
            "source": src,
        })

    classes_out = []
    for cls in canon.CLASSES:
        known_norms = [canon.normalize(s) for s in cls["subclasses"]]
        subs = []

        # 1) sottoclassi NOTE: attribuisci ai manuali in cui compaiono (+ PHB garantito)
        for name in cls["subclasses"]:
            tn = canon.normalize(name)
            present = []
            for src in manuals_in_index:
                ce = corpus.get(src)
                if ce is None:
                    continue
                score, raw, page = best_match(tn, ce)
                if score >= FUZZY_MIN:
                    present.append({
                        "manual": manual_value(src),
                        "page": page,
                        "score": round(score, 3),
                    })
            ensure_phb(present)
            subs.append({
                "name": name,
                "canonical": True,
                "manuals": present,
            })

        # 2) sottoclassi SCOPERTE per-manuale (non in canon)
        discovered = {}
        for src in manuals_in_index:
            ce = corpus.get(src)
            if ce is None:
                continue
            for d in discover_subclasses(cls, ce, known_norms):
                key = canon.normalize(d["name"])
                entry = discovered.setdefault(
                    key, {"name": d["name"], "canonical": False, "manuals": []}
                )
                entry["manuals"].append({"manual": manual_value(src), "page": d["page"]})

        # scarta frammenti che sono super-stringhe di un nome più corto già presente
        all_norms = [canon.normalize(s["name"]) for s in subs] + \
                    [canon.normalize(v["name"]) for v in discovered.values()]
        for key, v in discovered.items():
            kn = canon.normalize(v["name"])
            if any(other != kn and kn.startswith(other + " ") for other in all_norms):
                continue
            subs.append(v)

        classes_out.append({
            "value": cls["value"],
            "label": cls["label"],
            "subclass_level": cls["subclass_level"],
            "group_label": cls["group_label"],
            "caster": cls["caster"],
            "subclasses": subs,
        })

    # 3) razze: attribuzione per-manuale (heading-only, soglia 0.86)
    races_out = []
    for race in canon.RACES:
        name = race["name"]
        tn = canon.normalize(name)
        # Umano Variante non ha un heading dedicato — eredita la presenza di "Umano".
        if name == "Umano Variante":
            tn = canon.normalize("Umano")
        present = []
        for src in manuals_in_index:
            ce = corpus.get(src)
            if ce is None:
                continue
            score, raw, page = best_match(tn, ce, heading_only=True)
            if score >= 0.86:
                present.append({
                    "manual": manual_value(src),
                    "page": page,
                    "score": round(score, 3),
                })
        ensure_phb(present)
        races_out.append({"name": name, "manuals": present})

    # 3.5) talenti: attribuzione per-manuale (heading-only, soglia 0.86)
    feats_out = []
    for name in canon.FEATS:
        tn = canon.normalize(name)
        present = []
        for src in manuals_in_index:
            ce = corpus.get(src)
            if ce is None:
                continue
            score, raw, page = best_match(tn, ce, heading_only=True)
            if score >= 0.86:
                present.append({
                    "manual": manual_value(src),
                    "page": page,
                    "score": round(score, 3),
                })
        ensure_phb(present)
        feats_out.append({"name": name, "manuals": present})

    # 4) background: attribuzione per-manuale
    backgrounds_out = []
    scag_src = next((s for s in manuals_in_index if "Costa della Spada" in s), None)
    scag_value = manual_value(scag_src) if scag_src else None
    for name in canon.BACKGROUNDS:
        tn = canon.normalize(name)
        present = []
        for src in manuals_in_index:
            ce = corpus.get(src)
            if ce is None:
                continue
            score, raw, page = best_match(tn, ce, heading_only=True)
            if score >= 0.90:
                present.append({
                    "manual": manual_value(src),
                    "page": page,
                    "score": round(score, 3),
                })
        # Garantisce la fonte canonica corretta: PHB per i background base, SCAG per gli aggiuntivi.
        if name in canon.BACKGROUNDS_PHB:
            ensure_phb(present)
        elif name in canon.BACKGROUNDS_SCAG and scag_value:
            if not any(p["manual"] == scag_value for p in present):
                present.insert(0, {"manual": scag_value, "page": None, "score": 1.0})
        backgrounds_out.append({"name": name, "manuals": present})

    out = {
        "manuals": manuals_out,
        "classes": classes_out,
        "backgrounds": backgrounds_out,
        "races": races_out,
        "feats": feats_out,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # report
    print(f"[catalog] scritto {OUT}")
    for c in classes_out:
        nsub = len(c["subclasses"])
        disc = sum(1 for s in c["subclasses"] if not s["canonical"])
        attr = sum(1 for s in c["subclasses"] if s["manuals"])
        print(f"  {c['label']:<10} sottoclassi={nsub:<2} (scoperte={disc}, con manuale={attr})")
    bg_attr = sum(1 for b in backgrounds_out if b["manuals"])
    print(f"  background: {len(backgrounds_out)} (con manuale={bg_attr})")
    race_attr = sum(1 for r in races_out if r["manuals"])
    print(f"  razze:      {len(races_out)} (con manuale={race_attr})")
    feat_attr = sum(1 for f in feats_out if f["manuals"])
    print(f"  talenti:    {len(feats_out)} (con manuale={feat_attr})")


if __name__ == "__main__":
    main()
