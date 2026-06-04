const params  = new URLSearchParams(window.location.search);
const id      = params.get('id');
const content = document.getElementById('content');

let sheet = null;

const CHECK_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
  stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 6"/></svg>`;

(async () => {
  if (!id) {
    content.innerHTML = `<div class="error">ID scheda mancante</div>`;
    return;
  }
  UI.skeleton(content, 1);
  try {
    const [s] = await Promise.all([api.get(id), SchemaCache.load(), DndCache.load(), FeaturesCache.load()]);
    await DndCache.loadSpells();
    sheet = s;
    renderView();
  } catch (e) {
    content.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
  }
})();

function renderView() {
  const s = sheet;
  document.title = `${s.name} — CharacterZero`;

  const kindLabel         = SchemaCache.kindLabel(s.kind);
  const data  = s.data || {};
  const usesClasses = SchemaCache.usesClasses(s.kind);

  const subtypeLabel      = SchemaCache.subtypeLabel(s.kind, s.subtype);
  const subtypeGroupLabel = SchemaCache.subtypeGroupLabel(s.kind);
  const raceDisplay = usesClasses ? (data.race || subtypeLabel) : subtypeLabel;

  // Multiclasse: normalizza eventuali schede vecchie con .class singolo
  const mcState = MulticlassWidget.deserialize(data);
  const totalLevel = MulticlassWidget.totalLevel(mcState);

  let dndRows = '';
  let classesBlock = '';
  if (usesClasses) {
    const background = data.background || '—';
    const sources = Array.isArray(data.sources) && data.sources.length
      ? data.sources.map(v => escapeHtml(DndCache.manualLabel(v))).join(', ')
      : '—';
    // Riepilogo classi: "Guerriero 3 / Mago 2"
    const classesSummary = mcState.classes.length
      ? mcState.classes.map(c => `${escapeHtml(DndCache.classLabel(c.value))} ${c.levels}`).join(' / ')
      : '—';
    const featRow = data.variant_feat
      ? `<dt>Talento razziale</dt> <dd>${escapeHtml(data.variant_feat)}${data.variant_feat_stat ? ` (+1 ${STATS.find(s=>s.key===data.variant_feat_stat)?.short || data.variant_feat_stat.toUpperCase()})` : ''}</dd>`
      : '';
    dndRows = `
      <dt>Livello totale</dt>     <dd>${totalLevel || '—'}</dd>
      <dt>Classi</dt>             <dd>${classesSummary}</dd>
      <dt>Background</dt>         <dd>${escapeHtml(background)}</dd>
      ${featRow}
      <dt>Fonti</dt>              <dd>${sources}</dd>`;

    // Card per ogni classe con sottoclasse + scelte ASI/Talento
    if (mcState.classes.length) {
      classesBlock = `
        <div class="card">
          <h3 class="card-title">Classi</h3>
          ${mcState.classes.map(c => renderClassDetailView(c)).join('')}
        </div>`;
    }
  }

  // Stats
  let statsBlock = '';
  let savesBlock = '';
  let skillsBlock = '';
  let spellsBlock = '';
  if (usesClasses) {
    const stState = StatsWidget.deserialize(data);
    const asiByKey = MulticlassWidget.asiBonuses(mcState);
    statsBlock = `
      <div class="card">
        <h3 class="card-title">Statistiche</h3>
        <div class="stats-grid view">
          ${STATS.map(s => {
            const total = StatsWidget.finalScore(stState, data.race, s.key, asiByKey);
            const racial = StatsWidget.racialBonuses(data.race, stState)[s.key] || 0;
            const asi = asiByKey[s.key] || 0;
            return `
              <div class="stat-cell">
                <div class="stat-head">
                  <span class="stat-short">${s.short}</span>
                  <span class="stat-label">${s.label}</span>
                </div>
                <div class="stat-value">${total}</div>
                <div class="stat-meta">
                  ${racial ? `<span class="stat-bonus">${racial>0?'+':''}${racial} razziale</span>` : ''}
                  ${asi ? `<span class="stat-asi">${asi>0?'+':''}${asi} ASI</span>` : ''}
                  <span class="stat-mod">Mod. ${StatsWidget.fmtMod(StatsWidget.statMod(total))}</span>
                </div>
              </div>`;
          }).join('')}
        </div>
      </div>`;

    const activeSkills = data.skills && typeof data.skills === 'object'
      ? Object.keys(data.skills).filter(k => data.skills[k])
      : [];

    // Tiri Salvezza
    const profBonus = profBonusFromLevel(totalLevel || 1);
    const primaryClass = mcState.classes[0]?.value;
    const classSaveProfs = new Set(DndCache.saveProfs(primaryClass));
    const featSP = MulticlassWidget.featSaveProfs(mcState);
    const savingProfs = new Set([...classSaveProfs, ...featSP]);

    savesBlock = `
      <div class="card">
        <h3 class="card-title">Tiri Salvezza <span class="card-sub">(bonus comp. +${profBonus})</span></h3>
        <div class="ts-grid">
          ${STATS.map(st => {
            const total = StatsWidget.finalScore(stState, data.race, st.key, asiByKey);
            const mod = StatsWidget.statMod(total);
            const prof = savingProfs.has(st.key);
            const val = mod + (prof ? profBonus : 0);
            return `
              <div class="ts-cell${prof ? ' ts-prof' : ''}">
                <div class="ts-short">${st.short}</div>
                <div class="ts-value">${val >= 0 ? '+' : ''}${val}</div>
                <div class="ts-dot">${prof ? '●' : '○'}</div>
              </div>`;
          }).join('')}
        </div>
      </div>`;

    if (activeSkills.length) {
      const rows = DndCache.skills()
        .filter(sk => activeSkills.includes(sk.key))
        .map(sk => {
          const score = StatsWidget.finalScore(stState, data.race, sk.ability, asiByKey);
          const mod = StatsWidget.statMod(score) + profBonus;
          const ab = ({str:'FOR',dex:'DES',con:'COS',int:'INT',wis:'SAG',cha:'CAR'})[sk.ability];
          return `<li><span class="sk-name">${escapeHtml(sk.label)}</span>
                      <span class="sk-ability">${ab}</span>
                      <span class="sk-mod">${StatsWidget.fmtMod(mod)}</span></li>`;
        }).join('');
      skillsBlock = `
        <div class="card">
          <h3 class="card-title">Competenze in abilità <span class="card-sub">(bonus +${profBonus})</span></h3>
          <ul class="skills-list">${rows}</ul>
        </div>`;
    }

    // Incantesimi (view)
    const casters = mcState.classes.filter(c => DndCache.isEffectiveCaster(c.value, c.subclass, c.levels) && c.levels > 0);
    if (casters.length) {
      const slotPool = DndCache.fullCasterSlotsForMulticlass(mcState.classes);
      const pact = DndCache.pactSlotsFor(mcState.classes);
      const slotsHtml = slotPool.map((n, i) => n > 0
        ? `<div class="slot-pill"><span class="slot-lvl">L${i+1}</span><span class="slot-n">${n}</span></div>`
        : '').filter(Boolean).join('');
      const pactHtml = pact && pact.slots > 0
        ? `<div class="pact-block"><div class="pact-title">Pact Magic</div>
             <div class="slot-pill pact"><span class="slot-lvl">L${pact.slot_level}</span><span class="slot-n">${pact.slots}</span></div></div>`
        : '';
      const sp = data.spells || {};
      // Indicizza il catalogo per nome per dare livello/scuola alle chip in vista
      const allSp = DndCache._data?._spells || [];
      const idx = {};
      for (const x of allSp) idx[x.name] = x;
      const fmtChip = (n) => {
        const meta = idx[n];
        const lvl = meta?.level;
        const lvlTag = (lvl === 0) ? 'T' : (lvl ? `L${lvl}` : '');
        return `<span class="spell-view-chip">
          ${lvlTag ? `<span class="lvl-tag">${lvlTag}</span>` : ''}
          <span class="nm">${escapeHtml(n)}</span>
          ${meta?.ritual ? `<span class="rit-tag" title="Rituale">R</span>` : ''}
        </span>`;
      };
      const sortByLevel = (a, b) => {
        const la = idx[a]?.level ?? 99, lb = idx[b]?.level ?? 99;
        if (la !== lb) return la - lb;
        return a.localeCompare(b, 'it');
      };
      const classBlocks = casters.map(c => {
        const def = DndCache.classDef(c.value);
        const entry = sp[c.value] || { cantrips: [], spells: [] };
        const cs = (entry.cantrips || []).slice().sort((a,b) => a.localeCompare(b, 'it'));
        const ss = (entry.spells || []).slice().sort(sortByLevel);
        const cantripsHtml = cs.length
          ? `<div class="spell-view-chips">${cs.map(fmtChip).join('')}</div>`
          : `<div class="field-hint">—</div>`;
        const spellsHtml = ss.length
          ? `<div class="spell-view-chips">${ss.map(fmtChip).join('')}</div>`
          : `<div class="field-hint">—</div>`;
        return `<div class="spell-view-class">
          <h4>${escapeHtml(def?.label || c.value)} <span class="card-sub">L${c.levels} · ${cs.length} truc. · ${ss.length} inc.</span></h4>
          <div class="spell-view-section"><strong>Trucchetti</strong>${cantripsHtml}</div>
          <div class="spell-view-section"><strong>Incantesimi</strong>${spellsHtml}</div>
        </div>`;
      }).join('');
      spellsBlock = `
        <div class="card">
          <h3 class="card-title">Incantesimi</h3>
          ${slotsHtml ? `<div class="slots-grid">${slotsHtml}</div>` : ''}
          ${pactHtml}
          ${classBlocks}
        </div>`;
    }
  }

  // ── Privilegi ───────────────────────────────────────────────────────────
  let featuresBlock = '';
  if (usesClasses) {
    const featureSections = [];

    // Sezione per ogni classe
    for (const cls of mcState.classes) {
      const def = DndCache.classDef(cls.value);
      if (!def) continue;
      const clsLabel = def.label || cls.value;
      const feats = FeaturesCache.classFeatures(cls.value, cls.levels);
      if (feats.length) {
        featureSections.push({
          title: `${escapeHtml(clsLabel)} <span class="feat-lv">livello ${cls.levels}</span>`,
          features: feats,
          icon: '⚔️',
        });
      }

      // Sottoclasse
      if (cls.subclass) {
        const subFeats = FeaturesCache.subclassFeatures(cls.subclass, cls.levels);
        if (subFeats.length) {
          featureSections.push({
            title: `${escapeHtml(cls.subclass)}`,
            subtitle: escapeHtml(def.group_label),
            features: subFeats,
            icon: '✦',
          });
        }
      }
    }

    // Razza
    if (data.race) {
      const raceFeats = FeaturesCache.raceFeatures(data.race);
      if (raceFeats.length) {
        featureSections.push({
          title: escapeHtml(data.race),
          subtitle: 'Razza',
          features: raceFeats,
          icon: '🌿',
          noLevel: true,
        });
      }
    }

    // Background
    if (data.background && data.background !== '—') {
      const bgFeats = FeaturesCache.backgroundFeatures(data.background);
      if (bgFeats.length) {
        featureSections.push({
          title: escapeHtml(data.background),
          subtitle: 'Background',
          features: bgFeats,
          icon: '📜',
          noLevel: true,
        });
      }
    }

    // Talenti (da ASI choices)
    const talentFeats = [];
    for (const cls of mcState.classes) {
      for (const choice of (cls.asi_choices || [])) {
        if (choice?.kind === 'feat' && choice.name) {
          const meta = DndCache.featMeta(choice.name);
          const fullDesc = DndCache.featDesc(choice.name);
          let shortDesc = '';
          if (meta?.save_prof) {
            const st = STATS.find(s => s.key === choice.feat_stat);
            shortDesc = `+1 ${st ? st.short : choice.feat_stat?.toUpperCase() || ''}, competenza Tiro Salvezza ${st ? st.label : ''}.`;
          } else if (meta?.stat_bonus_value) {
            const st = STATS.find(s => s.key === choice.feat_stat);
            shortDesc = `+${meta.stat_bonus_value} ${st ? st.label : choice.feat_stat || ''}.`;
          }
          talentFeats.push({ name: choice.name, desc: fullDesc || shortDesc });
        }
      }
    }
    if (data.variant_feat) {
      talentFeats.push({ name: data.variant_feat, desc: DndCache.featDesc(data.variant_feat) });
    }
    if (talentFeats.length) {
      featureSections.push({
        title: 'Talenti',
        features: talentFeats,
        icon: '⭐',
        noLevel: true,
      });
    }

    if (featureSections.length) {
      featuresBlock = `
        <div class="card" id="features-card">
          <h3 class="card-title">Privilegi</h3>
          <div class="feat-sections">
            ${featureSections.map((sec, si) => `
              <div class="feat-section">
                <div class="feat-section-head">
                  <span class="feat-icon">${sec.icon}</span>
                  <div class="feat-section-label">
                    <span class="feat-section-title">${sec.title}</span>
                    ${sec.subtitle ? `<span class="feat-section-sub">${sec.subtitle}</span>` : ''}
                  </div>
                  <span class="feat-count">${sec.features.length}</span>
                </div>
                <div class="feat-list">
                  ${sec.features.map((f, fi) => `
                    <button class="feat-row" data-section="${si}" data-feat="${fi}" type="button">
                      <span class="feat-name">${escapeHtml(f.name)}</span>
                      ${!sec.noLevel && f.level ? `<span class="feat-lv-badge">Lv ${f.level}</span>` : ''}
                      ${f.desc ? `<span class="feat-has-desc" title="Descrizione disponibile">▸</span>` : ''}
                    </button>
                  `).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        </div>`;

      // Store sections data for click handler (set after innerHTML)
      window.__featSections = featureSections;
    }
  }

  content.innerHTML = `
    <header class="header">
      ${data.token ? `<div class="token-view-wrap"><img class="token-view" src="${data.token}" alt="Token"></div>` : ''}
      <h1>${escapeHtml(s.name)}</h1>
      <p class="tagline">${escapeHtml(kindLabel)} · ${escapeHtml(raceDisplay)}</p>
    </header>

    <div class="card">
      <dl class="kv">
        <dt>Nome</dt>                              <dd>${escapeHtml(s.name)}</dd>
        <dt>${escapeHtml(subtypeGroupLabel)}</dt>  <dd>${escapeHtml(raceDisplay)}</dd>
        ${dndRows}
        <dt>Tipo</dt>                              <dd>${escapeHtml(kindLabel)}</dd>
        <dt>Creata</dt>                            <dd>${fmtDate(s.created_at)}</dd>
        <dt>Aggiornata</dt>                        <dd>${fmtDate(s.updated_at)}</dd>
      </dl>
    </div>

    ${classesBlock}
    ${featuresBlock}
    ${statsBlock}
    ${usesClasses ? savesBlock : ''}
    ${skillsBlock}
    ${spellsBlock}

    <div class="actions between">
      <a href="/" class="btn ghost">← Indietro</a>
      <div class="actions">
        <button id="edit-btn">Modifica</button>
        <button id="delete-btn" class="danger">Elimina</button>
      </div>
    </div>
  `;

  document.getElementById('edit-btn').addEventListener('click', renderEdit);
  document.getElementById('delete-btn').addEventListener('click', onDelete);

  // Click handler per i privilegi
  const featCard = document.getElementById('features-card');
  if (featCard) {
    featCard.addEventListener('click', e => {
      const btn = e.target.closest('.feat-row');
      if (!btn) return;
      const si = +btn.dataset.section;
      const fi = +btn.dataset.feat;
      const sec = window.__featSections?.[si];
      if (!sec) return;
      const feat = sec.features[fi];
      if (!feat) return;
      openFeatModal(feat, sec);
    });
  }
}

function openFeatModal(feat, sec) {
  const existing = document.getElementById('feat-modal-overlay');
  if (existing) existing.remove();

  const levelLine = (!sec.noLevel && feat.level)
    ? `<div class="feat-modal-level">Livello ${feat.level}</div>` : '';
  const secLabel = sec.subtitle
    ? `<div class="feat-modal-source">${escapeHtml(sec.subtitle)}</div>` : '';
  const descHtml = feat.desc
    ? `<p class="feat-modal-desc">${escapeHtml(feat.desc)}</p>`
    : `<p class="feat-modal-desc muted">Descrizione non disponibile nei manuali selezionati.</p>`;

  const overlay = document.createElement('div');
  overlay.id = 'feat-modal-overlay';
  overlay.className = 'feat-modal-overlay';
  // Stili critici inline per garantire il centramento anche con CSS in cache stale
  overlay.style.cssText = `
    position: fixed !important;
    top: 0 !important; right: 0 !important; bottom: 0 !important; left: 0 !important;
    z-index: 9999 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 24px;
    background: rgba(8,6,14,0.78);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
  `;
  overlay.innerHTML = `
    <div class="feat-modal" role="dialog" aria-modal="true" style="max-width:560px;width:100%;max-height:82vh;">
      <div class="feat-modal-head">
        <div>
          ${secLabel}
          <h3 class="feat-modal-name">${escapeHtml(feat.name)}</h3>
          ${levelLine}
        </div>
        <button class="feat-modal-close" aria-label="Chiudi">✕</button>
      </div>
      <div class="feat-modal-body">
        ${descHtml}
      </div>
    </div>`;

  overlay.addEventListener('click', e => {
    if (e.target === overlay || e.target.classList.contains('feat-modal-close')) {
      overlay.remove();
    }
  });
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', esc); }
  });
  document.body.appendChild(overlay);
}

function renderClassDetailView(c) {
  const def = DndCache.classDef(c.value);
  if (!def) return '';
  const subLine = c.subclass
    ? `<span class="cls-sub">${escapeHtml(def.group_label)}: <strong>${escapeHtml(c.subclass)}</strong></span>`
    : (c.levels >= def.subclass_level
        ? `<span class="cls-sub muted">${escapeHtml(def.group_label)} non scelta</span>`
        : `<span class="cls-sub muted">${escapeHtml(def.group_label)} dal livello ${def.subclass_level}</span>`);

  // ASI scelti
  const slots = (def.asi_levels || []).filter(l => l <= c.levels);
  const asiRows = slots.map((lvl, i) => {
    const ch = c.asi_choices?.[i];
    if (!ch) return `<li><strong>Livello ${lvl}:</strong> <span class="muted">non scelto</span></li>`;
    if (ch.kind === 'feat') {
      let featDesc = escapeHtml(ch.name || '?');
      if (ch.feat_stat) {
        const st = STATS.find(s => s.key === ch.feat_stat);
        const statLabel = st ? st.short : ch.feat_stat.toUpperCase();
        const meta = DndCache.featMeta(ch.name);
        if (meta?.save_prof) {
          featDesc += ` <span class="muted">(+1 ${statLabel}, TS ${statLabel})</span>`;
        } else if (meta?.stat_bonus_value) {
          featDesc += ` <span class="muted">(+${meta.stat_bonus_value} ${statLabel})</span>`;
        }
      }
      return `<li><strong>Livello ${lvl}:</strong> Talento — ${featDesc}</li>`;
    }
    if (ch.kind === 'asi') {
      const desc = Object.entries(ch.plus || {})
        .map(([k, v]) => `${({str:'FOR',dex:'DES',con:'COS',int:'INT',wis:'SAG',cha:'CAR'})[k] || k} +${v}`)
        .join(', ') || '—';
      return `<li><strong>Livello ${lvl}:</strong> ASI ${desc}</li>`;
    }
    return '';
  }).join('');

  return `
    <div class="cls-block">
      <div class="cls-head">
        <span class="cls-name">${escapeHtml(def.label)}</span>
        <span class="cls-lv">livello ${c.levels}</span>
      </div>
      <div class="cls-body">
        ${subLine}
        ${slots.length ? `<ul class="cls-asi-list">${asiRows}</ul>` : ''}
      </div>
    </div>`;
}

function renderEdit() {
  const s = sheet;
  const data = s.data || {};
  const usesClasses = SchemaCache.usesClasses(s.kind);

  const ed = {
    background: data.background || '',
    race: data.race || '',
    sources: Array.isArray(data.sources) && data.sources.length
      ? data.sources.slice()
      : (usesClasses && DndCache.manuals()[0] ? [DndCache.manuals()[0].value] : []),
    multiclass: MulticlassWidget.deserialize(data),
    stats: StatsWidget.deserialize(data),
    skills: SkillsWidget.deserialize(data),
    spells: SpellsWidget.normalize(data.spells),
    token: TokenWidget.deserialize(data),
  };

  let dndMarkup = '';
  if (usesClasses) {
    const manualsHtml = DndCache.manuals().map(m => `
      <div class="manual-option" data-manual="${escapeHtml(m.value)}" tabindex="0" role="checkbox" aria-checked="false">
        <span class="check">${CHECK_SVG}</span>
        <span class="m-label">${escapeHtml(m.label)}</span>
      </div>`).join('');
    dndMarkup = `
      <div class="field">
        <label>Manuali da cui attingere</label>
        <div class="manual-grid" id="f-manuals">${manualsHtml}</div>
      </div>
      <div class="field">
        <label for="f-race">Razza</label>
        <select id="f-race"></select>
      </div>
      <div class="field">
        <label>Classi (multiclasse)</label>
        <div id="f-multiclass"></div>
      </div>
      <div class="field">
        <label for="f-background">Background</label>
        <select id="f-background"></select>
      </div>
      <div class="field">
        <label>Statistiche</label>
        <div id="f-stats-widget"></div>
      </div>
      <div class="field">
        <label>Competenze in abilità</label>
        <div id="f-skills-widget"></div>
      </div>
      <div class="field" id="f-spells-field">
        <label>Incantesimi</label>
        <div id="f-spells-widget"></div>
      </div>`;
  }

  content.innerHTML = `
    <header class="header">
      <h1>Modifica scheda</h1>
      <p class="tagline">${escapeHtml(SchemaCache.kindLabel(s.kind))} · ${escapeHtml(SchemaCache.subtypeLabel(s.kind, s.subtype))}</p>
    </header>

    <div class="card">
      <div class="field">
        <label for="f-name">Nome</label>
        <input id="f-name" type="text" maxlength="200" value="${escapeHtml(s.name)}" autocomplete="off">
      </div>
      <div class="field">
        <label>Token personaggio (opzionale)</label>
        <div id="f-token-widget"></div>
      </div>
      ${dndMarkup}
      <div id="edit-error" class="error hidden"></div>
    </div>

    <div class="actions between">
      <button id="cancel-btn" class="ghost">Annulla</button>
      <button id="save-btn">Salva modifiche</button>
    </div>
  `;

  const nameInput  = document.getElementById('f-name');
  const errorBox   = document.getElementById('edit-error');
  const saveBtn    = document.getElementById('save-btn');

  document.getElementById('cancel-btn').addEventListener('click', renderView);

  let manualGrid, backgroundSel, raceSel, mcBox, statsBox, skillsBox, spellsBox, spellsField;

  function syncManualUI() {
    const sel = new Set(ed.sources);
    manualGrid.querySelectorAll('.manual-option').forEach(o => {
      const on = sel.has(o.dataset.manual);
      o.classList.toggle('selected', on);
      o.setAttribute('aria-checked', String(on));
    });
  }

  function refreshRace() {
    const races = DndCache.races(ed.sources);
    if (!races.length) {
      raceSel.innerHTML = `<option value="">— Nessuna nei manuali scelti —</option>`;
      ed.race = '';
      return;
    }
    raceSel.innerHTML =
      `<option value="">— Scegli razza —</option>` +
      races.map(r => `<option value="${escapeHtml(r.name)}">${escapeHtml(r.name)}</option>`).join('');
    if (ed.race && races.some(r => r.name === ed.race)) {
      raceSel.value = ed.race;
    } else {
      ed.race = '';
    }
  }

  function refreshBackground() {
    const bgs = DndCache.backgrounds(ed.sources);
    backgroundSel.innerHTML =
      `<option value="">— Nessuno —</option>` +
      bgs.map(b => `<option value="${escapeHtml(b.name)}">${escapeHtml(b.name)}</option>`).join('');
    if (ed.background && bgs.some(b => b.name === ed.background)) {
      backgroundSel.value = ed.background;
    } else {
      ed.background = '';
    }
  }

  function primaryClass() { return ed.multiclass.classes[0] || null; }

  function computeFinalStatsEdit() {
    const asi = MulticlassWidget.asiBonuses(ed.multiclass);
    const out = {};
    for (const s of STATS) out[s.key] = StatsWidget.finalScore(ed.stats, ed.race, s.key, asi);
    return out;
  }

  function renderMcEdit() {
    MulticlassWidget.render(mcBox, ed.multiclass, {
      sources: ed.sources,
      onChange: (s) => {
        ed.multiclass = s;
        renderStatsEdit();
        renderSkillsEdit();
        renderSpellsEdit();
      },
    });
  }
  function renderStatsEdit() {
    StatsWidget.render(statsBox, ed.stats, {
      raceName: ed.race,
      sources: ed.sources,
      idPrefix: 'sw-edit',
      asiByKey: MulticlassWidget.asiBonuses(ed.multiclass),
      onChange: (s) => { ed.stats = s; renderSpellsEdit(); },
    });
  }
  function renderSkillsEdit() {
    const pri = primaryClass();
    SkillsWidget.render(skillsBox, ed.skills, {
      classDef: pri ? DndCache.classDef(pri.value) : null,
      raceDef:  DndCache.raceDef(ed.race),
      bgDef:    DndCache.backgrounds(ed.sources).find(b => b.name === ed.background) || null,
      onChange: (s) => { ed.skills = s; },
    });
  }
  function renderSpellsEdit() {
    if (!spellsBox || !spellsField) return;
    const casters = (ed.multiclass.classes || []).filter(c => DndCache.isEffectiveCaster(c.value, c.subclass, c.levels) && c.levels > 0);
    if (!casters.length) {
      spellsField.classList.add('hidden');
      return;
    }
    spellsField.classList.remove('hidden');
    SpellsWidget.render(spellsBox, ed.spells, {
      classes: ed.multiclass.classes,
      sources: ed.sources,
      finalStats: computeFinalStatsEdit(),
      onChange: (s) => { ed.spells = s; },
    });
  }

  // Token widget: visibile per tutti i kind
  TokenWidget.render(document.getElementById('f-token-widget'), ed.token, {
    onChange: s => { ed.token = s; },
  });

  if (usesClasses) {
    manualGrid    = document.getElementById('f-manuals');
    backgroundSel = document.getElementById('f-background');
    raceSel       = document.getElementById('f-race');
    mcBox         = document.getElementById('f-multiclass');
    statsBox      = document.getElementById('f-stats-widget');
    skillsBox     = document.getElementById('f-skills-widget');
    spellsBox     = document.getElementById('f-spells-widget');
    spellsField   = document.getElementById('f-spells-field');

    syncManualUI();
    refreshRace();
    refreshBackground();
    renderMcEdit();
    renderStatsEdit();
    renderSkillsEdit();
    renderSpellsEdit();

    const toggleManual = (opt) => {
      if (!opt) return;
      const v = opt.dataset.manual;
      const i = ed.sources.indexOf(v);
      if (i >= 0) ed.sources.splice(i, 1);
      else ed.sources.push(v);
      syncManualUI();
      refreshRace();
      refreshBackground();
      renderMcEdit();
      renderStatsEdit();
      renderSkillsEdit();
      renderSpellsEdit();
    };
    manualGrid.addEventListener('click', e => toggleManual(e.target.closest('.manual-option')));
    manualGrid.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleManual(e.target.closest('.manual-option'));
      }
    });

    backgroundSel.addEventListener('change', () => { ed.background = backgroundSel.value; renderSkillsEdit(); });
    raceSel.addEventListener('change', () => { ed.race = raceSel.value; renderStatsEdit(); renderSkillsEdit(); renderSpellsEdit(); });
  }

  saveBtn.addEventListener('click', async () => {
    errorBox.classList.add('hidden');
    const name = nameInput.value.trim();
    if (!name) {
      errorBox.textContent = 'Il nome è obbligatorio.';
      errorBox.classList.remove('hidden');
      return;
    }

    const newData = { ...(sheet.data || {}) };
    if (usesClasses) {
      // Pulisci campi legacy
      for (const k of ['class','subclass','classes','level','stats','stats_method','racial_bonus_mode',
                       'racial_bonus_flex','variant_bonuses','variant_feat','variant_feat_stat','skills','skill_choices',
                       'stats_roll_pool','stats_roll_assign','spells']) {
        delete newData[k];
      }

      const mcErrs = MulticlassWidget.validate(ed.multiclass);
      if (mcErrs.length) {
        errorBox.textContent = mcErrs[0];
        errorBox.classList.remove('hidden');
        return;
      }
      const statErrs = StatsWidget.validate(ed.stats, ed.race);
      if (statErrs.length) {
        errorBox.textContent = statErrs[0];
        errorBox.classList.remove('hidden');
        return;
      }
      const skillCtx = {
        classDef: primaryClass() ? DndCache.classDef(primaryClass().value) : null,
        raceDef:  DndCache.raceDef(ed.race),
        bgDef:    DndCache.backgrounds(ed.sources).find(b => b.name === ed.background) || null,
      };
      const skillErrs = SkillsWidget.validate(ed.skills, skillCtx);
      if (skillErrs.length) {
        errorBox.textContent = skillErrs[0];
        errorBox.classList.remove('hidden');
        return;
      }
      const spellErrs = SpellsWidget.validate(ed.spells, ed.multiclass.classes);
      if (spellErrs.length) {
        errorBox.textContent = spellErrs[0];
        errorBox.classList.remove('hidden');
        return;
      }

      const mcOut = MulticlassWidget.serialize(ed.multiclass);
      newData.classes = mcOut.classes;
      newData.level = mcOut.level;
      if (ed.race) newData.race = ed.race;
      if (ed.background) newData.background = ed.background;
      if (ed.sources.length) newData.sources = ed.sources.slice();
      Object.assign(newData, StatsWidget.serialize(ed.stats));
      Object.assign(newData, SkillsWidget.serialize(ed.skills, skillCtx));
      const spOut = SpellsWidget.normalize(ed.spells);
      if (Object.keys(spOut).length) newData.spells = spOut;
    }

    // Token: aggiorna o rimuovi indipendentemente dal kind
    delete newData.token;
    delete newData.token_thumb;
    Object.assign(newData, TokenWidget.serialize(ed.token));

    saveBtn.disabled = true;
    try {
      await api.update(id, { name, data: newData });
      const fresh = await api.get(id);
      sheet = fresh;
      UI.toast('Modifiche salvate', 'success');
      renderView();
    } catch (e) {
      errorBox.textContent = e.message;
      errorBox.classList.remove('hidden');
      saveBtn.disabled = false;
    }
  });

  nameInput.focus();
}

async function onDelete() {
  const ok = await UI.confirm({
    title: 'Eliminare la scheda?',
    message: `"${sheet.name}" verrà eliminata definitivamente. Impossibile annullare.`,
    confirmLabel: 'Elimina',
    danger: true,
  });
  if (!ok) return;
  try {
    await api.remove(id);
    UI.toast('Scheda eliminata', 'success');
    setTimeout(() => { window.location.href = '/'; }, 500);
  } catch (e) {
    UI.toast(e.message, 'error');
  }
}
