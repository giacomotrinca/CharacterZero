# COMPARING_DES — Protocollo di correzione dataset D&D 5e

Istruzioni per un agente AI che deve correggere descrizioni, campi e nomi
negli incantesimi (`web/data/spells.json`) e nei privilegi
(`web/data/features.json`) confrontando tre fonti:
il dato corrente, il testo grezzo estratto dai PDF italiani, e la reference
inglese SRD online.

---

## 1. Input

| File | Contenuto |
|------|-----------|
| `manuals/_index/spell_context.json` | 429 incantesimi — ogni entry ha `current` (IT attuale), `raw_pages` (OCR PDF IT), `online_ref` (EN SRD) |
| `manuals/_index/feature_context.json` | 824 privilegi — ogni entry ha `current`, `raw_pages` (OCR PHB IT), nessun online_ref |
| `manuals/_index/pages/*.jsonl` | Pagine raw dei manuali (fonte secondaria per contesto extra) |

## 2. Output (da modificare)

| File | Cosa modificare |
|------|-----------------|
| `web/data/spells.json` | `description`, `casting_time`, `range`, `components`, `duration`, `level_text` |
| `web/data/features.json` | Solo campo `desc` di ogni privilegio |

## 3. Cose da NON toccare

Tutti questi campi rimangono invariati:

- **Incantesimi**: `name`, `name_en`, `classes`, `classes_subclass_only`, `level`, `school`, `ritual`, `complete`, `tags`, `target`, `source`, `page`
- **Privilegi**: `name`, `level`, e la struttura delle chiavi (`__v`, `class_features`, ecc.)
- **Versioni**: `__v` in `features.json` (lo gestisce `build_features.py`)

---

## 4. Regola metrica (fondamentale)

**Tutte le distanze devono essere in metri**, come nella traduzione italiana ufficiale
D&D 5e. Fattore: **1 piede (foot) = 0,3 metri**. Arrotondamento: usa la tabella seguente,
non calcolare a mano.

### Tabella di conversione rapida

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

### Dove applicare

- **`range`**: "30 feet" → "9 metri", "Self" → "Incantatore", "Touch" → "Contatto"
- **`description`**: qualsiasi occorrenza di piedi → metri (es. "cono di 60 piedi"
  → "cono di 18 metri", "raggio di 30 piedi" → "raggio di 9 metri")
- **`duration`**: solo se contiene distanze
- **`components`**: raramente, ma controlla
- **Non riconvertire**: se il testo corrente usa già i metri, lascialo stare

---

## 5. Priorità delle fonti

Per ogni entry, l'agente segue questo ordine di priorità:

### Incantesimo con `online_ref` disponibile (279 spell SRD)

```
1. Leggi online_ref (EN pulito) → capisci cosa fa lo spell
2. Leggi raw_pages (IT da PDF) → vedi la versione italiana OCR
3. Se raw_pages è leggibile: correggi artefatti OCR + converti feet→metri
4. Se raw_pages troppo corrotto/illeggibile: traduci tu dall'inglese all'italiano,
   convertendo le distanze in metri
```

### Incantesimo SENZA `online_ref` (145 spell non-SRD: Xanathar, Tasha, SCAG)

```
1. Leggi raw_pages (IT da PDF) → unica fonte
2. Correggi artefatti OCR + converti feet→metri
3. Se raw_pages è illeggibile: usa la tua conoscenza del gioco
```

### Privilegi (solo `raw_pages`)

```
1. Leggi raw_pages (OCR PHB IT)
2. Correggi artefatti OCR
3. Se illeggibile: usa dati canonici SRD / conoscenza del gioco
   (non tradurre dall'inglese se non serve — le descrizioni sono già italiane nel PHB)
```

---

## 6. Cosa correggere

### Incantesimi — 77 incompleti, focus su questi

Casi tipici trovati nel dataset:

| Problema | Esempio | Fix |
|----------|---------|-----|
| `duration: null` ma nel raw text c'è "Durata: ..." | Prendi dal raw text | Ripristina campo |
| `components` con testo spurio | `"S, M (un frammento di fosforo, di legno, <descrizione spell successivo>"` | Taglia al campo corretto |
| Descrizione troncata | Descr. finisce a metà frase | Cerca il resto nelle pagine raw successive |
| Descrizione sbagliata (dello spell adiacente) | raw_pages[212] inizia con lo spell precedente | Salta pagine finché non trovi il nome giusto |
| Artefatti OCR | Matusione, spazi mancanti, lettere strane | Normalizza |

### Privilegi — artefatti OCR frequenti

| Artefatto | Corretto |
|-----------|----------|
| "perla" | "per la" |
| "conla" | "con la" |
| "un" + parola attaccata | "un " + parola staccata |
| "dellospe" | "dello spe" (o parola intera) |
| caratteri OCR: ° | ° (giusto, è il simbolo dei gradi/livelli) |

---

## 7. Flusso di lavoro consigliato

1. Leggi `spell_context.json` in memoria
2. Per ogni entry:
   a. Se `online_ref` esiste (non null): leggilo per capire effetto corretto
   b. Leggi `raw_pages` per la/e pagina/e interessate
   c. Confronta `current.description` con ciò che trovi
   d. Se serve correggere: sovrascrivi i campi in `current.description`, ecc.
   e. **Non modificare la struttura** — solo valori stringa
3. Scrivi `web/data/spells.json` aggiornato
4. Ripeti per `feature_context.json` → `web/data/features.json`

### Cosa significa "correggi" concretamente

- **Riscrivi** la descrizione dal raw text, pulendo artefatti e convertendo unità
- **Completa** le descrizioni tronche con il testo dalla pagina successiva
- **Aggiorna** `casting_time`, `range`, `components`, `duration` se il raw text
  ha valori più corretti di quelli attuali
- **Non** riarrangiare la formattazione — plain text con `\n` per separare paragrafi

---

## 8. Verifica qualità

Dopo la correzione, esegui:

```bash
python3 -c "
import json
s = json.load(open('web/data/spells.json'))
complete = sum(1 for x in s if x.get('complete'))
total = len(s)
total_desc_chars = sum(len(x.get('description','')) for x in s)
print(f'{total} spell, {complete} complete (sufficiente)')
print(f'{total - complete} incomplete (insufficiente, deve tendere a 0)')
print(f'Lunghezza media descrizione: {total_desc_chars / total:.0f} caratteri')
"
```

Criteri:
- Il numero di `complete: false` deve avvicinarsi a 0
- Nessuna descrizione deve finire con `...` troncato
- Non devono esserci piedi nelle descrizioni (fare grep di "piedi", "piede")
- Campiona 5 spell a caso e verifica manualmente

---

## 9. Esempio concreto

### Input incantesimo incompleto

```json
{
  "name": "Luci Danzanti",
  "current": {
    "description": "Finché l'incantesimo non termina, quando l'incantatore...",
    "duration": null,
    "components": "V, S, M (un frammento di fosforo, di legno,"
  },
  "raw_pages": {
    "248": "LUCI DANZANTI\nTrucchetto di Illusione\nTempo di Lancio: 1 azione\nGittata: 36 metri\nComponenti: V, S, M (un frammento di fosforo o di legno di tasso, o una lucciola)\nDurata: Concentrazione, fino a 1 minuto\nPer la durata dell'incantesimo... [testo completo]"
  },
  "online_ref": {
    "name": "Dancing Lights",
    "desc": ["Create up to four torch-sized lights within range..."]
  }
}
```

### Output corretto

```json
{
  "description": "testo completo della descrizione italiana",
  "duration": "Concentrazione, fino a 1 minuto",
  "components": "V, S, M (un frammento di fosforo o di legno di tasso, o una lucciola)"
}
```

---

## 10. Versioni

- `spell_context.json` e `feature_context.json`: rigenerabili con `python3 tools/extract_for_correction.py`
- `online_reference.json`: rigenerabile con `python3 tools/fetch_online_reference.py`
- `web/data/spells.json` e `web/data/features.json`: sono i file da correggere

Dopo la correzione, se la struttura dei dati cambia, aggiorna `__v` in
`features.json` e `DATASET_VERSION` in `build_features.py` / `build_dataset.py`.
