const state = {
  kind: null, subtype: null, name: '',
  background: '', race: '', sources: [],
  multiclass: MulticlassWidget.defaultState(),
  stats: StatsWidget.defaultState(),
  skills: SkillsWidget.defaultState(),
  spells: SpellsWidget.defaultState(),
  token: TokenWidget.defaultState(),
};

const kindGrid          = document.getElementById('kind-grid');
const stepSubtype       = document.getElementById('step-subtype');
const stepSources       = document.getElementById('step-sources');
const stepDetails       = document.getElementById('step-details');
const subtypeStepLabel  = document.getElementById('subtype-step-label');
const subtypeFieldLabel = document.getElementById('subtype-field-label');
const subtypeSel        = document.getElementById('subtype');
const manualGrid        = document.getElementById('manual-grid');
const nameInput         = document.getElementById('name');
const multiclassField   = document.getElementById('multiclass-field');
const multiclassBox     = document.getElementById('multiclass-widget');
const backgroundField   = document.getElementById('background-field');
const backgroundSel     = document.getElementById('background');
const raceField         = document.getElementById('race-field');
const raceSel           = document.getElementById('race');
const statsField        = document.getElementById('stats-field');
const statsContainer    = document.getElementById('stats-widget');
const skillsField       = document.getElementById('skills-field');
const skillsContainer   = document.getElementById('skills-widget');
const spellsField       = document.getElementById('spells-field');
const spellsContainer   = document.getElementById('spells-widget');
const tokenContainer    = document.getElementById('token-widget');
const saveBtn           = document.getElementById('save-btn');
const errorBox          = document.getElementById('error');

(async function init() {
  try {
    await Promise.all([SchemaCache.load(), DndCache.load()]);
    await DndCache.loadSpells();
    renderKinds();
    renderManuals();
    TokenWidget.render(tokenContainer, state.token, { onChange: s => { state.token = s; } });
  } catch (e) {
    kindGrid.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
  }
})();

function renderKinds() {
  kindGrid.innerHTML = SchemaCache.kinds().map(k => `
    <div class="choice" data-kind="${escapeHtml(k.value)}" tabindex="0" role="button"
         aria-pressed="false">
      <div class="icon">${ICONS[k.value] || ''}</div>
      <div class="label">${escapeHtml(k.label)}</div>
      <div class="desc">${escapeHtml(k.description || '')}</div>
    </div>
  `).join('');
}

const CHECK_SVG = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"
  stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 6"/></svg>`;

function renderManuals() {
  const manuals = DndCache.manuals();
  manualGrid.innerHTML = manuals.map(m => `
    <div class="manual-option" data-manual="${escapeHtml(m.value)}" tabindex="0" role="checkbox"
         aria-checked="false">
      <span class="check">${CHECK_SVG}</span>
      <span class="m-label">${escapeHtml(m.label)}</span>
    </div>
  `).join('');
  state.sources = manuals.length ? [manuals[0].value] : [];
  syncManualUI();
}

function syncManualUI() {
  const sel = new Set(state.sources);
  manualGrid.querySelectorAll('.manual-option').forEach(o => {
    const on = sel.has(o.dataset.manual);
    o.classList.toggle('selected', on);
    o.setAttribute('aria-checked', String(on));
  });
}

function toggleManual(opt) {
  if (!opt) return;
  const v = opt.dataset.manual;
  const i = state.sources.indexOf(v);
  if (i >= 0) state.sources.splice(i, 1);
  else state.sources.push(v);
  syncManualUI();
  refreshRace();
  refreshBackground();
  renderMulticlass();
  renderStats();
  renderSkills();
  renderSpells();
}

manualGrid.addEventListener('click', e => toggleManual(e.target.closest('.manual-option')));
manualGrid.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    toggleManual(e.target.closest('.manual-option'));
  }
});

function renumberSteps() {
  let n = 0;
  document.querySelectorAll('.wizard-step').forEach(step => {
    if (step.classList.contains('hidden')) return;
    n += 1;
    step.dataset.step = String(n);
  });
}

function primaryClass() {
  return state.multiclass.classes[0] || null;
}

function selectKind(card) {
  if (!card) return;
  state.kind = card.dataset.kind;
  kindGrid.querySelectorAll('.choice').forEach(c => {
    const sel = c === card;
    c.classList.toggle('selected', sel);
    c.setAttribute('aria-pressed', String(sel));
  });

  const usesClasses = SchemaCache.usesClasses(state.kind);

  stepSubtype.classList.toggle('hidden', usesClasses);
  raceField.classList.toggle('hidden', !usesClasses);
  multiclassField.classList.toggle('hidden', !usesClasses);
  backgroundField.classList.toggle('hidden', !usesClasses);
  statsField.classList.toggle('hidden', !usesClasses);
  skillsField.classList.toggle('hidden', !usesClasses);

  if (usesClasses) {
    const subtypes = SchemaCache.kindDef(state.kind)?.subtypes || [];
    state.subtype = subtypes[0]?.value || 'human';
  } else {
    const groupLabel = SchemaCache.subtypeGroupLabel(state.kind);
    subtypeStepLabel.textContent = groupLabel;
    subtypeFieldLabel.textContent = `Scegli ${groupLabel.toLowerCase()}`;
    const subtypes = SchemaCache.kindDef(state.kind)?.subtypes || [];
    subtypeSel.innerHTML = subtypes.map(o =>
      `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`
    ).join('');
    state.subtype = subtypes[0]?.value || null;
  }
  stepSources.classList.toggle('hidden', !usesClasses);

  if (usesClasses) {
    // default: 1 livello in Guerriero per partire (utente cambia subito)
    if (state.multiclass.classes.length === 0) {
      const firstClass = DndCache.classes()[0]?.value;
      if (firstClass) state.multiclass.classes.push({ value: firstClass, levels: 1, subclass: '', asi_choices: [] });
    }
    refreshRace();
    refreshBackground();
    renderMulticlass();
    renderStats();
    renderSkills();
    renderSpells();
  } else {
    state.multiclass = MulticlassWidget.defaultState();
    state.background = '';
    state.race = '';
  }

  stepSubtype.classList.remove('locked');
  stepSources.classList.remove('locked');
  stepDetails.classList.remove('locked');
  renumberSteps();
  updateSaveBtn();
}

function renderMulticlass() {
  if (!SchemaCache.usesClasses(state.kind)) return;
  MulticlassWidget.render(multiclassBox, state.multiclass, {
    sources: state.sources,
    onChange: (s) => {
      state.multiclass = s;
      renderStats();
      renderSkills();
      renderSpells();
      updateSaveBtn();
    },
  });
}

function renderStats() {
  if (!SchemaCache.usesClasses(state.kind)) return;
  StatsWidget.render(statsContainer, state.stats, {
    raceName: state.race,
    sources: state.sources,
    idPrefix: 'sw-new',
    asiByKey: MulticlassWidget.asiBonuses(state.multiclass),
    onChange: (s) => { state.stats = s; renderSpells(); updateSaveBtn(); },
  });
  updateSaveBtn();
}

function renderSkills() {
  if (!SchemaCache.usesClasses(state.kind)) return;
  const pri = primaryClass();
  SkillsWidget.render(skillsContainer, state.skills, {
    classDef: pri ? DndCache.classDef(pri.value) : null,
    raceDef:  DndCache.raceDef(state.race),
    bgDef:    DndCache.backgrounds(state.sources).find(b => b.name === state.background) || null,
    onChange: (s) => { state.skills = s; updateSaveBtn(); },
  });
  updateSaveBtn();
}

function computeFinalStats() {
  const asi = MulticlassWidget.asiBonuses(state.multiclass);
  const out = {};
  for (const s of STATS) {
    out[s.key] = StatsWidget.finalScore(state.stats, state.race, s.key, asi);
  }
  return out;
}

function renderSpells() {
  if (!SchemaCache.usesClasses(state.kind)) {
    spellsField.classList.add('hidden');
    return;
  }
  const casters = (state.multiclass.classes || []).filter(c => DndCache.isEffectiveCaster(c.value, c.subclass, c.levels) && c.levels > 0);
  if (!casters.length) {
    spellsField.classList.add('hidden');
    return;
  }
  spellsField.classList.remove('hidden');
  SpellsWidget.render(spellsContainer, state.spells, {
    classes: state.multiclass.classes,
    sources: state.sources,
    finalStats: computeFinalStats(),
    onChange: (s) => { state.spells = s; updateSaveBtn(); },
  });
}

function refreshRace() {
  if (!SchemaCache.usesClasses(state.kind)) return;
  const races = DndCache.races(state.sources);
  if (!races.length) {
    raceSel.innerHTML = `<option value="">— Nessuna nei manuali scelti —</option>`;
    state.race = '';
    return;
  }
  raceSel.innerHTML =
    `<option value="">— Scegli razza —</option>` +
    races.map(r => `<option value="${escapeHtml(r.name)}">${escapeHtml(r.name)}</option>`).join('');
  if (state.race && races.some(r => r.name === state.race)) {
    raceSel.value = state.race;
  } else {
    state.race = '';
  }
}

function refreshBackground() {
  if (!SchemaCache.usesClasses(state.kind)) return;
  const bgs = DndCache.backgrounds(state.sources);
  backgroundSel.innerHTML =
    `<option value="">— Nessuno —</option>` +
    bgs.map(b => `<option value="${escapeHtml(b.name)}">${escapeHtml(b.name)}</option>`).join('');
  if (state.background && bgs.some(b => b.name === state.background)) {
    backgroundSel.value = state.background;
  } else {
    state.background = '';
  }
}

kindGrid.addEventListener('click', e => selectKind(e.target.closest('.choice')));
kindGrid.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    selectKind(e.target.closest('.choice'));
  }
});

subtypeSel.addEventListener('change', () => {
  state.subtype = subtypeSel.value;
  updateSaveBtn();
});

backgroundSel.addEventListener('change', () => { state.background = backgroundSel.value; renderSkills(); });
raceSel.addEventListener('change', () => { state.race = raceSel.value; renderStats(); renderSkills(); renderSpells(); updateSaveBtn(); });

nameInput.addEventListener('input', () => {
  state.name = nameInput.value.trim();
  updateSaveBtn();
});

function updateSaveBtn() {
  const raceOk  = !SchemaCache.usesClasses(state.kind) || !!state.race;
  let statsOk = true, skillsOk = true, mcOk = true, spellsOk = true;
  if (SchemaCache.usesClasses(state.kind)) {
    mcOk = MulticlassWidget.validate(state.multiclass).length === 0;
    statsOk = StatsWidget.validate(state.stats, state.race).length === 0;
    const pri = primaryClass();
    skillsOk = SkillsWidget.validate(state.skills, {
      classDef: pri ? DndCache.classDef(pri.value) : null,
      raceDef:  DndCache.raceDef(state.race),
      bgDef:    DndCache.backgrounds(state.sources).find(b => b.name === state.background) || null,
    }).length === 0;
    spellsOk = SpellsWidget.validate(state.spells, state.multiclass.classes).length === 0;
  }
  saveBtn.disabled = !(state.kind && state.subtype && state.name && raceOk && mcOk && statsOk && skillsOk && spellsOk);
}

saveBtn.addEventListener('click', async () => {
  errorBox.classList.add('hidden');
  saveBtn.disabled = true;
  try {
    const data = {};
    if (SchemaCache.usesClasses(state.kind)) {
      const mcOut = MulticlassWidget.serialize(state.multiclass);
      data.classes = mcOut.classes;
      data.level = mcOut.level;
      if (state.race) data.race = state.race;
      if (state.background) data.background = state.background;
      if (state.sources.length) data.sources = state.sources.slice();
      Object.assign(data, StatsWidget.serialize(state.stats));
      const pri = primaryClass();
      Object.assign(data, SkillsWidget.serialize(state.skills, {
        classDef: pri ? DndCache.classDef(pri.value) : null,
        raceDef:  DndCache.raceDef(state.race),
        bgDef:    DndCache.backgrounds(state.sources).find(b => b.name === state.background) || null,
      }));
      const spellsState = SpellsWidget.normalize(state.spells);
      if (Object.keys(spellsState).length) data.spells = spellsState;
    } else {
      data.level = 1;
    }
    Object.assign(data, TokenWidget.serialize(state.token));
    const { id } = await api.create({
      kind: state.kind,
      subtype: state.subtype,
      name: state.name,
      data,
    });
    UI.toast('Scheda creata', 'success');
    window.location.href = `/sheet.html?id=${id}`;
  } catch (e) {
    errorBox.textContent = e.message;
    errorBox.classList.remove('hidden');
    saveBtn.disabled = false;
  }
});
