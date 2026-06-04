// SpellsWidget — gestione incantesimi multiclasse.
// Stato:
//   state = { [classValue]: { cantrips:[name,...], spells:[name,...] } }
// Per ciascuna classe caster, l'utente sceglie:
//   - N trucchetti (cap = cantrips_known)
//   - per 'known': N spell (cap = spells_known) di livello <= slot massimo accessibile
//   - per 'prepared': lista libera (cap = ability_mod + level [o /2])
// Filtra il catalogo per le fonti (manuali) scelte.

const SpellsWidget = (() => {

  function defaultState() { return {}; }

  function normalize(s) {
    if (!s || typeof s !== 'object') return {};
    const out = {};
    for (const [k, v] of Object.entries(s)) {
      out[k] = {
        cantrips: Array.isArray(v?.cantrips) ? v.cantrips.slice() : [],
        spells: Array.isArray(v?.spells) ? v.spells.slice() : [],
      };
    }
    return out;
  }

  // Massimo livello di slot accessibile a questa classe (in modalità single-class progression).
  // Per scelta di spell, ci si attiene alla progressione DELLA CLASSE (non al pool multiclasse).
  function maxSpellLevelForClass(classValue, classLevel, subclassName) {
    const sc = DndCache.effectiveSpellcasting(classValue, subclassName, classLevel);
    if (!sc) return 0;
    const lv = Math.max(1, Math.min(20, parseInt(classLevel, 10) || 0));
    if (sc.category === 'pact') {
      const t = DndCache._data?.spell_slots?.pact?.[lv - 1];
      return t?.slot_level || 0;
    }
    let tbl;
    if (sc.category === 'full')       tbl = DndCache._data?.spell_slots?.full_caster?.[lv - 1];
    else if (sc.category === 'half')  tbl = DndCache._data?.spell_slots?.half_caster?.[lv - 1];
    else if (sc.category === 'third') tbl = DndCache._data?.spell_slots?.third_caster?.[lv - 1];
    if (!tbl) return 0;
    let maxL = 0;
    for (let i = 0; i < tbl.length; i++) if (tbl[i] > 0) maxL = i + 1;
    return maxL;
  }

  function abilityModFromStats(stats, key) {
    if (!stats || !key) return 0;
    const v = parseInt(stats[key], 10) || 10;
    return Math.floor((v - 10) / 2);
  }

  function preparedCountFor(c, finalStats) {
    const sc = DndCache.effectiveSpellcasting(c.value, c.subclass, c.levels);
    if (!sc || sc.prep_mode !== 'prepared') return 0;
    const mod = abilityModFromStats(finalStats, sc.ability);
    return DndCache.preparedCount(c.value, c.levels, mod, c.subclass);
  }

  function knownCountFor(c) {
    const sc = DndCache.effectiveSpellcasting(c.value, c.subclass, c.levels);
    if (!sc) return 0;
    return DndCache.spellsKnown(c.value, c.levels, c.subclass);
  }

  function validate(state, classes) {
    const errs = [];
    state = normalize(state);
    for (const c of (classes || [])) {
      const sc = DndCache.effectiveSpellcasting(c.value, c.subclass, c.levels);
      if (!sc || sc.category === 'martial') continue;
      const cs = state[c.value] || { cantrips: [], spells: [] };
      const def = DndCache.classDef(c.value);
      const cmax = DndCache.cantripsKnown(c.value, c.levels, c.subclass);
      if (cs.cantrips.length > cmax) errs.push(`${def.label}: troppi trucchetti (${cs.cantrips.length}/${cmax}).`);
      if (sc.prep_mode === 'known') {
        const kmax = knownCountFor(c);
        if (cs.spells.length > kmax) errs.push(`${def.label}: troppi incantesimi conosciuti (${cs.spells.length}/${kmax}).`);
      }
    }
    return errs;
  }

  // Snapshot UI: quali <details> sono aperti + valore delle ricerche.
  function snapshotUI(container) {
    const open = new Set();
    container.querySelectorAll('details[data-picker]').forEach(d => {
      if (d.open) open.add(d.dataset.picker);
    });
    const searches = {};
    container.querySelectorAll('input.spell-search').forEach(inp => {
      searches[inp.dataset.searchKey] = inp.value;
    });
    // Salva lo scrollTop di ogni .spell-list (sono scroll interni, indipendenti dalla window).
    // Chiave = data-picker del <details> contenitore + kind ('cantrip'/'spell').
    const scrolls = {};
    container.querySelectorAll('details[data-picker] .spell-list').forEach(list => {
      const det = list.closest('details[data-picker]');
      if (!det) return;
      // primo .spell-list = cantrip flat list; quelli dentro .spell-level-group = per livello
      const grp = list.closest('.spell-level-group');
      const key = det.dataset.picker + '|' + (grp ? ('lvl=' + grp.dataset.level) : 'flat');
      scrolls[key] = list.scrollTop;
    });
    return { open, searches, scrolls };
  }

  function restoreUI(container, snap) {
    if (!snap) return;
    container.querySelectorAll('details[data-picker]').forEach(d => {
      if (snap.open.has(d.dataset.picker)) d.open = true;
    });
    container.querySelectorAll('input.spell-search').forEach(inp => {
      const v = snap.searches[inp.dataset.searchKey];
      if (v) {
        inp.value = v;
        applySearchFilter(inp);
      }
    });
    container.querySelectorAll('details[data-picker] .spell-list').forEach(list => {
      const det = list.closest('details[data-picker]');
      if (!det) return;
      const grp = list.closest('.spell-level-group');
      const key = det.dataset.picker + '|' + (grp ? ('lvl=' + grp.dataset.level) : 'flat');
      const y = snap.scrolls?.[key];
      if (typeof y === 'number') list.scrollTop = y;
    });
  }

  function render(container, state, opts) {
    if (!container) return;
    opts = opts || {};
    const classes = (opts.classes || []).filter(c => {
      const sc = DndCache.effectiveSpellcasting(c.value, c.subclass, c.levels);
      return sc && sc.category !== 'martial';
    });
    const sources = opts.sources || [];
    const finalStats = opts.finalStats || {};
    state = normalize(state);

    if (!classes.length) {
      container.innerHTML = `<div class="field-hint">Nessuna classe incantatrice selezionata.</div>`;
      return;
    }

    const snap = snapshotUI(container);

    const slotPool = DndCache.fullCasterSlotsForMulticlass(classes);
    const pact = DndCache.pactSlotsFor(classes);

    const slotsCard = renderSlotsCard(slotPool, pact);
    const classCards = classes.map(c => renderClassCard(c, state, sources, finalStats)).join('');

    UI.preserveScroll(() => {
      container.innerHTML = `
        <div class="spells-widget">
          ${slotsCard}
          ${classCards}
        </div>`;

      wireEvents(container, state, opts);
      restoreUI(container, snap);
    });
  }

  function renderSlotsCard(slotPool, pact) {
    const hasFull = slotPool.some(n => n > 0);
    if (!hasFull && !pact) return '';
    const slotsHtml = slotPool.map((n, i) => n > 0
      ? `<div class="slot-pill"><span class="slot-lvl">L${i+1}</span><span class="slot-n">${n}</span></div>`
      : '').filter(Boolean).join('');
    const pactHtml = pact && pact.slots > 0
      ? `<div class="pact-block">
           <div class="pact-title">Pact Magic (Warlock)</div>
           <div class="slot-pill pact"><span class="slot-lvl">L${pact.slot_level}</span><span class="slot-n">${pact.slots}</span></div>
           <div class="field-hint">Slot recuperati con riposo breve.</div>
         </div>`
      : '';
    return `
      <div class="card">
        <h3 class="card-title">Slot di incantesimo</h3>
        ${hasFull ? `<div class="slots-grid">${slotsHtml}</div>` : ''}
        ${pactHtml}
      </div>`;
  }

  function renderClassCard(c, state, sources, finalStats) {
    const def = DndCache.classDef(c.value);
    const sc = DndCache.effectiveSpellcasting(c.value, c.subclass, c.levels);
    const cs = state[c.value] || { cantrips: [], spells: [] };
    const cmax = DndCache.cantripsKnown(c.value, c.levels, c.subclass);
    const maxLvl = maxSpellLevelForClass(c.value, c.levels, c.subclass);

    // Classe da cui pescare la lista (per third-caster: la sottoclasse dichiara `spell_list_class`).
    const listClass = sc.spell_list_class || c.value;

    // Filtro: per classe (default) / per classe + sottoclassi / tutto il manuale.
    window.__spellFilters = window.__spellFilters || {};
    const filterMode = window.__spellFilters[c.value] || 'class';

    let pool;
    if (filterMode === 'all')      pool = DndCache.spellsForSources(sources);
    else if (filterMode === 'sub') pool = DndCache.spellsForClass(listClass, sources, { includeSubclassOnly: true });
    else                            pool = DndCache.spellsForClass(listClass, sources);

    pool = pool.slice().sort((a, b) => a.name.localeCompare(b.name, 'it'));
    const cantripPool = pool.filter(s => s.level === 0);
    const spellPool   = pool.filter(s => s.level !== null && s.level >= 1 && s.level <= maxLvl);

    // Info "header": dipende dalla modalità di gestione degli incantesimi
    // - spellbook (Mago): registriamo il LIBRO (gestione persistente); i preparati cambiano ogni giorno.
    // - class_list (Chierico/Druido/Paladino/Artefice): registriamo i PREPARATI (selezione del giorno).
    // - known_list (Bardo/Stregone/Ranger/Warlock/Cavaliere Mistico/Mistificatore Arcano): registriamo i CONOSCIUTI.
    let prepInfo, prepHint = '';
    if (sc.prep_source === 'spellbook') {
      const book = DndCache.wizardSpellbookSize(c.levels);
      const prepDaily = preparedCountFor(c, finalStats);
      prepInfo = `Libro: <strong>${cs.spells.length}</strong> / ${book} suggeriti`;
      prepHint = `Stiamo registrando il tuo <strong>Libro degli Incantesimi</strong>. A L${c.levels} contiene almeno ${book} spell (6 a L1 + 2 per livello, oltre alle copie da pergamene). Ogni giorno preparerai ${prepDaily} spell scegliendoli dal libro — quella scelta si fa a tavolo, non qui in scheda.`;
    } else if (sc.prep_mode === 'prepared') {
      const max = preparedCountFor(c, finalStats);
      prepInfo = `Preparati al giorno: <strong>${cs.spells.length}</strong> / ${max}`;
      if (sc.prep_source === 'class_list') {
        prepHint = `${escapeHtml(def.label)} conosce <strong>tutta la lista</strong> della classe (${sc.ability.toUpperCase()}). Qui scegli i ${max} incantesimi che il personaggio prepara oggi.`;
      } else {
        prepHint = `Ogni giorno prepari ${max} incantesimi.`;
      }
    } else if (sc.category === 'pact') {
      const max = knownCountFor(c);
      prepInfo = `Conosciuti: <strong>${cs.spells.length}</strong> / ${max}`;
      prepHint = `<strong>Pact Magic:</strong> conosci ${max} incantesimi, lanciati con slot dedicati recuperati con riposo breve.`;
    } else {
      const max = knownCountFor(c);
      prepInfo = `Conosciuti: <strong>${cs.spells.length}</strong> / ${max}`;
      if (sc.from_subclass) {
        prepHint = `Conosci ${max} incantesimi dalla lista del ${escapeHtml(DndCache.classLabel(listClass))} (${sc.ability.toUpperCase()}). Al level-up puoi sostituirne 1.`;
        if (sc.preferred_schools?.length) {
          prepHint += ` Scuole preferite: ${sc.preferred_schools.map(escapeHtml).join(', ')}.`;
        }
      } else {
        prepHint = `Conosci ${max} incantesimi (${sc.ability.toUpperCase()}). Al level-up puoi sostituirne 1.`;
      }
    }

    const pickerKeyC = `${c.value}::cantrip`;
    const pickerKeyS = `${c.value}::spell`;

    const filterUI = `
      <div class="spell-filter" data-class="${c.value}">
        <label class="seg-btn ${filterMode==='class'?'on':''}"><input type="radio" name="sf-${c.value}" value="class" ${filterMode==='class'?'checked':''}> Solo lista classe</label>
        <label class="seg-btn ${filterMode==='sub'?'on':''}"><input type="radio" name="sf-${c.value}" value="sub" ${filterMode==='sub'?'checked':''}> + Sottoclassi</label>
        <label class="seg-btn ${filterMode==='all'?'on':''}"><input type="radio" name="sf-${c.value}" value="all" ${filterMode==='all'?'checked':''}> Tutto il manuale</label>
      </div>`;

    const cantripsBlock = cmax > 0 ? `
      <div class="spells-section">
        <div class="spells-section-head">
          <strong>Trucchetti</strong>
          <span class="count-info">${cs.cantrips.length} / ${cmax}</span>
        </div>
        ${renderSpellChips(cs.cantrips, c.value, 'cantrip')}
        <details class="spell-picker" data-picker="${pickerKeyC}">
          <summary>+ Aggiungi trucchetto <span class="muted">(${cantripPool.length} disponibili)</span></summary>
          <input type="text" class="spell-search" data-search-key="${pickerKeyC}" placeholder="Cerca trucchetto per nome…">
          ${renderSpellList(cantripPool, cs.cantrips, c.value, 'cantrip')}
        </details>
      </div>` : '';

    // Etichetta della sezione spell dipende dalla modalità di gestione
    let spellsHeadLabel = 'Incantesimi';
    let pickerLabel = '+ Aggiungi incantesimo';
    if (sc.prep_source === 'spellbook') {
      spellsHeadLabel = 'Libro degli Incantesimi';
      pickerLabel = '+ Aggiungi al libro';
    } else if (sc.prep_mode === 'prepared') {
      spellsHeadLabel = 'Preparati al giorno';
      pickerLabel = '+ Prepara incantesimo';
    } else if (sc.category === 'pact') {
      spellsHeadLabel = 'Incantesimi del Patto';
    } else {
      spellsHeadLabel = 'Incantesimi conosciuti';
      pickerLabel = '+ Aggiungi conosciuto';
    }

    const spellsBlock = maxLvl > 0 ? `
      <div class="spells-section">
        <div class="spells-section-head">
          <strong>${escapeHtml(spellsHeadLabel)}</strong> <span class="muted">(livello max accessibile: ${maxLvl})</span>
          <span class="count-info">${prepInfo}</span>
        </div>
        ${prepHint ? `<div class="field-hint">${prepHint}</div>` : ''}
        ${renderSpellChips(cs.spells, c.value, 'spell')}
        <details class="spell-picker" data-picker="${pickerKeyS}">
          <summary>${pickerLabel} <span class="muted">(${spellPool.length} disponibili)</span></summary>
          <input type="text" class="spell-search" data-search-key="${pickerKeyS}" placeholder="Cerca per nome…">
          ${renderSpellListByLevel(spellPool, cs.spells, c.value, 'spell', maxLvl)}
        </details>
      </div>` : '';

    // Titolo: per third-caster mostra "Ladro · Mistificatore Arcano" invece di solo "Ladro".
    const subTitle = sc.from_subclass && c.subclass
      ? `${escapeHtml(def.label)} · <em>${escapeHtml(c.subclass)}</em>`
      : escapeHtml(def.label);

    return `
      <div class="card spell-class-card">
        <h3 class="card-title">${subTitle} <span class="card-sub">L${c.levels} · ${escapeHtml(prepLabel(sc))}</span></h3>
        ${filterUI}
        ${cantripsBlock}
        ${spellsBlock}
      </div>`;
  }

  function prepLabel(sc) {
    if (!sc) return '';
    if (sc.category === 'pact')        return 'Pact Magic';
    if (sc.category === 'third')       return 'Terzo-incantatore (' + (sc.ability || '').toUpperCase() + ')';
    if (sc.prep_source === 'spellbook') return 'Mago · Libro degli Incantesimi (' + sc.ability.toUpperCase() + ')';
    if (sc.prep_mode === 'prepared')   return 'Preparazione quotidiana (' + sc.ability.toUpperCase() + ')';
    if (sc.prep_mode === 'known')      return 'Conosciuti (' + sc.ability.toUpperCase() + ')';
    return sc.ability ? sc.ability.toUpperCase() : '';
  }

  function renderSpellChips(names, classValue, kind) {
    if (!names.length) return `<div class="field-hint">Nessuno selezionato.</div>`;
    return `<div class="spell-chips">
      ${names.map(n => `<div class="spell-chip">
        <span>${escapeHtml(n)}</span>
        <button type="button" data-spell-remove="${escapeAttr(n)}" data-class="${classValue}" data-kind="${kind}" title="Rimuovi">×</button>
      </div>`).join('')}
    </div>`;
  }

  function renderSpellList(spells, picked, classValue, kind) {
    if (!spells.length) return `<div class="field-hint">Nessuno disponibile nei manuali scelti.</div>`;
    const set = new Set(picked);
    return `<div class="spell-list">
      ${spells.map(s => {
        const on = set.has(s.name);
        return `<label class="spell-row${on?' on':''}">
          <input type="checkbox" data-spell-toggle="${escapeAttr(s.name)}" data-class="${classValue}" data-kind="${kind}" ${on?'checked':''}>
          <span class="spell-name">${escapeHtml(s.name)}</span>
          ${s.school ? `<span class="spell-school">${escapeHtml(s.school)}</span>` : ''}
          ${s.ritual ? `<span class="spell-tag">R</span>` : ''}
        </label>`;
      }).join('')}
    </div>`;
  }

  function renderSpellListByLevel(spells, picked, classValue, kind, maxLvl) {
    const buckets = {};
    for (const s of spells) {
      const l = s.level || 1;
      (buckets[l] = buckets[l] || []).push(s);
    }
    const levels = Object.keys(buckets).map(Number).sort((a,b) => a-b);
    if (!levels.length) return `<div class="field-hint">Nessun incantesimo accessibile.</div>`;
    return levels.map(l => `
      <div class="spell-level-group" data-level="${l}">
        <div class="spell-level-head">Livello ${l}</div>
        ${renderSpellList(buckets[l], picked, classValue, kind)}
      </div>`).join('');
  }

  function wireEvents(container, state, opts) {
    const onChange = opts.onChange || (() => {});
    container.querySelectorAll('[data-spell-toggle]').forEach(cb => {
      cb.addEventListener('change', () => {
        const name = cb.dataset.spellToggle;
        const cls = cb.dataset.class;
        const kind = cb.dataset.kind; // 'cantrip' | 'spell'
        const key = kind === 'cantrip' ? 'cantrips' : 'spells';
        state[cls] = state[cls] || { cantrips: [], spells: [] };
        const arr = state[cls][key];
        const i = arr.indexOf(name);
        if (cb.checked && i === -1) arr.push(name);
        else if (!cb.checked && i >= 0) arr.splice(i, 1);
        render(container, state, opts);
        onChange(state);
      });
    });
    container.querySelectorAll('[data-spell-remove]').forEach(btn => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.spellRemove;
        const cls = btn.dataset.class;
        const kind = btn.dataset.kind;
        const key = kind === 'cantrip' ? 'cantrips' : 'spells';
        if (state[cls] && Array.isArray(state[cls][key])) {
          state[cls][key] = state[cls][key].filter(n => n !== name);
        }
        render(container, state, opts);
        onChange(state);
      });
    });
    // Filtro ricerca (semplice show/hide nei picker)
    container.querySelectorAll('.spell-search').forEach(inp => {
      inp.addEventListener('input', () => applySearchFilter(inp));
      // evita che il click sull'input chiuda <details>
      inp.addEventListener('click', e => e.stopPropagation());
    });
    // Radio filtro classe/sottoclasse/tutti
    container.querySelectorAll('.spell-filter input[type=radio]').forEach(r => {
      r.addEventListener('change', () => {
        const cls = r.closest('.spell-filter').dataset.class;
        window.__spellFilters = window.__spellFilters || {};
        window.__spellFilters[cls] = r.value;
        render(container, state, opts);
        onChange(state);
      });
    });
  }

  function applySearchFilter(inp) {
    const q = inp.value.trim().toLowerCase();
    const details = inp.closest('details');
    if (!details) return;
    details.querySelectorAll('.spell-row').forEach(row => {
      const n = row.querySelector('.spell-name')?.textContent?.toLowerCase() || '';
      row.style.display = (!q || n.includes(q)) ? '' : 'none';
    });
    // nasconde gruppi-livello vuoti
    details.querySelectorAll('.spell-level-group').forEach(g => {
      const any = Array.from(g.querySelectorAll('.spell-row')).some(r => r.style.display !== 'none');
      g.style.display = any ? '' : 'none';
    });
  }

  function escapeAttr(s) { return String(s).replace(/"/g, '&quot;'); }

  return { render, validate, normalize, defaultState };
})();
