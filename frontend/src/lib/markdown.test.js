// Rendererul de markdown: ce ajunge in `{@html}` din notele vault-ului.
//
// De ce are test: iesirea lui intra NEFILTRATA in pagina (`MarkdownView.svelte`), deci
// orice scapa de aici e script care ruleaza cu sesiunea lui Ion. Doua garzi, amandoua
// testate: textul se escapeaza INAINTE de orice substitutie, iar un link nu poate duce
// la o schema care executa cod. A doua avea o gaura pana pe 2026-09-28: era o lista de
// INTERDICTII verificata pe textul brut, iar browserul sterge caracterele de control
// din fata unui URL — deci `\u0001javascript:` trecea de regex si ramanea `javascript:`
// pentru browser.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { renderMarkdown } from './markdown.js'

const href = (md) => {
  const m = renderMarkdown(md).match(/href="([^"]*)"/)
  return m ? m[1] : null
}
const src = (md) => {
  const m = renderMarkdown(md).match(/src="([^"]*)"/)
  return m ? m[1] : null
}

test('HTML-ul din nota se escapeaza, nu se executa', () => {
  const out = renderMarkdown('<script>alert(1)</script> si <img src=x onerror=alert(1)>')
  assert.ok(!out.includes('<script>'), out)
  assert.ok(!out.includes('<img src=x'), out)
  assert.ok(out.includes('&lt;script&gt;'), out)
})

test('linkurile obisnuite raman', () => {
  assert.equal(href('[site](https://abb.com/drives)'), 'https://abb.com/drives')
  assert.equal(href('[mail](mailto:ion@example.com)'), 'mailto:ion@example.com')
  assert.equal(href('[nota](proiecte/26_205.md)'), 'proiecte/26_205.md')
  assert.equal(href('[ancora](#sus)'), '#sus')
})

test('schemele care executa cod devin „#"', () => {
  for (const rau of [
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    'data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==',
    'vbscript:msgbox(1)',
    'file:///C:/Windows/win.ini',
  ]) {
    assert.equal(href(`[x](${rau})`), '#', rau)
    assert.equal(src(`![x](${rau})`), '#', 'imagine: ' + rau)
  }
})

test('caracterele de control din fata schemei nu o ascund', () => {
  // Browserul sterge C0 + spatiu din capul URL-ului: pentru el, astea sunt `javascript:`.
  for (const c of ['\u0001', '\u0000', '\u001f']) {
    assert.equal(href(`[x](${c}javascript:alert(1))`), '#', JSON.stringify(c))
  }
})

test('o schema necunoscuta nu trece (lista e de scheme PERMISE)', () => {
  assert.equal(href('[x](ms-settings:privacy)'), '#')
})

test('ghilimelele nu pot rupe atributul', () => {
  const out = renderMarkdown('[x](https://a.ro"onmouseover="alert(1))')
  assert.ok(!/href="[^"]*"\s*onmouseover/.test(out), out)
})

test('wikilink cu alias', () => {
  const out = renderMarkdown('vezi [[Biochem Podari|Podari]]')
  assert.ok(out.includes('data-wikilink="Biochem Podari"'), out)
  assert.ok(out.includes('>Podari</span>'), out)
})
