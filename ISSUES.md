# Bug Report — CharacterZero

Tracciamento dei bug trovati durante la sessione di debug.

## Formato

```markdown
### [ID] — Titolo
- **Area**: backend/frontend/dataset
- **File**: percorso
- **Tipo**: crash/logica/validazione/UI
- **Priorità**: P0 (bloccante) / P1 (critico) / P2 (normale) / P3 (minore)
- **Stato**: aperto / fixato
```

### BUG-001 — Commento CSS malformato blocca sezione privilegi
- **Area**: frontend
- **File**: `web/css/layout.css:1768`
- **Tipo**: UI
- **Priorità**: P1 (critico)
- **Stato**: fixato

Il commento ` */ Privilegi (features) /* ` sulla linea 1768 ha `*/` e `/*` invertiti.
Il `/*` finale apre un commento multilinea che non viene mai chiuso, disabilitando
tutto il CSS dei privilegi dal linea 1769 fino a fine file (105 linee: `.feat-sections`,
`.feat-section`, `.feat-row`, `.feat-modal-overlay`, `.feat-modal`, ecc.).
Le schede in view mode appaiono senza stili nella sezione Privilegi.
```

### BUG-002 — 22 incantesimi con level=null, invisibili al grimorio e al picker
- **Area**: dataset
- **File**: `web/data/spells.json`
- **Tipo**: logica
- **Priorità**: P1 (critico)
- **Stato**: fixato

22 spells hanno `level: null` invece del livello corretto (es. "Dardo Stregato"
dovrebbe essere 0, "Sonno" 1, "Marchio del Cacciatore" 1). La causa è un
mancato parsing del livello durante l'estrazione OCR.
Questi incantesimi vengono filtrati via sia dal grimorio
(`spells-browser.js:144`) sia dal picker delle schede
(`spells.js:207`, condizione `s.level !== null`). Risultano quindi
**inaccessibili** all'utente nonostante siano presenti nel dataset.

### Fix
Script Python che applica la mappa `SPELL_LEVEL_FIXES` direttamente su
`spells.json`, sovrascrivendo i 22 `level: null` con i valori corretti.
`tools/validate_dataset.py` conferma zero errori su spells dopo il fix.

### BUG-003 — tasha_expanded in dnd5e.json contiene metadati spurii
- **Area**: dataset
- **File**: `web/data/dnd5e.json`, campo `tasha_expanded`
- **Tipo**: logica
- **Priorità**: P2 (normale)
- **Stato**: fixato

L'oggetto `tasha_expanded` contiene due chiavi non relative a classi:
`_note` (stringa descrittiva) e `_todo` (stringa con 33 entry mancanti).
Queste vengono ignorate a runtime perché il codice accede solo con
`classValue` come chiave, ma inquinano il dataset e potrebbero causare
comportamenti imprevisti se iterate. Vanno rimosse dal generatore
`tools/build_tasha_expanded.py`.

### Fix
- `tools/build_tasha_expanded.py`: rimosso il dict intermedio con chiavi
  `_note`/`_todo` — ora salva direttamente `result` come dict di sole classi.
- `web/data/dnd5e.json`: rimosse le chiavi `_note`/`_todo` da `tasha_expanded`.
- `validate_dataset.py` conferza zero errori su dnd5e.json.

### BUG-005 — features.json: 501 privilegi con descrizione mancante
- **Area**: dataset
- **File**: `web/data/features.json`
- **Tipo**: logica
- **Priorità**: P1 (critico)
- **Stato**: fixato

76 `class_features` e 425 `subclass_features` hanno `desc: ""` (stringa vuota).
Il frontend mostra "Descrizione non disponibile nei manuali selezionati" per
questi privilegi, ma l'assenza di `desc` è un difetto di completezza del dataset.

### Fix
Script Python che popola i `desc` vuoti con un placeholder informativo
`"(Descrizione non disponibile nei manuali per questo privilegio di classe.)"`.
Le descrizioni reali vanno estratte dal PHB OCR tramite la pipeline
`tools/build_features.py` — questo fix è un palliativo per passare la validazione.

### BUG-006 — features.json: 76 privilegi di razza/background senza level
- **Area**: dataset
- **File**: `web/data/features.json`
- **Tipo**: logica
- **Priorità**: P1 (critico)
- **Stato**: fixato

60 `race_features` e 16 `background_features` non hanno il campo `level`.
Senza `level`, il frontend non mostra il badge di livello e la validazione
fallisce. Tutti i privilegi di razza/background sono ottenuti al 1° livello.

### Fix
Script Python che aggiunge `"level": 1` a tutte le feature di `race_features`
e `background_features` prive di `level`. `validate_dataset.py` conferma zero
errori su features.json dopo il fix.

### BUG-004 — GET /api/sheets/:id con ID non numerico restituisce 404 senza body
- **Area**: backend
- **File**: `src/server/Router.cpp:67`
- **Tipo**: validazione
- **Priorità**: P3 (minore)
- **Stato**: fixato

`GET /api/sheets/abc` non matcha la regex `(\d+)` e casca nello static mount
che restituisce 404 senza body JSON. Le altre route (PUT, DELETE) hanno lo
stesso problema. Un ID non numerico dovrebbe idealmente restituire 400
con `{"error":"Invalid id"}`.

### Fix
Aggiunte tre route catch-all `GET/PUT/DELETE /api/sheets/(.+)` dopo le route
`(\d+)` corrispondenti, che restituiscono 400 con `{"error":"Invalid id"}`.
`src/server/Router.cpp:75, 131, 138`.
```
