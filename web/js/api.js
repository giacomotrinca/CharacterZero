const api = {
  async health() {
    const r = await fetch('/api/health');
    return r.ok;
  },
  async schema() {
    const r = await fetch('/api/schema');
    if (!r.ok) throw new Error('Errore caricamento schema');
    return r.json();
  },
  async list() {
    const r = await fetch('/api/sheets');
    if (!r.ok) throw new Error('Errore caricamento elenco');
    return r.json();
  },
  async get(id) {
    const r = await fetch(`/api/sheets/${id}`);
    if (!r.ok) throw new Error('Scheda non trovata');
    return r.json();
  },
  async create({ kind, subtype, name, data }) {
    const r = await fetch('/api/sheets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, subtype, name, data: data || {} }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.error || 'Errore creazione');
    }
    return r.json();
  },
  async update(id, { name, data }) {
    const payload = {};
    if (name !== undefined) payload.name = name;
    if (data !== undefined) payload.data = data;
    const r = await fetch(`/api/sheets/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.error || 'Errore salvataggio');
    }
  },
  async remove(id) {
    const r = await fetch(`/api/sheets/${id}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Errore eliminazione');
  },
};

const SchemaCache = {
  _data: null,
  _kindMap: null,
  _version: 'v3-dnd',

  async load() {
    if (this._data) return this._data;
    const cached = sessionStorage.getItem('cz_schema');
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed && parsed.__v === this._version) this._data = parsed;
      } catch {}
    }
    if (!this._data) {
      this._data = await api.schema();
      this._data.__v = this._version;
      try { sessionStorage.setItem('cz_schema', JSON.stringify(this._data)); } catch {}
    }
    this._kindMap = {};
    for (const k of this._data.kinds) {
      this._kindMap[k.value] = k;
    }
    return this._data;
  },

  kinds()                    { return this._data?.kinds || []; },
  kindDef(kind)              { return this._kindMap?.[kind] || null; },
  kindLabel(kind)            { return this._kindMap?.[kind]?.label || kind; },
  subtypeGroupLabel(kind)    { return this._kindMap?.[kind]?.subtypeGroupLabel || 'Sottotipo'; },
  subtypeLabel(kind, subtype) {
    const subtypes = this._kindMap?.[kind]?.subtypes || [];
    return subtypes.find(s => s.value === subtype)?.label || subtype;
  },
  usesClasses(kind)          { return !!this._kindMap?.[kind]?.usesClasses; },
};

// Dataset D&D 5e (classi, sottoclassi, background, manuali) — servito staticamente.
const LEGACY_CLASS = { warrior: 'guerriero' };

const DndCache = {
  _data: null,
  _classMap: null,
  _version: 15,

  async load() {
    if (this._data) { this._index(); return this._data; }
    const cached = sessionStorage.getItem('cz_dnd');
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed && parsed.__v === this._version) this._data = parsed;
      } catch {}
    }
    if (!this._data) {
      const r = await fetch('/data/dnd5e.json');
      if (!r.ok) throw new Error('Errore caricamento dati D&D');
      this._data = await r.json();
      try { sessionStorage.setItem('cz_dnd', JSON.stringify(this._data)); } catch {}
    }
    this._index();
    return this._data;
  },

  _index() {
    this._classMap = {};
    for (const c of (this._data?.classes || [])) this._classMap[c.value] = c;
  },

  manuals()        { return this._data?.manuals || []; },
  manualLabel(v)   { return this.manuals().find(m => m.value === v)?.label || v; },
  classes()        { return this._data?.classes || []; },

  // Risolve un value di classe (incl. alias legacy) al value canonico del dataset.
  resolveClass(v) {
    if (!v) return null;
    if (this._classMap?.[v]) return v;
    return LEGACY_CLASS[v] || v;
  },
  classDef(v)      { return this._classMap?.[this.resolveClass(v)] || null; },
  classLabel(v) {
    const c = this.classDef(v);
    return c ? c.label : (v || '—');
  },
  subclassLevel(v) { return this.classDef(v)?.subclass_level || null; },
  subclassGroupLabel(v) { return this.classDef(v)?.group_label || 'Sottoclasse'; },

  // Sottoclassi di una classe, filtrate ai manuali selezionati (se forniti).
  subclasses(classValue, selectedManuals) {
    const c = this.classDef(classValue);
    if (!c) return [];
    const sel = (selectedManuals && selectedManuals.length) ? new Set(selectedManuals) : null;
    return c.subclasses.filter(s => !sel || s.manuals.some(m => sel.has(m)));
  },

  // Background filtrati ai manuali selezionati (se forniti).
  backgrounds(selectedManuals) {
    const bgs = this._data?.backgrounds || [];
    const sel = (selectedManuals && selectedManuals.length) ? new Set(selectedManuals) : null;
    return bgs.filter(b => !sel || b.manuals.some(m => sel.has(m)));
  },

  // Razze filtrate ai manuali selezionati (se forniti).
  races(selectedManuals) {
    const rs = this._data?.races || [];
    const sel = (selectedManuals && selectedManuals.length) ? new Set(selectedManuals) : null;
    return rs.filter(r => !sel || r.manuals.some(m => sel.has(m)));
  },
  raceLabel(name) { return name || '—'; },
  raceDef(name) {
    if (!name) return null;
    return (this._data?.races || []).find(r => r.name === name) || null;
  },

  // Talenti filtrati ai manuali selezionati.
  feats(selectedManuals) {
    const fs = this._data?.feats || [];
    const sel = (selectedManuals && selectedManuals.length) ? new Set(selectedManuals) : null;
    return fs.filter(f => !sel || f.manuals.some(m => sel.has(m)));
  },

  // Metadati di un talento (stat_bonus_value, stat_options, save_prof) — null se non ha effetti strutturati.
  featMeta(featName) {
    if (!featName) return null;
    const f = (this._data?.feats || []).find(x => x.name === featName);
    return (f && f.stat_bonus_value !== undefined) ? f : null;
  },

  // Descrizione testuale di un talento (estratta dall'OCR dei manuali). '' se non disponibile.
  featDesc(featName) {
    if (!featName) return '';
    const f = (this._data?.feats || []).find(x => x.name === featName);
    return f?.description || '';
  },

  // Competenze nei Tiri Salvezza per una classe (solo la primaria conta, PHB).
  saveProfs(classValue) {
    return this.classDef(classValue)?.save_profs || [];
  },

  // Abilità (skills) D&D 5e — lista canonica.
  skills() { return this._data?.skills || []; },
  skillByKey(key) { return this.skills().find(s => s.key === key) || null; },
  skillLabel(key) { return this.skillByKey(key)?.label || key; },

  // Livelli ASI di una classe (default [4,8,12,16,19]).
  asiLevels(classValue) {
    const c = this.classDef(classValue);
    return c?.asi_levels || [4,8,12,16,19];
  },

  // Dimensione MINIMA del Libro degli Incantesimi del Mago (PHB pag.114).
  // 6 spell L1 a livello 1, +2 per livello successivo, senza contare copie da pergamene.
  wizardSpellbookSize(level) {
    const lv = Math.max(1, Math.min(20, parseInt(level, 10) || 1));
    return 2 * lv + 4;
  },

  // ---------- Incantesimi ----------
  spellcasting(classValue) { return this.classDef(classValue)?.spellcasting || null; },
  isCaster(classValue)     { return !!this.spellcasting(classValue) && this.spellcasting(classValue).category !== 'martial'; },

  // True se questa istanza di classe (con sottoclasse e livello) è effettivamente
  // un incantatore — copre i casi Cavaliere Mistico / Mistificatore Arcano.
  isEffectiveCaster(classValue, subclassName, classLevel) {
    const sc = this.effectiveSpellcasting(classValue, subclassName, classLevel);
    return !!sc && sc.category !== 'martial';
  },

  // Trova la sottoclasse (per nome) di una classe — ritorna l'oggetto della sottoclasse
  // se presente nel dataset, altrimenti null.
  subclassDef(classValue, subclassName) {
    if (!subclassName) return null;
    const c = this.classDef(classValue);
    if (!c) return null;
    return (c.subclasses || []).find(s => s.name === subclassName) || null;
  },

  // Spellcasting EFFETTIVO: tiene conto delle sottoclassi che danno incantesimi a una
  // classe altrimenti marziale (Cavaliere Mistico/Mistificatore Arcano).
  // Ritorna un oggetto compatibile con spellcasting() ma con campo extra `from_subclass`
  // e (se applicabile) `class_value` = classe da cui pescare la spell list.
  effectiveSpellcasting(classValue, subclassName, classLevel) {
    const base = this.spellcasting(classValue);
    const sub  = this.subclassDef(classValue, subclassName);
    const subSc = sub?.spellcasting || null;
    if (!subSc) return base;
    const lv = parseInt(classLevel, 10) || 0;
    // Solo dopo lo start_level la sottoclasse "attiva" lo spellcasting.
    if (subSc.start_level && lv > 0 && lv < subSc.start_level) {
      return base; // ancora marziale
    }
    // Se la classe è già caster e la sottoclasse aggiunge spell di dominio, manteniamo
    // la base (gestione caso comune); altrimenti la sottoclasse SCRIVE lo spellcasting.
    if (!base || base.category === 'martial') {
      return {
        ...subSc,
        from_subclass: true,
        // dove pescare la spell list (italiano): se la sottoclasse lo dichiara, vince.
        spell_list_class: subSc.spell_list_class || classValue,
      };
    }
    return base;
  },

  // Cantrip noti per (classe, livello), o per sottoclasse-caster se la classe non cantrippa.
  cantripsKnown(classValue, classLevel, subclassName) {
    const sc = this.effectiveSpellcasting(classValue, subclassName, classLevel);
    if (!sc?.cantrips_known) return 0;
    const lv = Math.max(1, Math.min(20, parseInt(classLevel, 10) || 0));
    return sc.cantrips_known[lv - 1] || 0;
  },

  // Numero di spell "known" per classi a numero fisso (Bardo, Stregone, Ranger, Warlock,
  // Cavaliere Mistico, Mistificatore Arcano).
  spellsKnown(classValue, classLevel, subclassName) {
    const sc = this.effectiveSpellcasting(classValue, subclassName, classLevel);
    if (!sc?.spells_known) return 0;
    const lv = Math.max(1, Math.min(20, parseInt(classLevel, 10) || 0));
    return sc.spells_known[lv - 1] || 0;
  },

  // Numero di spell preparati per classi 'prepared' dato il modificatore della stat e il livello.
  // Minimo 1 (regola PHB/TCE).
  preparedCount(classValue, classLevel, abilityMod, subclassName) {
    const sc = this.effectiveSpellcasting(classValue, subclassName, classLevel);
    if (!sc || sc.prep_mode !== 'prepared') return 0;
    const lv = Math.max(1, parseInt(classLevel, 10) || 0);
    const mod = parseInt(abilityMod, 10) || 0;
    const f = sc.prep_formula || '';
    let n = 0;
    if (f === 'wis_mod+level' || f === 'int_mod+level') n = mod + lv;
    else if (f === 'cha_mod+level/2_floor' || f === 'cha_mod+level/2') n = mod + Math.floor(lv / 2);
    else if (f === 'int_mod+level/2_ceil')                              n = mod + Math.ceil(lv / 2);
    else if (f === 'int_mod+level/2' || f === 'wis_mod+level/2')        n = mod + Math.floor(lv / 2);
    else n = mod + lv;
    return Math.max(1, n);
  },

  // Slot pool per i full-caster (PHB pag.164 — regola multiclasse).
  // classes = [{value, levels, subclass}, ...].
  // Warlock NON contribuisce a questo pool (pact magic separato).
  // Third-caster (Cavaliere Mistico / Mistificatore Arcano) contribuisce con floor(lv/3).
  fullCasterSlotsForMulticlass(classes) {
    const tbl = this._data?.spell_slots?.full_caster;
    if (!tbl) return [0,0,0,0,0,0,0,0,0];
    let eff = 0;
    for (const c of (classes || [])) {
      const sc = this.effectiveSpellcasting(c.value, c.subclass, c.levels);
      if (!sc) continue;
      const lv = parseInt(c.levels, 10) || 0;
      if (sc.category === 'full')       eff += lv;
      else if (sc.category === 'half')  eff += Math.floor(lv / 2);
      else if (sc.category === 'third') eff += Math.floor(lv / 3);
      // 'pact' (warlock) -> pool separato
    }
    if (eff <= 0) return [0,0,0,0,0,0,0,0,0];
    return tbl[Math.min(20, eff) - 1].slice();
  },

  // Slot pact (Warlock) — se non c'è warlock, ritorna null.
  pactSlotsFor(classes) {
    const wl = (classes || []).find(c => c.value === 'warlock');
    if (!wl || !wl.levels) return null;
    const t = this._data?.spell_slots?.pact;
    if (!t) return null;
    return { ...t[Math.min(20, wl.levels) - 1] };
  },

  // Tutti gli incantesimi disponibili dato l'insieme di fonti (manuali) scelte.
  // Ritorna oggetti con name, level, school, ritual, components, source, etc.
  spellsForSources(sources) {
    const all = this._data?._spells || [];
    if (!sources || !sources.length) return all.slice();
    const allow = new Set(sources);
    // Mappa source string PHB -> value manuale: useremo il campo 'source' degli spell.
    // Best-effort: filtra se source manuale contiene una keyword corrispondente al value.
    const KEY = { manuale_del_giocatore: 'manuale del giocatore', xanathar: 'xanathar', tasha: 'tasha', guida_degli_avventurieri: 'guida degli avventurieri', manuale_dei_mostri: 'mostri', manuale_del_master: 'master' };
    return all.filter(sp => {
      const src = (sp.source || '').toLowerCase();
      for (const v of allow) {
        for (const [k, keyword] of Object.entries(KEY)) {
          if (v.includes(k) && src.includes(keyword)) return true;
        }
      }
      return false;
    });
  },

  // Mappa classValue (italiano) -> nome classe inglese usato da 5e.tools.
  _CLASS_VALUE_TO_EN: {
    barbaro: 'Barbarian', bardo: 'Bard', chierico: 'Cleric', druido: 'Druid',
    guerriero: 'Fighter', ladro: 'Rogue', mago: 'Wizard', monaco: 'Monk',
    paladino: 'Paladin', ranger: 'Ranger', stregone: 'Sorcerer', warlock: 'Warlock',
    artefice: 'Artificer',
  },

  // Filtra spell per classe (5e.tools BASE list). Se includeSubclassOnly è true,
  // include anche gli spell aggiunti dalle sottoclassi (Cleric Arcana → Fireball, ecc.).
  // sources opzionale: se passato, restringe ulteriormente per fonte/manuale.
  // Se Tasha (tasha_italiano) è tra le fonti, aggiunge anche le liste ampliate
  // del Calderone di Tasha (cap. 1) per quella classe.
  spellsForClass(classValue, sources, opts) {
    opts = opts || {};
    const en = this._CLASS_VALUE_TO_EN[classValue];
    if (!en) return [];
    const pool = sources ? this.spellsForSources(sources) : (this._data?._spells || []);
    const base = pool.filter(sp => {
      if (Array.isArray(sp.classes) && sp.classes.includes(en)) return true;
      if (opts.includeSubclassOnly && Array.isArray(sp.classes_subclass_only) && sp.classes_subclass_only.includes(en)) return true;
      return false;
    });
    // Tasha expanded list: aggiunge spell esistenti alla lista di classe
    // quando il personaggio ha 'tasha_italiano' tra le fonti selezionate.
    const hasTasha = Array.isArray(sources) && sources.includes('tasha_italiano');
    const expanded = this._data?.tasha_expanded?.[classValue] || [];
    if (hasTasha && expanded.length && pool.length) {
      const seen = new Set(base.map(s => s.name));
      const byName = new Map(pool.map(s => [s.name, s]));
      for (const ex of expanded) {
        if (seen.has(ex.name)) continue;
        const sp = byName.get(ex.name);
        if (sp) { base.push(sp); seen.add(ex.name); }
      }
    }
    return base;
  },

  // Carica spells.json on-demand
  async loadSpells() {
    if (this._data?._spells) return this._data._spells;
    const r = await fetch('/data/spells.json', { headers: { 'Accept': 'application/json' } });
    if (!r.ok) throw new Error('Errore caricando spells.json');
    const arr = await r.json();
    if (this._data) this._data._spells = arr;
    return arr;
  },
};

// ---------- Multiclasse: normalizzazione e backcompat ----------
// Nuovo modello: data.classes = [{value, levels, subclass, asi_choices:[...]}, ...]
// Vecchio modello (compat): data.class + data.subclass + data.level
function MC_normalize(data) {
  if (!data) return [];
  if (Array.isArray(data.classes) && data.classes.length) {
    return data.classes.map(c => ({
      value: DndCache.resolveClass(c.value),
      levels: Math.max(0, parseInt(c.levels, 10) || 0),
      subclass: c.subclass || '',
      asi_choices: Array.isArray(c.asi_choices) ? c.asi_choices.slice() : [],
    })).filter(c => c.value);
  }
  if (data.class) {
    return [{
      value: DndCache.resolveClass(data.class),
      levels: Math.max(1, parseInt(data.level, 10) || 1),
      subclass: data.subclass || '',
      asi_choices: [],
    }];
  }
  return [];
}
function MC_totalLevel(classes) {
  return (classes || []).reduce((n, c) => n + (parseInt(c.levels, 10) || 0), 0);
}
// Numero di ASI completati in quella classe (in base ai levels presi).
function MC_asiSlotsFor(classDef, levels) {
  if (!classDef || !levels) return 0;
  return (classDef.asi_levels || []).filter(l => l <= levels).length;
}
// Bonus competenza (PHB): basato sul livello TOTALE del PG.
function profBonusFromLevel(totalLevel) {
  const n = Math.max(1, Math.min(20, parseInt(totalLevel, 10) || 1));
  return Math.floor((n - 1) / 4) + 2;
}

// Definizioni statistiche (ordine di visualizzazione canonico D&D)
const STATS = [
  { key: 'str', label: 'Forza',        short: 'FOR' },
  { key: 'dex', label: 'Destrezza',    short: 'DES' },
  { key: 'con', label: 'Costituzione', short: 'COS' },
  { key: 'int', label: 'Intelligenza', short: 'INT' },
  { key: 'wis', label: 'Saggezza',     short: 'SAG' },
  { key: 'cha', label: 'Carisma',      short: 'CAR' },
];

// Costo Point Buy 5e standard (27 punti, intervallo 8-15)
const POINT_BUY_COST = { 8:0, 9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9 };
const POINT_BUY_BUDGET = 27;

function statMod(score) {
  if (!Number.isFinite(score)) return 0;
  return Math.floor((score - 10) / 2);
}
function fmtMod(m) { return (m >= 0 ? '+' : '') + m; }

// Tira 4d6 scarta il più basso
function roll4d6dl() {
  const rolls = [0,0,0,0].map(() => 1 + Math.floor(Math.random() * 6));
  rolls.sort((a,b) => a-b);
  return rolls[1] + rolls[2] + rolls[3];
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso.replace(' ', 'T') + 'Z');
  if (isNaN(d)) return iso;
  return d.toLocaleString('it-IT', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const ICONS = {
  character: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
    stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="8" r="4"/>
    <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>
  </svg>`,
  npc: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 12c0-4 3-7 8-7s8 3 8 7v3a2 2 0 0 1-2 2h-1v2H7v-2H6a2 2 0 0 1-2-2z"/>
    <circle cx="9" cy="12" r="1.1"/><circle cx="15" cy="12" r="1.1"/>
  </svg>`,
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
