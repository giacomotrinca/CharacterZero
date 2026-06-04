#!/usr/bin/env python3
"""
Valida tools/spell_name_map_it_en.json contro tools/spell_classes_en_5etools.json
e contro web/data/spells.json. Stampa:
- Quanti nomi IT mappano a un EN valido
- Quali nomi EN dichiarati non esistono in 5e.tools (probabilmente nome canonical sbagliato)
- Quali spell del nostro catalogo NON sono mappati (mancanti)
- Quali spell IT marcati come None (scartati)
"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mp = json.load(open(os.path.join(BASE, 'tools/spell_name_map_it_en.json')))
mp = {k: v for k, v in mp.items() if not k.startswith('_')}
en = json.load(open(os.path.join(BASE, 'tools/spell_classes_en_5etools.json')))
en_base = en['base']  # dict {en_lower: [class,...]}
en_ext = en['extended']
spells = json.load(open(os.path.join(BASE, 'web/data/spells.json')))

# 1) Tutti i nomi spell sono presenti nella mappa?
missing = []
for s in spells:
    if s['name'] not in mp:
        missing.append(s['name'])

# 2) Tutti gli EN dichiarati esistono in 5e.tools?
unknown_en = []
mapped_ok = 0
mapped_skip = 0
for it_name, entry in mp.items():
    en_name = entry.get('en')
    if en_name is None:
        mapped_skip += 1
        continue
    if en_name not in en_base and en_name not in en_ext:
        unknown_en.append((it_name, en_name))
    else:
        mapped_ok += 1

print(f'Spell nel catalogo IT: {len(spells)}')
print(f'Entries nella mappa  : {len(mp)}')
print(f'  - mappati OK       : {mapped_ok}')
print(f'  - scartati (null)  : {mapped_skip}')
print(f'  - EN sconosciuti   : {len(unknown_en)}')
print()
print(f'Spell IT NON nella mappa ({len(missing)}):')
for n in missing[:30]: print(f'  • {n}')
if len(missing) > 30: print(f'  ... e altri {len(missing)-30}')
print()
print(f'EN canonical che NON matchano 5e.tools ({len(unknown_en)}):')
for it, e in unknown_en:
    # suggerisci candidati simili
    cands = [n for n in en_base if e.split()[0] in n][:3]
    print(f'  • {it!r:55s} -> {e!r:30s} candidati: {cands}')
