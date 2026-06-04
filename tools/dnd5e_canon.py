"""
Scheletro canonico D&D 5e (italiano) — sorgente di verità per le REGOLE FISSE.

Approccio ibrido (vedi plan): qui stanno i dati che NON dipendono da OCR e non cambiano:
- le 12 classi, con il livello a cui si sceglie la sottoclasse e l'etichetta del gruppo;
- il dizionario dei nomi noti di sottoclasse (per ancorare il fuzzy-match dell'estrattore);
- i background base del Manuale del Giocatore.

L'attribuzione "quale sottoclasse/background sta in quale manuale" NON si decide qui:
la calcola `build_catalog.py` scansionando i manuali estratti.
"""

import re
import unicodedata

# --- 12 classi: struttura canonica 5e -------------------------------------
# subclass_level = livello a cui si sceglie la sottoclasse (regola fissa 5e).
# group_label    = come il manuale chiama il gruppo di sottoclassi.
# caster         = tipo di incantatore (full/half/third/pact/none) — utile per gli incantesimi.
# anchor         = regex per SCOPRIRE nomi di sottoclasse dal testo (solo classi con prefisso comune).
CLASSES = [
    {
        "value": "barbaro", "label": "Barbaro",
        "subclass_level": 3, "group_label": "Cammino Primordiale", "caster": "none",
        "anchor": r"cammino\s+(?:del|della|dello|dei|degli|delle)\s+\w",
        "subclasses": [
            "Cammino del Berserker",
            "Cammino del Combattente Totemico",
        ],
    },
    {
        "value": "bardo", "label": "Bardo",
        "subclass_level": 3, "group_label": "Collegio Bardico", "caster": "full",
        "anchor": r"collegio\s+(?:del|della|dei|degli|delle|dell')\s*\w",
        "subclasses": [
            "Collegio della Sapienza",
            "Collegio del Valore",
        ],
    },
    {
        "value": "chierico", "label": "Chierico",
        "subclass_level": 1, "group_label": "Dominio Divino", "caster": "full",
        "anchor": r"dominio\s+(?:del|della|dell'|dello|dei|degli)\s*\w",
        "subclasses": [
            "Dominio della Conoscenza",
            "Dominio della Guerra",
            "Dominio dell'Inganno",
            "Dominio della Luce",
            "Dominio della Natura",
            "Dominio della Tempesta",
            "Dominio della Vita",
        ],
    },
    {
        "value": "druido", "label": "Druido",
        "subclass_level": 2, "group_label": "Circolo Druidico", "caster": "full",
        "anchor": r"circolo\s+(?:del|della|dei|degli|delle|dell')\s*\w",
        "subclasses": [
            "Circolo della Terra",
            "Circolo della Luna",
        ],
    },
    {
        "value": "guerriero", "label": "Guerriero",
        "subclass_level": 3, "group_label": "Archetipo Marziale", "caster": "none",
        "anchor": None,
        "subclasses": [
            "Campione",
            "Maestro di Battaglia",
            "Cavaliere Mistico",
            "Arciere Arcano",
            "Cavaliere Errante",
            "Samurai",
            "Cavaliere Runico",
            "Guerriero Psionico",
        ],
    },
    {
        "value": "ladro", "label": "Ladro",
        "subclass_level": 3, "group_label": "Archetipo Ladresco", "caster": "none",
        "anchor": None,
        "subclasses": [
            "Ladro",
            "Assassino",
            "Mistificatore Arcano",
            "Esploratore",
            "Indagatore",
            "Pianificatore",
            "Spadaccino",
            "Fantasma",
            "Lama Spirituale",
        ],
    },
    {
        "value": "mago", "label": "Mago",
        "subclass_level": 2, "group_label": "Tradizione Arcana", "caster": "full",
        "anchor": r"scuola\s+di\s+\w",
        "subclasses": [
            "Scuola di Abiurazione",
            "Scuola di Ammaliamento",
            "Scuola di Divinazione",
            "Scuola di Evocazione",
            "Scuola di Illusione",
            "Scuola di Invocazione",
            "Scuola di Necromanzia",
            "Scuola di Trasmutazione",
            "Magia della Guerra",
            "Canto della Lama",
            "Ordine degli Scribi",
        ],
    },
    {
        "value": "monaco", "label": "Monaco",
        "subclass_level": 3, "group_label": "Tradizione Monastica", "caster": "none",
        "anchor": r"via\s+(?:del|della|dei|degli|delle|dell')\s*\w",
        "subclasses": [
            "Via della Mano Aperta",
            "Via dell'Ombra",
            "Via dei Quattro Elementi",
        ],
    },
    {
        "value": "paladino", "label": "Paladino",
        "subclass_level": 3, "group_label": "Giuramento Sacro", "caster": "half",
        "anchor": r"giuramento\s+(?:di|degli|della|del)\s*\w",
        "subclasses": [
            "Giuramento di Devozione",
            "Giuramento degli Antichi",
            "Giuramento di Vendetta",
        ],
    },
    {
        "value": "ranger", "label": "Ranger",
        "subclass_level": 3, "group_label": "Archetipo Ranger", "caster": "half",
        "anchor": None,
        "subclasses": [
            "Cacciatore",
            "Signore delle Bestie",
            "Cacciatore delle Tenebre",
            "Uccisore di Mostri",
            "Custode degli Sciami",
            "Viandante Fatato",
        ],
    },
    {
        "value": "stregone", "label": "Stregone",
        "subclass_level": 1, "group_label": "Origine Stregonesca", "caster": "full",
        "anchor": None,
        "subclasses": [
            "Discendenza Draconica",
            "Magia Selvaggia",
            "Anima Divina",
            "Magia delle Ombre",
            "Stregoneria della Tempesta",
            "Anima Meccanica",
            "Mente Aberrante",
        ],
    },
    {
        "value": "warlock", "label": "Warlock",
        "subclass_level": 1, "group_label": "Patrono Ultraterreno", "caster": "pact",
        "anchor": None,
        "subclasses": [
            "L'Immondo",
            "Il Grande Antico",
            "Il Signore Fatato",
            "Il Celestiale",
            "La Lama del Sortilegio",
            "Il Genio",
            "L'Insondabile",
        ],
    },
    {
        "value": "artefice", "label": "Artefice",
        "subclass_level": 3, "group_label": "Specialista Artefice", "caster": "half",
        "anchor": None,
        "subclasses": [
            "Alchimista",
            "Artigliere",
            "Forgia di Battaglia",
            "Armaiolo",
        ],
    },
]

# --- Background base (Manuale del Giocatore) -------------------------------
# Livelli a cui ogni classe ottiene un Aumento Caratteristica o Talento (PHB cap.3).
# Default: 4, 8, 12, 16, 19. Eccezioni: Guerriero +6 e +14, Ladro +10.
ASI_LEVELS_DEFAULT = [4, 8, 12, 16, 19]
ASI_LEVELS_BY_CLASS = {
    "guerriero": [4, 6, 8, 12, 14, 16, 19],
    "ladro":     [4, 8, 10, 12, 16, 19],
}
def asi_levels_for(class_value):
    return ASI_LEVELS_BY_CLASS.get(class_value, ASI_LEVELS_DEFAULT)

# Competenze nei Tiri Salvezza per ogni classe (PHB) — solo dalla classe primaria.
SAVE_PROFS = {
    "barbaro":  ["str", "con"],
    "bardo":    ["dex", "cha"],
    "chierico": ["wis", "cha"],
    "druido":   ["int", "wis"],
    "guerriero":["str", "con"],
    "ladro":    ["dex", "int"],
    "mago":     ["int", "wis"],
    "monaco":   ["str", "dex"],
    "paladino": ["wis", "cha"],
    "ranger":   ["str", "dex"],
    "stregone": ["con", "cha"],
    "warlock":  ["wis", "cha"],
    "artefice": ["con", "int"],
}

# Talenti con effetti strutturati: bonus stat e/o competenza nei Tiri Salvezza.
# stat_bonus_value : punti bonus alla caratteristica scelta
# stat_options     : lista di stat valide ([] = qualsiasi, [x] = fissa = solo x)
# save_prof        : True → aggiunge anche competenza nel TS della stat scelta
FEAT_META = {
    "Resiliente": {"stat_bonus_value": 1, "stat_options": [], "save_prof": True},
    "Atletico":   {"stat_bonus_value": 1, "stat_options": ["str", "dex"]},
    "Attore":     {"stat_bonus_value": 1, "stat_options": ["cha"]},
    "Osservatore":{"stat_bonus_value": 1, "stat_options": ["int", "wis"]},
}

# Descrizioni curate per talenti non catturati dall'OCR dei manuali.
# Usate come fallback da build_dataset.py.
FEAT_DESCRIPTIONS_FALLBACK = {
    "Cecchino Magico": (
        "Prerequisito: la capacità di lanciare almeno un incantesimo. "
        "Quando lanci un incantesimo che richiede un tiro per colpire, la sua gittata "
        "raddoppia. I tuoi attacchi con incantesimi ignorano la copertura a metà e la "
        "copertura per tre quarti. Impari un trucchetto che richiede un tiro per colpire, "
        "a scelta tra le liste di druido, mago, chierico o stregone/warlock."
    ),
    "Combattente a Due Armi": (
        "Ottieni i benefici seguenti finché impugni un'arma da mischia in ciascuna mano: "
        "+1 alla CA. "
        "Puoi usare il combattimento con due armi anche quando le armi da mischia che impugni "
        "non hanno la proprietà Leggera. "
        "Puoi estrarre o riporre due armi a una mano quando normalmente potresti estrarne o "
        "riporne solo una."
    ),
    "Combattente in Sella": (
        "Sei un formidabile combattente in sella e ottieni i benefici seguenti: "
        "Hai vantaggio ai tiri per colpire contro qualsiasi creatura smontata che sia di taglia "
        "inferiore alla tua cavalcatura. "
        "Puoi fare in modo che qualsiasi attacco destinato alla tua cavalcatura bersagli te. "
        "Se la tua cavalcatura è soggetta a un effetto che le permette di effettuare un tiro "
        "salvezza su Destrezza per dimezzare i danni, non subisce danni se supera il tiro e "
        "solo la metà se non lo supera."
    ),
    "Corazze Medie": (
        "Prerequisito: competenza nelle armature medie. "
        "Hai imparato a indossare le armature medie in modo efficace e ottieni i benefici "
        "seguenti: indossare un'armatura media non ti impone svantaggio alle prove di Destrezza "
        "(Furtività). "
        "Puoi aggiungere 3 alla tua CA, anziché 2, se hai un punteggio di Destrezza pari "
        "o superiore a 16."
    ),
}

# -------- INCANTESIMI (regole PHB) -----------------------------------------
# Tabella slot full-caster (1-9) per livello 1..20 (PHB pag. 113).
# Anche usata per il pool slot MULTICLASSE (somma livelli effettivi).
FULL_CASTER_SLOTS = [
    [2,0,0,0,0,0,0,0,0],  # L1
    [3,0,0,0,0,0,0,0,0],  # L2
    [4,2,0,0,0,0,0,0,0],
    [4,3,0,0,0,0,0,0,0],
    [4,3,2,0,0,0,0,0,0],
    [4,3,3,0,0,0,0,0,0],
    [4,3,3,1,0,0,0,0,0],
    [4,3,3,2,0,0,0,0,0],
    [4,3,3,3,1,0,0,0,0],
    [4,3,3,3,2,0,0,0,0],
    [4,3,3,3,2,1,0,0,0],
    [4,3,3,3,2,1,0,0,0],
    [4,3,3,3,2,1,1,0,0],
    [4,3,3,3,2,1,1,0,0],
    [4,3,3,3,2,1,1,1,0],
    [4,3,3,3,2,1,1,1,0],
    [4,3,3,3,2,1,1,1,1],
    [4,3,3,3,3,1,1,1,1],
    [4,3,3,3,3,2,1,1,1],
    [4,3,3,3,3,2,2,1,1],  # L20
]

# Tabella slot mezzo-incantatore (Paladino, Ranger; PHB).
HALF_CASTER_SLOTS = [
    [0,0,0,0,0],          # L1
    [2,0,0,0,0],
    [3,0,0,0,0],
    [3,0,0,0,0],
    [4,2,0,0,0],
    [4,2,0,0,0],
    [4,3,0,0,0],
    [4,3,0,0,0],
    [4,3,2,0,0],
    [4,3,2,0,0],
    [4,3,3,0,0],
    [4,3,3,0,0],
    [4,3,3,1,0],
    [4,3,3,1,0],
    [4,3,3,2,0],
    [4,3,3,2,0],
    [4,3,3,3,1],
    [4,3,3,3,1],
    [4,3,3,3,2],
    [4,3,3,3,2],         # L20
]

# Warlock — pact magic (PHB pag. 110). idx = livello warlock (1..20).
# Ogni voce: (numero_slot, livello_slot).
PACT_SLOTS = [
    (1,1),(2,1),(2,2),(2,2),(2,3),(2,3),(2,4),(2,4),
    (2,5),(2,5),(3,5),(3,5),(3,5),(3,5),(3,5),(3,5),
    (4,5),(4,5),(4,5),(4,5),
]

# Tabella slot terzo-incantatore (Cavaliere Mistico del Guerriero,
# Mistificatore Arcano del Ladro). PHB pag. 75 / 98. Inizia a L3.
# idx = livello DELLA CLASSE (1..20). Slot L1..L4 (max L4).
THIRD_CASTER_SLOTS = [
    [0,0,0,0],  # L1
    [0,0,0,0],  # L2
    [2,0,0,0],  # L3
    [3,0,0,0],
    [3,0,0,0],
    [3,0,0,0],
    [4,2,0,0],  # L7
    [4,2,0,0],
    [4,2,0,0],
    [4,3,0,0],  # L10
    [4,3,0,0],
    [4,3,0,0],
    [4,3,2,0],  # L13
    [4,3,2,0],
    [4,3,2,0],
    [4,3,3,0],  # L16
    [4,3,3,0],
    [4,3,3,0],
    [4,3,3,1],  # L19
    [4,3,3,1],  # L20
]

# Cantrip noti per livello (1..20) per classe (0 se classe non cantrippa).
# Per le sottoclassi terzo-incantatore (Cavaliere Mistico, Mistificatore Arcano)
# i cantrip cominciano a L3 della classe: vedi SUBCLASS_SPELLCASTING.
CANTRIPS_KNOWN = {
    "bardo":    [2,2,2,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4],
    "chierico": [3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5],
    "druido":   [2,2,2,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4],
    "mago":     [3,3,3,4,4,4,4,4,4,5,5,5,5,5,5,5,5,5,5,5],
    "stregone": [4,4,4,5,5,5,5,5,5,6,6,6,6,6,6,6,6,6,6,6],
    "warlock":  [2,2,2,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4],
}

# Spell noti (esclusi cantrip) per livello, solo per "known casters" (PHB).
SPELLS_KNOWN = {
    "bardo":    [4,5,6,7,8,9,10,11,12,14,15,15,16,18,19,19,20,22,22,22],
    "stregone": [2,3,4,5,6,7,8,9,10,11,12,12,13,13,14,14,15,15,15,15],
    "ranger":   [0,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11],
    "warlock":  [2,3,4,5,6,7,8,9,10,10,11,11,12,12,13,13,14,14,15,15],
}

# Cantrip / Spell noti per le sottoclassi terzo-incantatori.
# Index = livello DELLA CLASSE (1..20). Valori 0 ai livelli 1-2.
# Cavaliere Mistico (PHB pag. 75): 2 cantrip a L3, sale a 3 a L10.
# Mistificatore Arcano (PHB pag. 98): 3 cantrip a L3, sale a 4 a L10.
THIRD_CANTRIPS_KNOWN_EK = [0,0,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3,3,3,3]
THIRD_CANTRIPS_KNOWN_AT = [0,0,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4]
# Stessa progressione di spell known per entrambe (PHB).
THIRD_SPELLS_KNOWN     = [0,0,3,4,4,4,5,6,6,7,8,8,9,10,10,11,11,11,12,13]

def wizard_spellbook_size(level: int) -> int:
    """Dimensione minima del Libro degli Incantesimi del Mago (PHB pag.114).
    6 spell di L1 a livello 1, +2 ad ogni livello successivo. Non include spell
    copiati da pergamene. = 2*level + 4."""
    lv = max(1, min(20, level or 1))
    return 2 * lv + 4


# Metadati spellcasting per classe.
# category   : 'martial' | 'full' | 'half' | 'third' | 'pact'
# ability    : 'cha'|'wis'|'int' o None
# prep_mode  : 'prepared' (sa tutta la lista o la riempie nel libro, prepara N ogni giorno)
#              'known'    (numero fisso noto, da tabella SPELLS_KNOWN; nessuna preparazione)
#              None       (martial)
# prep_source: cosa pesca al momento della preparazione/uso (informativo per la UI)
#              'class_list' → Chierico/Druido/Paladino/Artefice: conoscono l'intera lista
#                              di classe, preparano N spell ogni giorno.
#              'spellbook'  → Mago: gli incantesimi devono trovarsi nel suo libro, e da quello
#                              ne prepara N ogni giorno.
#              'known_list' → known caster (Bardo, Stregone, Ranger, Warlock, Cavaliere Mistico,
#                              Mistificatore Arcano): conosce un set fisso.
# prep_formula: stringa interpretabile in JS — vedi DndCache.preparedCount()
#   - 'wis_mod+level'         (Chierico, Druido)
#   - 'cha_mod+level/2_floor' (Paladino — half caster, arrotondato per difetto, min 1)
#   - 'int_mod+level'         (Mago)
#   - 'int_mod+level/2_ceil'  (Artefice — TCE: arrotondato per ECCESSO, min 1)
#   - null per known/martial
SPELLCASTING = {
    "barbaro":  {"category": "martial", "ability": None,  "prep_mode": None,        "prep_source": None,         "prep_formula": None},
    "monaco":   {"category": "martial", "ability": None,  "prep_mode": None,        "prep_source": None,         "prep_formula": None},
    "guerriero":{"category": "martial", "ability": None,  "prep_mode": None,        "prep_source": None,         "prep_formula": None},
    "ladro":    {"category": "martial", "ability": None,  "prep_mode": None,        "prep_source": None,         "prep_formula": None},

    "bardo":    {"category": "full", "ability": "cha", "prep_mode": "known",    "prep_source": "known_list", "prep_formula": None},
    "stregone": {"category": "full", "ability": "cha", "prep_mode": "known",    "prep_source": "known_list", "prep_formula": None},
    "mago":     {"category": "full", "ability": "int", "prep_mode": "prepared", "prep_source": "spellbook",  "prep_formula": "int_mod+level"},
    "chierico": {"category": "full", "ability": "wis", "prep_mode": "prepared", "prep_source": "class_list", "prep_formula": "wis_mod+level"},
    "druido":   {"category": "full", "ability": "wis", "prep_mode": "prepared", "prep_source": "class_list", "prep_formula": "wis_mod+level"},

    "paladino": {"category": "half", "ability": "cha", "prep_mode": "prepared", "prep_source": "class_list", "prep_formula": "cha_mod+level/2_floor"},
    "ranger":   {"category": "half", "ability": "wis", "prep_mode": "known",    "prep_source": "known_list", "prep_formula": None},

    "warlock":  {"category": "pact", "ability": "cha", "prep_mode": "known",    "prep_source": "known_list", "prep_formula": None},

    # Artefice (TCE pag. 13): prepara INT mod + livello/2 ARROTONDATO PER ECCESSO (min 1).
    "artefice": {"category": "half", "ability": "int", "prep_mode": "prepared", "prep_source": "class_list", "prep_formula": "int_mod+level/2_ceil"},
}

# Spellcasting derivante dalle SOTTOCLASSI (sovrascrive/aggiunge a quello della classe
# quando la classe è martial). Chiave = nome sottoclasse normalizzato (lowercase, accenti
# rimossi, spazi singoli). 'spell_list_class' = classe italiana da cui pescare la lista.
# 'start_level' = livello della classe-padre in cui inizia lo spellcasting.
# 'cantrips_known' / 'spells_known' = vettori 1..20 (0 prima di start_level).
# Le scuole "preferite" PHB sono solo flavor: non vengono enforced (lista wizard libera).
SUBCLASS_SPELLCASTING = {
    # Guerriero / Cavaliere Mistico (PHB pag. 74-75)
    "cavaliere mistico": {
        "category": "third", "ability": "int",
        "prep_mode": "known", "prep_source": "known_list", "prep_formula": None,
        "spell_list_class": "mago",
        "start_level": 3,
        "preferred_schools": ["Abiurazione", "Evocazione"],
        "cantrips_known": THIRD_CANTRIPS_KNOWN_EK,
        "spells_known":   THIRD_SPELLS_KNOWN,
    },
    # Ladro / Mistificatore Arcano (PHB pag. 97-98)
    "mistificatore arcano": {
        "category": "third", "ability": "int",
        "prep_mode": "known", "prep_source": "known_list", "prep_formula": None,
        "spell_list_class": "mago",
        "start_level": 3,
        "preferred_schools": ["Ammaliamento", "Illusione"],
        "cantrips_known": THIRD_CANTRIPS_KNOWN_AT,
        "spells_known":   THIRD_SPELLS_KNOWN,
    },
}


def normalize_subclass_name(name: str) -> str:
    """Normalizza un nome di sottoclasse per il lookup in SUBCLASS_SPELLCASTING."""
    if not name:
        return ""
    import unicodedata
    s = unicodedata.normalize("NFD", str(name))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    s = " ".join(s.split())
    return s

# Background del Manuale del Giocatore (assegnati a PHB di default).
BACKGROUNDS_PHB = [
    "Accolito",
    "Artigiano di Gilda",
    "Ciarlatano",
    "Criminale",
    "Eremita",
    "Eroe Popolare",
    "Forestiero",
    "Intrattenitore",
    "Marinaio",
    "Monello",
    "Nobile",
    "Sapiente",
    "Soldato",
]
# Background aggiuntivi (Guida degli Avventurieri alla Costa della Spada).
BACKGROUNDS_SCAG = [
    "Agente della Fazione",
    "Artigiano di Clan",
    "Cacciatore di Taglie Urbano",
    "Cortigiano",
    "Ereditiere",
    "Membro della Tribù Uthgardt",
    "Membro della Vigilanza Cittadina",
    "Nobile di Waterdeep",
    "Viaggiatore Straniero",
]
BACKGROUNDS = BACKGROUNDS_PHB + BACKGROUNDS_SCAG

# Le 18 abilità (skills) D&D 5e (italiano).
# key = identificatore stabile; label = nome italiano; ability = caratteristica associata.
SKILLS = [
    {"key": "acrobazia",         "label": "Acrobazia",          "ability": "dex"},
    {"key": "addestrare_animali","label": "Addestrare Animali", "ability": "wis"},
    {"key": "arcano",            "label": "Arcano",             "ability": "int"},
    {"key": "atletica",          "label": "Atletica",           "ability": "str"},
    {"key": "furtivita",         "label": "Furtività",          "ability": "dex"},
    {"key": "indagare",          "label": "Indagare",           "ability": "int"},
    {"key": "inganno",           "label": "Inganno",            "ability": "cha"},
    {"key": "intimidire",        "label": "Intimidire",         "ability": "cha"},
    {"key": "intrattenere",      "label": "Intrattenere",       "ability": "cha"},
    {"key": "intuizione",        "label": "Intuizione",         "ability": "wis"},
    {"key": "medicina",          "label": "Medicina",           "ability": "wis"},
    {"key": "natura",            "label": "Natura",             "ability": "int"},
    {"key": "percezione",        "label": "Percezione",         "ability": "wis"},
    {"key": "persuasione",       "label": "Persuasione",        "ability": "cha"},
    {"key": "rapidita_di_mano",  "label": "Rapidità di Mano",   "ability": "dex"},
    {"key": "religione",         "label": "Religione",          "ability": "int"},
    {"key": "sopravvivenza",     "label": "Sopravvivenza",      "ability": "wis"},
    {"key": "storia",            "label": "Storia",             "ability": "int"},
]
SKILL_KEYS = {s["label"]: s["key"] for s in SKILLS}
ALL_SKILL_KEYS = [s["key"] for s in SKILLS]

def _sk(*labels):
    return [SKILL_KEYS[l] for l in labels]

# Scelte di competenza in abilità per classe (PHB).
# count = numero di abilità da scegliere; options = lista chiavi (o "any" per qualunque abilità).
CLASS_SKILL_CHOICES = {
    "barbaro":   {"count": 2, "options": _sk("Addestrare Animali","Atletica","Intimidire","Intuizione","Natura","Percezione","Sopravvivenza")},
    "bardo":     {"count": 3, "options": "any"},
    "chierico":  {"count": 2, "options": _sk("Intuizione","Medicina","Persuasione","Religione","Storia")},
    "druido":    {"count": 2, "options": _sk("Addestrare Animali","Arcano","Intuizione","Medicina","Natura","Percezione","Religione","Sopravvivenza")},
    "guerriero": {"count": 2, "options": _sk("Acrobazia","Addestrare Animali","Atletica","Intimidire","Intuizione","Percezione","Sopravvivenza","Storia")},
    "ladro":     {"count": 4, "options": _sk("Acrobazia","Atletica","Furtività","Indagare","Inganno","Intimidire","Intuizione","Percezione","Persuasione","Rapidità di Mano")},
    "mago":      {"count": 2, "options": _sk("Arcano","Indagare","Intuizione","Medicina","Religione","Storia")},
    "monaco":    {"count": 2, "options": _sk("Acrobazia","Atletica","Furtività","Intuizione","Religione","Storia")},
    "paladino":  {"count": 2, "options": _sk("Atletica","Intimidire","Intuizione","Medicina","Persuasione","Religione")},
    "ranger":    {"count": 3, "options": _sk("Addestrare Animali","Atletica","Furtività","Indagare","Intuizione","Natura","Percezione","Sopravvivenza")},
    "stregone":  {"count": 2, "options": _sk("Arcano","Inganno","Intimidire","Intuizione","Persuasione","Religione")},
    "warlock":   {"count": 2, "options": _sk("Arcano","Inganno","Indagare","Intimidire","Natura","Religione","Storia")},
    "artefice":  {"count": 2, "options": _sk("Arcano","Indagare","Inganno","Medicina","Natura","Percezione","Storia")},
}

# Abilità concesse dai background PHB (2 fisse ciascuno).
BACKGROUND_SKILLS = {
    "Accolito":           _sk("Intuizione","Religione"),
    "Artigiano di Gilda": _sk("Intuizione","Persuasione"),
    "Ciarlatano":         _sk("Inganno","Rapidità di Mano"),
    "Criminale":          _sk("Inganno","Furtività"),
    "Eremita":            _sk("Medicina","Religione"),
    "Eroe Popolare":      _sk("Addestrare Animali","Sopravvivenza"),
    "Forestiero":         _sk("Atletica","Sopravvivenza"),
    "Intrattenitore":     _sk("Acrobazia","Intrattenere"),
    "Marinaio":           _sk("Atletica","Percezione"),
    "Monello":            _sk("Furtività","Rapidità di Mano"),
    "Nobile":             _sk("Storia","Persuasione"),
    "Sapiente":           _sk("Arcano","Storia"),
    "Soldato":            _sk("Atletica","Intimidire"),
    # SCAG
    "Agente della Fazione":            _sk("Intuizione"),  # + Inganno/Indagare/Persuasione (1 a scelta, qui semplificato)
    "Artigiano di Clan":               _sk("Storia","Intuizione"),
    "Cacciatore di Taglie Urbano":     [],  # 2 abilità a scelta tra 4: lasciato vuoto (scelta libera al giocatore)
    "Cortigiano":                      _sk("Intuizione","Persuasione"),
    "Ereditiere":                      _sk("Arcano","Storia"),  # variante semplificata: storia/arcano
    "Membro della Tribù Uthgardt":     _sk("Atletica","Sopravvivenza"),
    "Membro della Vigilanza Cittadina":_sk("Atletica","Intuizione"),
    "Nobile di Waterdeep":             _sk("Storia","Persuasione"),
    "Viaggiatore Straniero":           _sk("Intuizione","Percezione"),
}

# Bonus razziali alle abilità. fixed = chiavi sempre concesse; choices = {count, options}.
RACE_SKILLS = {
    "Elfo Alto":      {"fixed": _sk("Percezione")},
    "Elfo dei Boschi":{"fixed": _sk("Percezione")},
    "Elfo Oscuro":    {"fixed": _sk("Percezione")},
    "Mezzelfo":       {"choices": {"count": 2, "options": "any"}},
    "Mezzorco":       {"fixed": _sk("Intimidire")},
    "Umano Variante": {"choices": {"count": 1, "options": "any"}},
}

# Razze giocabili canoniche PHB 5e (include sottorazza dove applicabile).
# stat_bonuses: dict abbreviazione->incremento; flexible_count: numero di bonus a scelta;
# half_elf_special: True per Mezzelfo (CAR+2 + 2x +1 a scelta non-CAR);
# variant_human: True per Umano Variante (1 talento + 2x +1 a scelta).
RACES = [
    {"name": "Dragonide",            "stat_bonuses": {"str": 2, "cha": 1}},
    {"name": "Elfo Alto",            "stat_bonuses": {"dex": 2, "int": 1}},
    {"name": "Elfo dei Boschi",      "stat_bonuses": {"dex": 2, "wis": 1}},
    {"name": "Elfo Oscuro",          "stat_bonuses": {"dex": 2, "cha": 1}},
    {"name": "Gnomo delle Foreste",  "stat_bonuses": {"int": 2, "dex": 1}},
    {"name": "Gnomo delle Rocce",    "stat_bonuses": {"int": 2, "con": 1}},
    {"name": "Halfling Piedileggeri","stat_bonuses": {"dex": 2, "cha": 1}},
    {"name": "Halfling Robusto",     "stat_bonuses": {"dex": 2, "con": 1}},
    {"name": "Mezzelfo",             "stat_bonuses": {"cha": 2}, "half_elf_special": True},
    {"name": "Mezzorco",             "stat_bonuses": {"str": 2, "con": 1}},
    {"name": "Nano delle Colline",   "stat_bonuses": {"con": 2, "wis": 1}},
    {"name": "Nano delle Montagne",  "stat_bonuses": {"con": 2, "str": 2}},
    {"name": "Tiefling",             "stat_bonuses": {"cha": 2, "int": 1}},
    {"name": "Umano",                "stat_bonuses": {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1}},
    {"name": "Umano Variante",       "stat_bonuses": {}, "variant_human": True},
]

# Talenti canonici del Manuale del Giocatore (capitolo Opzioni di Personalizzazione).
# Necessario per: Umano Variante (1 talento al 1° livello) e ASI (4°/8°/12°/16°/19°).
FEATS = [
    "Abile",
    "Adepto Elementale",
    "Adepto Marziale",
    "Aggressore Selvaggio",
    "Allerta",
    "Appostato",
    "Atleta",
    "Attore",
    "Carica",
    "Cecchino Magico",
    "Combattente a Due Armi",
    "Combattente in Sella",
    "Condottiero Ispiratore",
    "Corazze Leggere",
    "Corazze Medie",
    "Corazze Pesanti",
    "Duellante Difensivo",
    "Esperto di Balestre",
    "Esperto di Dungeon",
    "Fortunato",
    "Guaritore",
    "Incantatore da Guerra",
    "Incantatore Rituale",
    "Iniziato alla Magia",
    "Linguista",
    "Lottatore",
    "Lottatore da Taverna",
    "Maestro d'Armi",
    "Maestro d'Armi Possenti",
    "Maestro degli Scudi",
    "Maestro delle Armature Medie",
    "Maestro delle Armature Pesanti",
    "Maestro delle Armi su Asta",
    "Mente Acuta",
    "Mobilità",
    "Osservatore",
    "Resiliente",
    "Robusto",
    "Sentinella",
    "Sterminatore di Maghi",
    "Tenace",
    "Tiratore Scelto",
]


def normalize(s: str) -> str:
    """Minuscolo, senza accenti/punteggiatura, spazi collassati — per fuzzy match robusto su OCR."""
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


CLASS_BY_VALUE = {c["value"]: c for c in CLASSES}


def all_known_subclasses():
    """[(class_value, subclass_name), ...] per il dizionario di riconoscimento."""
    out = []
    for c in CLASSES:
        for sc in c["subclasses"]:
            out.append((c["value"], sc))
    return out
