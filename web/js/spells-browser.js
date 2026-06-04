// Grimorio: browser incantesimi con filtri multipli + modal dettaglio.
(function () {
  const SCHOOLS = ['abiurazione','ammaliamento','divinazione','evocazione','illusione','invocazione','necromanzia','trasmutazione'];
  const TAGS = ['danno','controllo','cura','protezione','potenziamento','indebolimento','evocazione','utilità','movimento','rituale'];
  const SCHOOL_COLORS = {
    abiurazione:'#6eaaff', ammaliamento:'#d490ff', divinazione:'#7ce0d2',
    evocazione:'#ffb86b', illusione:'#ff8fd0', invocazione:'#ff7464',
    necromanzia:'#9aa3b8', trasmutazione:'#9be07b',
  };

  // Stato filtri persistito su sessionStorage
  const state = loadState() || {
    search: '',
    classes: new Set(),
    levels: new Set(),
    schools: new Set(),
    tags: new Set(),
    sources: new Set(),
    sort: 'level',
  };

  let ALL = [];
  let CLASSES = [];
  let SOURCES = [];

  async function init() {
    try {
      await DndCache.load();
      ALL = await DndCache.loadSpells();
    } catch (e) {
      UI.toast('Impossibile caricare il grimorio: ' + e.message, 'error');
      return;
    }
    CLASSES = DndCache.classes().map(c => ({ value: c.value, label: c.label }));
    SOURCES = collectSources(ALL);
    renderFilters();
    wire();
    apply();
  }

  function collectSources(spells) {
    const counts = new Map();
    for (const s of spells) {
      const src = s.source || 'Sconosciuto';
      counts.set(src, (counts.get(src) || 0) + 1);
    }
    return [...counts.entries()]
      .sort((a,b) => b[1]-a[1])
      .map(([source, n]) => ({ source, n }));
  }

  function renderFilters() {
    // Classi
    document.getElementById('sb-classes').innerHTML = CLASSES.map(c =>
      `<button class="sb-chip${state.classes.has(c.value)?' on':''}" data-f="classes" data-v="${escapeAttr(c.value)}">${escapeHtml(c.label)}</button>`
    ).join('');

    // Livelli 0..9
    document.getElementById('sb-levels').innerHTML = [0,1,2,3,4,5,6,7,8,9].map(l =>
      `<button class="sb-chip${state.levels.has(String(l))?' on':''}" data-f="levels" data-v="${l}">${l===0?'T':l}</button>`
    ).join('');

    // Scuole
    document.getElementById('sb-schools').innerHTML = SCHOOLS.map(s =>
      `<button class="sb-chip sb-chip-school${state.schools.has(s)?' on':''}" data-f="schools" data-v="${s}" style="--school:${SCHOOL_COLORS[s]||'#888'}">${escapeHtml(capitalize(s))}</button>`
    ).join('');

    // Tag
    document.getElementById('sb-tags').innerHTML = TAGS.map(t =>
      `<button class="sb-chip sb-chip-tag${state.tags.has(t)?' on':''}" data-f="tags" data-v="${t}">${escapeHtml(capitalize(t))}</button>`
    ).join('');

    // Manuali — tabella centrata acronimo + spunta
    document.getElementById('sb-sources').innerHTML =
      `<table class="sb-src-table">` +
      SOURCES.map(s =>
        `<tr class="${state.sources.has(s.source)?'on':''}">
          <td class="sb-src-acr">${escapeHtml(shortSource(s.source))}</td>
          <td class="sb-src-n">${s.n}</td>
          <td class="sb-src-chk"><input type="checkbox" data-source="${escapeAttr(s.source)}" ${state.sources.has(s.source)?'checked':''}></td>
        </tr>`
      ).join('') +
      `</table>`;

    // Search / sort
    document.getElementById('sb-search').value = state.search;
    document.getElementById('sb-sort').value = state.sort;
  }

  function wire() {
    const root = document.getElementById('sb-filters');
    root.addEventListener('click', e => {
      const chip = e.target.closest('.sb-chip');
      if (chip) {
        const f = chip.dataset.f, v = chip.dataset.v;
        if (state[f].has(v)) state[f].delete(v); else state[f].add(v);
        chip.classList.toggle('on');
        saveState(); apply();
      }
    });
    root.addEventListener('change', e => {
      const src = e.target.dataset.source;
      if (src !== undefined) {
        if (e.target.checked) state.sources.add(src); else state.sources.delete(src);
        saveState(); apply();
      }
    });
    document.getElementById('sb-search').addEventListener('input', e => {
      state.search = e.target.value; saveState(); apply();
    });
    document.getElementById('sb-sort').addEventListener('change', e => {
      state.sort = e.target.value; saveState(); apply();
    });
    document.getElementById('sb-reset').addEventListener('click', () => {
      state.search = '';
      state.classes.clear(); state.levels.clear(); state.schools.clear();
      state.tags.clear(); state.sources.clear();
      saveState(); renderFilters(); apply();
    });

    // Click su una riga risultato → apri modal
    document.getElementById('sb-list').addEventListener('click', e => {
      const card = e.target.closest('.sb-row');
      if (!card) return;
      const idx = +card.dataset.idx;
      const spell = window.__filtered[idx];
      if (spell) openDetail(spell);
    });
  }

  function apply() {
    const q = norm(state.search);
    const enClasses = [...state.classes].map(v => classEn(v)).filter(Boolean);
    const levels = [...state.levels].map(Number);
    const schools = [...state.schools];
    const tags = [...state.tags];
    const sources = [...state.sources];

    const out = ALL.filter(s => {
      if (q) {
        const it = norm(s.name); const en = norm(s.name_en || '');
        if (!it.includes(q) && !en.includes(q)) return false;
      }
      if (levels.length && !levels.includes(s.level)) return false;
      if (schools.length && !schools.includes((s.school||'').toLowerCase())) return false;
      if (tags.length) {
        const hasRitual = tags.includes('rituale');
        const otherTags = tags.filter(t => t !== 'rituale');
        const matchOther = otherTags.length === 0 || otherTags.some(t => (s.tags||[]).includes(t));
        if (!matchOther) return false;
        if (hasRitual && !s.ritual) return false;
      }
      if (sources.length && !sources.includes(s.source)) return false;
      if (enClasses.length) {
        const has = enClasses.some(en => (s.classes||[]).includes(en) || (s.classes_subclass_only||[]).includes(en));
        if (!has) return false;
      }
      return true;
    });

    sortIn(out, state.sort);
    window.__filtered = out;
    document.getElementById('sb-count').textContent =
      out.length === 1 ? '1 incantesimo' : `${out.length} incantesimi`;
    document.getElementById('sb-list').innerHTML = out.map(renderRow).join('') ||
      '<div class="sb-empty">Nessun incantesimo corrisponde ai filtri.</div>';
  }

  function sortIn(arr, mode) {
    if (mode === 'name') arr.sort((a,b) => a.name.localeCompare(b.name, 'it'));
    else if (mode === 'school') arr.sort((a,b) => (a.school||'').localeCompare(b.school||'','it') || a.name.localeCompare(b.name,'it'));
    else arr.sort((a,b) => (a.level??99)-(b.level??99) || a.name.localeCompare(b.name,'it'));
  }

  function renderRow(s, i) {
    const lvl = s.level === 0 ? 'T' : (s.level ?? '?');
    const school = s.school ? `<span class="sb-school" style="color:${SCHOOL_COLORS[s.school]||'#aaa'}">${escapeHtml(capitalize(s.school))}</span>` : '';
    const ritual = s.ritual ? `<span class="sb-tag-r">R</span>` : '';
    const tags = (s.tags||[]).slice(0,3).map(t => `<span class="sb-tag">${escapeHtml(t)}</span>`).join('');
    const classes = (s.classes||[]).slice(0,4).map(c => `<span class="sb-classpill">${escapeHtml(classIt(c))}</span>`).join('');
    return `<button type="button" class="sb-row" data-idx="${i}">
      <span class="sb-lvl">${lvl}</span>
      <span class="sb-main">
        <span class="sb-name">${escapeHtml(s.name)}${ritual}</span>
        <span class="sb-meta">${school}${classes ? ' · ' + classes : ''}</span>
      </span>
      <span class="sb-tags">${tags}</span>
    </button>`;
  }

  // Splitta "V, S, M (vischio raccolto a luna piena)" in {vsm:['V','S','M'], material:'vischio...'}
  function parseComponents(raw) {
    const out = { vsm: [], material: '', extra: '' };
    if (!raw) return out;
    let s = String(raw).trim();
    const matM = s.match(/M\s*\((.+?)\)\s*$/i);
    if (matM) { out.material = matM[1].trim(); s = s.slice(0, matM.index).trim().replace(/[,;]\s*$/, ''); }
    const tokens = s.split(/[\s,;]+/).filter(Boolean);
    for (const t of tokens) {
      const u = t.toUpperCase();
      if (u === 'V' || u === 'S' || u === 'M') {
        if (!out.vsm.includes(u)) out.vsm.push(u);
      } else if (t) {
        out.extra = (out.extra ? out.extra + ' ' : '') + t;
      }
    }
    return out;
  }

  function targetLabels(target) {
    const MAP = {
      self: 'Incantatore',
      contatto: 'Contatto',
      creatura: 'Creatura',
      oggetto: 'Oggetto',
      area: 'Area',
      punto: 'Punto nello spazio',
    };
    return (target || []).map(t => MAP[t] || t);
  }

  function openDetail(s) {
    const host = document.getElementById('sb-modal-host');
    const lvl = s.level === 0 ? 'Trucchetto' : `Livello ${s.level}`;
    const school = s.school ? capitalize(s.school) : '';
    const desc = (s.description || '').trim();
    const descHtml = desc
      ? desc.split(/\n{2,}|\n/).filter(Boolean).map(p => `<p>${escapeHtml(p)}</p>`).join('')
      : '<p class="faint">Descrizione non disponibile (estrazione OCR).</p>';
    const classes = (s.classes||[]);
    const subOnly = (s.classes_subclass_only||[]);
    const tags = (s.tags||[]);
    const comp = parseComponents(s.components);
    const compChips = ['V','S','M'].map(c => {
      const on = comp.vsm.includes(c);
      const title = c === 'V' ? 'Verbale' : c === 'S' ? 'Somatica' : 'Materiale';
      return `<span class="sb-comp-chip${on?' on':''}" title="${title}">${c}</span>`;
    }).join('');
    const targets = targetLabels(s.target);

    host.innerHTML = `<div class="modal-backdrop sb-modal-bd">
      <div class="modal sb-modal" role="dialog" aria-modal="true">
        <button class="sb-modal-close" aria-label="Chiudi">×</button>
        <h2 class="sb-modal-title">${escapeHtml(s.name)}${s.ritual?'<span class="sb-tag-r" style="vertical-align:middle;margin-left:8px">R</span>':''}</h2>
        <p class="sb-modal-sub">${escapeHtml(lvl)}${school ? ' · ' + escapeHtml(school) : ''}${s.name_en ? ` · <span class="faint">${escapeHtml(s.name_en)}</span>` : ''}</p>

        <dl class="sb-kv">
          <div><dt>Tempo di lancio</dt><dd>${escapeHtml(s.casting_time || '—')}</dd></div>
          <div><dt>Gittata</dt><dd>${escapeHtml(s.range || '—')}</dd></div>
          <div><dt>Componenti</dt><dd><span class="sb-comp-chips">${compChips}</span></dd></div>
          <div><dt>Durata</dt><dd>${escapeHtml(s.duration || '—')}</dd></div>
          ${targets.length ? `<div><dt>Bersaglio</dt><dd>${targets.map(t=>`<span class="sb-tag">${escapeHtml(t)}</span>`).join(' ')}</dd></div>` : ''}
          ${comp.material ? `<div class="sb-kv-wide"><dt>Materiale</dt><dd>${escapeHtml(comp.material)}</dd></div>` : ''}
        </dl>

        ${tags.length ? `<div class="sb-modal-tags">${tags.map(t=>`<span class="sb-tag">${escapeHtml(t)}</span>`).join('')}</div>` : ''}

        <div class="sb-modal-desc">${descHtml}</div>

        ${classes.length ? `<div class="sb-modal-classes"><strong>Classi:</strong> ${classes.map(c=>escapeHtml(classIt(c))).join(', ')}</div>` : ''}
        ${subOnly.length ? `<div class="sb-modal-classes faint"><strong>Solo via sottoclasse:</strong> ${subOnly.map(c=>escapeHtml(classIt(c))).join(', ')}</div>` : ''}

        <p class="sb-modal-source faint">${escapeHtml(s.source || '')}${s.page ? ` · p. ${s.page}` : ''}</p>
      </div>
    </div>`;

    const close = () => host.innerHTML = '';
    host.querySelector('.sb-modal-bd').addEventListener('click', e => {
      if (e.target.classList.contains('sb-modal-bd') || e.target.classList.contains('sb-modal-close')) close();
    });
    const onKey = e => { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); } };
    document.addEventListener('keydown', onKey);
  }

  // Helpers
  const EN_TO_IT_CLASS = {
    Barbarian:'Barbaro', Bard:'Bardo', Cleric:'Chierico', Druid:'Druido', Fighter:'Guerriero',
    Rogue:'Ladro', Wizard:'Mago', Monk:'Monaco', Paladin:'Paladino', Ranger:'Ranger',
    Sorcerer:'Stregone', Warlock:'Warlock', Artificer:'Artefice',
  };
  function classIt(en) { return EN_TO_IT_CLASS[en] || en; }

  // espone helper per recuperare nome EN dalla classe IT (riusa la mappa di DndCache)
  function classEn(val) { return DndCache._CLASS_VALUE_TO_EN ? DndCache._CLASS_VALUE_TO_EN[val] : null; }

  function norm(s) { return (s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,''); }
  function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }
  function shortSource(s) {
    if (/manuale del giocatore/i.test(s))  return 'PHB';
    if (/xanathar/i.test(s))              return 'XGE';
    if (/tasha/i.test(s))                 return 'TCE';
    if (/costa della spada/i.test(s))     return 'SCAG';
    if (/manuale del master/i.test(s))    return 'DMG';
    if (/manuale dei mostri/i.test(s))    return 'MM';
    // fallback: prima sigla uppercase o troncamento
    const m = s.match(/\b([A-Z]{2,5})\b/);
    return m ? m[1] : s.slice(0, 12);
  }
  function escapeHtml(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function escapeAttr(s) { return escapeHtml(s); }

  // Persist filtri
  function saveState() {
    try {
      sessionStorage.setItem('cz_grimorio', JSON.stringify({
        search: state.search, sort: state.sort,
        classes: [...state.classes], levels: [...state.levels],
        schools: [...state.schools], tags: [...state.tags], sources: [...state.sources],
      }));
    } catch(_) {}
  }
  function loadState() {
    try {
      const raw = sessionStorage.getItem('cz_grimorio');
      if (!raw) return null;
      const o = JSON.parse(raw);
      return {
        search: o.search || '', sort: o.sort || 'level',
        classes: new Set(o.classes || []), levels: new Set(o.levels || []),
        schools: new Set(o.schools || []), tags: new Set(o.tags || []),
        sources: new Set(o.sources || []),
      };
    } catch(_) { return null; }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
