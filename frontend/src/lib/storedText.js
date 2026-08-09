// Rendering helpers for user-entered rich text stored as HTML (from RichTextEditor)
// or legacy plain text. Shared by ProjectDetail (observatii/service fields) and task notes.

const SAFE_TAGS = new Set([
  'P', 'BR', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'LI',
  // S/STRIKE/DEL: butonul „Tăiat" din editor (execCommand strikeThrough) produce
  // <strike> (Chrome/Safari) sau <s>; fara ele aici, sanitizarea de la salvare
  // dezbraca tagul si formatarea disparea in tacere la round-trip.
  'STRONG', 'B', 'EM', 'I', 'U', 'S', 'STRIKE', 'DEL', 'A', 'HR', 'BLOCKQUOTE', 'SPAN',
  // tables — users paste finished tables from Word/Excel/web
  'TABLE', 'THEAD', 'TBODY', 'TFOOT', 'TR', 'TD', 'TH', 'CAPTION', 'COLGROUP', 'COL',
])

// Attributes kept per tag (everything else is stripped). Tables need span attrs
// so pasted merged cells keep their layout.
const KEEP_ATTRS = {
  A: new Set(['href']),
  TD: new Set(['colspan', 'rowspan']),
  TH: new Set(['colspan', 'rowspan']),
  COL: new Set(['span']),
  COLGROUP: new Set(['span']),
}

export function sanitizeHtml(html) {
  const tmp = document.createElement('div')
  tmp.innerHTML = html
  ;(function walk(node) {
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === 1) {
        if (!SAFE_TAGS.has(child.tagName)) {
          while (child.firstChild) node.insertBefore(child.firstChild, child)
          child.remove()
        } else {
          const keep = KEEP_ATTRS[child.tagName]
          for (const a of Array.from(child.attributes)) {
            if (keep && keep.has(a.name.toLowerCase())) continue
            child.removeAttribute(a.name)
          }
          // href pastrat doar cu scheme sigure — javascript:/data: etc. ar fi
          // XSS stocat la click (poate veni din paste sau dintr-un backup)
          if (child.tagName === 'A' && child.hasAttribute('href')) {
            const href = (child.getAttribute('href') || '').trim()
            if (!/^(https?:|mailto:|tel:|\/|#)/i.test(href)) child.removeAttribute('href')
          }
          walk(child)
        }
      }
    }
  })(tmp)
  return tmp.innerHTML
}

export function renderStoredText(raw) {
  if (!raw || !raw.trim()) return ''
  if (/<\/?[a-z][\s\S]*>/i.test(raw)) return sanitizeHtml(raw)
  return raw.split(/\n\n+/).map(p => '<p>' + p.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>') + '</p>').join('')
}
