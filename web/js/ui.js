const UI = {
  toast(message, kind = 'info', timeout = 3200) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
      el.style.transition = 'opacity 200ms ease';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 220);
    }, timeout);
  },

  confirm({ title, message, confirmLabel = 'Conferma', cancelLabel = 'Annulla', danger = false }) {
    return new Promise(resolve => {
      const backdrop = document.createElement('div');
      backdrop.className = 'modal-backdrop';
      backdrop.innerHTML = `
        <div class="modal" role="dialog" aria-modal="true">
          <h3>${escapeHtml(title)}</h3>
          <p>${escapeHtml(message)}</p>
          <div class="modal-actions">
            <button class="ghost" data-act="cancel">${escapeHtml(cancelLabel)}</button>
            <button class="${danger ? 'danger' : ''}" data-act="ok">${escapeHtml(confirmLabel)}</button>
          </div>
        </div>`;
      const close = (result) => {
        document.removeEventListener('keydown', onKey);
        backdrop.remove();
        resolve(result);
      };
      const onKey = (e) => {
        if (e.key === 'Escape') close(false);
        if (e.key === 'Enter')  close(true);
      };
      backdrop.addEventListener('click', e => {
        if (e.target === backdrop) close(false);
        const act = e.target.closest('[data-act]')?.dataset.act;
        if (act === 'ok')     close(true);
        if (act === 'cancel') close(false);
      });
      document.addEventListener('keydown', onKey);
      document.body.appendChild(backdrop);
      backdrop.querySelector('[data-act="ok"]').focus();
    });
  },

  skeleton(container, rows = 3) {
    container.innerHTML = `<div class="skeleton">${
      Array.from({ length: rows }, () => '<div class="skeleton-row"></div>').join('')
    }</div>`;
  },

  // Evita "scroll jump" quando un widget ricostruisce il proprio DOM via innerHTML.
  // Uso: UI.preserveScroll(() => { container.innerHTML = ...; ... });
  // Salva e ripristina la posizione di scroll della window — abbastanza per tutti i nostri
  // widget che vivono in pagine a singolo scroll.
  preserveScroll(fn) {
    const x = window.scrollX;
    const y = window.scrollY;
    try {
      fn();
    } finally {
      // due RAF: dopo il reflow, poi dopo che il browser ha eventualmente "auto-scrollato"
      // verso l'elemento focusato. behavior:'instant' evita transizioni.
      window.scrollTo({ top: y, left: x, behavior: 'instant' });
      requestAnimationFrame(() => {
        window.scrollTo({ top: y, left: x, behavior: 'instant' });
      });
    }
  },
};
