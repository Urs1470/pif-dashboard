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

// Allowlist of safe URL schemes. Anything else (javascript:, data:, vbscript:,
// file:) is rewritten to "#" to neutralise XSS via Markdown links and images.
function _safeUrl(url) {
    const t = String(url || '').trim().toLowerCase();
    if (/^(javascript|data|vbscript|file):/.test(t)) return '#';
    return url;
}

// Inline-level Markdown. Wikilinks become <span class="md-wikilink"
// data-wikilink="..."> — both shells delegate clicks on that class/attr.
function mdInline(text) {
    let s = escapeHtml(text);
    // Protect inline code spans from further substitution. The placeholder is
    // wrapped in U+E000 (a Private Use Area char) so it can never collide with
    // real note text \u2014 e.g. a note literally containing "IC3".
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (m, c) => { codes.push(c); return '\uE000IC' + (codes.length - 1) + '\uE000'; });
    // Images, then links. URLs go through _safeUrl which rejects
    // javascript:/data:/vbscript:/file: schemes — XSS hardening.
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g,
        (m, alt, url) => `<img alt="${alt}" src="${_safeUrl(url)}">`);
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g,
        (m, txt, url) => `<a href="${_safeUrl(url)}" target="_blank" rel="noopener">${txt}</a>`);
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

// --- Time formatting ------------------------------------------------
// Format a duration in seconds as HH:MM:SS (zero-padded). Negative inputs
// are clamped to 0 to absorb client/server clock drift on running timers.
// Desktop calls it formatTime; mobile calls it formatDuration — both
// names resolve to the same function.
function formatTime(seconds) {
    seconds = Math.max(0, Math.floor(seconds)); // never render negative time
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}
const formatDuration = formatTime;   // mobile-side alias

// --- Param helpers --------------------------------------------------
// Pull a short human name out of the long English param description
// (e.g. "Motor nominal speed Specifies the rated…" -> "Motor nominal speed").
// Heuristic: take the first 2-4 words, but stop early if we hit a verb that
// usually begins the explanatory clause ("Specifies", "Sets", "Defines"…).
function extractParamName(descriere) {
    if (!descriere) return '-';
    const words = descriere.trim().split(/\s+/);
    let nameEnd = Math.min(words.length, 4);
    for (let i = 2; i < Math.min(words.length, 6); i++) {
        if (/^(Scaled|Received|Selects|Specifies|Sets|Defines|Controls|Enables|Disables|Shows|Indicates|Returns|Contains|Used|When|If|The|A|An)$/i.test(words[i])) {
            nameEnd = i;
            break;
        }
    }
    return words.slice(0, nameEnd).join(' ');
}

// Parse a parametru.influenteaza payload into [{code, efect, tip}].
// Accepts:
//   - CSV string "30.12, 21.13"
//   - JSON array of strings ["30.12", "21.13"]
//   - JSON array of objects [{parametru, efect?, tip?}]
function _parseInfluenteaza(data) {
    if (!data || data === 'null' || data === '[]') return [];
    if (Array.isArray(data)) {
        return data.map(o => typeof o === 'string'
            ? { code: o, efect: '', tip: '' }
            : { code: o.parametru || '?', efect: o.efect || '', tip: o.tip || '' });
    }
    if (typeof data !== 'string') return [];
    const trimmed = data.trim();
    if (!trimmed) return [];
    // JSON?
    if (trimmed.startsWith('[')) {
        try { return _parseInfluenteaza(JSON.parse(trimmed)); } catch { /* fall through to CSV */ }
    }
    // CSV: split on commas (and whitespace) → unique codes
    return trimmed.split(/[\s,]+/).filter(Boolean).map(c => ({ code: c, efect: '', tip: '' }));
}
const _mobParseInflu = _parseInfluenteaza;   // mobile-side alias

// --- HTML helpers shared by both shells -----------------------------
// Attribute-safe escaping for values placed inside data-* attributes.
// Mobile imports the same function under the older name _obsAttr.
function _attrEsc(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
        .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
const _obsAttr = _attrEsc;   // mobile-side alias

// Safe term highlighting for search results: escape FIRST, then wrap matches
// in <mark>. Used by global search (desktop _gsHi, mobile _gsHighlight) and
// the mobile Obsidian search (_obsHighlight) — all three were identical.
function _gsHighlight(text, q) {
    let s = escapeHtml(text || '');
    if (q) {
        const esc = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        try { s = s.replace(new RegExp('(' + esc + ')', 'gi'), '<mark>$1</mark>'); } catch (e) {}
    }
    return s;
}
const _gsHi = _gsHighlight;          // desktop-side alias
const _obsHighlight = _gsHighlight;  // mobile Obsidian-side alias

// --- Obsidian tree --------------------------------------------------
// Group a flat list of notes (each with a .path "Folder/Sub/Note.md")
// into a nested { folders: {…}, notes: [] } tree. Pure data shaping,
// shared by the desktop and mobile Obsidian tabs.
function _buildNoteTree(notes) {
    const root = { folders: {}, notes: [] };
    for (const n of notes) {
        const parts = n.path.split('/');
        parts.pop(); // drop the filename
        let node = root;
        for (const p of parts) {
            if (!node.folders[p]) node.folders[p] = { folders: {}, notes: [] };
            node = node.folders[p];
        }
        node.notes.push(n);
    }
    return root;
}
const _obsBuildTree = _buildNoteTree;   // mobile-side alias

// Count the total number of notes under a tree node (recursive).
function _countTreeNotes(node) {
    let c = node.notes.length;
    for (const k in node.folders) c += _countTreeNotes(node.folders[k]);
    return c;
}
const _obsCountNotes = _countTreeNotes;   // mobile-side alias

// --- KaTeX options --------------------------------------------------
// Shared by renderMathIn() in both shells. Delimiters: $...$ inline,
// $$...$$ display, and the standard \\(…\\) / \\[…\\] variants.
const _katexOptions = {
    delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$',  right: '$',  display: false },
        { left: '\\(', right: '\\)', display: false },
        { left: '\\[', right: '\\]', display: true },
    ],
    throwOnError: false,
    errorColor: 'var(--danger)',
};

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
    fault_code:  { label: 'Coduri eroare', icon: 'alert-triangle' },
    obsidian:    { label: 'Notițe', icon: 'book-open' },
};
const _GS_ORDER = ['proiect', 'observatie', 'task', 'global_task', 'checklist',
                   'jurnal', 'echipament', 'client', 'parametru', 'fault_code', 'obsidian'];

// ====================================================================
// TASK CARD — unified renderer (string-returning) for project tasks
// AND global tasks. Both shells call this with a ctx that switches
// the action handler names. DOM glue (expand toggle, menu open/close,
// outside-click) lives in the calling shell (app.js / mobile.js).
// ====================================================================

// Deadline → visual class. Done tasks never highlight.
function _tcardDeadlineState(dateStr, isDone) {
    if (!dateStr || isDone) return '';
    const today = new Date().toISOString().split('T')[0];
    if (dateStr < today) return 'overdue';
    if (dateStr === today) return 'today';
    const soon = new Date();
    soon.setDate(soon.getDate() + 7);
    if (dateStr <= soon.toISOString().split('T')[0]) return 'soon';
    return '';
}

// Pretty recurrence label.
const _TCARD_REC_LBL = { zilnic: 'Zilnic', saptamanal: 'Săptămânal', lunar: 'Lunar' };

// Chip row (between title and actions).
function _tcardChips(task, ctx) {
    const chips = [];
    const isGlobalLike = ctx.kind === 'global' || ctx.kind === 'overview';
    if (isGlobalLike && task.categorie && task.categorie !== 'General') {
        chips.push(`<span class="tcard__chip tcard__chip--cat">${escapeHtml(task.categorie)}</span>`);
    }
    if ((ctx.kind === 'project' || ctx.kind === 'overview') && task.proiect_nume) {
        chips.push(`<span class="tcard__chip tcard__chip--cat">${escapeHtml(task.proiect_nume)}</span>`);
    }
    if (task.data_scadenta) {
        const dstate = _tcardDeadlineState(task.data_scadenta, task.status === 'done');
        chips.push(`<span class="tcard__chip tcard__chip--deadline${dstate ? ' ' + dstate : ''}"><i data-lucide="calendar"></i>${escapeHtml(task.data_scadenta)}</span>`);
    }
    const tot = task.subtask_total || 0;
    const done = task.subtask_done || 0;
    if (tot > 0) {
        const complete = (done === tot) ? ' complete' : '';
        const handler = isGlobalLike ? 'toggleInlineSubtaskAddGt' : 'toggleInlineSubtaskAdd';
        chips.push(`<span class="tcard__chip tcard__chip--subs${complete}" onclick="event.stopPropagation();${handler}('${task.id}')" title="Adaugă subtask"><i data-lucide="list-checks"></i>${done}/${tot}</span>`);
    }
    if (task.recurenta) {
        const lbl = _TCARD_REC_LBL[task.recurenta] || task.recurenta;
        chips.push(`<span class="tcard__chip tcard__chip--rec"><i data-lucide="repeat"></i>${escapeHtml(lbl)}</span>`);
    }
    if (task.descriere && String(task.descriere).trim() && !task._tcard_expanded) {
        chips.push(`<span class="tcard__chip tcard__chip--desc" title="Are descriere"><i data-lucide="align-left"></i></span>`);
    }
    return chips.join('');
}

// Timer button — green when running. formatTimerDuration is shell-defined
// but falls back to formatTime from core.
function _tcardTimer(task, ctx) {
    const handler = (ctx.kind === 'global' || ctx.kind === 'overview') ? 'toggleGtTimerInline' : 'toggleTaskTimerInline';
    const running = !!task._timer_running;
    const total = task.timp_secunde || 0;
    const cls = running ? 'tcard__timer tcard__timer--running' : 'tcard__timer';
    const icon = running ? '⏸' : '▶';
    const fmt = (typeof formatTimerDuration === 'function') ? formatTimerDuration : formatTime;
    const label = total > 0 ? fmt(total) : '';
    return `<button type="button" class="${cls}" onclick="event.stopPropagation();${handler}('${task.id}',this)" data-timer-running="${running}" title="${running ? 'Oprește timer' : 'Pornește timer'}"><span class="tcard__timer-icon">${icon}</span>${label ? `<span>${label}</span>` : ''}</button>`;
}

// Expanded body — descriere (markdown) + subtaskuri inline. Subtasks come
// from the shell's _taskSubtasksCache (same dict used by both shells).
function _tcardBody(task, ctx) {
    const subs = (typeof _taskSubtasksCache !== 'undefined' && _taskSubtasksCache[task.id]) || [];
    const subsDone = subs.filter(s => s.done).length;
    const isGlobalLike = ctx.kind === 'global' || ctx.kind === 'overview';
    const addSubName = isGlobalLike ? 'addSubtaskInlineGt' : 'addSubtaskInline';
    const subsList = subs.map(s => `
        <div class="tcard__subtask ${s.done ? 'done' : ''}">
            <input type="checkbox" ${s.done ? 'checked' : ''} onclick="event.stopPropagation()" onchange="event.stopPropagation();toggleSubtaskInline('${s.id}',this.checked,'${task.id}')">
            <span class="tcard__subtask-title">${escapeHtml(s.titlu || '')}</span>
            <button type="button" class="tcard__subtask-timer" onclick="event.stopPropagation();toggleSubtaskTimerInline('${s.id}',this)" data-timer-running="${!!s._timer_running}" title="Pornește timer"><span class="tcard__timer-icon">▶</span></button>
            <button type="button" class="tcard__subtask-manual" onclick="event.stopPropagation();openManualTimeForSubtask('${s.id}')" title="Adaugă timp manual">✎</button>
            <button type="button" class="tcard__subtask-reset" onclick="event.stopPropagation();resetSubtaskTimer('${s.id}','${task.id}')" title="Resetează timer subtask"><i data-lucide="rotate-ccw"></i></button>
            <button type="button" class="tcard__subtask-del" onclick="event.stopPropagation();deleteSubtask('${s.id}')" title="Șterge subtask"><i data-lucide="x"></i></button>
        </div>`).join('');
    const desc = (task.descriere || '').trim();
    const descHtml = desc
        ? `<div class="tcard__desc">${(typeof renderMarkdown === 'function') ? renderMarkdown(desc) : escapeHtml(desc).replace(/\n/g, '<br>')}</div>`
        : '';
    return `<div class="tcard__body" onclick="event.stopPropagation()">
        ${descHtml}
        <div class="tcard__subtasks">
            <div class="tcard__subtasks-head"><i data-lucide="list-checks"></i> Subtaskuri (${subsDone}/${subs.length})</div>
            ${subsList}
            <div class="tcard__subtask-add">
                <input type="text" placeholder="Subtask nou — Enter pentru a adăuga" aria-label="Subtask nou"
                    onkeydown="if(event.key==='Enter'){event.preventDefault();${addSubName}('${task.id}',this.value);this.value='';}">
                <button type="button" onclick="${addSubName}('${task.id}',this.previousElementSibling.value);this.previousElementSibling.value='';"><i data-lucide="plus"></i></button>
            </div>
        </div>
    </div>`;
}

// Main renderer. ctx = { kind: 'project'|'global', projectId? }.
// Shell extends each task with _tcard_expanded / _timer_running before calling.
function renderTaskCard(task, ctx) {
    ctx = ctx || { kind: 'global' };
    const kind = ctx.kind || 'global';
    const isDone = task.status === 'done';
    const prio = String(task.prioritate || 'Normal').toLowerCase();
    const prioCap = prio.charAt(0).toUpperCase() + prio.slice(1);

    const isGlobalLike = kind === 'global' || kind === 'overview';
    const cycPrio    = kind === 'overview' ? 'cycleOverviewPriority' : (isGlobalLike ? 'cycleGtPriority'  : 'cycleTodoPriority');
    const cycStatus  = kind === 'overview' ? 'cycleOverviewStatus'   : (isGlobalLike ? 'cycleGtStatus'    : 'cycleTodoStatus');
    const toggleSt   = kind === 'overview' ? 'toggleOverviewTask'    : (isGlobalLike ? 'toggleGtTask'     : 'toggleTodo');
    const deleteName = kind === 'overview' ? 'deleteOverviewTask'    : (isGlobalLike ? 'deleteGtTask'     : 'deleteTodo');

    const cls = ['tcard', `tcard--prio-${prio}`];
    if (isDone) cls.push('tcard--done');
    if (task._tcard_expanded) cls.push('tcard--expanded');
    if (task._timer_running) cls.push('tcard--running');

    const statusLabel = (typeof getStatusLabel === 'function') ? getStatusLabel(task.status) : task.status;
    const statusCls = `tcard__status tcard__status--${task.status}`;
    const prioCls = `tcard__pill tcard__pill--${prio}`;
    const taskJsonAttr = escapeHtml(JSON.stringify(task));

    const body = task._tcard_expanded ? _tcardBody(task, ctx) : '';

    return `<div class="${cls.join(' ')}" data-task-id="${task.id}" data-tcard-kind="${kind}" onclick="_tcardToggleExpand('${task.id}', this)">
        <div class="tcard__stripe"></div>
        <input type="checkbox" class="tcard__check" ${isDone ? 'checked' : ''} onclick="event.stopPropagation()" onchange="event.stopPropagation();${toggleSt}('${task.id}',this.checked)" title="Marchează finalizat">
        <div class="tcard__main">
            <div class="tcard__title">${escapeHtml(task.titlu || '')}</div>
            <div class="tcard__chips">${_tcardChips(task, ctx)}</div>
        </div>
        <div class="tcard__actions">
            <span class="${prioCls}" onclick="event.stopPropagation();${cycPrio}('${task.id}','${prioCap}')" title="Click pentru ciclu prioritate">${prioCap}</span>
            <span class="${statusCls}" onclick="event.stopPropagation();${cycStatus}('${task.id}','${task.status}')" title="Click pentru ciclu status">${statusLabel}</span>
            ${_tcardTimer(task, ctx)}
            <button type="button" class="tcard__menu-btn" onclick="event.stopPropagation();_tcardToggleMenu('${task.id}', this)" title="Mai multe acțiuni" aria-label="Mai multe acțiuni">⋯</button>
        </div>
        <div class="tcard__menu" onclick="event.stopPropagation()">
            <button type="button" class="tcard__menu-item" onclick="event.stopPropagation();_tcardCloseMenus();openTaskEditModal(JSON.parse(this.closest('.tcard').dataset.taskJson))" data-act="edit"><i data-lucide="edit-2"></i> Editează detalii</button>
            <button type="button" class="tcard__menu-item" onclick="event.stopPropagation();_tcardCloseMenus();_tcardOpenManualTime('${kind}','${task.id}')"><i data-lucide="clock"></i> Intrare manuală timp</button>
            <button type="button" class="tcard__menu-item danger" onclick="event.stopPropagation();_tcardCloseMenus();_tcardResetTimer('${kind}','${task.id}')"><i data-lucide="rotate-ccw"></i> Resetează timer</button>
            <div class="tcard__menu-divider"></div>
            <button type="button" class="tcard__menu-item danger" onclick="event.stopPropagation();_tcardCloseMenus();${deleteName}('${task.id}')"><i data-lucide="trash-2"></i> Șterge task</button>
        </div>
        ${body}
    </div>`.replace('data-tcard-kind="' + kind + '"', 'data-tcard-kind="' + kind + '" data-task-json="' + taskJsonAttr + '"');
}
