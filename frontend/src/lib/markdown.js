// Port al rendererului markdown din static/core.js (linii 144-288).
// Input-ul e escapat INAINTE de orice substitutie — continutul din vault
// nu poate injecta HTML (XSS-safe). Emite clasele .md-* stilizate in
// MarkdownView.svelte. Suporta wikilinks [[...]], callouts Obsidian,
// tabele, task checkboxes, frontmatter strip.

const _ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

function escapeHtml(text) {
  if (text == null) return ''
  return String(text).replace(/[&<>"']/g, ch => _ESC_MAP[ch])
}

// Allowlist scheme-uri sigure. javascript:/data:/vbscript:/file: → "#".
function _safeUrl(url) {
  const t = String(url || '').trim().toLowerCase()
  if (/^(javascript|data|vbscript|file):/.test(t)) return '#'
  return url
}

function mdInline(text) {
  let s = escapeHtml(text)
  // Protejeaza code spans de alte substitutii (placeholder U+E000).
  const codes = []
  s = s.replace(/`([^`]+)`/g, (m, c) => { codes.push(c); return '\uE000IC' + (codes.length - 1) + '\uE000' })
  s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g,
    (m, alt, url) => `<img alt="${alt}" src="${_safeUrl(url)}">`)
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g,
    (m, txt, url) => `<a href="${_safeUrl(url)}" target="_blank" rel="noopener">${txt}</a>`)
  // Wikilinks Obsidian [[Note]] / [[Note|alias]] (si embeds ![[...]]).
  s = s.replace(/!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, target, alias) =>
    `<span class="md-wikilink" data-wikilink="${escapeHtml(target.trim())}">${(alias || target).trim()}</span>`)
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>')
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  // _italic_ doar la margini de cuvant, ca sa nu strice snake_case (p0114, global_task)
  s = s.replace(/(^|\s)_([^_\s][^_]*?)_(?=\s|$|[.,;:!?)])/g, '$1<em>$2</em>')
  s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  s = s.replace(/==([^=]+)==/g, '<mark>$1</mark>')
  s = s.replace(/(^|\s)#([a-zA-Z][\w/\-]*)/g, '$1<span class="md-tag">#$2</span>')
  s = s.replace(/\uE000IC(\d+)\uE000/g, (m, i) => '<code>' + escapeHtml(codes[+i]) + '</code>')
  return s
}

// Tip callout Obsidian -> [clasa css, titlu implicit RO].
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
  }
  const t = (type || '').toLowerCase()
  return map[t] || ['note', type ? (type.charAt(0).toUpperCase() + type.slice(1)) : 'Notă']
}

export function renderMarkdown(src) {
  let text = String(src || '').replace(/\r\n/g, '\n')
  // Strip frontmatter YAML si comentarii Obsidian %% %%.
  text = text.replace(/^---\n[\s\S]*?\n---\n?/, '')
  text = text.replace(/%%[\s\S]*?%%/g, '')
  const lines = text.split('\n')
  const out = []
  let i = 0, inCode = false, codeBuf = []
  const listStack = []
  const closeLists = () => { while (listStack.length) out.push('</' + listStack.pop() + '>') }

  while (i < lines.length) {
    const line = lines[i]
    const fence = line.match(/^```(.*)$/)
    if (fence) {
      if (inCode) { out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>'); inCode = false; codeBuf = [] }
      else { closeLists(); inCode = true }
      i++; continue
    }
    if (inCode) { codeBuf.push(line); i++; continue }
    if (line.trim() === '') { closeLists(); i++; continue }

    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) { closeLists(); const lvl = Math.min(h[1].length, 3); out.push(`<h${lvl}>${mdInline(h[2])}</h${lvl}>`); i++; continue }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) { closeLists(); out.push('<hr>'); i++; continue }

    if (/^>\s?/.test(line)) {
      closeLists()
      const quote = []
      while (i < lines.length && /^>\s?/.test(lines[i])) { quote.push(lines[i].replace(/^>\s?/, '')); i++ }
      // Callout Obsidian: prima linie e [!type] titlu-optional.
      const cm = quote[0] && quote[0].match(/^\[!(\w+)\][+-]?\s*(.*)$/)
      if (cm) {
        const meta = _calloutMeta(cm[1])
        const ctitle = cm[2].trim() || meta[1]
        const body = quote.slice(1).join('\n').trim()
        out.push(`<div class="md-callout md-callout-${meta[0]}">`
          + `<div class="md-callout-title">${mdInline(ctitle)}</div>`
          + (body ? `<div class="md-callout-body">${renderMarkdown(body)}</div>` : '')
          + '</div>')
      } else {
        out.push('<blockquote>' + renderMarkdown(quote.join('\n')) + '</blockquote>')
      }
      continue
    }

    // Tabel: rand header cu pipes + rand separator cu liniute.
    if (line.includes('|') && i + 1 < lines.length &&
        /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      closeLists()
      const cells = r => r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim())
      const head = cells(line)
      i += 2
      let tbl = '<table><thead><tr>' + head.map(c => `<th>${mdInline(c)}</th>`).join('') + '</tr></thead><tbody>'
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        tbl += '<tr>' + cells(lines[i]).map(c => `<td>${mdInline(c)}</td>`).join('') + '</tr>'
        i++
      }
      out.push(tbl + '</tbody></table>')
      continue
    }

    const ul = line.match(/^(\s*)[-*+]\s+(.*)$/)
    const ol = line.match(/^(\s*)\d+\.\s+(.*)$/)
    if (ul || ol) {
      const type = ul ? 'ul' : 'ol'
      if (listStack[listStack.length - 1] !== type) { closeLists(); out.push('<' + type + '>'); listStack.push(type) }
      const content = ul ? ul[2] : ol[2]
      const task = content.match(/^\[([ xX])\]\s+(.*)$/)
      if (task) out.push(`<li><input type="checkbox" disabled ${task[1] !== ' ' ? 'checked' : ''}> ${mdInline(task[2])}</li>`)
      else out.push('<li>' + mdInline(content) + '</li>')
      i++; continue
    }

    closeLists()
    const para = [line]; i++
    while (i < lines.length && lines[i].trim() !== '' &&
           !/^(#{1,6}\s|```|>\s?|\s*[-*+]\s|\s*\d+\.\s)/.test(lines[i]) &&
           !/^(-{3,}|\*{3,}|_{3,})$/.test(lines[i].trim())) {
      para.push(lines[i]); i++
    }
    out.push('<p>' + mdInline(para.join('\n')).replace(/\n/g, '<br>') + '</p>')
  }
  closeLists()
  if (inCode) out.push('<pre><code>' + escapeHtml(codeBuf.join('\n')) + '</code></pre>')
  return out.join('\n')
}
