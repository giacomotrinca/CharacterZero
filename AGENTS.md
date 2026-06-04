# CharacterZero — Project Memory

Memoria di progetto per agenti AI che lavorano su questo repo. Tienila aggiornata quando
cambiano architettura, convenzioni o decisioni di design.

## Chi sei
Sei un esperto di programmazione c++ per backend robusti. Sei anche un designer di siti web. Prediligi interfacce pulite, ma ricche, con animazioni smooth ma semplici. 

## Cos'è

Character sheet manager personale per giochi di ruolo. Locale-first, single user.
Backend C++ che serve sia API JSON sia frontend static in vanilla JS.
Dati D&D 5e offline: classi, incantesimi, privilegi, talenti, manuali.

## Stack

- **Backend**: C++17, [cpp-httplib](https://github.com/yhirose/cpp-httplib) v0.18.1,
  [nlohmann/json](https://github.com/nlohmann/json) v3.11.3,
  [SQLiteCpp](https://github.com/SRombauts/SQLiteCpp) 3.3.2 (con sqlite interno).
- **Build**: CMake ≥ 3.20 (`FetchContent`). `Release` di default.
  Warning: `-Wall -Wextra -Wpedantic` (GCC/Clang), `/W4` (MSVC).
- **DB**: SQLite (WAL, foreign_keys ON). Migrations in `src/db/migrations/NNN_*.sql`,
  version tracking via tabella `schema_version`.
- **Frontend**: HTML statico + vanilla JS, nessun bundler/ framework.
  Servito da httplib (`set_mount_point("/", webRoot)`).
- **Lingua UI**: italiano.

## Layout

```
CMakeLists.txt                     # build configuration
src/
  main.cpp                         # entry point, server bootstrap
  db/
    Database.{h,cpp}               # wrapper SQLiteCpp + migrations runner
    migrations/
      001_init.sql                 # sheets table
      002_aragorn_details.sql      # seed data
  domain/
    Sheet.{h,cpp}                  # entity + to JSON
    SheetRepository.{h,cpp}        # CRUD SQL
    Schema.{h,cpp}                 # definizioni kind/subtype
  server/
    Json.h                         # alias cz::Json = nlohmann::json
    Router.{h,cpp}                 # registra route API + static mount
web/
  index.html                       # home page (lista schede)
  new.html                         # creazione personaggio (wizard)
  sheet.html                       # visualizzazione / modifica
  spells.html                      # grimorio esplorativo
  css/
    theme.css                      # design tokens, base, tipografia
    layout.css                     # tutti i componenti
  js/
    api.js                         # client HTTP, SchemaCache, DndCache, helpers
    ui.js                          # toast, confirm, skeleton, preserveScroll
    home.js                        # home page controller
    new.js                         # wizard creazione controller
    sheet.js                       # sheet view/edit controller
    token.js                       # TokenWidget (upload immagini)
    stats.js                       # StatsWidget (punteggi caratteristica)
    multiclass.js                  # MulticlassWidget (classi/ASI/talenti)
    skills.js                      # SkillsWidget (abilità)
    spells.js                      # SpellsWidget (incantesimi scheda)
    spells-browser.js              # grimorio browser (filtri, modal)
    features.js                    # FeaturesCache (privilegi)
  data/
    dnd5e.json                     # classi, sottoclassi, background, razze, talenti, ASI, spell_slots, tasha_expanded
    spells.json                    # 429 incantesimi indicizzati
    features.json                  # privilegi di classe/sottoclasse/razza/background
data/                              # creata a runtime (SQLite DB qui)
tools/                             # pipeline Python offline (estrazione manuali, dataset)
```

`CZ_WEB_ROOT`, `CZ_DATA_DIR`, `CZ_MIGRATIONS_DIR` sono iniettati come
`target_compile_definitions` puntando al source tree → **il binario non è rilocabile**.
Host/porta configurabili via `CZ_HOST`/`CZ_PORT` (default `127.0.0.1:8080`).

## Build & run

```bash
cmake -S . -B build
cmake --build build -j
./build/CharacterZero        # http://127.0.0.1:8080
```

## API

Base path `/api`. Tutto JSON. Payload max 1 MiB.

| Method | Path | Note |
|--------|------|------|
| GET | `/api/health` | `{status:"ok"}` |
| GET | `/api/schema` | `{kinds:[{value,label,description,subtypeGroupLabel,subtypes:[],usesClasses}]}` |
| GET | `/api/sheets` | Summary list, `updated_at DESC`. Include `race`/`token_thumb` da `data` |
| GET | `/api/sheets/:id` | Full sheet (404 se mancante) |
| POST | `/api/sheets` | `{kind, subtype, name, data?}` → `{id}` 201 |
| PUT | `/api/sheets/:id` | PATCH di `name`/`data`. **Non** modifica `kind`/`subtype` |
| DELETE | `/api/sheets/:id` | 204 / 404 |

Risposte errore: `{ "error": "..." }` con status 4xx.

### Validazioni server-side

- **id numerico** non negativo
- **name** trimmed, non vuoto, ≤ 200 char
- **kind** ∈ `Schema::kinds()`
- **subtype** valido per il kind (validato da `Schema::isValidSubtypeFor`)
- **data** JSON object opzionale (default `{}`)
- `character ⇒ human`, `npc ⇒ beast` (vincolo applicativo in `Router.cpp`)

Log: `[http] METHOD PATH -> STATUS (N bytes)`.
Graceful shutdown su SIGINT/SIGTERM.

## Modello dati

Tabella unica `sheets`:

| Colonna | Tipo | Note |
|---------|------|------|
| `id` | INTEGER PK AUTO | |
| `kind` | TEXT NOT NULL | CHECK (`character`/`npc`) |
| `subtype` | TEXT NOT NULL | |
| `name` | TEXT NOT NULL | |
| `data` | TEXT NOT NULL DEFAULT `'{}'` | JSON blob |
| `created_at` | TEXT DEFAULT `datetime('now')` | |
| `updated_at` | TEXT DEFAULT `datetime('now')` | Aggiornato ad ogni write |

Indici: `idx_sheets_kind`, `idx_sheets_name`.

### Campi di gioco in `data` (kind `character`)

```json
{
  "classes": [
    {
      "value": "guerriero",
      "levels": 5,
      "subclass": "cavaliere mistico",
      "asi_choices": [
        { "kind": "asi", "plus": { "str": 2 } },
        { "kind": "feat", "name": "Resiliente" }
      ]
    }
  ],
  "level": 5,
  "background": "Soldato",
  "sources": ["manuale_del_giocatore", "guida_di_xanathar"],
  "race": "Umano",
  "stats": { ... },
  "skills": { ... },
  "spells": { ... },
  "token": "data:image/jpeg;base64,...",
  "token_thumb": "data:image/jpeg;base64,..."
}
```

**Legacy** (schede pre-multiclasse): `class:string + level + subclass`. Ricostruito
automaticamente da `MulticlassWidget.deserialize()`; ripulito al save.
Alias legacy: `warrior → guerriero` in `LEGACY_CLASS`.

## Schema kind/subtype

Fonte unica: `src/domain/Schema.cpp`, esposta via `GET /api/schema`.

| Kind | Label | Subtype | UsesClasses |
|------|-------|---------|-------------|
| `character` | Personaggio | `human` (Umano) | `true` |
| `npc` | PNG | `beast` (Bestia) | `false` |

`SchemaCache` in `api.js` (chiave `cz_schema`, version `v3-dnd`) carica e cacha lo
schema in `sessionStorage`. Helper: `kindLabel()`, `subtypeGroupLabel()`,
`subtypeLabel()`, `usesClasses()`.

## Frontend — widget JS

Niente framework, niente bundler. Ogni file è un IIFE che espone un costruttore/oggetto
globale. `new.html` e `sheet.html` includono i widget in ordine:
`api.js → token.js → stats.js → multiclass.js → skills.js → spells.js → ui.js → [controller]`.

| File | Righe | Export | Scopo |
|------|-------|--------|-------|
| `api.js` | 482 | `api`, `SchemaCache`, `DndCache`, `MC_*`, `STATS`, `ICONS`, `fmtDate`, `escapeHtml` | Client HTTP, cache dataset 5e, helpers multiclasse/proficency |
| `ui.js` | 74 | `UI.toast/confirm/skeleton/preserveScroll` | Toast, confirm modale, skeleton loading |
| `token.js` | 134 | `TokenWidget` | Upload immagini (trascinamento, crop 512px, thumb 64px, JPEG) |
| `stats.js` | 534 | `StatsWidget` | Punteggi (point-buy/roll/manual), bonus razziali, ASI, mod |
| `multiclass.js` | 476 | `MulticlassWidget` | Liste classi, sottoclassi, slot ASI/talenti, validazione |
| `skills.js` | 239 | `SkillsWidget` | 18 abilità, concessioni fisse/scelte classe/razza |
| `spells.js` | 430 | `SpellsWidget` | Incantesimi per scheda, slot pool multiclasse, prep modes |
| `features.js` | 90 | `FeaturesCache` | Privilegi classi/sottoclassi/razze/background |
| `spells-browser.js` | 327 | — (IIFE) | Grimorio esplorativo con filtri, modal dettaglio |
| `home.js` | 37 | `renderHome()` | Lista schede |
| `new.js` | 351 | — (script) | Wizard creazione (4 step) |
| `sheet.js` | 824 | — (script) | View/edit scheda, privilegi, delete |

### DndCache (`api.js`)

Carica `web/data/dnd5e.json` (cache `sessionStorage` `cz_dnd`, version bump via `__v`
numerico — attualmente `14`). Helper principali:

- `manuals()`, `manualLabel()` — 6 manuali
- `classes()` — 13 classi con `spellcasting`, `subclass_level`, `asi_levels`, `save_profs`
- `resolveClass()` — legacy alias
- `subclasses(class, sources)`, `subclassDef(class, subclass)`
- `backgrounds(sources)`, `races(sources)`, `feats(sources)`
- `asiLevels(class)`, `spellcasting(class)`, `isCaster(class)`
- `effectiveSpellcasting(class, subclass, level)` — gestisce third-caster (Eldritch Knight, Arcane Trickster)
- `cantripsKnown()`, `spellsKnown()`, `preparedCount()` — accept subclass param
- `fullCasterSlotsForMulticlass()` — PHB pag.164 (full + half/2 + third/3)
- `pactSlotsFor()` — Warlock pact magic
- `spellsForClass(class, sources)` — applica Tasha expanded lists
- `loadSpells()` — lazy-load `spells.json`

### FeaturesCache (`features.js`)

Carica `web/data/features.json` (cache `cz_features`, version `5`).
Helper: `classFeatures()`, `subclassFeatures()`, `raceFeatures()`, `backgroundFeatures()`.
Usato da `sheet.js` per renderizzare la sezione "Privilegi".

### Schemi dataset (`web/data/`)

| File | Entità | Uso |
|------|--------|-----|
| `dnd5e.json` | 6 manuals, 13 classes, 103 subclasses, 22 backgrounds, 15 races, 42 feats, 18 skills, spell_slots, tasha_expanded | Creator e editor |
| `spells.json` | 429 spells con nome/EN/livello/scuola/tempo/gittata/componenti/durata/descrizione/classi/target/tags | Grimorio + spells widget |
| `features.json` | Privilegi classe/sottoclasse/razza/background con descrizioni | Sezione privilegi |

### Dataset — rigenerazione

```bash
python3 tools/build_tasha_expanded.py   # (opzionale, se aggiorni mappe)
python3 tools/build_catalog.py          # da chunks OCR
python3 tools/build_dataset.py          # merge → web/data/{dnd5e,spells}.json
python3 tools/build_features.py         # → web/data/features.json
```

### Dataset version bump

Quando modifichi la **forma** di un dataset (nuovo campo, struttura cambiata), incrementa
la versione corrispondente nel JS e nel generatore Python:
- `dnd5e.json` → `DndCache._version` in `api.js` + `DATASET_VERSION` in `build_dataset.py`
- `features.json` → `VERSION` in `features.js` + `DATASET_VERSION` in `build_features.py`

## Dataset 5e — pipeline tools

Pipeline offline Python (`~/miniconda3/bin/python`) per estrarre manuali PDF.
Vedi `tools/extract_manuals.py` (subcomandi `probe`/`extract`/`index`/`all`).
`pdftext` per testo pulito (Xanathar, Tasha); `pypdfium2` + Tesseract per OCR
(Manuale del Giocatore/Master/Mostri, Guida Avventurieri).

File importanti:
- `tools/dnd5e_canon.py` — scheletro canonico (classi, sottoclassi, slot, spellcasting, skill choices, backgrounds PHB, feats, races)
- `tools/build_catalog.py` — fuzzy-match sottoclassi/background da chunk OCR
- `tools/build_dataset.py` — merge canon + catalog + spells + Tasha
- `tools/build_features.py` — assembla `features.json` da OCR PHB + chunk testuali
- `tools/class_features_data.py` — dati privilegi canonici (SRD 5.1 CC-BY-4.0)
- `tools/spell_name_map_it_en.json` — mapping IT→EN per gli incantesimi (444 entries)
- `tools/spell_classes_en_5etools.json` — EN class lookup da 5e.tools
- `tools/extract_for_correction.py` — produce dati di confronto per agente AI di correzione
- `tools/fetch_online_reference.py` — fetch descrizioni EN da dnd5eapi.co per SRD spells

### Correzione dataset via AI agent

`tools/extract_for_correction.py` prepara il materiale di confronto per un agente
AI che deve correggere `web/data/spells.json` e `web/data/features.json`:

```bash
python3 tools/extract_for_correction.py
```

Produce in `manuals/_index/`:
- `pages/<manual>.jsonl` — testo pagina-per-pagina ricostruito dai content_list già estratti
- `spell_context.json` — 429 incantesimi con dato corrente + pagine raw del manuale
- `feature_context.json` — 824 privilegi con dato corrente + pagine PHB raw

L'agente confronta `current` (dato attuale nel dataset) con `raw_pages`
(testo OCR/pdftext grezzo) e corregge descrizioni, campi, nomi.
Non riesegue OCR — riusa i content_list.json già in `_extracted/`.

Il protocollo completo di correzione è in `COMPARING_DES.md`, che include
la regola di conversione piedi→metri e la priorità fonte online EN.

## Sistema incantesimi

Regole PHB cap.10 + pag.164–165. Categorizzazione classi in `dnd5e_canon.py`
(`SPELLCASTING`):

| Categoria | Classi | Prep mode | Slot |
|-----------|--------|-----------|------|
| `full` | Bardo, Chierico, Druido, Mago, Stregone | prepared (lista classe) o known | FULL_CASTER_SLOTS[1..9] |
| `half` | Paladino, Ranger, Artefice | prepared (lista classe) | HALF_CASTER_SLOTS[1..5] |
| `pact` | Warlock | known (lista pact) | PACT_SLOTS dedicati (short-rest) |
| `third` | Cavaliere Mistico, Mistificatore Arcano | known (lista mago, gated a L3) | THIRD_CASTER_SLOTS[1..4] |
| `martial` | Barbaro, Guerriero, Ladro, Monaco | — | — |

- **Third-caster**: definiti in `SUBCLASS_SPELLCASTING`, promuovono classe martial
  a incantatrice da L3. `spell_list_class: 'mago'`.
- **Multiclasse** (PHB pag.164): livello effettivo = `full + floor(half/2) + floor(third/3)`.
  Warlock separato (pact slot dedicati).
- **Tasha expanded**: `DndCache.spellsForClass()` applica automaticamente le liste
  ampliate del Calderone di Tasha quando `tasha_italiano` è tra le fonti.
- **Prepared**: Chierico/Druido = `wis_mod + level`; Paladino = `cha_mod + level/2_floor`;
  Artefice = `int_mod + level/2_ceil` (TCE); Mago = `int_mod + level` (libro: 6 + 2/livello).

## Multiclasse + ASI/Talenti

`data.classes` è array ordinato. La prima classe è la primaria (dà skill choices).
Livello totale = somma (`MC_totalLevel`) → `profBonusFromLevel`.

Slot ASI/Talento per classe ai livelli in `asi_levels`:
- Default: `[4,8,12,16,19]`
- Guerriero: `[4,6,8,12,14,16,19]`
- Ladro: `[4,8,10,12,16,19]`

Ogni slot: `kind:'asi'` (con `plus` +2 a una stat o +1/+1 a due) o `kind:'feat'`
(con `name`). Non validato: cap a 20, due stat diverse per +1/+1.

## Design system

- **Dark premium**: base `#08060e`, ink `#ede9ff`, accent `#e8993a` (amber).
- **Background**: radial gradient bloom (purple top, amber bottom-right) + dot grid CSS.
- **Font**: Bricolage Grotesque (display/h1), Inter (body/UI).
- **Vietato**: tema chiaro, font fantasy, `alert()`/`confirm()` nativi, hard-code di
  kind/subtype/classi nel frontend.

## Convenzioni codice

- Namespace `cz::` per tutto il backend.
- `Json` = alias `nlohmann::json` (sempre via `server/Json.h`).
- Repository pattern: niente SQL fuori da `*Repository.cpp`.
- Validazione input: nel `Router`, prima di toccare il repository.
- Frontend: helpers globali in `api.js`, widget come IIFE.
- Microcopy: italiano.
- Migration: nuovo file `NNN_descrittivo.sql` con `NNN` > ultima, idempotente
  (`IF NOT EXISTS`) quando possibile. Mai editare `001_init.sql`.
- Kind/subtype nuovi: basta toccare `Schema.cpp` — frontend via `/api/schema`.
  Aggiungi icona in `ICONS` se serve.
- Errori frontend: `UI.toast(msg, 'error')`. Conferme distruttive:
  `await UI.confirm({ danger: true })`. No `alert()`/`confirm()` nativi.
- Sviluppo su macOS.

## Debiti tecnici (priorità decrescente)

1. `CZ_*` definitions puntano al source tree → binario non rilocabile.
2. Nessun test, nessuna CI, nessun `.clang-format`.
3. Nessuna paginazione/ricerca su `GET /api/sheets`.
4. PUT non permette di modificare `kind`/`subtype` (solo `name` + `data`).
5. Nessuna gestione di `SQLITE_BUSY` (retry/mutex).
6. Nessuna validazione JSON Schema su `data` (né su `features.json`).
7. Multiclasse: niente skill grants classi secondarie (subset PHB pag.164),
   niente validazione due stat diverse per ASI +1/+1, niente cap a 20.
8. `spells.json` classi basate su EN lookup statico (`spell_classes_en_5etools.json`)
   — assenza di tagging diretto IT→classi nel dataset.
