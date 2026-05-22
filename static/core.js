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

// --- Lightweight Markdown renderer (no external lib) -----------------
// Shared by the desktop Obsidian tab and the mobile Obsidian tab. Input is
// escaped FIRST so vault content can never inject HTML (no XSS). Emits the
// md-* CSS classes styled identically in both index.html and mobile.html.

// Inline-level Markdown. Wikilinks become <span class="md-wikilink"
// data-wikilink="..."> — both shells delegate clicks on that class/attr.
function mdInline(text) {
    let s = escapeHtml(text);
    // Protect inline code spans from further substitution. The placeholder is
    // wrapped in U+E000 (a Private Use Area char) so it can never collide with
    // real note text \u2014 e.g. a note literally containing "IC3".
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (m, c) => { codes.push(c); return '\uE000IC' + (codes.length - 1) + '\uE000'; });
    // Images, then links. URLs come from already-escaped text.
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, '<img alt="$1" src="$2">');
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g,
        '<a href="$2" target="_blank" rel="noopener">$1</a>');
    // Obsidian wikilinks [[Note]] / [[Note|alias]] (also embeds ![[...]]).
    // escapeHtml already escapes quotes, so it is safe for the data-attribute.
    s = s.replace(/!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, target, alias) =>
        `<span class="md-wikilink" data-wikilink="${escapeHtml(target.trim())}">${(alias || target).trim()}</span>`);
    // Bold, italic, strikethrough, ==highlight==.
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
    s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>');
    s = s.replace(/==([^=]+)==/g, '<mark>$1</mark>');
    // Tags #tag.
    s = s.replace(/(^|\s)#([a-zA-Z][\w/\-]*)/g, '$1<span class="md-tag">#$2</span>');
    // Restore inline code (re-escaped — codes[] holds raw text).
    s = s.replace(/\uE000IC(\d+)\uE000/g, (m, i) => '<code>' + escapeHtml(codes[+i]) + '</code>');
    return s;
}

// Obsidian callout type -> [css class, default Romanian title].
function _calloutMeta(type) {
    const map = {
        note: ['note', 'Notă'], info: ['note', 'Info'], abstract: ['note', 'Rezumat'],
        summary: ['note', 'Rezumat'], tldr: ['note', 'TL;DR'], todo: ['note', 'De făcut'],
        tip: ['tip', 'Tip'], hint: ['tip', 'Tip'], important: ['tip', 'Important'],
        success: ['success', 'Succes'], check: ['success', 'OK'], done: ['success', 'Gata'],
        question: ['question', 'Întrebare'], help: ['question', 'Ajutor'], faq: ['question', 'FAQ'],
        warning: ['warning', 'Atenție'], caution: ['warning', 'Atenție'], attention: ['warning', 'Atenție'],
        failure: ['danger', 'Eșec'], fail: ['danger', 'Eșec'], missing: ['danger', 'Lipsă'],
        danger: ['danger', 'Pericol'], error: ['danger', 'Eroare'], bug: ['danger', 'Bug'],
        example: ['example', 'Exemplu'], quote: ['quote', 'Citat'], cite: ['quote', 'Citat'],
    };
    const t = (type || '').toLowerCase();
    return map[t] || ['note', type ? (type.charAt(0).toUpperCase() + type.slice(1)) : 'Notă'];
}

// Block-level Markdown. Returns an HTML string; wrap it in a .md-rendered
// container at the call site.
function renderMarkdown(src) {
    let text = String(src || '').replace(/\r\n/g, '\n');
    // Strip leading YAML frontmatter and Obsidian %% comments %%.
    text = text.replace(/^---\n[\s\S]*?\n---\n?/, '');
    text = text.replace(/%%[\s\S]*?%%/g, '');
    const lines = text.split('\n');
    const out = [];
    let i = 0, inCode = false, codeBuf = [];
    const listStack = [];
    const closeLists = () => { while (listStack.length) out.push('</' + listStack.pop() + '>'); };

    while (i < lines.length) {
        const line = lines[i];
        const fence = line.match(/^```(.*)$/);
        if (fence) {
            if (inCode) { out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>'); inCode = false; codeBuf = []; }
            else { closeLists(); inCode = true; }
            i++; continue;
        }
        if (inCode) { codeBuf.push(line); i++; continue; }
        if (line.trim() === '') { closeLists(); i++; continue; }

        const h = line.match(/^(#{1,6})\s+(.*)$/);
        if (h) { closeLists(); const lvl = Math.min(h[1].length, 3); out.push(`<h${lvl}>${mdInline(h[2])}</h${lvl}>`); i++; continue; }

        if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) { closeLists(); out.push('<hr>'); i++; continue; }

        if (/^>\s?/.test(line)) {
            closeLists();
            const quote = [];
            while (i < lines.length && /^>\s?/.test(lines[i])) { quote.push(lines[i].replace(/^>\s?/, '')); i++; }
            // Obsidian callout: first line is [!type] optional-title.
            const cm = quote[0] && quote[0].match(/^\[!(\w+)\][+-]?\s*(.*)$/);
            if (cm) {
                const meta = _calloutMeta(cm[1]);
                const ctitle = cm[2].trim() || meta[1];
                const body = quote.slice(1).join('\n').trim();
                out.push(`<div class="md-callout md-callout-${meta[0]}">`
                    + `<div class="md-callout-title">${mdInline(ctitle)}</div>`
                    + (body ? `<div class="md-callout-body">${renderMarkdown(body)}</div>` : '')
                    + '</div>');
            } else {
                out.push('<blockquote>' + renderMarkdown(quote.join('\n')) + '</blockquote>');
            }
            continue;
        }

        // Table: header row with pipes + separator row of dashes.
        if (line.includes('|') && i + 1 < lines.length &&
            /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
            closeLists();
            const cells = r => r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim());
            const head = cells(line);
            i += 2;
            let tbl = '<table><thead><tr>' + head.map(c => `<th>${mdInline(c)}</th>`).join('') + '</tr></thead><tbody>';
            while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
                tbl += '<tr>' + cells(lines[i]).map(c => `<td>${mdInline(c)}</td>`).join('') + '</tr>';
                i++;
            }
            out.push(tbl + '</tbody></table>');
            continue;
        }

        const ul = line.match(/^(\s*)[-*+]\s+(.*)$/);
        const ol = line.match(/^(\s*)\d+\.\s+(.*)$/);
        if (ul || ol) {
            const type = ul ? 'ul' : 'ol';
            if (listStack[listStack.length - 1] !== type) { closeLists(); out.push('<' + type + '>'); listStack.push(type); }
            const content = ul ? ul[2] : ol[2];
            const task = content.match(/^\[([ xX])\]\s+(.*)$/);
            if (task) out.push(`<li><input type="checkbox" disabled ${task[1] !== ' ' ? 'checked' : ''}> ${mdInline(task[2])}</li>`);
            else out.push('<li>' + mdInline(content) + '</li>');
            i++; continue;
        }

        closeLists();
        const para = [line]; i++;
        while (i < lines.length && lines[i].trim() !== '' &&
               !/^(#{1,6}\s|```|>\s?|\s*[-*+]\s|\s*\d+\.\s)/.test(lines[i]) &&
               !/^(-{3,}|\*{3,}|_{3,})$/.test(lines[i].trim())) {
            para.push(lines[i]); i++;
        }
        out.push('<p>' + mdInline(para.join('\n')).replace(/\n/g, '<br>') + '</p>');
    }
    closeLists();
    if (inCode) out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>');
    return out.join('\n');
}

// --- Global search metadata -----------------------------------------
// type -> { label, icon } for grouped rendering in the command palette
// (desktop) and the search overlay (mobile). _GS_ORDER fixes group order.
const _GS_META = {
    proiect:     { label: 'Proiecte', icon: 'folder-kanban' },
    observatie:  { label: 'Observații', icon: 'file-text' },
    task:        { label: 'Taskuri', icon: 'check-square' },
    global_task: { label: 'Taskuri zilnice', icon: 'calendar-check' },
    checklist:   { label: 'Checklist', icon: 'list-checks' },
    jurnal:      { label: 'Jurnal', icon: 'notebook-pen' },
    echipament:  { label: 'Echipamente', icon: 'cpu' },
    client:      { label: 'Clienți', icon: 'users' },
    parametru:   { label: 'Parametri', icon: 'sliders-horizontal' },
    obsidian:    { label: 'Notițe', icon: 'book-open' },
};
const _GS_ORDER = ['proiect', 'observatie', 'task', 'global_task', 'checklist',
                   'jurnal', 'echipament', 'client', 'parametru', 'obsidian'];
