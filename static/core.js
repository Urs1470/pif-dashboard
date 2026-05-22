// PIF Dashboard — shared core
// =====================================================================
// Logic shared by BOTH the desktop shell (app.js) and the mobile shell
// (mobile.js). Loaded as a plain <script> before each shell's own script,
// so everything declared here is available to both.
//
// Keep this file UI-agnostic: only pure helpers, constants and business
// logic — no DOM-render code, no shell-specific state.
// =====================================================================

// --- HTML escaping ---------------------------------------------------
const _ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function escapeHtml(text) {
    if (text == null) return '';   // null/undefined -> ''; 0 / false still render
    return String(text).replace(/[&<>"']/g, ch => _ESC_MAP[ch]);
}

// --- Debounce --------------------------------------------------------
function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// --- Project / task status labels -----------------------------------
// Superset map: covers both spellings of "asteptare" the two shells used.
function getStatusLabel(status) {
    const labels = {
        'in_lucru': 'În Lucru',
        'finalizat': 'Finalizat',
        'blocat': 'Blocat',
        'in_asteptare': 'În Așteptare',
        'in_așteptare': 'În Așteptare',
        'to_do': 'To Do',
        'done': 'Finalizat'
    };
    return labels[status] || status;
}

// --- Human-readable file size (512 B, 12.4 KB, 4.7 MB, 1.2 GB) -------
function formatFileSize(bytes) {
    if (bytes == null || bytes === '') return '';
    const n = Number(bytes);
    if (!isFinite(n) || n < 0) return '';
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB';
    if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + ' MB';
    return (n / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}
