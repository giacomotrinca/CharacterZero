# Protocollo di Bug-Fixing — CharacterZero

Protocollo operativo per agenti AI. Leggi prima `AGENTS.md` per contesto completo.

## Pre-flight

- [ ] Leggi `AGENTS.md` — specialmente Stack, Layout, Convenzioni, Debiti tecnici
- [ ] Identifica area del bug: **backend** / **frontend** / **dataset** / **build**
- [ ] Se bug già tracciato, verifica stato e note in `ISSUES.md`
- [ ] `git log --oneline -10` per modifiche recenti
- [ ] `git diff --name-only` per file toccati ma non committati

---

## Fase 1 — Riprodurre

```bash
# Build pulita
cmake -S . -B build && cmake --build build -j

# Avvia server in background
./build/CharacterZero &
SERVER_PID=$!

# Test che il server risponda
curl -s http://127.0.0.1:8080/api/health
# → {"status":"ok"}
```

- Riproduci lo scenario che causa il bug (curl per API, browser per UI)
- Cattura output server, console browser, response HTTP
- Se il bug è intermittente, ripeti 3× per escludere race condition

Stop server: `kill $SERVER_PID` (o SIGINT).

---

## Fase 2 — Isolare (trova la root cause)

Lancia **task paralleli** per esplorare il codebase:

```bash
# Backend: cerca pattern sospetti
rg "catch\s*\(" src/          # eccezioni inghiottite
rg "std::cerr\|std::cout" src/ # debug output
rg "TODO\|FIXME\|HACK" src/    # debiti noti

# Frontend: cerca pattern problematici
rg "console\.log" web/js/      # debug dimenticato
rg "alert\(" web/js/           # alert nativo (vietato)
rg "undefined\b" web/js/      # potenziali undefined
```

Usa `task` (general agent) per esplorazioni mirate in parallelo, ad esempio:

- "Trova tutte le route API e confrontale con quelle documentate in AGENTS.md"
- "Cerca nel frontend accessi a variabili non dichiarate o potenziali `undefined is not an object`"
- "Valida i dataset: `python3 tools/validate_dataset.py`"
- "Cerca commenti CSS malformati: `rg '/\*' web/css/` e verifica bilanciamento"
- "Confronta response API attuali con gli schemi attesi dal frontend"

### Checklist per area

**Backend** (`src/`)
- [ ] Log HTTP: `[http] METHOD PATH -> STATUS (bytes)` — status 4xx/5xx?
- [ ] Eccezioni C++ non catturate (std::terminate)
- [ ] `sendError()` chiamata con status giusto? Body JSON valido?
- [ ] Validazione input: `parseId()`, `trim()`, `kMaxNameLength`
- [ ] Regex route: matcha il pattern giusto? (`\d+` per ID)
- [ ] SQL: migrazioni eseguite? `001_init.sql` + `002_*.sql`
- [ ] `SQLite::Exception` propagata o catturata?

**Frontend** (`web/js/`, `web/css/`)
- [ ] Console errors: TypeError, undefined, network errors
- [ ] Network tab: API response status e body
- [ ] Elements tab: CSS applicato? Classi giuste?
- [ ] SessionStorage: `cz_schema`, `cz_dnd`, `cz_features` — version bump fatto?
- [ ] `UI.toast()` visto dall'utente?
- [ ] Commenti CSS: `/* */` bilanciati? (ricorda BUG-001)
- [ ] Async: Promise non gestite, race su cache multiple

**Dataset** (`web/data/`)
- [ ] `python3 tools/validate_dataset.py` — zero errori
- [ ] Version bump: `DndCache._version` in `api.js`, `DATASET_VERSION` in Python
- [ ] `__v` in `dnd5e.json` / `features.json` incrementato se struttura cambiata
- [ ] Encoding UTF-8 (no latin-1)
- [ ] `null` fields dove ci si aspetta valori (BUG-002)
- [ ] Chiavi spurie (`_note`, `_todo` — BUG-003)

---

## Fase 3 — Correggere

Segui le convenzioni di `AGENTS.md`. Regole chiave:

- Backend: namespace `cz::`, validazione input in `Router.cpp`, SQL solo nei Repository
- Frontend: IIFE/widget pattern, helpers globali in `api.js`, niente bundler
- UI: niente `alert()`/`confirm()` nativi — usa `UI.toast()` / `await UI.confirm()`
- Dataset: version bump (`DndCache._version` in `api.js`, `__v` nel JSON, `DATASET_VERSION` in Python)
- CSS: verifica `/* */` bilanciati dopo ogni modifica
- Kind/subtype nuovi: solo in `Schema.cpp` — il frontend si adatta via `/api/schema`
- Migration nuove: file `NNN_descrittivo.sql` con `NNN` > ultima, idempotente (`IF NOT EXISTS`)

---

## Fase 4 — Verificare

```bash
# Ricostruisci (zero warning richiesti: -Wall -Wextra -Wpedantic)
cmake --build build -j

# Smoke test API di base
curl -s http://127.0.0.1:8080/api/health
curl -s http://127.0.0.1:8080/api/schema | python3 -m json.tool > /dev/null
curl -s http://127.0.0.1:8080/api/sheets | python3 -m json.tool > /dev/null

# Se dataset modificato
python3 tools/validate_dataset.py
```

- [ ] `cmake --build build -j` completed without warnings
- [ ] Server si avvia senza crash
- [ ] `GET /api/health` → `{"status":"ok"}`
- [ ] Scenario del bug: non più riproducibile
- [ ] Regression check: API base funzionano (GET sheets, POST, PUT, DELETE, schema)
- [ ] Se frontend: UI si carica senza errori console in home/new/sheet
- [ ] `python3 tools/validate_dataset.py` — zero errori (se dataset toccato)

Se il fix introduce regressioni, torna a **Fase 2**.

---

## Aggiornamento ISSUES.md

Se il bug era tracciato in `ISSUES.md`:

```diff
- **Stato**: aperto
+ **Stato**: fixato
```

Aggiungi in fondo al bug:

```
### Fix
<dettaglio della soluzione, file modificati, commit>
```

Se il bug non era tracciato, valuta se aggiungerlo per memoria futura.

---

## Comandi rapidi

| Azione | Comando |
|--------|---------|
| Build | `cmake -S . -B build && cmake --build build -j` |
| Run | `./build/CharacterZero &` |
| Health check | `curl -s http://127.0.0.1:8080/api/health` |
| GET sheets | `curl -s http://127.0.0.1:8080/api/sheets` |
| GET sheet by ID | `curl -s http://127.0.0.1:8080/api/sheets/1` |
| POST sheet | `curl -s -X POST -H 'Content-Type: application/json' -d '{"kind":"character","subtype":"human","name":"Test"}' http://127.0.0.1:8080/api/sheets` |
| PUT sheet | `curl -s -X PUT -H 'Content-Type: application/json' -d '{"name":"New name"}' http://127.0.0.1:8080/api/sheets/1` |
| DELETE sheet | `curl -s -X DELETE http://127.0.0.1:8080/api/sheets/1` |
| Validate dataset | `python3 tools/validate_dataset.py` |
| Git log | `git log --oneline -10` |
| Git diff | `git diff` |
| Git diff (names only) | `git diff --name-only` |
| Search code | `rg <pattern> src/` o `rg <pattern> web/js/` |
| Search CSS comments | `rg '/\*' web/css/layout.css` |
| Servi file statici via Python | `python3 -m http.server 8888 -d web/` (debug UI senza backend) |

---

## Appendice — Piano di esecuzione (campagna 2026-07-05)

| # | Area | Bug | Fix | Stato |
|---|------|-----|-----|-------|
| 1 | dataset | BUG-002 — 22 spells level=null | Script Python: applica SPELL_LEVEL_FIXES su spells.json | ✓ |
| 2 | dataset | BUG-005 — 501 desc mancanti in features.json | Script Python: placeholder per desc vuote | ✓ |
| 3 | dataset | BUG-006 — 76 level mancanti in race/background features | Script Python: aggiunge `level: 1` | ✓ |
| 4 | dataset | BUG-003 — tasha_expanded metadati spurii | build_tasha_expanded.py: rimuovi _note/_todo | ✓ |
| 5 | backend | BUG-004 — ID non numerico -> 400 | Router.cpp: catch-all route (.+) | ✓ |
| 6 | dataset | Version bump | dnd5e.json 14→15, features.json 5→6 | ✓ |
| 7 | verifica | Smoke test | build + validate + curl | ✓ |
