#!/usr/bin/env python3
"""Estrae le 'liste di incantesimi ampliate' dal Calderone di Tasha (cap. 1).

Output: tools/tasha_expanded_lists.json mappa class_value -> [name_it,...]

Le liste ampliate aggiungono spell PHB esistenti alla lista incantesimi delle
classi caster del PHB. Vengono usate dal frontend quando il personaggio ha
'tasha_italiano' tra le fonti per offrire più scelte da picker.
"""
import json
import re
import glob
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Spell names italiani conosciuti dal nostro dataset
raw = json.load(open(ROOT / 'manuals/_index/spells.json'))
mp = json.load(open(ROOT / 'tools/spell_name_map_it_en.json'))

known_names = set()
for s in raw:
    n = (s.get('name') or '').strip()
    if n:
        known_names.add(n)
for k, v in mp.items():
    if k.startswith('_') or not v or v.get('en') is None:
        continue
    canon = (v.get('canon_it') or k).strip()
    if canon:
        known_names.add(canon)


def norm(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s'/-]", ' ', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


known_norm = {}
for n in known_names:
    nk = norm(n)
    # Mantieni la versione "carina" preferendo Title Case su ALL CAPS
    prev = known_norm.get(nk)
    if prev is None or (prev.isupper() and not n.isupper()):
        known_norm[nk] = n


# Carica blocchi tasha con page offset
files = sorted(glob.glob(
    str(ROOT / 'manuals/_extracted/tasha_italiano/batch_*/tasha_italiano/txt/tasha_italiano_content_list.json')
))
all_blocks = []
for f in files:
    m = re.search(r'batch_(\d+)', f)
    off = int(m.group(1)) if m else 0
    for b in json.load(open(f)):
        if isinstance(b, dict):
            b['_page'] = (b.get('page_idx', 0) or 0) + off
            all_blocks.append(b)


markers = [i for i, b in enumerate(all_blocks)
           if 'ampliano la lista' in b.get('text', '').lower()]

CLASS_KW = [
    ('da bardo', 'bardo'), ('da chierico', 'chierico'), ('da druido', 'druido'),
    ('da mago', 'mago'), ('da paladino', 'paladino'), ('da ranger', 'ranger'),
    ('dello stregone', 'stregone'), ('da warlock', 'warlock'),
    ('da artefice', 'artefice'),
]


def class_for_marker(mi):
    # Cerca nei 10 blocchi successivi al marker (testo intro)
    for k in range(mi, min(mi + 10, len(all_blocks))):
        t = all_blocks[k].get('text', '').lower()
        for kw, cls in CLASS_KW:
            if kw in t:
                return cls
    return None


LEVEL_INLINE = re.compile(r'(\d)\s*[\u00b0\u00ba\u00ba\xb0o]\s*livello', re.IGNORECASE)
RITUAL_TAIL = re.compile(r'\s*\(?\s*rituale\s*\)?\s*$', re.IGNORECASE)


def try_match(piece, level, bucket):
    if level is None:
        return
    piece = piece.strip().rstrip('*').strip()
    piece = RITUAL_TAIL.sub('', piece).strip()
    if not piece or len(piece) > 60:
        return
    n = norm(piece)
    if not n:
        return
    if n in known_norm:
        bucket.setdefault(level, set()).add(known_norm[n])


def parse_line(line, cur_level, bucket):
    # spezza sui marker di livello inline
    parts = LEVEL_INLINE.split(line)
    # parts: [text, lvl, text, lvl, text...]
    new_level = cur_level
    if len(parts) == 1:
        # Solo testo: prova a separare per multi-spazi (colonne mergiate)
        for piece in re.split(r'\s{2,}|\t', line):
            try_match(piece, new_level, bucket)
        return new_level
    i = 0
    while i < len(parts):
        seg = parts[i]
        if seg.strip():
            for piece in re.split(r'\s{2,}|\t|;|,', seg):
                try_match(piece, new_level, bucket)
        if i + 1 < len(parts):
            try:
                new_level = int(parts[i + 1])
            except (ValueError, TypeError):
                pass
        i += 2
    return new_level


result = {}
for idx, mi in enumerate(markers):
    cls = class_for_marker(mi)
    if not cls:
        continue
    end = markers[idx + 1] if idx + 1 < len(markers) else min(mi + 200, len(all_blocks))
    bucket = result.setdefault(cls, {})
    cur_level = None
    # Salta blocchi di intro (i prossimi ~10 contengono la spiegazione)
    start = mi + 1
    for k in range(start, end):
        t = all_blocks[k].get('text', '').strip()
        if not t:
            continue
        # Stop euristico: nuova sezione "PRIVILEGIO" o titolo lungo che parla di altro
        # (la lista vera è breve, ~20-40 spell)
        if re.match(r'^[A-Z\u00c0-\u017f\s]{8,}$', t) and len(t) > 40 and 'livello' not in t.lower():
            # heading di nuova sezione
            break
        cur_level = parse_line(t, cur_level, bucket)


# Converti set -> sorted list e ordina per livello
out = {}
for cls, lvls in result.items():
    flat = []
    for lvl in sorted(lvls):
        for name in sorted(lvls[lvl]):
            flat.append({'level': lvl, 'name': name})
    out[cls] = flat


outpath = ROOT / 'tools/tasha_expanded_lists.json'
outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Scritto {outpath}')
for cls, lst in sorted(out.items()):
    print(f'  {cls}: {len(lst)} spell')
    for s in lst:
        print(f'    L{s["level"]} {s["name"]}')
