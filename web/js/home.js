const container = document.getElementById('sheets-container');
const countEl   = document.getElementById('count');

async function renderHome() {
  UI.skeleton(container, 3);
  try {
    const [sheets] = await Promise.all([api.list(), SchemaCache.load()]);
    if (sheets.length === 0) {
      countEl.textContent = '';
      container.innerHTML = `
        <div class="empty-state">
          <h3 style="margin:0 0 .4rem;color:var(--ink)">Nessuna scheda</h3>
          <p>Crea la prima scheda per iniziare.</p>
        </div>`;
      return;
    }
    countEl.textContent = `${sheets.length} ${sheets.length === 1 ? 'scheda' : 'schede'}`;
    container.innerHTML = sheets.map(s => `
      <a class="sheet-row" href="/sheet.html?id=${s.id}">
        <div class="avatar ${s.token_thumb ? 'has-token' : ''}">${
          s.token_thumb
            ? `<img src="${s.token_thumb}" alt="Token">`
            : (ICONS[s.kind] || '')
        }</div>
        <div class="meta">
          <div class="name">${escapeHtml(s.name)}</div>
          <div class="sub">${escapeHtml(SchemaCache.kindLabel(s.kind))} · ${escapeHtml(s.race || SchemaCache.subtypeLabel(s.kind, s.subtype))}</div>
        </div>
        <div class="date">${fmtDate(s.updated_at)}</div>
      </a>
    `).join('');
  } catch (e) {
    container.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
  }
}

renderHome();
