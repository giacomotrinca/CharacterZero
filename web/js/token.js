// TokenWidget — gestisce l'upload e la preview del token (immagine circolare).
// Ridimensiona qualsiasi immagine a 512×512 (center-crop quadrato, poi scale)
// e genera un thumbnail 64×64 per il summary di lista.
//
// API pubblica:
//   TokenWidget.render(container, state, { onChange })
//   TokenWidget.deserialize(data)  → state
//   TokenWidget.serialize(state)   → { token, token_thumb } oppure {}
//   TokenWidget.defaultState()     → { token: null, thumb: null }

const TokenWidget = (() => {
  const TARGET = 512;
  const THUMB  = 64;

  function defaultState() {
    return { token: null, thumb: null };
  }

  function deserialize(data) {
    if (!data || typeof data !== 'object') return defaultState();
    return {
      token: data.token       || null,
      thumb: data.token_thumb || null,
    };
  }

  function serialize(state) {
    if (!state.token) return {};
    return { token: state.token, token_thumb: state.thumb };
  }

  // Ritaglia il canvas sorgente in un quadrato centrato, poi scala a `size`.
  function processImage(file, size) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(url);
        const sw = img.naturalWidth;
        const sh = img.naturalHeight;
        const side = Math.min(sw, sh);
        const sx = (sw - side) / 2;
        const sy = (sh - side) / 2;
        const canvas = document.createElement('canvas');
        canvas.width  = size;
        canvas.height = size;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, sx, sy, side, side, 0, 0, size, size);
        resolve(canvas.toDataURL('image/jpeg', 0.88));
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Impossibile caricare immagine')); };
      img.src = url;
    });
  }

  function render(container, state, opts = {}) {
    const onChange = opts.onChange || (() => {});
    const hasToken = !!state.token;
    const previewSrc = state.token || '';

    container.innerHTML = `
      <div class="token-widget">
        <div class="token-drop ${hasToken ? 'has-token' : ''}" id="tw-drop" tabindex="0"
             role="button" aria-label="Carica token">
          ${hasToken
            ? `<img class="token-preview" src="${previewSrc}" alt="Token">`
            : `<div class="token-placeholder">
                 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
                   stroke-linecap="round" stroke-linejoin="round">
                   <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                   <circle cx="12" cy="7" r="4"/>
                 </svg>
                 <span>Carica immagine</span>
               </div>`}
        </div>
        ${hasToken
          ? `<button class="btn ghost small" id="tw-remove" type="button">Rimuovi token</button>`
          : `<div class="token-hint">PNG · JPG · WebP — ritagliata a cerchio 512×512</div>`}
        <input type="file" id="tw-file" accept="image/png,image/jpeg,image/webp,image/gif" style="display:none">
      </div>`;

    const dropZone  = container.querySelector('#tw-drop');
    const fileInput = container.querySelector('#tw-file');
    const removeBtn = container.querySelector('#tw-remove');

    const openPicker = () => fileInput.click();
    dropZone.addEventListener('click', openPicker);
    dropZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }});

    // Drag & drop
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer?.files[0];
      if (file) handleFile(file);
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) handleFile(fileInput.files[0]);
    });

    if (removeBtn) {
      removeBtn.addEventListener('click', () => {
        const ns = defaultState();
        onChange(ns);
        render(container, ns, { onChange });
      });
    }

    async function handleFile(file) {
      if (!file.type.startsWith('image/')) {
        UI.toast('Seleziona un file immagine (PNG, JPG, WebP)', 'error');
        return;
      }
      dropZone.classList.add('loading');
      try {
        const [token, thumb] = await Promise.all([
          processImage(file, TARGET),
          processImage(file, THUMB),
        ]);
        const ns = { token, thumb };
        onChange(ns);
        render(container, ns, { onChange });
      } catch (err) {
        UI.toast(err.message, 'error');
        dropZone.classList.remove('loading');
      }
    }
  }

  return { render, deserialize, serialize, defaultState };
})();
