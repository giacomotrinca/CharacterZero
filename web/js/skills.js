// SkillsWidget — selezione competenze in abilità per un personaggio.
// Mostra le 18 abilità con checkbox. Le concessioni fisse (background, razza)
// sono "locked" e contano automaticamente. Le scelte (classe, razza/variant)
// hanno un budget (count) e si bloccano alle altre opzioni quando esaurite.
//
// Stato persistito in sheet.data:
//   skills:        { [key]: true }   // tutte le abilità con competenza (fisse + scelte)
//   skill_choices: { class:[keys], race:[keys] }   // solo le scelte fatte (per re-edit)
const SkillsWidget = (function () {
  'use strict';

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c =>
      ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }

  function defaultState() {
    return { classChoices: [], raceChoices: [] };
  }

  function normalize(x) {
    if (!x) return defaultState();
    return {
      classChoices: Array.isArray(x.classChoices) ? x.classChoices.slice() : [],
      raceChoices:  Array.isArray(x.raceChoices)  ? x.raceChoices.slice()  : [],
    };
  }

  // Ricava skill_choices da un sorgente (class def, race def o {count, options}).
  function _choices(src) {
    if (!src) return null;
    const sc = src.skill_choices || (src.count && src.options ? src : null);
    if (!sc || !sc.count) return null;
    return { count: sc.count, options: sc.options };
  }

  // Risolve "any" o lista in un Set di chiavi disponibili.
  function _optionsSet(options) {
    if (!options) return null;
    if (options === 'any') return null; // null = tutte
    return new Set(options);
  }

  function _grants(srcs) {
    const out = new Set();
    for (const src of srcs) {
      if (src && Array.isArray(src.skill_grants)) {
        for (const k of src.skill_grants) out.add(k);
      }
    }
    return out;
  }

  // Calcola dato uno stato + contesto:
  // - fixed: Set di skill garantite (background + razza-fisse)
  // - classCh: {count, options} | null
  // - raceCh:  {count, options} | null
  // - classChosen / raceChosen: arrays validati dello state
  // - allActive: Set di tutte le skill attive
  // - errors: array messaggi
  function compute(state, ctx) {
    state = normalize(state);
    const classDef = ctx.classDef || null;
    const raceDef  = ctx.raceDef  || null;
    const bgDef    = ctx.bgDef    || null;
    const classCh  = _choices(classDef);
    const raceCh   = _choices(raceDef);
    const fixedBg   = _grants([bgDef]);
    const fixedRace = _grants([raceDef]);
    const fixed     = new Set([...fixedBg, ...fixedRace]);

    // Filtra scelte non più valide (es. cambio classe) ed elimina collisioni con fixed.
    const classOpts = classCh ? _optionsSet(classCh.options) : null;
    const raceOpts  = raceCh  ? _optionsSet(raceCh.options)  : null;
    const classChosen = state.classChoices
      .filter(k => !fixed.has(k))
      .filter(k => !classOpts || classOpts.has(k))
      .slice(0, classCh ? classCh.count : 0);
    // Race chosen: deve essere fuori da fixed E fuori da classChosen.
    const classSet = new Set(classChosen);
    const raceChosen = state.raceChoices
      .filter(k => !fixed.has(k))
      .filter(k => !classSet.has(k))
      .filter(k => !raceOpts || raceOpts.has(k))
      .slice(0, raceCh ? raceCh.count : 0);

    const allActive = new Set(fixed);
    for (const k of classChosen) allActive.add(k);
    for (const k of raceChosen)  allActive.add(k);

    const errors = [];
    if (classCh && classChosen.length < classCh.count) {
      errors.push(`${classDef.label}: scegli ${classCh.count - classChosen.length} ${classCh.count - classChosen.length === 1 ? 'abilità' : 'abilità'} in più.`);
    }
    if (raceCh && raceChosen.length < raceCh.count) {
      errors.push(`${raceDef.name}: scegli ${raceCh.count - raceChosen.length} abilità in più.`);
    }

    return {
      fixed, fixedBg, fixedRace, classCh, raceCh, classChosen, raceChosen, allActive, errors,
      classOpts, raceOpts,
    };
  }

  function validate(state, ctx) {
    return compute(state, ctx).errors;
  }

  function render(container, state, ctx) {
    if (!container) return;
    const onChange = ctx.onChange || (() => {});
    const all = DndCache.skills();
    const info = compute(state, ctx);
    const { fixed, fixedBg, fixedRace, classCh, raceCh, classChosen, raceChosen, allActive, classOpts, raceOpts } = info;

    // Stato dei budget
    const classLeft = classCh ? (classCh.count - classChosen.length) : 0;
    const raceLeft  = raceCh  ? (raceCh.count  - raceChosen.length)  : 0;

    // Header con conteggio
    const headerParts = [];
    if (classCh) {
      headerParts.push(`<span class="sk-budget${classLeft===0?' done':''}"><strong>${ctx.classDef.label}:</strong> ${classChosen.length}/${classCh.count}</span>`);
    }
    if (raceCh) {
      headerParts.push(`<span class="sk-budget${raceLeft===0?' done':''}"><strong>${ctx.raceDef.name}:</strong> ${raceChosen.length}/${raceCh.count}</span>`);
    }
    if (fixedBg.size) {
      headerParts.push(`<span class="sk-budget done"><strong>Background:</strong> ${fixedBg.size}</span>`);
    }
    if (fixedRace.size) {
      headerParts.push(`<span class="sk-budget done"><strong>Razza:</strong> ${fixedRace.size}</span>`);
    }

    const rows = all.map(sk => {
      const isFixed = fixed.has(sk.key);
      const inClass = classChosen.includes(sk.key);
      const inRace  = raceChosen.includes(sk.key);
      const active  = allActive.has(sk.key);

      // Determina disponibilità:
      // - se isFixed: locked, sempre attivo
      // - altrimenti: può cliccarsi solo se è opzione di classe o di razza
      const isClassOption = classCh && (!classOpts || classOpts.has(sk.key));
      const isRaceOption  = raceCh  && (!raceOpts  || raceOpts.has(sk.key));
      const selectable = isClassOption || isRaceOption;

      // Disabilita se budget esaurito e non già selezionato
      let disabled = false;
      let lockReason = '';
      if (isFixed) { disabled = true; lockReason = 'concessa'; }
      else if (!selectable) { disabled = true; lockReason = 'non disponibile'; }
      else if (!active) {
        // se nessun budget disponibile la rendiamo disabled
        const classAvail = isClassOption && classLeft > 0;
        const raceAvail  = isRaceOption  && raceLeft  > 0;
        if (!classAvail && !raceAvail) { disabled = true; lockReason = 'budget esaurito'; }
      }

      const tag = fixedBg.has(sk.key) ? 'background'
                : fixedRace.has(sk.key) ? 'razza-fissa'
                : inClass ? 'classe'
                : inRace  ? 'razza'
                : '';

      const abLabel = ({str:'FOR',dex:'DES',con:'COS',int:'INT',wis:'SAG',cha:'CAR'})[sk.ability] || sk.ability.toUpperCase();

      return `
        <label class="skill-row${active?' active':''}${disabled?' disabled':''}" data-skill="${sk.key}">
          <input type="checkbox" data-skill-cb="${sk.key}" ${active?'checked':''} ${disabled?'disabled':''}>
          <span class="sk-name">${escapeHtml(sk.label)}</span>
          <span class="sk-ability">${abLabel}</span>
          ${tag ? `<span class="sk-tag tag-${tag}">${tag}</span>` : (disabled && !isFixed ? `<span class="sk-tag tag-locked">${lockReason}</span>` : '')}
        </label>`;
    }).join('');

    UI.preserveScroll(() => {
      container.innerHTML = `
        <div class="skills-widget">
          <div class="sk-header">${headerParts.join(' · ') || '<span class="field-hint">Nessuna scelta richiesta.</span>'}</div>
          <div class="skills-grid">${rows}</div>
        </div>`;

      container.querySelectorAll('[data-skill-cb]').forEach(cb => {
        cb.addEventListener('change', () => {
          const key = cb.dataset.skillCb;
          toggle(state, ctx, key);
          render(container, state, ctx);
          onChange(state);
        });
      });
    });
  }

  // Logica di toggle: se attivo, lo rimuove dalle scelte; altrimenti lo aggiunge
  // al primo budget disponibile (preferenza classe -> razza).
  function toggle(state, ctx, key) {
    const info = compute(state, ctx);
    if (info.fixed.has(key)) return; // immutabile

    // Già scelto da classe?
    const ic = state.classChoices.indexOf(key);
    if (ic >= 0) { state.classChoices.splice(ic, 1); return; }
    const ir = state.raceChoices.indexOf(key);
    if (ir >= 0) { state.raceChoices.splice(ir, 1); return; }

    const classOpts = info.classCh ? _optionsSet(info.classCh.options) : null;
    const raceOpts  = info.raceCh  ? _optionsSet(info.raceCh.options)  : null;

    const canClass = info.classCh && (!classOpts || classOpts.has(key)) && info.classChosen.length < info.classCh.count;
    const canRace  = info.raceCh  && (!raceOpts  || raceOpts.has(key))  && info.raceChosen.length  < info.raceCh.count;

    if (canClass) state.classChoices.push(key);
    else if (canRace) state.raceChoices.push(key);
  }

  function serialize(state, ctx) {
    const info = compute(state, ctx);
    const all = {};
    for (const k of info.allActive) all[k] = true;
    return {
      skills: all,
      skill_choices: {
        class: info.classChosen.slice(),
        race:  info.raceChosen.slice(),
      },
    };
  }

  function deserialize(data) {
    const sc = data?.skill_choices || {};
    return normalize({
      classChoices: Array.isArray(sc.class) ? sc.class : [],
      raceChoices:  Array.isArray(sc.race)  ? sc.race  : [],
    });
  }

  return { render, validate, serialize, deserialize, normalize, defaultState, compute };
})();
