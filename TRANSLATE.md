# TRANSLATE.md — Traduzione e completamento descrizioni D&D 5e

Istruzioni per un agente AI che deve tradurre dall'inglese all'italiano
e completare le descrizioni mancanti negli incantesimi
(`web/data/spells.json`) e nei privilegi (`web/data/features.json`).

Regola d'oro: se manca, scrivila tu basandoti sulla conoscenza del gioco.
Dopo aver scritto, si può sempre cercare una reference più precisa.

---

## 1. Input / Output

### File da leggere

| File | Contenuto |
|------|-----------|
| `web/data/spells.json` | 429 incantesimi — stato corrente (`description`, `duration`, ecc.) |
| `web/data/features.json` | 824 privilegi — stato corrente (`desc`, `name`, `level`) |
| `manuals/_index/spell_context.json` | Contesto incantesimi: `online_ref` (EN SRD), `raw_pages` (OCR IT), `current` |
| `manuals/_index/feature_context.json` | Contesto privilegi: `raw_pages` (OCR IT pagine PHB), `current` |
| `manuals/_index/online_reference.json` | Descrizioni EN fetchate da dnd5eapi.co (solo SRD) |

### File da modificare

| File | Cosa modificare |
|------|-----------------|
| `web/data/spells.json` | Solo `description` |
| `web/data/features.json` | Solo `desc` (il campo si chiama `desc`, non `description`) |

### Struttura `spell_context.json` (lista di 429 oggetti)

```json
{
  "name": "Luci Danzanti",
  "source": "D&D 5th Manuale del Giocatore",
  "page": "248",
  "current": { "description": "...", "duration": null, ... },
  "raw_pages": { "248": "testo OCR pagina 248...", "249": "..." },
  "pages_available": true,
  "online_ref": { "name": "Dancing Lights", "desc": ["EN desc line 1..."] }
}
```

### Struttura `feature_context.json` (dict con 4 chiavi)

```json
{
  "class_features": [
    {
      "class": "barbaro",
      "name": "Difesa Senza Armatura",
      "level": 1,
      "current": { "name": "Difesa Senza Armatura", "level": 1, "desc": "..." },
      "source": "D&D 5th Manuale del Giocatore",
      "pages": "45-50",
      "raw_pages": { "45": "testo OCR...", "46": "..." },
      "pages_available": true
    }
  ],
  "subclass_features": [ /* 497 entries, same shape + subclass field */ ],
  "race_features": [ /* 60 entries, shape + race field */ ],
  "background_features": [ /* 16 entries, shape + background field */ ]
}
```

### Struttura `features.json` (dict annidato)

```json
{
  "__v": 6,
  "class_features": {
    "barbaro": [
      { "name": "Difesa Senza Armatura", "level": 1, "desc": "..." },
      { "name": "Ira", "level": 1, "desc": "..." }
    ],
    "bardo": [ /* ... */ ]
  },
  "subclass_features": {
    "Cammino del Berserker": [ /* ... */ ]
  },
  "race_features": {
    "Alto Elfo": [ /* ... */ ]
  },
  "background_features": {
    "Accademico": [ /* ... */ ]
  }
}
```

---

## 2. Incantesimi — flusso di lavoro

Per ogni spell in `spells.json` con `description` < 200 caratteri
(22 spell — elencate nella Sezione 7).

### Fase A — Traduzione da `online_ref` (se disponibile)

1. Leggi `spell_context.json[name].online_ref.desc` (testo EN pulito)
2. Traduci in italiano, rispettando:
   - **Distanze in metri** (vedi Sezione 5)
   - **Stile PHB italiano**: terza persona ("l'incantatore", non "you")
   - **Terminologia D&D 5e IT**: "tiro salvezza su Saggezza", "CA", "punti ferita",
     "V, S, M", "slot incantesimo", "Concentrazione", ecc.
3. Unisci le righe in un unico blocco di testo con `\n` tra i paragrafi
4. Sovrascrivi `spells.json[name].description`

**Cosa NON tradurre**: nomi propri di incantesimi, classi, mostri.
Se un nome ha traduzione ufficiale italiana, usala (es. "Fireball" → "Palla di Fuoco").

### Fase B — Estrazione da `raw_pages` (se `online_ref` non disponibile)

1. Per ogni pagina in `raw_pages`, cerca il nome spell **in maiuscolo**
   come heading di sezione (es. `LUCI DANZANTI`)
2. Se trovato:
   a. Il paragrafo dopo `Durata: ...` è la descrizione
   b. Estrai il testo fino al prossimo heading (altra spell) o fine pagina
   c. Pulisci artefatti OCR (Sezione 6)
   d. Converti piedi→metri (Sezione 5)
3. Se NON trovato in nessuna pagina: passa alla **Fase C**

### Fase C — Conoscenza del gioco (fallback universale)

1. Scrivi la descrizione italiana basata sulla conoscenza di D&D 5e
2. Rispetta le stesse regole di stile della Fase A
3. Per le spell di Xanathar/Tasha usa le statistiche note
   (livello, scuola, classi, tempi, gittata, ecc.)

---

## 3. Feature — flusso di lavoro

Per ogni feature in `features.json` con `desc` contenente
`"(Descrizione non disponibile"` (500 feature — elencate nella Sezione 8).

### Fase A — Estrazione da `raw_pages`

1. Trova l'entry corrispondente in `feature_context.json`:
   - Match per `section` (class_features/subclass_features/race_features/background_features)
     + `name`
   - Per subclass_features match anche `subclass`
2. Nelle `raw_pages` (dict di pagine OCR), cerca il nome feature
   **in maiuscolo** come heading di sezione (es. `DIFESA SENZA ARMATURA`)
3. Se trovato come heading (su una riga tutta maiuscola, senza `:`):
   a. Estrai il testo dal paragrafo successivo fino al prossimo heading
      (altro privilegio, tabella, o `CAPITOLO`)
   b. Pulisci artefatti OCR (Sezione 6)
   c. Converti piedi→metri (Sezione 5)
   d. Scrivi in `features.json[section][chiave][i].desc`
4. Se NON trovato come heading: passa alla **Fase B**

**Attenzione**: le raw_pages contengono interi capitoli di classe (es. pagine 45–50
per il barbaro). La feature potrebbe apparire come heading in mezzo ad altre.
Cerca pattern come `NOME PRIVILEGIO\n(testo descrittivo)\n\n` in maiuscolo.

### Fase B — Traduzione da SRD inglese (via online_reference o API)

1. Per feature coperte dalla SRD (classi base: barbaro, bardo, chierico, druido,
   guerriero, ladro, mago, monaco, paladino, ranger, stregone, warlock, artefice),
   cerca descrizione inglese in:
   - `manuals/_index/online_reference.json` (se presente)
   - API `https://www.dnd5eapi.co/api/features` (solo SRD 5.1)
2. Se trovata: traduci in IT (stessa terminologia della Sezione 2 Fase A)
3. Se NON trovata: passa alla **Fase C**

### Fase C — Conoscenza del gioco (fallback universale)

1. Scrivi la descrizione italiana basata sulla conoscenza di D&D 5e
2. Usa lo stesso stile delle descrizioni PHB italiane già presenti
   (terza persona, "l'incantatore", "il chierico", "Il bersaglio", ecc.)
3. Se non sei sicuro di numeri/esatti, scrivi comunque una descrizione
   qualitativa — è meglio di un placeholder

---

## 4. Cose da NON toccare

### Incantesimi
- `name` — nome italiano
- `name_en` — nome inglese
- `classes` — lista classi
- `classes_subclass_only` — classi con sottoclasse
- `level` — livello (0= trucchetto, 1–9)
- `school` — scuola
- `ritual` — booleano
- `complete` — flag completezza
- `tags` — array tag
- `target` — target
- `source` — manuale di origine
- `page` — numero pagina
- `casting_time`, `range`, `components`, `duration`, `level_text`
  — questi sono già stati corretti, ma se vedi un errore evidente
  puoi fixarlo (es. componente mancante, unità sbagliata)

### Feature
- `name` — nome privilegio
- `level` — livello
- `class`, `subclass`, `race`, `background` — chiavi di raggruppamento
- `__v` — versione dataset

---

## 5. Tabella di conversione piedi → metri

Tutte le distanze devono essere in metri, come nella traduzione
italiana ufficiale D&D 5e. Fattore: **1 piede (foot) = 0,3 metri**.

| Piedi | Metri | Piedi | Metri |
|-------|-------|-------|-------|
| 5 | 1,5 | 90 | 27 |
| 10 | 3 | 100 | 30 |
| 15 | 4,5 | 120 | 36 |
| 20 | 6 | 150 | 45 |
| 25 | 7,5 | 210 | 63 |
| 30 | 9 | 300 | 90 |
| 40 | 12 | 500 | 150 |
| 50 | 15 | 1000 | 300 |
| 60 | 18 | 1 miglio | 1,5 km |
| 80 | 24 | Speciale (Self) | Incantatore |
| — | — | Touch | Contatto |

### Dove applicare
- **`description`**: qualsiasi distanza ("30-foot cone" → "cono di 9 metri")
- **`range`**: "30 feet" → "9 metri"
- **`duration`**: solo se contiene distanze (raro)

### Non riconvertire
Se il testo IT usa già i metri, lascialo stare.
"Piede" come parte del corpo (es. "atterrare in piedi") non va convertito.
Usa il pattern `\d+\s*(piedi|piede|foot|feet)` per identificare
solo le distanze numeriche.

---

## 6. Artefatti OCR noti

| Scorretto | Corretto |
|-----------|----------|
| perla | per la |
| conla | con la |
| dellospe | dello spe |
| dell'incantesimo / dell'incantatore | (giusto, ma verifica contesto) |
| un'azione / unazione | un'azione |
| l'incantatore / l'incantesimo | (con apostrofo curvo o dritto, normalizza) |
| un'area / unarea | un'area |
| chegli | che gli |
| cheegli | che egli |
| Èuna / Èun | È una / È un |
| Seil / Seun / Sela | Se il / Se un / Se la |
| conun / dauna / daun | con un / da una / da un |
| sccita | scelta |
| fete | ferite |
| IspirazioneBardica | Ispirazione Bardica |
| faccare | spezzare |
| chiericoutilizza | chierico utilizza |
| uncerto | un certo |
| paria | pari a |
| ilivello / livell | il livello / livello |
| privilego | privilegio |
| Controfascino | Controincantesimo |

**Nota**: non tutti i `\bun\w+` sono errori. "unisce", "unica", "uncerto"
possono essere parole italiane valide. Usa giudizio.

---

## 7. Incantesimi da tradurre/completare

### 10 SRD con `online_ref` disponibile

| # | Nome | Source | Note |
|---|------|--------|------|
| 1 | Salvare i Morenti | PHB | Descrizione troncata da "CAPITOLO 11" |
| 2 | Scudo della Fede | PHB | OK, ma corta (178 char) |
| 3 | Passo Velato | PHB | Inizia con "Componenti: V" (contaminato) |
| 4 | Ristorare Inferiore | PHB | OK, ma corta (151 char) |
| 5 | Scurovisione | PHB | Fino a 18 metri. OK ma corta |
| 6 | Vedere Invisibilità | PHB | Troncata da "CAPITOLO ll" |
| 7 | Protezione dall'Energia | PHB | Incompleta (inizia senza soggetto) |
| 8 | Contingenza | PHB | Solo 62 char, troncata |
| 9 | Favore Divino | PHB | Corta (196 char) ma OK |
| 10 | Saltare | PHB | OK ma corta (129 char) |

### 12 non-SRD (solo raw_pages / conoscenza)

| # | Nome | Source | Note |
|---|------|--------|------|
| 1 | Creare Falò | Xanathar | Descrizione vuota |
| 2 | Lama Verdefiamma | Tasha | Descrizione vuota |
| 3 | Parola Radiosa | Xanathar | Descrizione vuota |
| 4 | Rombo di Tuono | Xanathar | Descrizione vuota |
| 5 | Scheggia della Mente | Tasha | Descrizione vuota |
| 6 | Catapulta | Xanathar | Descrizione vuota |
| 7 | Coltello di Ghiaccio | Xanathar | Descrizione vuota |
| 8 | Evoca Bestia | Tasha | Ha stat block invece di descrizione |
| 9 | Pirotecnica | Xanathar | Descrizione vuota |
| 10 | Servitore Minuscolo | Xanathar | Descrizione vuota |
| 11 | Guardiano della Natura | Xanathar | Descrizione vuota |
| 12 | Investitura della Fiamma | Xanathar | Descrizione vuota |

---

## 8. Feature placeholder da completare

500 feature con `"(Descrizione non disponibile nei manuali per questo privilegio di classe.)"`

Distribuzione:
- `class_features`: ~120 placeholder
- `subclass_features`: ~300 placeholder
- `race_features`: ~40 placeholder
- `background_features`: ~16 placeholder

### Priorità

1. Feature con `raw_pages` dove il nome è trovabile come heading → **Fase A**
2. Feature di classi SRD (tutte le 13 classi base) → **Fase A + B**
3. Feature di sottoclassi SRD → **Fase A + B**
4. Feature di razze/background → **Fase C** (poche, facili)
5. Tutto il resto → **Fase C** (conoscenza del gioco)

### Lista completa non riportata qui per brevità
Per ottenere la lista esaustiva delle feature placeholder:

```bash
python3 -c "
import json
f = json.load(open('web/data/features.json'))
placeholder = '(Descrizione non disponibile'
for section in ['class_features','subclass_features','race_features','background_features']:
    group = f.get(section,{})
    if isinstance(group, dict):
        for key, flist in group.items():
            if isinstance(flist, list):
                for feat in flist:
                    if isinstance(feat, dict) and placeholder in (feat.get('desc','') or ''):
                        print(f'{section}/{key}/{feat.get(\"name\")}')
"
```

---

## 9. Verifica qualità

Dopo la traduzione/correzione, esegui:

```bash
python3 -c "
import json, re

# === SPELLS ===
s = json.load(open('web/data/spells.json'))
complete = sum(1 for x in s if x.get('complete'))
total = len(s)
total_desc_chars = sum(len(x.get('description','')) for x in s)
short = [x for x in s if len(x.get('description','') or '') < 200]
feet = [x['name'] for x in s if re.search(r'\d+\s*(piedi|piede|foot|feet)\b', x.get('description','') + ' ' + (x.get('range') or ''), re.IGNORECASE)]
truncated = [x['name'] for x in s if x.get('description','').strip().endswith('...')]

print(f'Spell: {total} totali, {complete} complete, {total - complete} incomplete')
print(f'Descrizione media: {total_desc_chars/total:.0f} caratteri')
print(f'Descrizione < 200 char: {len(short)}')
print(f'Piedi come unità: {len(feet)}')
print(f'Troncate con ...: {len(truncated)}')
if short:
    print(f'Ancora corte: {[x[\"name\"] for x in short]}')

# === FEATURES ===
f = json.load(open('web/data/features.json'))
placeholder = '(Descrizione non disponibile'
remaining = 0
for section in ['class_features','subclass_features','race_features','background_features']:
    group = f.get(section,{})
    if isinstance(group, dict):
        for flist in group.values():
            if isinstance(flist, list):
                for feat in flist:
                    if isinstance(feat, dict) and placeholder in (feat.get('desc','') or ''):
                        remaining += 1
print(f'\\nFeature placeholder rimanenti: {remaining}')
"
```

### Criteri di accettazione
- `complete: false` deve tendere a 0 (attualmente 0)
- Descrizione media > 1000 caratteri
- `< 5` spell con descrizione < 200 caratteri
- Zero occorrenze di piedi/piede come unità
- Feature placeholder rimanenti: più ci si avvicina a 0, meglio è

---

## 10. Esempi di traduzione

### Input (EN da online_ref)
```json
{
  "name": "Passo Velato",
  "online_ref": {
    "desc": ["Briefly surrounded by silvery mist, you teleport up to 30 feet to an unoccupied space that you can see."]
  }
}
```

### Output (IT tradotto)
```json
{
  "description": "L'incantatore è avvolto per un istante da una foschia argentata e si teletrasporta di un massimo di 9 metri fino a uno spazio libero che egli sia in grado di vedere."
}
```

### Feature — Input
```json
{
  "name": "Difesa Senza Armatura",
  "current": { "desc": "(Descrizione non disponibile nei manuali per questo privilegio di classe.)" },
  "raw_pages": { "45": "...\nDIFESA SENZA ARMATURA\nFinché un barbaro non indossa alcuna armatura, la sua Classe Armatura è pari a 10 + il suo modificatore di Destrezza + il suo modificatore di Costituzione. Un barbaro può usare uno scudo e ottenere comunque questo beneficio.\n..." }
}
```

### Feature — Output
```json
{
  "desc": "Finché un barbaro non indossa alcuna armatura, la sua Classe Armatura è pari a 10 + il suo modificatore di Destrezza + il suo modificatore di Costituzione. Un barbaro può usare uno scudo e ottenere comunque questo beneficio."
}
```

---

## 11. Suggerimenti pratici

- **Lavora in batch**: prima tutti gli incantesimi, poi le feature di classe,
  poi sottoclasse, poi razze/background
- **Non modificare la struttura JSON**: solo i valori stringa di `description` / `desc`
- **Usa `\\n`** per separare paragrafi nelle descrizioni, ma non esagerare
  (1-2 `\\n` tra sezioni è sufficiente)
- **Non inventare meccaniche**: se non ricordi esattamente un numero
  (dadi, gittate, durate), usa la formulazione generica
  ("subisce danni da fulmine" invece di "subisce 8d6 danni da fulmine")
  — ma se sei sicuro/a, metti il numero giusto
- **Coerenza**: leggi 2-3 descrizioni già corrette dello stesso libro
  per prendere il tono, poi applica lo stesso stile
