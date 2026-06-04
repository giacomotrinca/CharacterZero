#!/usr/bin/env python3
"""
validate_dataset.py
Validates web/data/{spells,dnd5e,features}.json structural integrity.
Returns non-zero exit code on any issue.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "web", "data")

ERRORS = []


def err(msg):
    ERRORS.append(msg)
    print(f"  FAIL: {msg}", file=sys.stderr)


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        err(f"{name}: file not found")
        return None
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            err(f"{name}: invalid JSON — {e}")
            return None


# ── spells.json ──────────────────────────────────────────────────────────────

def validate_spells(data):
    if not isinstance(data, list):
        err("spells.json: expected array")
        return

    expected = {"name", "name_en", "classes", "level", "school", "ritual",
                "level_text", "casting_time", "range", "components", "duration",
                "description", "source", "page", "complete", "tags", "target"}

    for i, s in enumerate(data):
        if not isinstance(s, dict):
            err(f"spells[{i}]: not an object"); continue

        name = s.get("name")
        if not isinstance(name, str) or not name.strip():
            err(f"spells[{i}]: missing/empty name"); continue

        level = s.get("level")
        if level is None:
            err(f"spells[{i}] ({name}): level is null")
        elif not isinstance(level, int) or level < 0 or level > 9:
            err(f"spells[{i}] ({name}): level={level!r} out of range [0-9]")

        if not isinstance(s.get("classes"), list):
            err(f"spells[{i}] ({name}): classes is not a list")

        for field in expected:
            if field not in s:
                err(f"spells[{i}] ({name}): missing field '{field}'")


# ── dnd5e.json ──────────────────────────────────────────────────────────────

def validate_dnd5e(data):
    if not isinstance(data, dict):
        err("dnd5e.json: expected object"); return

    for section in ("manuals", "skills", "classes", "backgrounds", "races",
                    "feats", "spell_slots", "tasha_expanded"):
        if section not in data:
            err(f"dnd5e.json: missing '{section}'")

    # tasha_expanded — no spurious underscore-prefixed keys
    tasha = data.get("tasha_expanded", {})
    if isinstance(tasha, dict):
        for key in tasha:
            if key.startswith("_"):
                err(f"dnd5e.json tasha_expanded: spurious key '{key}'")

    # spell_slots — validate structure
    slots = data.get("spell_slots", {})
    for caster_type, arr in slots.items() if isinstance(slots, dict) else []:
        if not isinstance(arr, list):
            err(f"dnd5e.json spell_slots.{caster_type}: expected array")

    # classes — check each has required fields
    for cls in data.get("classes", []):
        if not cls.get("value"):
            err(f"dnd5e.json class missing 'value': {cls.get('label', '?')}")
        if not isinstance(cls.get("asi_levels"), list):
            err(f"dnd5e.json class {cls.get('value', '?')}: asi_levels not a list")
        if not isinstance(cls.get("save_profs"), list):
            err(f"dnd5e.json class {cls.get('value', '?')}: save_profs not a list")


# ── features.json ────────────────────────────────────────────────────────────

def validate_features(data):
    if not isinstance(data, dict):
        err("features.json: expected object"); return

    sections = {
        "class_features": dict,
        "subclass_features": dict,
        "race_features": dict,
        "background_features": dict,
    }
    for key, expected_type in sections.items():
        val = data.get(key)
        if val is None:
            err(f"features.json: missing '{key}'")
        elif not isinstance(val, expected_type):
            err(f"features.json.{key}: expected {expected_type.__name__}, "
                f"got {type(val).__name__}")

    # spot-check: each feature entry has name, level, desc
    for section_name in sections:
        section = data.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for entity_key, features in section.items():
            if not isinstance(features, list):
                err(f"features.json.{section_name}.{entity_key}: not a list")
                continue
            for i, feat in enumerate(features):
                if not isinstance(feat, dict):
                    err(f"features.json.{section_name}.{entity_key}[{i}]: "
                        f"not an object"); continue
                if not feat.get("name"):
                    err(f"features.json.{section_name}.{entity_key}[{i}]: "
                        f"missing name")
                if "level" not in feat:
                    err(f"features.json.{section_name}.{entity_key}[{i}]: "
                        f"missing level")
                if not feat.get("desc"):
                    err(f"features.json.{section_name}.{entity_key}[{i}]: "
                        f"missing desc")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    datasets = [
        ("spells.json", validate_spells),
        ("dnd5e.json", validate_dnd5e),
        ("features.json", validate_features),
    ]

    for fname, validator in datasets:
        print(f"Validating {fname}...")
        data = load_json(fname)
        if data is not None:
            validator(data)

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s) found.", file=sys.stderr)
        sys.exit(1)
    print("All datasets OK.")


if __name__ == "__main__":
    main()
