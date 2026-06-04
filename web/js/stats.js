// Widget condiviso per le statistiche (FOR/DES/COS/INT/SAG/CAR).
// Tre metodi: roll (4d6 scarta minore), pointbuy (27pt 8-15), manual.
// Più: bonus razziali (standard dalla razza, oppure flessibili +2/+1).
// Per Umano Variante: 1 talento + 2x +1 a scelta su caratteristiche diverse.

const StatsWidget = (() => {

  // -------- Modello dati --------
  function emptyStats() {
    return { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 };
  }
  function defaultState() {
    return {
      base: emptyStats(),
      method: 'manual',      // 'roll' | 'pointbuy' | 'manual'
      bonus_mode: 'standard',// 'standard' | 'flexible'
      bonus_flex: {},        // chiave stat -> incremento (somma deve essere +2 e +1)
      variant_feat: '',
      variant_feat_stat: '', // stat scelta per talenti con stat_bonus_value (es. Resiliente)
      variant_bonuses: [],   // 2 chiavi distinte per Umano Variante
      roll_pool: null,       // array di 6 numeri tirati (4d6 drop lowest), o null
      roll_assign: {},       // mappa stat-key -> indice nel pool (assegnamento drag&drop)
    };
  }

  function normalize(s) {
    const x = Object.assign(defaultState(), s || {});
    x.base = Object.assign(emptyStats(), s?.base || {});
    x.bonus_flex = Object.assign({}, s?.bonus_flex || {});
    x.variant_bonuses = Array.isArray(s?.variant_bonuses) ? s.variant_bonuses.slice(0, 2) : [];
    if (!['roll','pointbuy','manual'].includes(x.method)) x.method = 'manual';
    if (!['standard','flexible'].includes(x.bonus_mode)) x.bonus_mode = 'standard';
    x.roll_pool = Array.isArray(s?.roll_pool) && s.roll_pool.length === 6
      ? s.roll_pool.map(v => parseInt(v, 10) || 0)
      : null;
    x.roll_assign = (s && typeof s.roll_assign === 'object') ? { ...s.roll_assign } : {};
    return x;
  }

  // Sincronizza state.base in modalità roll dai roll_assign + roll_pool.
  function syncRollBase(state) {
    if (state.method !== 'roll' || !state.roll_pool) return;
    for (const s of STATS) {
      const idx = state.roll_assign?.[s.key];
      if (Number.isInteger(idx) && idx >= 0 && idx < 6) {
        state.base[s.key] = state.roll_pool[idx];
      } else {
        state.base[s.key] = 0; // non assegnata
      }
    }
  }

  // -------- Calcoli --------
  function pointBuyTotal(base) {
    let tot = 0;
    for (const s of STATS) {
      const v = base[s.key];
      if (!(v in POINT_BUY_COST)) return Infinity;
      tot += POINT_BUY_COST[v];
    }
    return tot;
  }

  function racialBonuses(raceName, state) {
    const def = DndCache.raceDef(raceName);
    const out = { str:0, dex:0, con:0, int:0, wis:0, cha:0 };
    if (!def) return out;

    if (def.variant_human) {
      for (const k of (state.variant_bonuses || [])) {
        if (out[k] !== undefined) out[k] += 1;
      }
      // Bonus dal talento di Umano Variante (es. Resiliente +1)
      if (state.variant_feat && state.variant_feat_stat) {
        const fd = DndCache.featMeta(state.variant_feat);
        if (fd?.stat_bonus_value && out[state.variant_feat_stat] !== undefined) {
          out[state.variant_feat_stat] += fd.stat_bonus_value;
        }
      }
      return out;
    }

    if (state.bonus_mode === 'flexible') {
      for (const [k, v] of Object.entries(state.bonus_flex || {})) {
        if (out[k] !== undefined) out[k] += v;
      }
      return out;
    }

    // standard: dalla definizione di razza
    for (const [k, v] of Object.entries(def.stat_bonuses || {})) {
      if (out[k] !== undefined) out[k] += v;
    }
    return out;
  }

  function finalScore(state, raceName, key, asiBonusByKey) {
    const bonus = racialBonuses(raceName, state)[key] || 0;
    const asi = (asiBonusByKey && asiBonusByKey[key]) || 0;
    return (state.base[key] || 0) + bonus + asi;
  }

  // -------- Validazione --------
  function validate(state, raceName) {
    const errs = [];
    for (const s of STATS) {
      const v = state.base[s.key];
      if (!Number.isInteger(v) || v < 1 || v > 30) {
        errs.push(`${s.label}: valore non valido.`);
      }
    }
    if (state.method === 'pointbuy') {
      const tot = pointBuyTotal(state.base);
      if (tot === Infinity) errs.push('Point Buy: ogni statistica deve essere tra 8 e 15.');
      else if (tot > POINT_BUY_BUDGET) errs.push(`Point Buy: hai speso ${tot}/${POINT_BUY_BUDGET} punti.`);
    }
    if (state.method === 'roll') {
      if (!state.roll_pool) {
        errs.push('Tira 4d6: clicca "Tira" per generare i valori, poi trascinali sulle caratteristiche.');
      } else {
        const assigned = STATS.filter(s => Number.isInteger(state.roll_assign?.[s.key])).length;
        if (assigned < 6) errs.push(`Tira 4d6: assegna tutti i 6 valori (${assigned}/6).`);
      }
    }
    const def = DndCache.raceDef(raceName);
    if (def?.variant_human) {
      const vb = state.variant_bonuses || [];
      if (vb.length !== 2 || vb[0] === vb[1] || vb.some(k => !STATS.find(s => s.key === k))) {
        errs.push('Umano Variante: scegli due caratteristiche diverse a cui assegnare +1.');
      }
      if (!state.variant_feat) errs.push('Umano Variante: scegli un talento.');
      else {
        const fd = DndCache.featMeta(state.variant_feat);
        if (fd?.stat_bonus_value && !state.variant_feat_stat) {
          errs.push(`Talento "${state.variant_feat}": scegli la caratteristica a cui applicare +${fd.stat_bonus_value}.`);
        }
      }
    } else if (state.bonus_mode === 'flexible') {
      const vals = Object.values(state.bonus_flex || {}).filter(v => v > 0);
      const sum = vals.reduce((a,b) => a+b, 0);
      const keys = Object.keys(state.bonus_flex || {}).filter(k => state.bonus_flex[k] > 0);
      const has2 = vals.includes(2);
      const has1 = vals.includes(1);
      if (sum !== 3 || keys.length !== 2 || !has2 || !has1) {
        errs.push('Bonus razziali liberi: assegna +2 a una caratteristica e +1 a un\'altra.');
      }
    }
    return errs;
  }

  // -------- Render --------
  function render(container, state, opts) {
    UI.preserveScroll(() => { renderInner(container, state, opts); });
  }

  function renderInner(container, state, opts) {
    state = normalize(state);
    const raceName = opts?.raceName || '';
    const sources = opts?.sources || [];
    const onChange = opts?.onChange || (() => {});
    const idPrefix = opts?.idPrefix || 'sw';
    const asiByKey = opts?.asiByKey || {};

    const def = DndCache.raceDef(raceName);
    const isVariant = !!def?.variant_human;

    const methodTabs = `
      <div class="seg">
        ${['roll','pointbuy','manual'].map(m => `
          <button type="button" class="seg-btn${state.method===m?' active':''}" data-method="${m}">
            ${m==='roll'?'Tira 4d6':m==='pointbuy'?'Point Buy':'Manuale'}
          </button>`).join('')}
      </div>`;

    const rollUI = state.roll_pool ? `
      <div class="roll-pool" data-roll-pool>
        ${state.roll_pool.map((v, i) => {
          const used = STATS.some(s => state.roll_assign?.[s.key] === i);
          return `<div class="roll-chip${used ? ' used' : ''}" draggable="${used ? 'false' : 'true'}" data-pool-idx="${i}">${v}</div>`;
        }).join('')}
      </div>
      <div class="roll-actions">
        <button type="button" class="btn ghost" id="${idPrefix}-roll-btn">🎲 Ritira tutto</button>
        <button type="button" class="btn ghost" id="${idPrefix}-roll-reset" data-roll-reset>↺ Svuota assegnazioni</button>
      </div>
      <div class="field-hint">Trascina ogni valore sulla caratteristica che preferisci. Per cambiare, trascinane uno nuovo sopra o usa × per liberarla.</div>` : `
      <button type="button" class="btn" id="${idPrefix}-roll-btn">🎲 Tira 4d6 (×6)</button>
      <div class="field-hint">Tira 6 valori (4d6, scarta il più basso), poi assegnali con drag &amp; drop.</div>`;

    const pbTotal = pointBuyTotal(state.base);
    const pbValid = pbTotal !== Infinity && pbTotal <= POINT_BUY_BUDGET;
    const pbUI = `
      <div class="pb-budget${pbValid?'':' over'}" data-pb-budget>
        Spesi: <strong data-pb-spent>${pbTotal === Infinity ? '—' : pbTotal}</strong> / ${POINT_BUY_BUDGET} punti
      </div>
      <div class="field-hint">Intervallo 8-15. Costi: 8=0, 9=1, 10=2, 11=3, 12=4, 13=5, 14=7, 15=9.</div>`;

    const helpByMethod = {
      roll: rollUI,
      pointbuy: pbUI,
      manual: `<div class="field-hint">Inserisci i valori a mano (1-30).</div>`,
    };

    // Tabella statistiche
    if (state.method === 'roll') syncRollBase(state);
    const racial = racialBonuses(raceName, state);
    const isRoll = state.method === 'roll';
    const statsGrid = `
      <div class="stats-grid${isRoll ? ' roll-mode' : ''}">
        ${STATS.map(s => {
          const base = state.base[s.key];
          const bonus = racial[s.key];
          const asi = asiByKey[s.key] || 0;
          const assignedIdx = state.roll_assign?.[s.key];
          const hasAssign = isRoll && Number.isInteger(assignedIdx);
          const total = (hasAssign || !isRoll) ? (base + bonus + asi) : 0;
          const inputAttrs = state.method === 'pointbuy'
            ? `min="8" max="15"`
            : `min="1" max="30"`;
          const inputEl = isRoll
            ? `<div class="stat-drop${hasAssign ? ' filled' : ''}" data-drop-stat="${s.key}">
                 <span class="stat-drop-value">${hasAssign ? base : '?'}</span>
                 ${hasAssign ? `<button type="button" class="stat-drop-clear" data-drop-clear="${s.key}" title="Libera">×</button>` : ''}
               </div>`
            : `<input type="number" class="stat-input" data-stat="${s.key}" ${inputAttrs} value="${base}">`;
          return `
            <div class="stat-cell" data-cell="${s.key}">
              <div class="stat-head">
                <span class="stat-short">${s.short}</span>
                <span class="stat-label">${s.label}</span>
              </div>
              ${inputEl}
              <div class="stat-meta">
                <span class="stat-bonus" data-bonus>${bonus ? `${bonus>0?'+':''}${bonus} razziale` : ''}</span>
                <span class="stat-asi" data-asi>${asi ? `${asi>0?'+':''}${asi} ASI` : ''}</span>
                <span class="stat-total">Totale: <strong data-total>${(hasAssign || !isRoll) ? total : '—'}</strong></span>
                <span class="stat-mod" data-mod>${(hasAssign || !isRoll) ? `Mod. ${fmtMod(statMod(total))}` : ''}</span>
              </div>
            </div>`;
        }).join('')}
      </div>`;

    // Bonus razziali (sotto la griglia)
    let raceUI = '';
    if (def && !isVariant) {
      const stdBonus = Object.entries(def.stat_bonuses || {})
        .map(([k,v]) => `${STATS.find(s=>s.key===k)?.short || k} ${v>0?'+':''}${v}`)
        .join(', ') || 'nessuno';
      raceUI = `
        <div class="race-bonus-block">
          <div class="rb-title">Bonus razziali — ${escapeHtml(raceName)}</div>
          <div class="seg">
            <button type="button" class="seg-btn${state.bonus_mode==='standard'?' active':''}" data-bmode="standard">Standard (${escapeHtml(stdBonus)})</button>
            <button type="button" class="seg-btn${state.bonus_mode==='flexible'?' active':''}" data-bmode="flexible">Libero (+2 / +1)</button>
          </div>
          ${state.bonus_mode==='flexible' ? renderFlexBonuses(state) : ''}
        </div>`;
    } else if (isVariant) {
      const feats = DndCache.feats(sources);
      raceUI = `
        <div class="race-bonus-block">
          <div class="rb-title">Umano Variante — +1 a due caratteristiche diverse + 1 talento</div>
          <div class="vh-pickers">
            <label>Prima caratteristica
              <select data-vh-idx="0">
                <option value="">—</option>
                ${STATS.map(s => `<option value="${s.key}"${state.variant_bonuses[0]===s.key?' selected':''}>${s.label}</option>`).join('')}
              </select>
            </label>
            <label>Seconda caratteristica
              <select data-vh-idx="1">
                <option value="">—</option>
                ${STATS.map(s => `<option value="${s.key}"${state.variant_bonuses[1]===s.key?' selected':''}>${s.label}</option>`).join('')}
              </select>
            </label>
          </div>
          <label class="vh-feat">Talento
            <select data-vh-feat>
              <option value="">— Scegli un talento —</option>
              ${feats.map(f => `<option value="${escapeHtml(f.name)}"${state.variant_feat===f.name?' selected':''}>${escapeHtml(f.name)}</option>`).join('')}
            </select>
          </label>
          ${(() => {
            const fd = state.variant_feat ? DndCache.featMeta(state.variant_feat) : null;
            if (!fd?.stat_bonus_value) return '';
            const opts = fd.stat_options && fd.stat_options.length > 0
              ? STATS.filter(s => fd.stat_options.includes(s.key))
              : STATS;
            return `<label class="vh-feat">Caratteristica per "${escapeHtml(state.variant_feat)}"
              <select data-vh-feat-stat>
                <option value="">— Scegli caratteristica —</option>
                ${opts.map(s => `<option value="${s.key}"${state.variant_feat_stat===s.key?' selected':''}>${s.label} (+${fd.stat_bonus_value})</option>`).join('')}
              </select>
            </label>`;
          })()}
          ${feats.length === 0 ? `<div class="gate-hint">Nessun talento nei manuali selezionati.</div>` : ''}
        </div>`;
    }

    container.innerHTML = `
      <div class="stats-widget">
        <div class="method-row">${methodTabs}<div class="method-help">${helpByMethod[state.method]}</div></div>
        ${statsGrid}
        ${raceUI}
      </div>
    `;

    // -------- Wire events --------
    container.querySelectorAll('.seg-btn[data-method]').forEach(b => {
      b.addEventListener('click', () => {
        const prev = state.method;
        state.method = b.dataset.method;
        if (state.method === 'pointbuy') {
          // resetta entro l'intervallo valido
          for (const s of STATS) if (!(state.base[s.key] in POINT_BUY_COST)) state.base[s.key] = 8;
        } else if (state.method !== 'roll' && prev === 'roll') {
          // uscendo da roll: se ci sono stat a 0 (non assegnate) portale a 10
          for (const s of STATS) if (!state.base[s.key]) state.base[s.key] = 10;
        }
        render(container, state, opts);
        onChange(state);
      });
    });
    container.querySelectorAll('.seg-btn[data-bmode]').forEach(b => {
      b.addEventListener('click', () => {
        state.bonus_mode = b.dataset.bmode;
        if (state.bonus_mode !== 'flexible') state.bonus_flex = {};
        render(container, state, opts);
        onChange(state);
      });
    });
    container.querySelectorAll('.stat-input').forEach(inp => {
      inp.addEventListener('input', () => {
        const k = inp.dataset.stat;
        const raw = inp.value;
        const v = parseInt(raw, 10);
        state.base[k] = Number.isFinite(v) ? v : 0;
        updateCellMeta(container, state, raceName, asiByKey);
        updatePbBudget(container, state);
        onChange(state);
      });
      inp.addEventListener('blur', () => {
        const k = inp.dataset.stat;
        const v = parseInt(inp.value, 10);
        if (!Number.isFinite(v)) { inp.value = state.base[k] || 0; }
      });
    });
    const rollBtn = container.querySelector(`#${idPrefix}-roll-btn`);
    if (rollBtn) {
      rollBtn.addEventListener('click', () => {
        state.roll_pool = [0,0,0,0,0,0].map(() => roll4d6dl());
        state.roll_assign = {};
        for (const s of STATS) state.base[s.key] = 0;
        render(container, state, opts);
        onChange(state);
      });
    }
    const rollReset = container.querySelector(`#${idPrefix}-roll-reset`);
    if (rollReset) {
      rollReset.addEventListener('click', () => {
        state.roll_assign = {};
        for (const s of STATS) state.base[s.key] = 0;
        render(container, state, opts);
        onChange(state);
      });
    }

    // Drag&drop: chips -> stat cell
    container.querySelectorAll('.roll-chip:not(.used)').forEach(chip => {
      chip.addEventListener('dragstart', (e) => {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', chip.dataset.poolIdx);
        chip.classList.add('dragging');
      });
      chip.addEventListener('dragend', () => chip.classList.remove('dragging'));
    });
    container.querySelectorAll('[data-drop-stat]').forEach(drop => {
      drop.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        drop.classList.add('drop-hover');
      });
      drop.addEventListener('dragleave', () => drop.classList.remove('drop-hover'));
      drop.addEventListener('drop', (e) => {
        e.preventDefault();
        drop.classList.remove('drop-hover');
        const idx = parseInt(e.dataTransfer.getData('text/plain'), 10);
        if (!Number.isInteger(idx)) return;
        const statKey = drop.dataset.dropStat;
        // se c'è già un altro stat con questo idx, liberalo (mossa unica)
        for (const k of Object.keys(state.roll_assign)) {
          if (state.roll_assign[k] === idx) delete state.roll_assign[k];
        }
        state.roll_assign[statKey] = idx;
        render(container, state, opts);
        onChange(state);
      });
    });
    container.querySelectorAll('[data-drop-clear]').forEach(btn => {
      btn.addEventListener('click', () => {
        const k = btn.dataset.dropClear;
        delete state.roll_assign[k];
        state.base[k] = 0;
        render(container, state, opts);
        onChange(state);
      });
    });
    container.querySelectorAll('select[data-vh-idx]').forEach(sel => {
      sel.addEventListener('change', () => {
        const i = parseInt(sel.dataset.vhIdx, 10);
        state.variant_bonuses[i] = sel.value;
        render(container, state, opts);
        onChange(state);
      });
    });
    const featSel = container.querySelector('select[data-vh-feat]');
    if (featSel) {
      featSel.addEventListener('change', () => {
        state.variant_feat = featSel.value;
        state.variant_feat_stat = ''; // reset stat choice when feat changes
        render(container, state, opts);
        onChange(state);
      });
    }
    const featStatSel = container.querySelector('select[data-vh-feat-stat]');
    if (featStatSel) {
      featStatSel.addEventListener('change', () => {
        state.variant_feat_stat = featStatSel.value;
        onChange(state);
      });
    }
    container.querySelectorAll('.flex-bonus-pick').forEach(sel => {
      sel.addEventListener('change', () => {
        const amount = parseInt(sel.dataset.amount, 10);
        // rimuovi i precedenti con lo stesso amount
        for (const k of Object.keys(state.bonus_flex)) {
          if (state.bonus_flex[k] === amount) delete state.bonus_flex[k];
        }
        if (sel.value) state.bonus_flex[sel.value] = amount;
        render(container, state, opts);
        onChange(state);
      });
    });
  }

  function updateCellMeta(container, state, raceName, asiByKey) {
    const racial = racialBonuses(raceName, state);
    const asi = asiByKey || {};
    for (const s of STATS) {
      const cell = container.querySelector(`.stat-cell[data-cell="${s.key}"]`);
      if (!cell) continue;
      const base = state.base[s.key] || 0;
      const bonus = racial[s.key] || 0;
      const a = asi[s.key] || 0;
      const total = base + bonus + a;
      const bEl = cell.querySelector('[data-bonus]');
      const aEl = cell.querySelector('[data-asi]');
      const tEl = cell.querySelector('[data-total]');
      const mEl = cell.querySelector('[data-mod]');
      if (bEl) bEl.textContent = bonus ? `${bonus>0?'+':''}${bonus} razziale` : '';
      if (aEl) aEl.textContent = a ? `${a>0?'+':''}${a} ASI` : '';
      if (tEl) tEl.textContent = total;
      if (mEl) mEl.textContent = `Mod. ${fmtMod(statMod(total))}`;
    }
  }

  function updatePbBudget(container, state) {
    if (state.method !== 'pointbuy') return;
    const tot = pointBuyTotal(state.base);
    const valid = tot !== Infinity && tot <= POINT_BUY_BUDGET;
    const box = container.querySelector('[data-pb-budget]');
    const spent = container.querySelector('[data-pb-spent]');
    if (box) box.classList.toggle('over', !valid);
    if (spent) spent.textContent = tot === Infinity ? '—' : tot;
  }

  function renderFlexBonuses(state) {
    const pick = (amount) => {
      const chosen = Object.entries(state.bonus_flex).find(([k,v]) => v === amount)?.[0] || '';
      return `<select class="flex-bonus-pick" data-amount="${amount}">
        <option value="">— Scegli —</option>
        ${STATS.map(s => `<option value="${s.key}"${chosen===s.key?' selected':''}>${s.label}</option>`).join('')}
      </select>`;
    };
    return `
      <div class="vh-pickers">
        <label>+2 a <br>${pick(2)}</label>
        <label>+1 a <br>${pick(1)}</label>
      </div>
    `;
  }

  // Serializza per il salvataggio in data
  function serialize(state) {
    const s = normalize(state);
    if (s.method === 'roll') syncRollBase(s);
    const out = {
      stats: { ...s.base },
      stats_method: s.method,
      racial_bonus_mode: s.bonus_mode,
    };
    if (s.bonus_mode === 'flexible' && Object.keys(s.bonus_flex).length) {
      out.racial_bonus_flex = { ...s.bonus_flex };
    }
    if (s.variant_bonuses.length) out.variant_bonuses = s.variant_bonuses.slice();
    if (s.variant_feat) out.variant_feat = s.variant_feat;
    if (s.variant_feat_stat) out.variant_feat_stat = s.variant_feat_stat;
    if (s.method === 'roll' && s.roll_pool) {
      out.stats_roll_pool = s.roll_pool.slice();
      out.stats_roll_assign = { ...s.roll_assign };
    }
    return out;
  }

  // Deserializza dai dati salvati
  function deserialize(data) {
    return normalize({
      base: data?.stats,
      method: data?.stats_method,
      bonus_mode: data?.racial_bonus_mode,
      bonus_flex: data?.racial_bonus_flex,
      variant_bonuses: data?.variant_bonuses,
      variant_feat: data?.variant_feat,
      variant_feat_stat: data?.variant_feat_stat,
      roll_pool: data?.stats_roll_pool,
      roll_assign: data?.stats_roll_assign,
    });
  }

  return {
    render, validate, serialize, deserialize, normalize,
    finalScore, racialBonuses, statMod, fmtMod, defaultState,
  };
})();
