// MulticlassWidget — gestisce: lista di classi prese (PHB pag.163),
// per ogni classe: livelli (0..20), sottoclasse (gated a subclass_level vs livelli IN quella classe),
// e le scelte ASI/Talento per ogni "slot ASI" maturato in QUELLA classe (separati per classe).
//
// Stato persistito in sheet.data.classes:
//   [
//     { value:'guerriero', levels:5, subclass:'Campione',
//       asi_choices: [
//         {kind:'asi', plus:{str:2}},                 // +2 a una stat
//         {kind:'asi', plus:{dex:1, con:1}},          // +1/+1 a due stats diverse
//         {kind:'feat', name:'Allerta'}               // talento
//       ] }
//   ]
//
// Il livello totale del PG = somma dei livelli per classe (max 20).
const MulticlassWidget = (function () {
  'use strict';

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
      ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  function defaultState() {
    return { classes: [] };
  }

  function normalize(x) {
    if (!x) return defaultState();
    return {
      classes: Array.isArray(x.classes) ? x.classes.map(c => ({
        value: c.value || null,
        levels: Math.max(0, Math.min(20, parseInt(c.levels, 10) || 0)),
        subclass: c.subclass || '',
        asi_choices: Array.isArray(c.asi_choices) ? c.asi_choices.slice() : [],
      })).filter(c => c.value) : [],
    };
  }

  function totalLevel(state) {
    return state.classes.reduce((n, c) => n + c.levels, 0);
  }

  function validate(state) {
    state = normalize(state);
    const errors = [];
    const tot = totalLevel(state);
    if (tot < 1) errors.push('Aggiungi almeno un livello in una classe.');
    if (tot > 20) errors.push(`Livello totale ${tot}: massimo 20.`);
    for (const c of state.classes) {
      const def = DndCache.classDef(c.value);
      if (!def) continue;
      // sottoclasse obbligatoria se livelli >= subclass_level
      if (c.levels >= (def.subclass_level || 99) && !c.subclass) {
        errors.push(`${def.label}: scegli la ${def.group_label.toLowerCase()}.`);
      }
      // ASI/Talento: ogni slot maturato deve essere compilato
      const slots = (def.asi_levels || []).filter(l => l <= c.levels).length;
      const choices = c.asi_choices || [];
      for (let i = 0; i < slots; i++) {
        const ch = choices[i];
        if (!ch || !ch.kind) {
          errors.push(`${def.label}: scelta ASI/Talento mancante (livello ${def.asi_levels[i]}).`);
          continue;
        }
        if (ch.kind === 'asi') {
          const tot2 = Object.values(ch.plus || {}).reduce((a, b) => a + b, 0);
          if (tot2 !== 2) errors.push(`${def.label}: l'ASI al livello ${def.asi_levels[i]} deve sommare a +2.`);
        } else if (ch.kind === 'feat') {
          if (!ch.name) {
            errors.push(`${def.label}: scegli il talento al livello ${def.asi_levels[i]}.`);
            continue;
          }
          const meta = DndCache.featMeta(ch.name);
          if (meta?.stat_bonus_value !== undefined && !ch.feat_stat) {
            errors.push(`${def.label}: scegli la caratteristica per "${ch.name}" (livello ${def.asi_levels[i]}).`);
          }
        }
      }
    }
    return errors;
  }

  // Somma tutti i bonus ASI e bonus stat da talenti -> { str, dex, con, int, wis, cha }
  function asiBonuses(state) {
    const out = { str:0, dex:0, con:0, int:0, wis:0, cha:0 };
    state = normalize(state);
    for (const c of state.classes) {
      const def = DndCache.classDef(c.value);
      if (!def) continue;
      const slots = (def.asi_levels || []).filter(l => l <= c.levels).length;
      for (let i = 0; i < slots; i++) {
        const ch = c.asi_choices?.[i];
        if (!ch) continue;
        if (ch.kind === 'asi' && ch.plus) {
          for (const [k, v] of Object.entries(ch.plus)) {
            if (k in out) out[k] += (parseInt(v, 10) || 0);
          }
        } else if (ch.kind === 'feat' && ch.name && ch.feat_stat) {
          const meta = DndCache.featMeta(ch.name);
          if (meta?.stat_bonus_value && ch.feat_stat in out) {
            out[ch.feat_stat] += meta.stat_bonus_value;
          }
        }
      }
    }
    return out;
  }

  // Ritorna un Set di chiavi stat che hanno competenza TS da talenti (es. Resiliente).
  function featSaveProfs(state) {
    const profs = new Set();
    state = normalize(state);
    for (const c of state.classes) {
      const def = DndCache.classDef(c.value);
      if (!def) continue;
      const slots = (def.asi_levels || []).filter(l => l <= c.levels).length;
      for (let i = 0; i < slots; i++) {
        const ch = c.asi_choices?.[i];
        if (!ch || ch.kind !== 'feat' || !ch.name || !ch.feat_stat) continue;
        const meta = DndCache.featMeta(ch.name);
        if (meta?.save_prof) profs.add(ch.feat_stat);
      }
    }
    return profs;
  }

  function renderInner(container, state, opts) {
    const onChange = opts.onChange || (() => {});
    const sources = opts.sources || [];

    const tot = totalLevel(state);
    const totColor = tot > 20 ? 'over' : (tot === 0 ? '' : 'ok');

    const allClasses = DndCache.classes();
    const taken = new Set(state.classes.map(c => c.value));

    const addOptions = allClasses
      .filter(c => !taken.has(c.value))
      .map(c => `<option value="${escapeHtml(c.value)}">${escapeHtml(c.label)}</option>`)
      .join('');

    const rows = state.classes.map((c, idx) => renderClassRow(c, idx, sources)).join('');

    container.innerHTML = `
      <div class="mc-widget">
        <div class="mc-header">
          <span class="mc-total ${totColor}">Livello totale: <strong>${tot}</strong>/20</span>
        </div>
        <div class="mc-classes">${rows || '<div class="field-hint">Nessuna classe selezionata.</div>'}</div>
        ${allClasses.length > state.classes.length ? `
          <div class="mc-add">
            <select data-mc-add>
              <option value="">— Aggiungi una classe —</option>
              ${addOptions}
            </select>
          </div>` : ''}
      </div>`;
    return onChange;
  }

  function render(container, state, opts) {
    if (!container) return;
    opts = opts || {};
    state = normalize(state);
    let onChange;
    UI.preserveScroll(() => { onChange = renderInner(container, state, opts); });

    // Add class
    const addSel = container.querySelector('[data-mc-add]');
    if (addSel) {
      addSel.addEventListener('change', () => {
        if (!addSel.value) return;
        // Default: 1 livello sulla nuova classe (per multiclasse aggiuntiva), oppure
        // se è la prima classe del PG, anch'essa 1 livello.
        state.classes.push({ value: addSel.value, levels: 1, subclass: '', asi_choices: [] });
        render(container, state, opts);
        onChange(state);
      });
    }

    // Remove class
    container.querySelectorAll('[data-mc-remove]').forEach(b => {
      b.addEventListener('click', () => {
        const i = parseInt(b.dataset.mcRemove, 10);
        state.classes.splice(i, 1);
        render(container, state, opts);
        onChange(state);
      });
    });

    // Levels change
    container.querySelectorAll('[data-mc-levels]').forEach(inp => {
      inp.addEventListener('input', () => {
        const i = parseInt(inp.dataset.mcLevels, 10);
        const v = parseInt(inp.value, 10);
        const newLv = Math.max(0, Math.min(20, Number.isFinite(v) ? v : 0));
        const def = DndCache.classDef(state.classes[i].value);
        state.classes[i].levels = newLv;
        // reset sottoclasse se sotto soglia
        if (def && newLv < (def.subclass_level || 99)) state.classes[i].subclass = '';
        // tronca asi_choices alle slot effettivamente disponibili
        const slots = def ? (def.asi_levels || []).filter(l => l <= newLv).length : 0;
        state.classes[i].asi_choices = (state.classes[i].asi_choices || []).slice(0, slots);
        render(container, state, opts);
        onChange(state);
      });
    });

    // Subclass change
    container.querySelectorAll('[data-mc-subclass]').forEach(sel => {
      sel.addEventListener('change', () => {
        const i = parseInt(sel.dataset.mcSubclass, 10);
        state.classes[i].subclass = sel.value;
        onChange(state);
      });
    });

    // ASI: tipo (asi/feat)
    container.querySelectorAll('[data-mc-asi-kind]').forEach(sel => {
      sel.addEventListener('change', () => {
        const ci = parseInt(sel.dataset.classIdx, 10);
        const si = parseInt(sel.dataset.slotIdx, 10);
        if (!state.classes[ci].asi_choices) state.classes[ci].asi_choices = [];
        if (sel.value === 'asi') {
          state.classes[ci].asi_choices[si] = { kind: 'asi', plus: {} };
        } else if (sel.value === 'feat') {
          state.classes[ci].asi_choices[si] = { kind: 'feat', name: '' };
        } else {
          state.classes[ci].asi_choices[si] = null;
        }
        render(container, state, opts);
        onChange(state);
      });
    });

    // ASI: variante (+2/+1+1)
    container.querySelectorAll('[data-mc-asi-variant]').forEach(sel => {
      sel.addEventListener('change', () => {
        const ci = parseInt(sel.dataset.classIdx, 10);
        const si = parseInt(sel.dataset.slotIdx, 10);
        const ch = state.classes[ci].asi_choices[si];
        if (!ch || ch.kind !== 'asi') return;
        ch.plus = {};
        ch.variant = sel.value;
        render(container, state, opts);
        onChange(state);
      });
    });

    // ASI: stat select (+2 single)
    container.querySelectorAll('[data-mc-asi-stat2]').forEach(sel => {
      sel.addEventListener('change', () => {
        const ci = parseInt(sel.dataset.classIdx, 10);
        const si = parseInt(sel.dataset.slotIdx, 10);
        const ch = state.classes[ci].asi_choices[si];
        if (!ch || ch.kind !== 'asi') return;
        ch.plus = sel.value ? { [sel.value]: 2 } : {};
        onChange(state);
      });
    });

    // ASI: stat select (+1/+1 — due selettori)
    container.querySelectorAll('[data-mc-asi-stat1]').forEach(sel => {
      sel.addEventListener('change', () => {
        const ci = parseInt(sel.dataset.classIdx, 10);
        const si = parseInt(sel.dataset.slotIdx, 10);
        const slot = parseInt(sel.dataset.subIdx, 10); // 0 o 1
        const ch = state.classes[ci].asi_choices[si];
        if (!ch || ch.kind !== 'asi') return;
        // ricostruisci ch.plus dai due selettori
        const row = container.querySelectorAll(`[data-mc-asi-stat1][data-class-idx="${ci}"][data-slot-idx="${si}"]`);
        const a = row[0]?.value, b = row[1]?.value;
        ch.plus = {};
        if (a) ch.plus[a] = (ch.plus[a] || 0) + 1;
        if (b) ch.plus[b] = (ch.plus[b] || 0) + 1;
        onChange(state);
      });
    });

    // Feat select
    container.querySelectorAll('[data-mc-feat]').forEach(sel => {
      sel.addEventListener('change', () => {
        const ci = parseInt(sel.dataset.classIdx, 10);
        const si = parseInt(sel.dataset.slotIdx, 10);
        const ch = state.classes[ci].asi_choices[si];
        if (!ch || ch.kind !== 'feat') return;
        ch.name = sel.value;
        ch.feat_stat = '';  // reset quando il talento cambia
        render(container, state, opts);
        onChange(state);
      });
    });

    // Feat stat picker (per talenti con bonus stat: Resiliente, Atletico, etc.)
    container.querySelectorAll('[data-mc-feat-stat]').forEach(sel => {
      sel.addEventListener('change', () => {
        const ci = parseInt(sel.dataset.classIdx, 10);
        const si = parseInt(sel.dataset.slotIdx, 10);
        const ch = state.classes[ci]?.asi_choices[si];
        if (!ch || ch.kind !== 'feat') return;
        ch.feat_stat = sel.value;
        onChange(state);
      });
    });
  }

  function renderClassRow(c, idx, sources) {
    const def = DndCache.classDef(c.value);
    if (!def) {
      return `<div class="mc-class">
        <div class="mc-class-head">
          <strong>${escapeHtml(c.value)}</strong> (sconosciuta)
          <button type="button" class="btn ghost icon-btn" data-mc-remove="${idx}" title="Rimuovi">×</button>
        </div></div>`;
    }
    const subs = DndCache.subclasses(c.value, sources);
    const subUI = c.levels >= def.subclass_level ? `
      <label class="mc-sub-label">${escapeHtml(def.group_label)}
        <select data-mc-subclass="${idx}">
          <option value="">— Scegli —</option>
          ${subs.map(s => `<option value="${escapeHtml(s.name)}"${c.subclass===s.name?' selected':''}>${escapeHtml(s.name)}</option>`).join('')}
        </select>
      </label>` : `
      <div class="gate-hint">${escapeHtml(def.group_label)}: dal livello ${def.subclass_level}.</div>`;

    // ASI slots maturati in QUESTA classe
    const slots = (def.asi_levels || []).filter(l => l <= c.levels);
    const asiUI = slots.length === 0 ? '' : `
      <div class="mc-asi-block">
        <div class="mc-asi-title">Aumenti / Talenti (questa classe)</div>
        ${slots.map((lvl, si) => renderAsiSlot(c, idx, si, lvl, sources)).join('')}
      </div>`;

    return `
      <div class="mc-class">
        <div class="mc-class-head">
          <span class="mc-class-name">${escapeHtml(def.label)}</span>
          <label class="mc-levels-label">Livelli
            <input type="number" min="0" max="20" step="1" value="${c.levels}" data-mc-levels="${idx}">
          </label>
          <button type="button" class="btn ghost icon-btn" data-mc-remove="${idx}" title="Rimuovi classe">×</button>
        </div>
        ${subUI}
        ${asiUI}
      </div>`;
  }

  function renderAsiSlot(c, ci, si, lvl, sources) {
    const ch = c.asi_choices?.[si];
    const kind = ch?.kind || '';
    const head = `<div class="mc-asi-slot-head">Livello ${lvl}:</div>`;

    const kindSel = `
      <select data-mc-asi-kind data-class-idx="${ci}" data-slot-idx="${si}">
        <option value=""${kind===''?' selected':''}>— Scegli —</option>
        <option value="asi"${kind==='asi'?' selected':''}>Aumento Caratteristica</option>
        <option value="feat"${kind==='feat'?' selected':''}>Talento</option>
      </select>`;

    let body = '';
    if (kind === 'asi') {
      const variant = ch.variant || (Object.keys(ch.plus || {}).length === 1 ? 'plus2' : 'plus11');
      const stats2 = STATS.map(s => {
        const sel = ch.plus && ch.plus[s.key] === 2 ? ' selected' : '';
        return `<option value="${s.key}"${sel}>${s.label}</option>`;
      }).join('');
      const stats1pairs = (() => {
        // Per il +1/+1, ricavo le due chiavi (l'utente le sceglie nei due selettori)
        const ks = Object.entries(ch.plus || {})
          .flatMap(([k, v]) => Array(v).fill(k));
        return [ks[0] || '', ks[1] || ''];
      })();

      const variantSel = `
        <select data-mc-asi-variant data-class-idx="${ci}" data-slot-idx="${si}">
          <option value="plus2"${variant==='plus2'?' selected':''}>+2 a una caratteristica</option>
          <option value="plus11"${variant==='plus11'?' selected':''}>+1 a due caratteristiche diverse</option>
        </select>`;

      const pickers = variant === 'plus2'
        ? `<select data-mc-asi-stat2 data-class-idx="${ci}" data-slot-idx="${si}">
             <option value="">— Caratteristica —</option>${stats2}
           </select>`
        : `<div class="mc-asi-pair">
             <select data-mc-asi-stat1 data-class-idx="${ci}" data-slot-idx="${si}" data-sub-idx="0">
               <option value="">—</option>
               ${STATS.map(s => `<option value="${s.key}"${stats1pairs[0]===s.key?' selected':''}>${s.label}</option>`).join('')}
             </select>
             <select data-mc-asi-stat1 data-class-idx="${ci}" data-slot-idx="${si}" data-sub-idx="1">
               <option value="">—</option>
               ${STATS.map(s => `<option value="${s.key}"${stats1pairs[1]===s.key?' selected':''}>${s.label}</option>`).join('')}
             </select>
           </div>`;
      body = `<div class="mc-asi-body">${variantSel}${pickers}</div>`;
    } else if (kind === 'feat') {
      const feats = DndCache.feats(sources);
      const selFeat = ch?.name || '';
      const meta = selFeat ? DndCache.featMeta(selFeat) : null;

      let statPickerHtml = '';
      if (meta?.stat_bonus_value !== undefined) {
        const opts = (meta.stat_options?.length) ? meta.stat_options : STATS.map(s => s.key);
        const hint = meta.save_prof
          ? `+${meta.stat_bonus_value} e competenza TS:`
          : `+${meta.stat_bonus_value} caratteristica:`;
        statPickerHtml = `
          <div class="mc-feat-stat">
            <label>${hint}
              <select data-mc-feat-stat data-class-idx="${ci}" data-slot-idx="${si}">
                <option value="">— Scegli —</option>
                ${opts.map(k => {
                  const st = STATS.find(x => x.key === k);
                  return `<option value="${k}"${ch?.feat_stat===k?' selected':''}>${st ? st.short : k.toUpperCase()}</option>`;
                }).join('')}
              </select>
            </label>
          </div>`;
      }

      body = `
        <div class="mc-asi-body">
          <select data-mc-feat data-class-idx="${ci}" data-slot-idx="${si}">
            <option value="">— Scegli un talento —</option>
            ${feats.map(f => `<option value="${escapeHtml(f.name)}"${selFeat===f.name?' selected':''}>${escapeHtml(f.name)}</option>`).join('')}
          </select>
          ${feats.length===0 ? '<div class="gate-hint">Nessun talento nei manuali selezionati.</div>' : ''}
          ${statPickerHtml}
        </div>`;
    }

    return `<div class="mc-asi-slot">${head}${kindSel}${body}</div>`;
  }

  function serialize(state) {
    state = normalize(state);
    // ripulisci: rimuovi "variant" dai chunk asi (è solo UI), tieni .plus
    const out = state.classes.map(c => {
      const asi = (c.asi_choices || []).map(ch => {
        if (!ch) return null;
        if (ch.kind === 'asi') return { kind: 'asi', plus: { ...(ch.plus || {}) } };
        if (ch.kind === 'feat') {
          const out = { kind: 'feat', name: ch.name || '' };
          if (ch.feat_stat) out.feat_stat = ch.feat_stat;
          return out;
        }
        return null;
      });
      return {
        value: c.value,
        levels: c.levels,
        subclass: c.subclass || '',
        asi_choices: asi,
      };
    });
    return { classes: out, level: totalLevel(state) };
  }

  function deserialize(data) {
    return normalize({
      classes: Array.isArray(data?.classes) ? data.classes : (
        data?.class ? [{
          value: DndCache.resolveClass(data.class),
          levels: parseInt(data.level, 10) || 1,
          subclass: data.subclass || '',
          asi_choices: [],
        }] : []
      ),
    });
  }

  return {
    render, validate, serialize, deserialize, normalize, defaultState,
    totalLevel, asiBonuses, featSaveProfs,
  };
})();
