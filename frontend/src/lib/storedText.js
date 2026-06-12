// Rendering helpers for user-entered rich text stored as HTML (from RichTextEditor)
// or legacy plain text. Shared by ProjectDetail (observatii/service fields) and task notes.

const SAFE_TAGS = new Set(['P', 'BR', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'LI', 'STRONG', 'B', 'EM', 'I', 'U', 'A', 'HR', 'BLOCKQUOTE', 'SPAN'])

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
          for (const a of Array.from(child.attributes)) {
            if (child.tagName === 'A' && a.name === 'href') continue
            child.removeAttribute(a.name)
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
