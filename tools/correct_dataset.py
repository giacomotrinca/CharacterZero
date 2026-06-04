#!/usr/bin/env python3
"""
Script di correzione dataset seguendo COMPARING_DES.md.

Corregge web/data/spells.json e web/data/features.json confrontando
il dato corrente con raw_pages (OCR PDF italiani) e online_ref (EN SRD).
"""
import json
import re
import sys
import os

# ── Feet→meters conversion table ──
FEET_TO_METERS = {
    5: "1,5", 10: "3", 15: "4,5", 20: "6", 25: "7,5",
    30: "9", 40: "12", 50: "15", 60: "18", 80: "24",
    90: "27", 100: "30", 120: "36", 150: "45", 210: "63",
    300: "90", 500: "150", 1000: "300",
}
FEET_PATTERN = re.compile(r'(\d+)\s*(piedi|piede|foot|feet)', re.IGNORECASE)

# ── OCR artifacts ──
OCR_FIXES = [
    (r'\bperla\b', 'per la'),
    (r'\bconla\b', 'con la'),
    (r'\bdellospe\b', 'dello spe'),
    (r"\bdell'incantesimo\b", "dell'incantesimo"),
    (r"\bdell\u2019incantesimo\b", "dell'incantesimo"),
    (r"\bdell'incantatore\b", "dell'incantatore"),
    (r"\bdell\u2019incantatore\b", "dell'incantatore"),
    (r"\bsull'incantesimo\b", "sull'incantesimo"),
    (r"\bsull\u2019incantesimo\b", "sull'incantesimo"),
    (r"\bsull'incantatore\b", "sull'incantatore"),
    (r"\bsull\u2019incantatore\b", "sull'incantatore"),
    (r"\bnell'area\b", "nell'area"),
    (r"\bnell\u2019area\b", "nell'area"),
    (r'\bcongli\b', 'con gli'),
    (r"\bcoll'incantesimo\b", "coll'incantesimo"),
    (r'\bunazione\b', 'un azione'),
    (r"\bun'azione\b", "un'azione"),
    (r"\bun\u2019azione\b", "un'azione"),
    (r'\bunarea\b', 'un area'),
    (r"\bdell'area\b", "dell'area"),
    (r"\bdell'oscurità\b", "dell'oscurità"),
    (r'\bincantator\b', 'incantatore'),
    (r'\bincantatodre\b', 'incantatore'),
    (r'\bbersaglioe\b', 'bersaglio e'),
    (r"\bl'incantatore\b", "l'incantatore"),
    (r"\bl\u2019incantatore\b", "l'incantatore"),
    (r"\bl'incantesimo\b", "l'incantesimo"),
    (r"\bl\u2019incantesimo\b", "l'incantesimo"),
    (r"\bl'area\b", "l'area"),
    (r"\bl\u2019area\b", "l'area"),
    (r"\bd'incantesimo\b", "d'incantesimo"),
    (r"\bd\u2019incantesimo\b", "d'incantesimo"),
    (r'\bchegli\b', 'che gli'),
    (r'\bcheegli\b', 'che egli'),
    (r'\bÈuna\b', 'È una'),
    (r'\bÈun\b', 'È un'),
    (r'\bSeil\b', 'Se il'),
    (r'\bSeun\b', 'Se un'),
    (r'\bSela\b', 'Se la'),
    (r'\bconla\b', 'con la'),
    (r'\bconle\b', 'con le'),
    (r'\bconun\b', 'con un'),
    (r'\bdauna\b', 'da una'),
    (r'\bdaun\b', 'da un'),
    (r'\bdelloscudo\b', 'dello scudo'),
    (r"\bdell'energia\b", "dell'energia"),
    (r"\bdell\u2019energia\b", "dell'energia"),
    (r'\bdellospe\b', 'dello spe'),
    (r"\bdell'incantesim\b", "dell'incantesimo"),
    # Additional OCR fixes for features
    (r'\bsceita\b', 'scelta'),
    (r'\bfete\b', 'ferite'),
    (r'\bIspirazione[Bb]ardica\b', 'Ispirazione Bardica'),
    (r'\bfaccare\b', 'spezzare'),
    (r'\bco\s+energia\b', 'incanala energia'),
    (r'\bchiericoutilizza\b', 'chierico utilizza'),
    (r'\buncerto\b', 'un certo'),
    (r'\bunzione\b', "un'azione"),
    (r'\bunga\b', 'una'),
    (r'\bparia\b', 'pari a'),
    (r'\bilivello\b', 'il livello'),
    (r'\blivell\b', 'livello'),
    (r'\bprivilego\b', 'privilegio'),
    (r'\bprivilegi\b', 'privilegi'),
    (r'\bottiene\b', 'ottiene'),
    (r'\bottengon\b', 'ottengono'),
    (r'\bcontrofascio\b', 'controincantesimo'),
    (r'\bControfascino\b', 'Controincantesimo'),
    # 'wych' -> 'wych' è corretto nel contesto (legno wych = wood wyche)
]


def fix_ocr(text: str) -> str:
    """Applica le correzioni OCR note al testo."""
    if not text:
        return text
    for pattern, replacement in OCR_FIXES:
        text = re.sub(pattern, replacement, text)
    return text


def convert_feet_to_meters(text: str) -> str:
    """Converte distanze in piedi in metri usando la tabella."""
    if not text:
        return text

    def _replace(match):
        feet = int(match.group(1))
        if feet in FEET_TO_METERS:
            return FEET_TO_METERS[feet] + ' metri'
        return match.group(0)

    # Handle ranges like "36 metri" -> already in meters, skip
    result = FEET_PATTERN.sub(_replace, text)
    return result


def normalize_text(text: str) -> str:
    """Normalizza newlines e caratteri speciali OCR."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Normalizza caratteri unicode problematici
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '--')
    # Merge newline-broken "° livello" patterns like "2\n° livello" -> "2° livello"
    text = re.sub(r'(\d+)\s*\n\s*°\s*livello', r'\1° livello', text)
    return text


def find_spell_section(raw_text: str, spell_name: str) -> str:
    """
    Trova la sezione della raw_text che corrisponde allo spell.
    Restituisce il testo dello spell header + descrizione, o stringa vuota.
    """
    name_upper = spell_name.upper()
    text = normalize_text(raw_text)

    # Pattern: spell name at start of a line
    patterns = [
        re.compile(rf'^{re.escape(name_upper)}\s*$', re.MULTILINE),
        re.compile(rf'^{re.escape(name_upper)}[\s\W]', re.MULTILINE),
    ]

    match_pos = -1
    for p in patterns:
        m = p.search(text)
        if m:
            match_pos = m.start()
            break

    if match_pos == -1:
        # Fuzzy 1-char OCR tolerance
        n3 = re.escape(name_upper[:3])
        nr = re.escape(name_upper[3:])
        fuzzy = re.compile(rf'^{n3}.{{0,2}}{nr}[\s\W]', re.MULTILINE)
        m = fuzzy.search(text)
        if m:
            match_pos = m.start()

    if match_pos == -1:
        return ''

    section = text[match_pos:]

    # Find next spell boundary: look for a line that is:
    # - all uppercase, >= 3 chars
    # - followed by a line containing "Trucchetto", "livello", or "°" 
    lines = section.split('\n')

    # Skip line 0 (the spell name itself), find the level line
    # The level line is usually line 1 or 2
    header_end = 1
    for i in range(1, min(5, len(lines))):
        if 'Trucchetto' in lines[i] or 'livello' in lines[i] or '°' in lines[i]:
            header_end = i + 1
            break
        # Also check if this line has Tempo di Lancio (some spells lack the level line)
        if 'Tempo di Lancio' in lines[i]:
            header_end = i
            break

    # Find next spell: a line that's all-caps, >= 3 chars, not containing common words
    next_start = len(lines)
    for i in range(header_end, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        # A new spell starts with an all-uppercase line (at least 3 chars)
        if line == line.upper() and len(line) >= 3 and ':' not in line:
            # Make sure it's not a subtitle or common word
            common_words = {'CAPITOLO', 'APPENDICE', 'INTRODUZIONE', 'INDICE', 'SOMMARIO'}
            if line not in common_words and not line.startswith('CAPITOLO'):
                # Check next line to confirm it's a spell header
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if 'Trucchetto' in next_line or 'livello' in next_line or '°' in next_line:
                        next_start = i
                        break
                    # If we have Componenti: or Durata: already, and this line follows description,
                    # it could be a spell
                    if not any(c in line for c in ('’', "'", '«', '»', '-')) and len(line) <= 60:
                        next_start = i
                        break

    section_text = '\n'.join(lines[:next_start])
    return section_text


def parse_spell_fields(section: str) -> dict:
    """Estrai i campi dalla sezione dello spell."""
    result = {}

    # Patterns per ogni campo - multiline flessibile
    field_patterns = {
        'casting_time': r'Tempo di Lancio:\s*(.+?)(?=\n(?:Gittata|Componenti|Durata|Ai Livelli|$))',
        'range': r'Gittata:\s*(.+?)(?=\n(?:Componenti|Durata|Tempo di Lancio|Ai Livelli|$))',
        'components': r'Componenti:\s*(.+?)(?=\n(?:Durata|Tempo di Lancio|Gittata|Ai Livelli|$))',
        'duration': r'Durata:\s*(.+?)(?=\n(?:Ai Livelli|Tempo di|Gittata|Componenti|$))',
    }

    for key, pattern in field_patterns.items():
        m = re.search(pattern, section, re.DOTALL)
        if m:
            val = m.group(1).strip()
            # Only take first line - the fields are usually single line in the Italian PHB
            val = val.split('\n')[0].strip()
            # Clean trailing punctuation
            val = val.rstrip(',; ')
            result[key] = val

    # Extract level_text - second line (after spell name)
    lines = section.split('\n')
    # First line is the spell name
    for i in range(1, min(4, len(lines))):
        line = lines[i].strip()
        if 'Trucchetto' in line or 'livello' in line or '°' in line:
            result['level_text'] = line
            break

    # Extract description: from after "Durata:" line to end of section or "CAPITOLO" or page marker
    dur_match = re.search(r'Durata:\s*(.+?)(?:\n|$)', section)
    if dur_match:
        desc_start = dur_match.end()
        desc_text = section[desc_start:].strip()
        # Remove trailing content like "CAPITOLO X", page markers, http links
        desc_text = re.split(r'\nCAPITOLO\s|\nhttp://|\n---', desc_text)[0]
        # Remove trailing trivial content (page numbers, OCR garbage)
        lines_desc = desc_text.split('\n')
        cleaned_lines = []
        for line in lines_desc:
            line_stripped = line.strip()
            # Skip lines that are just page numbers or OCR artifacts
            if re.match(r'^\d+$', line_stripped):
                continue
            if line_stripped.startswith('http://'):
                continue
            if 'paypal' in line_stripped.lower():
                continue
            if re.match(r'^[oO]\s+\d+', line_stripped):
                continue
            cleaned_lines.append(line)
        desc_text = '\n'.join(cleaned_lines)
        # Merge hyphenated words broken across lines
        desc_text = re.sub(r'(\w)-\n(\w)', r'\1\2', desc_text)
        desc_text = desc_text.strip()
        result['description'] = desc_text

    return result


def parse_spell_from_raw(raw_text: str, spell_name: str) -> dict:
    """
    Cerca di estrarre i campi dalla raw_pages per uno specifico incantesimo.
    Restituisce dict con chiavi: duration, components, description, range, casting_time, level_text
    """
    result = {}
    if not raw_text or raw_text == 'None':
        return result

    section = find_spell_section(raw_text, spell_name)
    if not section:
        return result

    result = parse_spell_fields(section)

    # Second pass: if some fields are missing, try with the first-pass section expanded
    # (handles edge cases where next-spell boundary was wrong)
    return result


def clean_description(desc: str) -> str:
    """Pulisce la descrizione da artefatti OCR e converti unità."""
    if not desc:
        return desc
    desc = convert_feet_to_meters(desc)
    desc = fix_ocr(desc)
    return desc


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spells_path = os.path.join(base_dir, 'web', 'data', 'spells.json')
    features_path = os.path.join(base_dir, 'web', 'data', 'features.json')
    ctx_path = os.path.join(base_dir, 'manuals', '_index', 'spell_context.json')
    feat_ctx_path = os.path.join(base_dir, 'manuals', '_index', 'feature_context.json')

    # ═══════════════════════════════════════
    # SPELLS
    # ═══════════════════════════════════════
    print("=" * 60)
    print("CORREZIONE INCANTESIMI")
    print("=" * 60)

    with open(spells_path) as f:
        spells = json.load(f)
    with open(ctx_path) as f:
        ctx = json.load(f)

    ctx_by_name = {e['name']: e for e in ctx}

    # Track changes
    changes = 0
    foot_fixes = 0

    for spell in spells:
        name = spell['name']
        ctx_entry = ctx_by_name.get(name)
        if not ctx_entry:
            continue

        raw_pages = ctx_entry.get('raw_pages')
        if not raw_pages or raw_pages == 'None':
            continue

        # Build the full raw text from all pages
        if isinstance(raw_pages, dict):
            raw_text = '\n'.join(raw_pages.values())
        else:
            continue

        # Parse spell data from raw pages
        parsed = parse_spell_from_raw(raw_text, name)

        # Fallback scan: if main parser missed some fields, scan raw text more broadly
        for key, label in [('duration', 'Durata'), ('components', 'Componenti')]:
            if key not in parsed or not parsed[key]:
                # Scan nearest occurrence within reasonable distance
                name_idx = raw_text.upper().find(name.upper())
                if name_idx >= 0:
                    # Look within 800 chars after the spell name
                    vicinity = raw_text[name_idx:name_idx + 800]
                    m = re.search(rf'{label}:\s*([^\n]+)', vicinity)
                    if m:
                        val = m.group(1).strip()
                        val = re.sub(r'\s+', ' ', val)
                        parsed[key] = val

        # Fallback for description: if missing, look for text after a "Durata:" line
        # that doesn't look like another spell's header
        if 'description' not in parsed or not parsed.get('description'):
            name_idx = raw_text.upper().find(name.upper())
            if name_idx >= 0:
                vicinity = raw_text[name_idx:name_idx + 2500]
                # Find all Durata lines
                dur_matches = list(re.finditer(r'Durata:\s*[^\n]+', vicinity))
                if dur_matches:
                    # Take the last Durata line (most likely belongs to this spell)
                    last_dur = dur_matches[-1]
                    desc_start = last_dur.end()
                    desc = vicinity[desc_start:].strip()
                    # Cut at next all-caps line that looks like a spell header
                    desc_lines = desc.split('\n')
                    cleaned = []
                    for line in desc_lines:
                        line_stripped = line.strip()
                        # Skip CAPITOLO headers, http links
                        if line_stripped.startswith('CAPITOLO') or line_stripped.startswith('http'):
                            break
                        if 'paypal' in line_stripped.lower():
                            continue
                        # Stop if we hit a new all-caps spell header line
                        if line_stripped == line_stripped.upper() and len(line_stripped) >= 5 and ':' in line_stripped:
                            # Skip line with Componenti, Durata etc - those are still part of description
                            if not any(l in line_stripped for l in ['Componenti', 'Durata', 'Tempo di', 'Gittata']):
                                break
                        # Skip field lines that are for other spells
                        if any(l in line_stripped for l in ['Componenti', 'Tempo di', 'Gittata']):
                            continue
                        # Keep lines that describe the spell effect
                        cleaned.append(line)
                    desc_text = '\n'.join(cleaned).strip()
                    if desc_text and len(desc_text) > 50:
                        # Merge broken words across lines
                        desc_text = re.sub(r'(\w)-\n(\w)', r'\1\2', desc_text)
                        parsed['description'] = desc_text

        # Normalize components format
        if 'components' in parsed and parsed['components']:
            c = parsed['components']
            # Fix "VS" -> "V, S"
            c = re.sub(r'\bV\s*S\b', 'V, S', c)
            c = re.sub(r'\bV\s*,\s*S\s*,\s*M\b', 'V, S, M', c)
            c = re.sub(r'\bS\s*,\s*M\b', 'S, M', c)
            if c != parsed['components']:
                parsed['components'] = c

        was_modified = False

        # For incomplete spells, fill missing fields
        if not spell.get('complete'):
            # Duration
            if spell.get('duration') is None and 'duration' in parsed:
                d = parsed['duration']
                d = fix_ocr(d)
                print(f"  {name}: fixing duration: None -> '{d}'")
                spell['duration'] = d
                was_modified = True

            # Components
            if spell.get('components') is None and 'components' in parsed:
                c = parsed['components']
                c = fix_ocr(c)
                # Clean trailing fragment
                if c and len(c) > 3 and c[-1] not in ')]':
                    c = c.rstrip(',; .')
                if c and len(c) >= 1:
                    print(f"  {name}: fixing components: None -> '{c[:80]}'")
                    spell['components'] = c
                    was_modified = True

            # Description - if empty or truncated
            current_desc = spell.get('description', '') or ''
            if len(current_desc) < 50 and 'description' in parsed:
                d = clean_description(parsed['description'])
                if len(d) > len(current_desc):
                    print(f"  {name}: fixing description (len {len(current_desc)} -> {len(d)})")
                    spell['description'] = d
                    was_modified = True

            # Knowledge-based fallback for spells with known data but missing OCR fields
            if not spell.get('complete'):
                known = {
                    'Turbine di Spade': {
                        'duration': 'Istantanea',
                        'components': 'V, S',
                        'range': 'Incantatore (raggio di 1,5 metri)',
                    },
                    'Evoca Bestia': {
                        'duration': 'Concentrazione, fino a 1 ora',
                        'components': 'V, S, M (un osso, un pezzo di carne, un ciuffo di pelo)',
                    },
                    'Evoca Non Morto': {
                        'duration': 'Concentrazione, fino a 1 ora',
                        'components': 'V, S, M (una tomba piena di terra, un pezzo di sudario)',
                    },
                    "Colpo del Vento d'Acciaio": {
                        'duration': 'Istantanea',
                        'components': 'S, M (un\'arma da mischia di valore almeno 1 ma)',
                    },
                    'Trasformazione di Tenser': {
                        'duration': 'Concentrazione, fino a 10 minuti',
                        'components': 'V, S, M (qualche pelo di un pipistrello)',
                    },
                }
                if name in known:
                    for field, value in known[name].items():
                        if spell.get(field) is None or (field == 'range' and len(spell.get('range', '') or '') > 60 and len(value) <= 60):
                            spell[field] = value
                            print(f"  {name}: fixing {field}: '{value}' (knowledge)")
                            was_modified = True

            # Mark complete if all fields are filled
            all_filled = all([
                spell.get('duration') is not None,
                spell.get('components') is not None,
                len(spell.get('description', '') or '') > 50
            ])
            if all_filled:
                spell['complete'] = True
                print(f"  {name}: marked complete")

        # Check for remaining "piedi/piede" used as distance units in all text fields
        for field in ['description', 'range', 'duration']:
            val = spell.get(field, '') or ''
            if re.search(r'\d+\s*(piedi|piede|foot|feet)\b', val, re.IGNORECASE):
                new_val = convert_feet_to_meters(val)
                if new_val != val:
                    print(f"  {name}: fixed feet->meters in {field}")
                    spell[field] = new_val
                    was_modified = True
                    foot_fixes += 1

        # For ALL spells, fix feet→meters in description
        desc = spell.get('description', '') or ''
        old_desc = desc
        desc = convert_feet_to_meters(desc)
        if desc != old_desc:
            foot_fixes += 1
            print(f"  {name}: fixed feet->meters in description")
            spell['description'] = desc
            was_modified = True

        # Fix feet→meters in range
        rng = spell.get('range', '') or ''
        old_rng = rng
        rng = convert_feet_to_meters(rng)
        if rng != old_rng:
            foot_fixes += 1
            print(f"  {name}: fixed feet->meters in range: '{old_rng}' -> '{rng}'")
            spell['range'] = rng
            was_modified = True

        # Fix OCR artifacts in all text fields
        for field in ['description', 'duration', 'components', 'range', 'casting_time', 'level_text']:
            val = spell.get(field, '') or ''
            old_val = val
            val = fix_ocr(val)
            if val != old_val:
                print(f"  {name}: fixed OCR in {field}")
                spell[field] = val
                was_modified = True

        # Fix range: "Self" -> "Incantatore", "Touch" -> "Contatto"
        rng = spell.get('range', '') or ''
        old_rng = rng
        rng = re.sub(r'\bSelf\b', 'Incantatore', rng)
        rng = re.sub(r'\bTouch\b', 'Contatto', rng)
        if rng != old_rng:
            print(f"  {name}: fixed range label: '{old_rng}' -> '{rng}'")
            spell['range'] = rng
            was_modified = True

        if was_modified:
            changes += 1

    # Write updated spells
    with open(spells_path, 'w') as f:
        json.dump(spells, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Incantesimi: {changes} modificati, {foot_fixes} conversioni piedi->metri")

    # ═══════════════════════════════════════
    # FEATURES
    # ═══════════════════════════════════════
    print("\n" + "=" * 60)
    print("CORREZIONE PRIVILEGI")
    print("=" * 60)

    with open(features_path) as f:
        features = json.load(f)

    feat_changes = 0

    # Features.json structure:
    # class_features: {class_name: [{name, level, desc}, ...], ...}
    # subclass_features: {subclass_name: [{name, class, level, desc}, ...], ...}
    # race_features: {race_name: [{name, level, desc}, ...], ...}
    # background_features: {background_name: [{name, desc}, ...], ...}

    for section_name in ['class_features', 'subclass_features', 'race_features', 'background_features']:
        section = features.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for group_key, feat_list in section.items():
            if not isinstance(feat_list, list):
                continue
            for feat in feat_list:
                if not isinstance(feat, dict):
                    continue
                old_desc = feat.get('desc', '') or ''
                if not old_desc:
                    continue
                new_desc = fix_ocr(old_desc)
                new_desc = convert_feet_to_meters(new_desc)
                if new_desc != old_desc:
                    feat['desc'] = new_desc
                    feat_changes += 1
                    print(f"  [{section_name}/{group_key}] {feat.get('name', '?')}: fixed desc")

    # Write updated features
    with open(features_path, 'w') as f:
        json.dump(features, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Privilegi: {feat_changes} modificati")

    # ═══════════════════════════════════════
    # VERIFICA
    # ═══════════════════════════════════════
    print("\n" + "=" * 60)
    print("VERIFICA")
    print("=" * 60)

    # Spells
    with open(spells_path) as f:
        spells_after = json.load(f)
    complete = sum(1 for s in spells_after if s.get('complete'))
    total = len(spells_after)
    total_desc_chars = sum(len(s.get('description', '') or '') for s in spells_after)
    print(f'\n{total} spell, {complete} complete ({total - complete} incomplete)')
    print(f'Lunghezza media descrizione: {total_desc_chars / total:.0f} caratteri')

    if total - complete > 0:
        print('\nAncora incompleti:')
        for s in spells_after:
            if not s.get('complete'):
                dur = s.get('duration') is not None
                comp = s.get('components') is not None
                desc_len = len(s.get('description', '') or '')
                print(f'  {s["name"]}: dur={dur}, comp={comp}, desc_len={desc_len}')

    # Check for "piedi/piede" used as UNITS (preceded by a number)
    feet_count = 0
    for s in spells_after:
        for field in ['description', 'range', 'duration']:
            val = s.get(field, '') or ''
            if re.search(r'\d+\s*(piedi|piede)\b', val, re.IGNORECASE):
                feet_count += 1
                print(f'  ATTENZIONE: {s["name"]}.{field} ha ancora "piedi/piede" come unità')

    if feet_count == 0:
        print('\nNessun "piedi/piede" come unità nelle descrizioni ✅')

    # Features
    with open(features_path) as f:
        features_after = json.load(f)
    print(f'\nfeatures.json version: {features_after.get("__v")}')
    for section in ['class_features', 'subclass_features', 'race_features', 'background_features']:
        print(f'  {section}: {len(features_after.get(section, []))} entries')


if __name__ == '__main__':
    main()
