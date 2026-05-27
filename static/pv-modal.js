/**
 * PV Service modal — invocat din desktop si mobile.
 * Foloseste paleta PIF + Lucide icons (definite global).
 *
 * Expune: window.openPvServiceModal(projectId)
 */
(function () {
  if (window.__pvModalInjected) return;
  window.__pvModalInjected = true;

  const LEGEND = [
    ['TD', 'Timp deplasare'],
    ['TP', 'Timp procesare'],
    ['TDI', 'Timp deplasare intoarcere'],
    ['TPP', 'Timp postprocesare'],
    ['OLS', 'Ore lucrate service'],
    ['TA', 'Timp asteptare'],
    ['CZA', 'Cazare'],
  ];

  const css = `
    .pv-modal-overlay {
      position: fixed; inset: 0; z-index: 1000;
      background: rgba(0,0,0,0.55);
      backdrop-filter: blur(6px);
      display: none; padding: 24px;
    }
    .pv-modal-overlay.active { display: grid; place-items: center; overflow: hidden; }
    body.pv-modal-open { overflow: hidden !important; }
    .pv-body { overscroll-behavior: contain; }
    .pv-images-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .pv-img-card { display: flex; gap: 10px; padding: 10px;
      background: var(--bg-elev2); border: 1px solid var(--line);
      border-radius: 10px; align-items: flex-start; }
    .pv-img-card .thumb { width: 86px; height: 86px; border-radius: 8px;
      object-fit: cover; flex-shrink: 0; background: var(--bg-elev3); }
    .pv-img-card .meta { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
    .pv-img-card .meta input,
    .pv-img-card .meta select { width: 100%; background: var(--bg-elev1);
      border: 1px solid var(--line); color: var(--text);
      border-radius: 6px; padding: 6px 8px; font-size: 12px; font-family: inherit; }
    .pv-img-card .meta input:focus, .pv-img-card .meta select:focus {
      outline: none; border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-ring); }
    .pv-img-card .filename { font-size: 10.5px; color: var(--text-dim);
      font-family: 'JetBrains Mono', monospace; text-overflow: ellipsis;
      overflow: hidden; white-space: nowrap; }
    .pv-img-card .del-img { width: 30px; height: 30px; flex-shrink: 0;
      border: 1px solid var(--line); background: transparent;
      color: var(--text-mut); border-radius: 6px; cursor: pointer;
      display: grid; place-items: center; }
    .pv-img-card .del-img:hover { color: var(--danger);
      border-color: var(--danger); background: var(--danger-soft); }
    .pv-img-card .del-img [data-lucide] { width: 14px; height: 14px; }
    .pv-width-toggle { display: flex; gap: 0; border: 1px solid var(--line);
      border-radius: 6px; overflow: hidden; width: fit-content; }
    .pv-width-toggle button { border: 0; background: var(--bg-elev1);
      color: var(--text-mut); font-size: 10.5px; font-weight: 600;
      padding: 4px 9px; cursor: pointer; font-family: inherit; }
    .pv-width-toggle button.on { background: var(--accent); color: #0a1311; }
    .pv-pif-overlay .pv-width-toggle button.on { background: var(--violet, #8b87ff); color: #0a0a1d; }
    @media (max-width: 720px) { .pv-images-list { grid-template-columns: 1fr; } }
    .pv-modal {
      width: 100%; max-width: 920px; max-height: calc(100vh - 48px);
      background: var(--bg-elev1, #11161e);
      border: 1px solid var(--line, #232b38);
      border-radius: 18px;
      box-shadow: 0 12px 36px rgba(0,0,0,.45);
      display: flex; flex-direction: column; overflow: hidden;
      color: var(--text, #e8edf5);
    }
    .pv-mh { display: flex; align-items: center; gap: 14px; padding: 18px 22px;
             border-bottom: 1px solid var(--line-soft, #1a212c);
             background: var(--bg-elev2, #161c26); }
    .pv-mh-ico { width: 38px; height: 38px; border-radius: 10px;
                 background: var(--accent-soft, rgba(88,209,201,0.10));
                 color: var(--accent, #58d1c9);
                 display: grid; place-items: center; }
    .pv-mh-ico [data-lucide] { width: 18px; height: 18px; }
    .pv-mh-title { font-size: 16px; font-weight: 700; letter-spacing: -0.01em; }
    .pv-mh-sub { font-size: 12px; color: var(--text-mut, #8590a0); margin-top: 2px; }
    .pv-mh-close { margin-left: auto; width: 32px; height: 32px; border-radius: 8px;
                   border: 1px solid var(--line); background: transparent; color: var(--text-mut);
                   cursor: pointer; display: grid; place-items: center; transition: all .15s;
                   font-family: inherit; }
    .pv-mh-close:hover { color: var(--text); background: var(--bg-elev3, #1d2530); }

    .pv-body { flex: 1; overflow-y: auto; padding: 18px 22px 8px; }

    .pv-preview { display: flex; align-items: center; gap: 12px;
                  padding: 12px 14px;
                  background: linear-gradient(90deg, var(--accent-soft), transparent 70%);
                  border: 1px solid var(--accent-ring, rgba(88,209,201,0.25));
                  border-radius: 10px; margin-bottom: 18px; }
    .pv-preview [data-lucide] { width: 18px; height: 18px; color: var(--accent); }
    .pv-preview .pv-l { font-size: 10.5px; text-transform: uppercase; letter-spacing: .1em;
                        color: var(--accent); font-weight: 600; }
    .pv-preview .pv-v { font-family: 'JetBrains Mono', monospace; font-size: 15px;
                        font-weight: 500; color: var(--text); margin-top: 2px; }
    .pv-preview .pv-v b { color: var(--accent); font-weight: 500; }

    .pv-sec { margin-bottom: 22px; }
    .pv-sec-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    .pv-sec-title { font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
                    color: var(--text-mut); font-weight: 700; }
    .pv-sec-hint { font-size: 11.5px; color: var(--text-dim, #5a6473);
                   margin-left: auto; display: inline-flex; align-items: center; gap: 4px; }
    .pv-sec-hint [data-lucide] { width: 12px; height: 12px; }

    .pv-auto { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 14px;
               padding: 14px; background: var(--bg-elev2);
               border: 1px dashed var(--line); border-radius: 10px; }
    .pv-auto .row { display: flex; gap: 6px; align-items: baseline; font-size: 13px; }
    .pv-auto .row.full { grid-column: 1 / -1; }
    .pv-auto .k { font-size: 11px; color: var(--text-mut); font-weight: 600;
                  text-transform: uppercase; letter-spacing: .05em; flex-shrink: 0; min-width: 110px; }
    .pv-auto .v { color: var(--text); }
    .pv-auto .v.muted { color: var(--text-mut); font-style: italic; }
    .pv-auto .v.code { font-family: 'JetBrains Mono', monospace; font-size: 12.5px; }
    .pv-auto select.echi-pick { flex: 1; max-width: 560px;
                                background: var(--bg-elev1); border: 1px solid var(--line);
                                color: var(--text); border-radius: 6px; padding: 6px 8px;
                                font-size: 12.5px; font-family: 'JetBrains Mono', monospace; }

    .pv-form { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
    .pv-form .full { grid-column: 1 / -1; }
    .pv-fld { display: flex; flex-direction: column; gap: 6px; }
    .pv-fld label { font-size: 12px; color: var(--text-mut); font-weight: 600;
                    display: flex; align-items: center; gap: 4px; }
    .pv-fld .opt { font-size: 10px; color: var(--text-dim); font-weight: 500;
                   text-transform: lowercase; letter-spacing: .02em; }
    .pv-fld input, .pv-fld textarea, .pv-fld select {
      background: var(--bg-elev2); border: 1px solid var(--line);
      color: var(--text); border-radius: 8px; padding: 9px 12px;
      font-size: 13.5px; font-family: inherit; transition: border-color .15s, background .15s;
    }
    .pv-fld input.mono, .pv-fld input[type="text"].mono { font-family: 'JetBrains Mono', monospace; }
    .pv-fld input:focus, .pv-fld textarea:focus, .pv-fld select:focus {
      outline: none; border-color: var(--accent); background: var(--bg-elev3);
      box-shadow: 0 0 0 3px var(--accent-ring);
    }
    .pv-fld input::placeholder, .pv-fld textarea::placeholder { color: var(--text-dim); }
    .pv-fld textarea { resize: vertical; min-height: 60px; }
    .pv-fld .help { font-size: 11px; color: var(--text-dim); }

    .pv-hours { background: var(--bg-elev2); border: 1px solid var(--line);
                border-radius: 10px; overflow: hidden; }
    .pv-hours table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
    .pv-hours th { text-align: left; font-size: 10.5px;
                   text-transform: uppercase; letter-spacing: .06em;
                   color: var(--text-mut); font-weight: 600;
                   padding: 10px 8px; background: var(--bg-elev3);
                   border-bottom: 1px solid var(--line); }
    .pv-hours td { padding: 6px; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
    .pv-hours tr:last-child td { border-bottom: 0; }
    .pv-hours .ci, .pv-hours .cs {
      width: 100%; background: var(--bg-elev1); border: 1px solid var(--line);
      color: var(--text); border-radius: 6px; padding: 6px 8px;
      font-size: 12.5px; font-family: inherit;
    }
    .pv-hours .ci.mono, .pv-hours input[type="number"] { font-family: 'JetBrains Mono', monospace; }
    .pv-hours .ci:focus, .pv-hours .cs:focus { outline: none; border-color: var(--accent);
                                                box-shadow: 0 0 0 2px var(--accent-ring); }
    .pv-hours .del {
      width: 28px; height: 28px; border-radius: 6px;
      border: 1px solid var(--line); background: transparent; color: var(--text-mut);
      cursor: pointer; display: grid; place-items: center; transition: all .15s;
    }
    .pv-hours .del:hover { color: var(--danger, #f97066); border-color: var(--danger);
                           background: var(--danger-soft, rgba(249,112,102,0.12)); }
    .pv-hours .del [data-lucide] { width: 13px; height: 13px; }

    .pv-hours-foot { display: flex; align-items: center; gap: 10px; padding: 10px;
                     background: var(--bg-elev2); border-top: 1px solid var(--line-soft); }
    .pv-add { display: inline-flex; align-items: center; gap: 6px;
              padding: 7px 12px; background: var(--accent-soft); color: var(--accent);
              border: 1px solid var(--accent-ring); border-radius: 7px;
              font-size: 12px; font-weight: 600; cursor: pointer; transition: all .15s;
              font-family: inherit; }
    .pv-add:hover { background: var(--accent); color: #0a1311; border-color: var(--accent); }
    .pv-add [data-lucide] { width: 13px; height: 13px; }
    .pv-sum { margin-left: auto; display: inline-flex; gap: 14px;
              font-size: 11.5px; color: var(--text-mut); }
    .pv-sum b { color: var(--text); font-family: 'JetBrains Mono', monospace; font-weight: 600; }

    .pv-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .pv-legend .tag { font-size: 10.5px; color: var(--text-mut);
                      padding: 3px 8px; border: 1px solid var(--line);
                      border-radius: 999px; background: var(--bg-elev2); }
    .pv-legend .tag b { color: var(--accent); font-weight: 700;
                        font-family: 'JetBrains Mono', monospace; margin-right: 4px; }

    .pv-foot { display: flex; align-items: center; gap: 10px; padding: 14px 22px;
               border-top: 1px solid var(--line-soft); background: var(--bg-elev2); }
    .pv-foot .meta { font-size: 11.5px; color: var(--text-mut);
                     display: inline-flex; align-items: center; gap: 6px; }
    .pv-foot .meta [data-lucide] { width: 13px; height: 13px; }
    .pv-foot .acts { margin-left: auto; display: flex; gap: 8px; }
    .pv-btn { height: 36px; padding: 0 16px; border-radius: 8px;
              font-weight: 600; font-size: 13px; cursor: pointer;
              display: inline-flex; align-items: center; gap: 7px;
              font-family: inherit; transition: all .15s; }
    .pv-btn-secondary { background: transparent; color: var(--text-mut);
                        border: 1px solid var(--line); }
    .pv-btn-secondary:hover { color: var(--text); background: var(--bg-elev3); }
    .pv-btn-primary { background: var(--accent); color: #0a1311; border: 1px solid var(--accent); }
    .pv-btn-primary:hover { background: #6ddbd3; }
    .pv-btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .pv-btn [data-lucide] { width: 14px; height: 14px; }

    @media (max-width: 720px) {
      .pv-modal-overlay { padding: 0; }
      .pv-modal { max-width: 100%; max-height: 100vh; border-radius: 0; height: 100vh; }
      .pv-auto { grid-template-columns: 1fr; }
      .pv-form { grid-template-columns: 1fr; }
      .pv-hours table { font-size: 11.5px; }
      .pv-hours th, .pv-hours td { padding: 4px; }
    }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  const overlay = document.createElement('div');
  overlay.className = 'pv-modal-overlay';
  overlay.id = 'pv-service-modal';
  overlay.innerHTML = `
    <div class="pv-modal" role="dialog" aria-modal="true">
      <div class="pv-mh">
        <div class="pv-mh-ico"><i data-lucide="file-text"></i></div>
        <div>
          <div class="pv-mh-title">Generează Proces Verbal de Service</div>
          <div class="pv-mh-sub">Output DOCX — header / footer / formatare păstrate</div>
        </div>
        <button class="pv-mh-close" data-pv-close title="Închide"><i data-lucide="x"></i></button>
      </div>

      <div class="pv-body">
        <div class="pv-preview">
          <i data-lucide="hash"></i>
          <div>
            <div class="pv-l">Număr proces verbal</div>
            <div class="pv-v" id="pv-nr-preview">Nr. 1 / <b>...</b> / <b>...</b></div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Date din proiect (auto)</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>Editabile în proiect, nu aici</span>
          </div>
          <div class="pv-auto" id="pv-auto">
            <div class="row"><span class="k">Client</span><span class="v" id="pv-a-client">—</span></div>
            <div class="row"><span class="k">Locație</span><span class="v" id="pv-a-locatie">—</span></div>
            <div class="row full"><span class="k">Echipament</span>
              <select class="echi-pick" id="pv-echipament"></select>
            </div>
            <div class="row"><span class="k">Serie</span><span class="v code" id="pv-a-serie">—</span></div>
            <div class="row"><span class="k">Garanție</span><span class="v">Nu</span></div>
            <div class="row full"><span class="k">Motivul intervenției</span><span class="v" id="pv-a-motiv">—</span></div>
            <div class="row full"><span class="k">Acțiuni efectuate</span><span class="v" id="pv-a-actiuni">—</span></div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Detalii proces verbal</div>
          </div>
          <div class="pv-form">
            <div class="pv-fld">
              <label>Cod proiect <span class="opt">ex. C26_102</span></label>
              <input type="text" id="pv-cod" class="mono" placeholder="C26_xxx">
            </div>
            <div class="pv-fld">
              <label>Data proces verbal</label>
              <input type="text" id="pv-data" class="mono" placeholder="DD.MM.YYYY">
            </div>
            <div class="pv-fld full">
              <label>Denumire scurtă comandă <span class="opt">— apare lângă codul de comandă</span></label>
              <input type="text" id="pv-denumire" placeholder="Ex: Diagnoză și verificare întrerupător SENTRON 3WL">
            </div>
            <div class="pv-fld full">
              <label>Observații <span class="opt">optional</span></label>
              <textarea id="pv-observatii" placeholder="Ex: Nu sunt."></textarea>
            </div>
            <div class="pv-fld full">
              <label>Notă de facturare <span class="opt">optional — dacă gol, nu apare în PV</span></label>
              <textarea id="pv-nota-fact" placeholder="Ex: Intervenția se va factura conform ofertei OF_..."></textarea>
            </div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Tabel ore lucrate</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>Adaugă / șterge rânduri</span>
          </div>
          <div class="pv-hours">
            <table>
              <thead>
                <tr>
                  <th style="width:110px">Tip activitate</th>
                  <th style="width:90px">Data</th>
                  <th style="width:140px">Durata (de la – la)</th>
                  <th style="width:60px">Nr. ing.</th>
                  <th style="width:70px">Ore Normal</th>
                  <th style="width:70px">Ore Supl.</th>
                  <th>Observații</th>
                  <th style="width:34px"></th>
                </tr>
              </thead>
              <tbody id="pv-rows"></tbody>
            </table>
            <div class="pv-hours-foot">
              <button class="pv-add" id="pv-add-row"><i data-lucide="plus"></i>Adaugă rând</button>
              <div class="pv-sum">
                <span>Total normal: <b id="pv-sum-normal">0h</b></span>
                <span>Total supl.: <b id="pv-sum-supl">0h</b></span>
                <span>Luna PV: <b id="pv-sum-luna">—</b></span>
              </div>
            </div>
          </div>
          <div class="pv-legend">
            ${LEGEND.map(([k,v]) => `<span class="tag"><b>${k}</b>${v}</span>`).join('')}
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Ingineri (max. 3)</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>Numele apar în tabelul de ingineri din PV</span>
          </div>
          <div class="pv-form" id="pv-ingineri-rows"></div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Anexe foto</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>2 poze pe rând, caption opțional</span>
          </div>
          <input type="file" id="pv-img-input" accept="image/*" multiple style="display:none;">
          <button type="button" class="pv-add" id="pv-add-images" style="margin-bottom:10px;">
            <i data-lucide="image-plus"></i>Adaugă poze
          </button>
          <div id="pv-images-list" class="pv-images-list"></div>
        </div>
      </div>

      <div class="pv-foot">
        <div class="meta"><i data-lucide="shield-check"></i>Header, footer și formatarea template-ului se păstrează</div>
        <div class="acts">
          <button class="pv-btn pv-btn-secondary" data-pv-close><i data-lucide="x"></i>Anulează</button>
          <button class="pv-btn pv-btn-primary" id="pv-generate"><i data-lucide="download"></i>Generează DOCX</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  // Helpers
  function $(sel) { return overlay.querySelector(sel); }
  function rerenderIcons() { if (window.lucide) lucide.createIcons(); }

  function rowHtml(i, defaults) {
    const d = defaults || {};
    const sel = (val) => LEGEND.map(([k]) => `<option value="${k}" ${val===k?'selected':''}>${k}</option>`).join('');
    return `
      <tr data-row="${i}">
        <td><select class="cs">${sel(d.tip || 'TD')}</select></td>
        <td><input class="ci mono" data-f="data" value="${d.data || ''}" placeholder="DD.MM"></td>
        <td><input class="ci mono" data-f="durata" value="${d.durata || ''}" placeholder="HH:MM - HH:MM"></td>
        <td><input class="ci" type="number" data-f="nr_ingineri" min="1" value="${d.nr_ingineri || 1}"></td>
        <td><input class="ci" type="number" data-f="ore_normal" min="0" step="0.5" value="${d.ore_normal || ''}"></td>
        <td><input class="ci" type="number" data-f="ore_supl" min="0" step="0.5" value="${d.ore_supl || ''}"></td>
        <td><input class="ci" data-f="observatii" value="${d.observatii || ''}"></td>
        <td><button class="del" data-del title="Șterge rând"><i data-lucide="trash-2"></i></button></td>
      </tr>
    `;
  }

  let rowSeq = 0;
  function addRow(defaults) {
    rowSeq += 1;
    const tbody = $('#pv-rows');
    tbody.insertAdjacentHTML('beforeend', rowHtml(rowSeq, defaults));
    rerenderIcons();
    bindRowEvents();
    updateSummary();
  }

  function bindRowEvents() {
    overlay.querySelectorAll('[data-del]').forEach(b => {
      b.onclick = () => {
        b.closest('tr').remove();
        updateSummary();
      };
    });
    overlay.querySelectorAll('#pv-rows input').forEach(el => {
      el.oninput = updateSummary;
    });
  }

  function collectRows() {
    const rows = [];
    overlay.querySelectorAll('#pv-rows tr').forEach(tr => {
      const get = (f) => tr.querySelector(`[data-f="${f}"]`)?.value || '';
      const tip = tr.querySelector('select')?.value || 'TD';
      rows.push({
        tip,
        data: get('data'),
        durata: get('durata'),
        nr_ingineri: parseInt(get('nr_ingineri') || '1', 10),
        ore_normal: get('ore_normal'),
        ore_supl: get('ore_supl'),
        observatii: get('observatii'),
      });
    });
    return rows;
  }

  function updateSummary() {
    const rows = collectRows();
    const n = rows.reduce((s, r) => s + (parseFloat(r.ore_normal) || 0), 0);
    const s = rows.reduce((s, r) => s + (parseFloat(r.ore_supl) || 0), 0);
    $('#pv-sum-normal').textContent = `${n}h`;
    $('#pv-sum-supl').textContent = `${s}h`;
    let luna = '—';
    for (const r of rows) {
      const m = (r.data || '').match(/(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?/);
      if (m) {
        const mm = m[2].padStart(2, '0');
        const yy = m[3] || new Date().getFullYear().toString();
        luna = `${mm}.${yy.length === 2 ? '20' + yy : yy}`;
        break;
      }
    }
    $('#pv-sum-luna').textContent = luna;
    updateNrPreview();
  }

  function updateNrPreview() {
    const cod = ($('#pv-cod').value || '...').trim() || '...';
    const data = ($('#pv-data').value || '...').trim() || '...';
    $('#pv-nr-preview').innerHTML = `Nr. 1 / <b>${escapeHtml(cod)}</b> / <b>${escapeHtml(data)}</b>`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function todayDDMMYYYY() {
    const d = new Date();
    return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
  }

  function trim(s, n) {
    s = (s || '').trim();
    return s.length > n ? s.slice(0, n) + '…' : s;
  }

  function close() {
    overlay.classList.remove('active');
    document.body.classList.remove('pv-modal-open');
  }

  // Ingineri: array de inputs, 1..3
  function renderIngineri(values) {
    const tbody = $('#pv-ingineri-rows');
    tbody.innerHTML = '';
    const list = (values && values.length) ? values : ['Ion Ursu'];
    list.slice(0, 3).forEach((nume, idx) => addInginerRow(nume, idx === 0));
    updateInginerAddButton();
  }
  function addInginerRow(value, isFirst) {
    const tbody = $('#pv-ingineri-rows');
    const wrap = document.createElement('div');
    wrap.className = 'pv-fld';
    wrap.innerHTML = `
      <label>Inginer ${tbody.children.length + 1}${isFirst ? ' <span class="opt">primary</span>' : ''}</label>
      <div style="display:flex;gap:6px;">
        <input type="text" class="pv-inginer-input" value="${escapeHtml(value || '')}" placeholder="Nume Prenume" style="flex:1;">
        <button type="button" class="pv-inginer-del" title="Sterge"
                style="width:32px;border:1px solid var(--line);background:transparent;color:var(--text-mut);border-radius:8px;cursor:pointer;display:grid;place-items:center;">
          <i data-lucide="trash-2" style="width:14px;height:14px;"></i>
        </button>
      </div>
    `;
    wrap.querySelector('.pv-inginer-del').onclick = () => {
      wrap.remove();
      renumberIngineri();
      updateInginerAddButton();
      rerenderIcons();
    };
    tbody.appendChild(wrap);
    rerenderIcons();
  }
  function renumberIngineri() {
    const rows = overlay.querySelectorAll('#pv-ingineri-rows .pv-fld');
    rows.forEach((r, i) => {
      const lbl = r.querySelector('label');
      if (lbl) lbl.innerHTML = `Inginer ${i + 1}${i === 0 ? ' <span class="opt">primary</span>' : ''}`;
    });
  }
  function updateInginerAddButton() {
    let btn = overlay.querySelector('#pv-add-inginer');
    const tbody = $('#pv-ingineri-rows');
    const count = tbody.querySelectorAll('.pv-fld').length;
    if (count < 3) {
      if (!btn) {
        const wrap = document.createElement('div');
        wrap.className = 'pv-fld full';
        wrap.innerHTML = `
          <button id="pv-add-inginer" type="button" class="pv-add">
            <i data-lucide="plus"></i>Adaugă inginer
          </button>
        `;
        tbody.appendChild(wrap);
        wrap.querySelector('#pv-add-inginer').onclick = () => {
          wrap.remove();
          addInginerRow('', false);
          renumberIngineri();
          updateInginerAddButton();
        };
        rerenderIcons();
      }
    } else if (btn) {
      btn.closest('.pv-fld').remove();
    }
  }
  function collectIngineri() {
    return Array.from(overlay.querySelectorAll('.pv-inginer-input'))
      .map(i => i.value.trim()).filter(Boolean);
  }

  // ----- Image manager (Service) -----
  let imgSeq = 0;
  const imageEntries = []; // {id, file, dataUrl, caption, anchor, width}
  let svcBeforeLines = [];  // liniile din service_before (motivul)
  let svcAfterLines = [];   // liniile din service_after (actiuni)

  function truncLine(s, n) {
    s = (s || '').trim();
    return s.length > n ? s.slice(0, n) + '…' : s;
  }

  function buildServiceAnchors() {
    // Returneaza lista {value, label} cu liniile reale din PV
    const opts = [];
    svcBeforeLines.forEach((l, i) => {
      opts.push({ value: `motiv:${i}`, label: `După: ${truncLine(l, 48)}` });
    });
    svcAfterLines.forEach((l, i) => {
      opts.push({ value: `actiuni:${i}`, label: `După: ${truncLine(l, 48)}` });
    });
    opts.push({ value: 'observatii', label: 'După Observații' });
    opts.push({ value: 'final', label: 'La final (anexă)' });
    return opts;
  }

  function addImageFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const id = ++imgSeq;
      const anchors = buildServiceAnchors();
      // default: dupa ultima linie de actiuni daca exista, altfel final
      const lastAct = svcAfterLines.length ? `actiuni:${svcAfterLines.length - 1}` : 'final';
      imageEntries.push({
        id, file, dataUrl: e.target.result, caption: '',
        anchor: lastAct, width: 'half',
      });
      renderImagesList();
    };
    reader.readAsDataURL(file);
  }

  function renderImagesList() {
    const list = $('#pv-images-list');
    list.innerHTML = '';
    const anchors = buildServiceAnchors();
    imageEntries.forEach((entry) => {
      // daca anchor-ul salvat nu mai exista in lista, fallback la final
      if (!anchors.some(a => a.value === entry.anchor)) entry.anchor = 'final';
      const card = document.createElement('div');
      card.className = 'pv-img-card';
      card.innerHTML = `
        <img class="thumb" src="${entry.dataUrl}" alt="">
        <div class="meta">
          <input type="text" placeholder="Caption opțional"
                 value="${escapeHtml(entry.caption)}" data-img-caption>
          <select data-img-anchor title="Unde apare poza în PV">
            ${anchors.map(a => `<option value="${a.value}" ${entry.anchor===a.value?'selected':''}>${escapeHtml(a.label)}</option>`).join('')}
          </select>
          <div class="pv-width-toggle">
            <button type="button" data-w="half" class="${entry.width==='half'?'on':''}">2 / rând</button>
            <button type="button" data-w="full" class="${entry.width==='full'?'on':''}">1 / rând</button>
          </div>
          <span class="filename">${escapeHtml(entry.file.name)}</span>
        </div>
        <button type="button" class="del-img" title="Șterge"><i data-lucide="trash-2"></i></button>
      `;
      card.querySelector('[data-img-caption]').oninput = (e) => { entry.caption = e.target.value; };
      card.querySelector('[data-img-anchor]').onchange = (e) => { entry.anchor = e.target.value; };
      card.querySelectorAll('.pv-width-toggle button').forEach(b => {
        b.onclick = () => {
          entry.width = b.dataset.w;
          card.querySelectorAll('.pv-width-toggle button').forEach(x => x.classList.toggle('on', x.dataset.w === entry.width));
        };
      });
      card.querySelector('.del-img').onclick = () => {
        const idx = imageEntries.findIndex(x => x.id === entry.id);
        if (idx >= 0) imageEntries.splice(idx, 1);
        renderImagesList();
      };
      list.appendChild(card);
    });
    rerenderIcons();
  }

  // Bind static elements
  overlay.querySelectorAll('[data-pv-close]').forEach(b => b.onclick = close);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#pv-add-row').onclick = () => addRow();
  ['#pv-cod', '#pv-data'].forEach(s => $(s).oninput = updateNrPreview);
  $('#pv-add-images').onclick = () => $('#pv-img-input').click();
  $('#pv-img-input').onchange = (e) => {
    Array.from(e.target.files || []).forEach(addImageFile);
    e.target.value = ''; // reset ca sa poate re-selecta acelasi fisier
  };

  $('#pv-echipament').onchange = function () {
    const opt = this.options[this.selectedIndex];
    $('#pv-a-serie').textContent = opt?.dataset?.serie || '—';
  };

  $('#pv-generate').onclick = async function () {
    const btn = this;
    btn.disabled = true;
    const orig = btn.innerHTML;
    btn.innerHTML = '<i data-lucide="loader-2"></i>Se generează...';
    rerenderIcons();
    try {
      const ingineri = collectIngineri();
      const payload = {
        echipament_id: $('#pv-echipament').value || null,
        cod_proiect: $('#pv-cod').value.trim(),
        data_pv: $('#pv-data').value.trim(),
        denumire_comanda: $('#pv-denumire').value.trim(),
        observatii: $('#pv-observatii').value,
        nota_facturare: $('#pv-nota-fact').value,
        reprezentant_eg: ingineri[0] || 'Ion Ursu',
        ingineri: ingineri,
        ore: collectRows(),
      };
      const projectId = overlay.dataset.projectId;
      let res;
      if (imageEntries.length > 0) {
        const fd = new FormData();
        fd.append('payload', JSON.stringify(payload));
        imageEntries.forEach((entry, i) => {
          fd.append(`image_${i}`, entry.file, entry.file.name);
          fd.append(`image_${i}_caption`, entry.caption || '');
          fd.append(`image_${i}_anchor`, entry.anchor || 'final');
          fd.append(`image_${i}_width`, entry.width || 'half');
        });
        res = await fetch(`/api/proiecte/${projectId}/pv/service/generate`, {
          method: 'POST', body: fd, credentials: 'same-origin',
        });
      } else {
        res = await fetch(`/api/proiecte/${projectId}/pv/service/generate`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload), credentials: 'same-origin',
        });
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const cd = res.headers.get('content-disposition') || '';
      let filename = `PV_Service_${payload.cod_proiect || 'PV'}.docx`;
      const m = cd.match(/filename="?([^";]+)"?/);
      if (m) filename = m[1];
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      if (window.showToast) showToast('PV generat cu succes');
      close();
    } catch (e) {
      console.error('PV generate failed:', e);
      if (window.showToast) showToast('Eroare: ' + e.message, true);
      else alert('Eroare la generarea PV: ' + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = orig;
      rerenderIcons();
    }
  };

  window.openPvServiceModal = async function (projectId) {
    overlay.dataset.projectId = projectId;
    // reset form
    $('#pv-cod').value = '';
    $('#pv-denumire').value = '';
    $('#pv-observatii').value = '';
    $('#pv-nota-fact').value = '';
    $('#pv-data').value = todayDDMMYYYY();
    $('#pv-rows').innerHTML = '';
    rowSeq = 0;
    addRow({ tip: 'TD' });
    renderIngineri(['Ion Ursu']);
    imageEntries.length = 0;
    renderImagesList();

    overlay.classList.add('active');
    document.body.classList.add('pv-modal-open');
    rerenderIcons();

    try {
      const res = await fetch(`/api/proiecte/${projectId}/pv/service/preview`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const p = data.proiect || {};
      const echs = data.echipamente || [];

      $('#pv-a-client').textContent = p.client || '—';
      $('#pv-a-locatie').textContent = p.locatie || '—';
      $('#pv-a-motiv').textContent = trim(p.service_before, 220) || 'Lipsește — completează "Constatări înainte" în proiect';
      $('#pv-a-actiuni').textContent = trim(p.service_after, 220) || 'Lipsește — completează "Acțiuni și rezultat" în proiect';
      if (!p.service_before) $('#pv-a-motiv').classList.add('muted');
      if (!p.service_after) $('#pv-a-actiuni').classList.add('muted');

      // Linii pentru ancorele pozelor (selectarea randului din PV)
      svcBeforeLines = (p.service_before || '').split('\n').map(l => l.trim()).filter(Boolean);
      svcAfterLines = (p.service_after || '').split('\n').map(l => l.trim()).filter(Boolean);
      renderImagesList();

      // pre-fill cod proiect din DB daca exista
      if (p.cod_proiect) {
        $('#pv-cod').value = p.cod_proiect;
        updateNrPreview();
      }
      if (p.nr_comanda && !$('#pv-denumire').value) {
        $('#pv-denumire').value = p.nr_comanda;
      }

      // echipamente
      const sel = $('#pv-echipament');
      sel.innerHTML = '';
      if (echs.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '— Niciun echipament în proiect —';
        opt.dataset.serie = '';
        sel.appendChild(opt);
        $('#pv-a-serie').textContent = '—';
      } else {
        echs.forEach((e, idx) => {
          const opt = document.createElement('option');
          opt.value = e.id;
          const label = [e.model || e.nume, e.serial_number ? `SN ${e.serial_number}` : ''].filter(Boolean).join(' — ');
          opt.textContent = label || e.nume;
          opt.dataset.serie = e.serial_number || '';
          sel.appendChild(opt);
        });
        sel.selectedIndex = 0;
        $('#pv-a-serie').textContent = echs[0].serial_number || '—';
      }
    } catch (e) {
      console.error('PV preview failed:', e);
      if (window.showToast) showToast('Eroare preview PV: ' + e.message, true);
    }
  };
})();

/* ===================== PV PIF (modal separat) ===================== */
(function () {
  if (window.__pvPifModalInjected) return;
  window.__pvPifModalInjected = true;

  // CSS-ul de baza e injectat de prima IIFE (pv-modal-overlay, pv-modal, etc.).
  // Adaug doar tweak-uri pentru variant PIF (accent violet).
  const css = `
    .pv-pif-overlay { position: fixed; inset: 0; z-index: 1000;
      background: rgba(0,0,0,0.55); backdrop-filter: blur(6px);
      display: none; padding: 24px; }
    .pv-pif-overlay.active { display: grid; place-items: center; }
    .pv-pif-overlay .pv-modal { width: 100%; max-width: 920px; max-height: calc(100vh - 48px);
      background: var(--bg-elev1); border: 1px solid var(--line);
      border-radius: 18px; box-shadow: 0 12px 36px rgba(0,0,0,.45);
      display: flex; flex-direction: column; overflow: hidden; color: var(--text); }
    .pv-pif-overlay .pv-mh-ico {
      background: var(--violet-soft, rgba(139,135,255,0.12)) !important;
      color: var(--violet, #8b87ff) !important; }
    .pv-pif-overlay .pv-preview {
      background: linear-gradient(90deg, var(--violet-soft, rgba(139,135,255,0.12)), transparent 70%) !important;
      border-color: rgba(139,135,255,0.25) !important; }
    .pv-pif-overlay .pv-preview .pv-l { color: var(--violet, #8b87ff) !important; }
    .pv-pif-overlay .pv-preview .pv-v b { color: var(--violet, #8b87ff) !important; }
    .pv-pif-overlay .pv-preview [data-lucide] { color: var(--violet, #8b87ff) !important; }
    .pv-pif-overlay .pv-fld input:focus,
    .pv-pif-overlay .pv-fld textarea:focus,
    .pv-pif-overlay .pv-fld select:focus {
      border-color: var(--violet, #8b87ff) !important;
      box-shadow: 0 0 0 3px rgba(139,135,255,0.18) !important; }
    .pv-pif-overlay .pv-btn-primary {
      background: var(--violet, #8b87ff) !important; color: #0a0a1d !important;
      border-color: var(--violet, #8b87ff) !important; }
    .pv-pif-overlay .pv-btn-primary:hover { background: #a39ffd !important; }
    .pv-pif-dates { background: var(--bg-elev2); border: 1px solid var(--line);
      border-radius: 8px; padding: 8px; }
    .pv-pif-dates .row { display: flex; gap: 8px; margin-bottom: 8px; }
    .pv-pif-dates .row:last-of-type { margin-bottom: 0; }
    .pv-pif-dates .row input { flex: 1; background: var(--bg-elev1);
      border: 1px solid var(--line); color: var(--text);
      border-radius: 6px; padding: 7px 10px; font-size: 13px;
      font-family: 'JetBrains Mono', monospace; }
    .pv-pif-dates .row .del { width: 30px; border: 1px solid var(--line);
      background: transparent; color: var(--text-mut); border-radius: 6px;
      cursor: pointer; display: grid; place-items: center; }
    .pv-pif-dates .row .del:hover { color: var(--danger); border-color: var(--danger);
      background: var(--danger-soft); }
    .pv-pif-dates .row .del [data-lucide] { width: 13px; height: 13px; }
    .pv-pif-add-date { margin-top: 4px; display: inline-flex; align-items: center;
      gap: 6px; padding: 6px 12px;
      background: var(--violet-soft, rgba(139,135,255,0.12));
      color: var(--violet, #8b87ff);
      border: 1px solid rgba(139,135,255,0.25); border-radius: 7px;
      font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit; }
    .pv-pif-add-date [data-lucide] { width: 13px; height: 13px; }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  const overlay = document.createElement('div');
  overlay.className = 'pv-pif-overlay';
  overlay.id = 'pv-pif-modal';
  overlay.innerHTML = `
    <div class="pv-modal" role="dialog" aria-modal="true">
      <div class="pv-mh">
        <div class="pv-mh-ico"><i data-lucide="badge-check"></i></div>
        <div>
          <div class="pv-mh-title">Generează Proces Verbal de Recepție PIF</div>
          <div class="pv-mh-sub">DOCX bazat pe template — header / footer / formatare păstrate</div>
        </div>
        <button class="pv-mh-close" data-pif-close><i data-lucide="x"></i></button>
      </div>
      <div class="pv-body">
        <div class="pv-preview">
          <i data-lucide="hash"></i>
          <div>
            <div class="pv-l">Număr proces verbal</div>
            <div class="pv-v" id="pif-nr-preview">Nr. 1 / <b>...</b> / data <b>...</b></div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Date din proiect (auto)</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>Editabile în proiect</span>
          </div>
          <div class="pv-auto">
            <div class="row"><span class="k">Beneficiar</span><span class="v" id="pif-a-client">—</span></div>
            <div class="row"><span class="k">Obiectiv</span><span class="v" id="pif-a-obiectiv">—</span></div>
            <div class="row full"><span class="k">Comanda / contract</span><span class="v code" id="pif-a-comanda">—</span></div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head"><div class="pv-sec-title">Detalii recepție</div></div>
          <div class="pv-form">
            <div class="pv-fld">
              <label>Cod proiect <span class="opt">ex. 250592E_C1</span></label>
              <input type="text" id="pif-cod" class="mono" placeholder="250592E_xx">
            </div>
            <div class="pv-fld">
              <label>Data PV (semnare)</label>
              <input type="text" id="pif-data" class="mono" placeholder="DD.MM.YYYY">
            </div>
            <div class="pv-fld">
              <label>Data convocării comisiei</label>
              <input type="text" id="pif-conv" class="mono" placeholder="DD.MM.YYYY">
            </div>
            <div class="pv-fld">
              <label>Data desfășurării activității</label>
              <input type="text" id="pif-desf" class="mono" placeholder="DD.MM.YYYY">
            </div>
            <div class="pv-fld full">
              <label>Datele efectuării probelor tehnologice</label>
              <div class="pv-pif-dates">
                <div id="pif-dates-rows"></div>
                <button class="pv-pif-add-date" id="pif-add-date" type="button"><i data-lucide="plus"></i>Adaugă dată</button>
              </div>
              <span class="help" style="font-size:11px;color:var(--text-dim);">Generează: "În zilele X și Y au fost efectuate probele..."</span>
            </div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head"><div class="pv-sec-title">Anexe și file</div></div>
          <div class="pv-form">
            <div class="pv-fld">
              <label>Nr. file proces verbal</label>
              <input type="number" id="pif-file" class="mono" value="2" min="1">
            </div>
            <div class="pv-fld">
              <label>Nr. anexe</label>
              <input type="number" id="pif-anexe" class="mono" value="0" min="0">
            </div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Alte constatări (punctul 3)</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>Pre-populat din "Observații" proiect</span>
          </div>
          <div class="pv-form">
            <div class="pv-fld full">
              <textarea id="pif-constatari" style="min-height:140px;"
                placeholder="Detalii activități realizate, echipamente puse în funcțiune, teste validate..."></textarea>
              <span class="help" style="font-size:11px;color:var(--text-dim);">Fiecare linie devine paragraf în PV</span>
            </div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head"><div class="pv-sec-title">Semnături</div></div>
          <div class="pv-form">
            <div class="pv-fld">
              <label>Reprezentant Beneficiar</label>
              <input type="text" id="pif-rep-client" placeholder="Ing. Nume Prenume">
            </div>
            <div class="pv-fld">
              <label>Reprezentant Electroglobal</label>
              <input type="text" id="pif-rep-eg" value="Ing. Ion Ursu">
            </div>
          </div>
        </div>

        <div class="pv-sec">
          <div class="pv-sec-head">
            <div class="pv-sec-title">Anexe foto</div>
            <span class="pv-sec-hint"><i data-lucide="info"></i>2 poze pe rând, caption opțional</span>
          </div>
          <input type="file" id="pif-img-input" accept="image/*" multiple style="display:none;">
          <button type="button" class="pv-pif-add-date" id="pif-add-images" style="margin-bottom:10px;">
            <i data-lucide="image-plus"></i>Adaugă poze
          </button>
          <div id="pif-images-list" class="pv-images-list"></div>
        </div>
      </div>

      <div class="pv-foot">
        <div class="meta"><i data-lucide="shield-check"></i>Header, footer și formatarea template-ului se păstrează</div>
        <div class="acts">
          <button class="pv-btn pv-btn-secondary" data-pif-close><i data-lucide="x"></i>Anulează</button>
          <button class="pv-btn pv-btn-primary" id="pif-generate"><i data-lucide="download"></i>Generează DOCX</button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  function $(sel) { return overlay.querySelector(sel); }
  function rerenderIcons() { if (window.lucide) lucide.createIcons(); }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function todayDDMMYYYY() {
    const d = new Date();
    return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
  }
  function close() {
    overlay.classList.remove('active');
    document.body.classList.remove('pv-modal-open');
  }

  function addDateRow(value) {
    const tbody = $('#pif-dates-rows');
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `
      <input class="mono" type="text" value="${escapeHtml(value || '')}" placeholder="DD.MM.YYYY">
      <button class="del" type="button" title="Șterge"><i data-lucide="trash-2"></i></button>
    `;
    tbody.appendChild(row);
    row.querySelector('.del').onclick = () => row.remove();
    rerenderIcons();
  }

  function collectDates() {
    const inputs = overlay.querySelectorAll('#pif-dates-rows input');
    return Array.from(inputs).map(i => i.value.trim()).filter(Boolean);
  }

  function updatePreview() {
    const cod = ($('#pif-cod').value || '...').trim() || '...';
    const data = ($('#pif-data').value || '...').trim() || '...';
    $('#pif-nr-preview').innerHTML =
      `Nr. 1 / <b>${escapeHtml(cod)}</b> / data <b>${escapeHtml(data)}</b>`;
  }

  overlay.querySelectorAll('[data-pif-close]').forEach(b => b.onclick = close);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  $('#pif-add-date').onclick = () => addDateRow('');
  ['#pif-cod', '#pif-data'].forEach(s => $(s).oninput = updatePreview);

  // Image manager (PIF)
  let pifImgSeq = 0;
  const pifImages = [];

  function pifTrunc(s, n) {
    s = (s || '').trim();
    return s.length > n ? s.slice(0, n) + '…' : s;
  }
  function buildPifAnchors() {
    // liniile din textarea constatari (live)
    const opts = [];
    const lines = ($('#pif-constatari').value || '').split('\n').map(l => l.trim()).filter(Boolean);
    lines.forEach((l, i) => {
      opts.push({ value: `constatari:${i}`, label: `După: ${pifTrunc(l, 48)}` });
    });
    opts.push({ value: 'concluzii', label: 'După Concluzii' });
    opts.push({ value: 'final', label: 'La final (anexă)' });
    return opts;
  }
  function pifAddImage(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const lines = ($('#pif-constatari').value || '').split('\n').map(l => l.trim()).filter(Boolean);
      const def = lines.length ? `constatari:${lines.length - 1}` : 'final';
      pifImages.push({
        id: ++pifImgSeq, file, dataUrl: e.target.result,
        caption: '', anchor: def, width: 'half',
      });
      pifRenderImages();
    };
    reader.readAsDataURL(file);
  }
  function pifRenderImages() {
    const list = $('#pif-images-list');
    list.innerHTML = '';
    const anchors = buildPifAnchors();
    pifImages.forEach((entry) => {
      if (!anchors.some(a => a.value === entry.anchor)) entry.anchor = 'final';
      const card = document.createElement('div');
      card.className = 'pv-img-card';
      card.innerHTML = `
        <img class="thumb" src="${entry.dataUrl}" alt="">
        <div class="meta">
          <input type="text" placeholder="Caption opțional"
                 value="${escapeHtml(entry.caption)}" data-img-caption>
          <select data-img-anchor title="Unde apare poza în PV">
            ${anchors.map(a => `<option value="${a.value}" ${entry.anchor===a.value?'selected':''}>${escapeHtml(a.label)}</option>`).join('')}
          </select>
          <div class="pv-width-toggle">
            <button type="button" data-w="half" class="${entry.width==='half'?'on':''}">2 / rând</button>
            <button type="button" data-w="full" class="${entry.width==='full'?'on':''}">1 / rând</button>
          </div>
          <span class="filename">${escapeHtml(entry.file.name)}</span>
        </div>
        <button type="button" class="del-img" title="Șterge"><i data-lucide="trash-2"></i></button>
      `;
      card.querySelector('[data-img-caption]').oninput = (e) => { entry.caption = e.target.value; };
      card.querySelector('[data-img-anchor]').onchange = (e) => { entry.anchor = e.target.value; };
      card.querySelectorAll('.pv-width-toggle button').forEach(b => {
        b.onclick = () => {
          entry.width = b.dataset.w;
          card.querySelectorAll('.pv-width-toggle button').forEach(x => x.classList.toggle('on', x.dataset.w === entry.width));
        };
      });
      card.querySelector('.del-img').onclick = () => {
        const idx = pifImages.findIndex(x => x.id === entry.id);
        if (idx >= 0) pifImages.splice(idx, 1);
        pifRenderImages();
      };
      list.appendChild(card);
    });
    rerenderIcons();
  }
  // Re-randeaza dropdown-urile cand se editeaza constatarile
  $('#pif-constatari').addEventListener('input', () => {
    if (pifImages.length) pifRenderImages();
  });
  $('#pif-add-images').onclick = () => $('#pif-img-input').click();
  $('#pif-img-input').onchange = (e) => {
    Array.from(e.target.files || []).forEach(pifAddImage);
    e.target.value = '';
  };

  $('#pif-generate').onclick = async function () {
    const btn = this;
    btn.disabled = true;
    const orig = btn.innerHTML;
    btn.innerHTML = '<i data-lucide="loader-2"></i>Se generează...';
    rerenderIcons();
    try {
      const payload = {
        cod_proiect: $('#pif-cod').value.trim(),
        data_pv: $('#pif-data').value.trim(),
        data_convocare: $('#pif-conv').value.trim(),
        data_desfasurare: $('#pif-desf').value.trim(),
        date_probe: collectDates(),
        nr_file: parseInt($('#pif-file').value || '2', 10),
        nr_anexe: parseInt($('#pif-anexe').value || '0', 10),
        constatari: $('#pif-constatari').value,
        rep_client: $('#pif-rep-client').value.trim(),
        rep_eg: $('#pif-rep-eg').value.trim() || 'Ing. Ion Ursu',
      };
      const projectId = overlay.dataset.projectId;
      // Hack to access body var name expected downstream
      const body = payload;
      let res;
      if (pifImages.length > 0) {
        const fd = new FormData();
        fd.append('payload', JSON.stringify(payload));
        pifImages.forEach((entry, i) => {
          fd.append(`image_${i}`, entry.file, entry.file.name);
          fd.append(`image_${i}_caption`, entry.caption || '');
          fd.append(`image_${i}_anchor`, entry.anchor || 'final');
          fd.append(`image_${i}_width`, entry.width || 'half');
        });
        res = await fetch(`/api/proiecte/${projectId}/pv/pif/generate`, {
          method: 'POST', body: fd, credentials: 'same-origin',
        });
      } else {
        res = await fetch(`/api/proiecte/${projectId}/pv/pif/generate`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload), credentials: 'same-origin',
        });
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const cd = res.headers.get('content-disposition') || '';
      let filename = `PV_PIF_${body.cod_proiect || 'PV'}.docx`;
      const m = cd.match(/filename="?([^";]+)"?/);
      if (m) filename = m[1];
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      if (window.showToast) showToast('PV PIF generat cu succes');
      close();
    } catch (e) {
      console.error('PV PIF generate failed:', e);
      if (window.showToast) showToast('Eroare: ' + e.message, true);
      else alert('Eroare la generarea PV PIF: ' + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = orig;
      rerenderIcons();
    }
  };

  window.openPvPifModal = async function (projectId) {
    overlay.dataset.projectId = projectId;
    const today = todayDDMMYYYY();
    $('#pif-cod').value = '';
    $('#pif-data').value = today;
    $('#pif-conv').value = today;
    $('#pif-desf').value = today;
    $('#pif-file').value = '2';
    $('#pif-anexe').value = '0';
    $('#pif-constatari').value = '';
    $('#pif-rep-client').value = '';
    $('#pif-rep-eg').value = 'Ing. Ion Ursu';
    $('#pif-dates-rows').innerHTML = '';
    addDateRow(today);
    pifImages.length = 0;
    pifRenderImages();
    updatePreview();
    overlay.classList.add('active');
    document.body.classList.add('pv-modal-open');
    rerenderIcons();

    try {
      const res = await fetch(`/api/proiecte/${projectId}/pv/pif/preview`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const p = data.proiect || {};
      $('#pif-a-client').textContent = p.client || '—';
      $('#pif-a-obiectiv').textContent = p.nume || '—';
      const combo = [p.nr_comanda, p.nr_contract].filter(Boolean).join(' / ');
      $('#pif-a-comanda').textContent = combo || '—';
      if (p.cod_proiect) { $('#pif-cod').value = p.cod_proiect; updatePreview(); }
      if (p.observatii) $('#pif-constatari').value = p.observatii;
    } catch (e) {
      console.error('PV PIF preview failed:', e);
      if (window.showToast) showToast('Eroare preview: ' + e.message, true);
    }
  };
})();
