#!/usr/bin/env python3
"""Genera tools/tasha_expanded_lists.json dalle vere Tasha Class Spell List
Expansions (TCE Chapter 1), mappando i nomi EN canonici (5e.tools) ai nomi IT
presenti nel nostro dataset via tools/spell_name_map_it_en.json.

Solo le spell che esistono nel nostro web/data/spells.json vengono incluse:
quelle non mappabili sono saltate (e segnalate). Questo evita di inquinare le
liste di classe con voci inventate o non disponibili nel dataset IT.

Rigenerazione dataset finale: `python3 tools/build_dataset.py`
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tasha's Cauldron of Everything — Chapter 1 — Class Spell List Expansions.
# Nomi EN canonici (lowercase, come 5e.tools / DnD Beyond).
EXP_EN = {
    "bardo": [
        (1, "bless"), (1, "cause fear"), (1, "command"),
        (1, "detect poison and disease"), (1, "gentle repose"),
        (1, "protection from evil and good"),
        (2, "aid"), (2, "continual flame"), (2, "enlarge/reduce"),
        (2, "magic weapon"), (2, "spiritual weapon"), (2, "warding bond"),
        (3, "spirit guardians"), (3, "spirit shroud"), (3, "summon fey"),
        (3, "summon shadowspawn"), (3, "summon undead"),
        (4, "aura of purity"), (4, "divination"), (4, "freedom of movement"),
        (4, "summon aberration"), (4, "summon construct"),
        (4, "summon elemental"),
        (5, "greater restoration"), (5, "holy weapon"),
        (5, "steel wind strike"), (5, "summon celestial"),
        (6, "heroes' feast"), (6, "sunbeam"), (6, "word of recall"),
        (7, "power word pain"), (7, "regenerate"), (7, "resurrection"),
        (8, "holy aura"),
        (9, "mass heal"), (9, "power word heal"),
    ],
    "chierico": [
        (1, "detect evil and good"), (1, "detect poison and disease"),
        (2, "rime's binding ice"), (2, "snilloc's snowball swarm"),
        (3, "erupting earth"), (3, "sleet storm"), (3, "tidal wave"),
        (3, "wall of water"),
        (4, "vitriolic sphere"), (4, "watery sphere"),
        (5, "cone of cold"), (5, "flame strike"), (5, "holy weapon"),
        (5, "summon celestial"),
        (6, "investiture of flame"), (6, "investiture of ice"),
        (6, "investiture of stone"), (6, "investiture of wind"),
        (6, "primordial ward"),
        (7, "fire storm"), (7, "whirlwind"),
        (8, "earthquake"), (8, "holy aura"),
        (9, "power word heal"), (9, "storm of vengeance"),
    ],
    "druido": [
        (1, "absorb elements"), (1, "beast bond"),
        (1, "protection from evil and good"),
        (2, "aid"), (2, "continual flame"), (2, "enlarge/reduce"),
        (2, "warding bond"),
        (3, "elemental weapon"), (3, "revivify"), (3, "summon fey"),
        (4, "aura of life"), (4, "summon construct"),
        (4, "summon elemental"),
        (5, "summon celestial"),
        (6, "heroes' feast"), (6, "primordial ward"),
        (7, "regenerate"),
        (8, "holy aura"),
        (9, "mass heal"), (9, "power word heal"),
    ],
    "paladino": [
        (1, "command"), (1, "compelled duel"), (1, "searing smite"),
        (1, "thunderous smite"), (1, "wrathful smite"),
        (2, "branding smite"), (2, "magic weapon"), (2, "spiritual weapon"),
        (3, "aura of vitality"), (3, "blinding smite"),
        (3, "crusader's mantle"), (3, "elemental weapon"),
        (3, "spirit shroud"),
        (4, "staggering smite"), (4, "summon celestial"),
        (5, "banishing smite"), (5, "destructive wave"),
        (5, "holy weapon"), (5, "summon celestial"),
    ],
    "ranger": [
        (1, "absorb elements"), (1, "ensnaring strike"), (1, "entangle"),
        (1, "hail of thorns"), (1, "searing smite"),
        (2, "magic weapon"), (2, "summon beast"),
        (3, "ashardalon's stride"), (3, "elemental weapon"),
        (3, "revivify"), (3, "summon fey"),
        (4, "summon elemental"),
        (5, "steel wind strike"), (5, "swift quiver"),
    ],
    "mago": [
        (1, "absorb elements"), (1, "chaos bolt"), (1, "chromatic orb"),
        (1, "command"), (1, "protection from evil and good"),
        (1, "witch bolt"),
        (2, "aganazzar's scorcher"), (2, "continual flame"),
        (2, "dragon's breath"), (2, "flame blade"), (2, "flaming sphere"),
        (2, "maximilian's earthen grasp"), (2, "melf's acid arrow"),
        (2, "pyrotechnics"), (2, "skywrite"),
        (2, "snilloc's snowball swarm"),
        (3, "elemental weapon"), (3, "erupting earth"), (3, "flame arrows"),
        (3, "melf's minute meteors"), (3, "sleet storm"),
        (3, "tidal wave"), (3, "wall of water"),
        (4, "elemental bane"), (4, "vitriolic sphere"), (4, "watery sphere"),
        (5, "control winds"), (5, "destructive wave"), (5, "immolation"),
        (5, "maelstrom"), (5, "transmute rock"),
        (6, "bones of the earth"), (6, "investiture of flame"),
        (6, "investiture of ice"), (6, "investiture of stone"),
        (6, "investiture of wind"), (6, "primordial ward"),
        (7, "crown of stars"), (7, "whirlwind"),
        (8, "abi-dalzim's horrid wilting"), (8, "earthquake"),
        (9, "storm of vengeance"),
    ],
    "stregone": [
        (1, "absorb elements"), (1, "beast bond"), (1, "catapult"),
        (1, "frost fingers"), (1, "ice knife"),
        (1, "protection from evil and good"),
        (2, "aganazzar's scorcher"), (2, "dragon's breath"),
        (2, "flame blade"), (2, "flaming sphere"),
        (2, "maximilian's earthen grasp"), (2, "melf's acid arrow"),
        (2, "pyrotechnics"), (2, "skywrite"),
        (2, "snilloc's snowball swarm"), (2, "warding wind"),
        (3, "erupting earth"), (3, "flame arrows"),
        (3, "melf's minute meteors"), (3, "sleet storm"),
        (3, "tidal wave"), (3, "wall of water"),
        (4, "elemental bane"), (4, "storm sphere"),
        (4, "vitriolic sphere"), (4, "watery sphere"),
        (5, "control winds"), (5, "destructive wave"), (5, "immolation"),
        (5, "maelstrom"), (5, "transmute rock"),
        (6, "bones of the earth"), (6, "investiture of flame"),
        (6, "investiture of ice"), (6, "investiture of stone"),
        (6, "investiture of wind"), (6, "primordial ward"),
        (7, "whirlwind"),
        (8, "abi-dalzim's horrid wilting"), (8, "earthquake"),
        (9, "storm of vengeance"),
    ],
    "warlock": [
        (1, "cause fear"), (1, "charm person"), (1, "command"),
        (1, "detect magic"), (1, "illusory script"),
        (1, "ray of sickness"), (1, "unseen servant"),
        (2, "darkness"), (2, "hold person"), (2, "mind spike"),
        (2, "spider climb"), (2, "spiritual weapon"),
        (2, "suggestion"), (2, "summon beast"),
        (3, "clairvoyance"), (3, "intellect fortress"),
        (3, "summon fey"), (3, "summon shadowspawn"),
        (3, "summon undead"),
        (4, "aura of purity"), (4, "charm monster"),
        (4, "shadow of moil"), (4, "summon aberration"),
        (4, "summon construct"),
        (5, "dream"), (5, "holy weapon"), (5, "modify memory"),
        (5, "planar binding"), (5, "summon celestial"),
        (6, "investiture of flame"), (6, "investiture of ice"),
        (6, "investiture of stone"), (6, "investiture of wind"),
        (6, "soul cage"),
        (7, "finger of death"), (7, "plane shift"),
        (8, "demiplane"), (8, "glibness"),
        (9, "astral projection"), (9, "weird"),
    ],
}


def main() -> int:
    map_path = os.path.join(ROOT, "tools", "spell_name_map_it_en.json")
    sp_path = os.path.join(ROOT, "web", "data", "spells.json")
    out_path = os.path.join(ROOT, "tools", "tasha_expanded_lists.json")

    name_map = json.load(open(map_path, encoding="utf-8"))
    en_to_it = {}
    for it_raw, info in name_map.items():
        if not isinstance(info, dict):
            continue
        en = (info.get("en") or "").lower().strip()
        canon = info.get("canon_it") or it_raw
        if en and canon:
            en_to_it.setdefault(en, canon)

    spells = json.load(open(sp_path, encoding="utf-8"))
    ds_names = {s["name"] for s in spells}

    result = {}
    skipped_total = 0
    for cls, lst in EXP_EN.items():
        kept, skipped = [], []
        seen = set()
        for lvl, en in lst:
            it = en_to_it.get(en.lower())
            if it and it in ds_names:
                key = (lvl, it)
                if key in seen:
                    continue
                seen.add(key)
                kept.append({"level": lvl, "name": it})
            else:
                skipped.append({"level": lvl, "en": en, "mapped_it": it})
        result[cls] = kept
        skipped_total += len(skipped)
        print(f"  {cls}: {len(kept)} kept, {len(skipped)} skipped (spell IT non nel dataset)")
        for s in skipped:
            print(f"    - L{s['level']} EN={s['en']!r} mapped_it={s['mapped_it']!r}")

    out = dict(result)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[tasha-expanded] scritto {out_path}")
    print(f"[tasha-expanded] {skipped_total} entry totali saltate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
