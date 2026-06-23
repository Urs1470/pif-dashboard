// Diagrame schematice de regim de serviciu (IEC 60034-1), REDESENATE ca SVG
// (vectorial, in tema aplicatiei, fara raster cu copyright). 3 panouri pe aceeasi
// axa de timp: P (sarcina), Pv (pierderi electrice), Theta (temperatura).
// Generator parametric: fiecare regim = o lista de faze {kind, w, p}.
//   kind: 'load' | 'rest' (deconectat) | 'noload' (mers in gol) | 'start' | 'brake'
//   w = latime relativa, p = nivel de sarcina (0..~1.2)

const HOT = '#e69875' // curba de temperatura — portocaliu Everforest

function dutyFigure(phases, opts = {}) {
  const W = 480, padL = 30, padR = 14, padT = 8
  const strip = 22            // banda de sus pt Tc/Δtp/Δtr
  const ph = 60, gap = 15     // inaltime panou + spatiu intre panouri
  const capH = 20             // legenda jos
  const tau = opts.tau ?? 0.5 // constanta termica relativa la timpul total
  const pv0 = opts.pv0 ?? 0.18
  const total = phases.reduce((s, p) => s + p.w, 0)
  const H = padT + strip + 3 * ph + 2 * gap + capH
  const x0 = padL, x1 = W - padR
  const sx = (t) => x0 + (t / total) * (x1 - x0)
  const top = (i) => padT + strip + i * (ph + gap)
  const ymax = 1.35
  const sy = (i, v) => top(i) + ph - (v / ymax) * (ph - 7)

  const pOf = (p) => (p.kind === 'rest' || p.kind === 'noload') ? 0 : (p.kind === 'start' || p.kind === 'brake') ? 1.18 : (p.p ?? 1)
  const pvOf = (p) => p.kind === 'rest' ? 0 : p.kind === 'noload' ? pv0 : (p.kind === 'start' || p.kind === 'brake') ? 1.25 : (p.p ?? 1) ** 2

  // boundaries
  const bnd = [0]; { let t = 0; for (const p of phases) { t += p.w; bnd.push(t) } }
  const phaseAt = (tt) => { let acc = 0; for (const p of phases) { acc += p.w; if (tt <= acc + 1e-9) return p } return phases[phases.length - 1] }

  // path treapta pt P / Pv
  function stepPath(i, valOf) {
    let t = 0, d = `M ${sx(0).toFixed(1)} ${sy(i, 0).toFixed(1)}`
    for (const p of phases) { const v = valOf(p); d += ` L ${sx(t).toFixed(1)} ${sy(i, v).toFixed(1)} L ${sx(t + p.w).toFixed(1)} ${sy(i, v).toFixed(1)}`; t += p.w }
    return d + ` L ${sx(t).toFixed(1)} ${sy(i, 0).toFixed(1)}`
  }

  // curba theta (integrare exponentiala monoconstanta)
  const N = 240; let th = 0, thMax = 0; const raw = []
  for (let k = 0; k <= N; k++) {
    const tt = (k / N) * total
    const thInf = pvOf(phaseAt(tt))
    th = thInf + (th - thInf) * Math.exp(-(total / N) / (tau * total))
    raw.push([tt, th]); if (th > thMax) thMax = th
  }
  const thScale = thMax > 0 ? 1.15 / thMax : 1
  const thPts = raw.map(([tt, v]) => `${sx(tt).toFixed(1)},${sy(2, v * thScale).toFixed(1)}`).join(' ')
  const yThMax = sy(2, thMax * thScale)

  // panouri: baseline + label
  const labels = ['P', 'Pᵥ', 'Θ']
  let panels = ''
  for (let i = 0; i < 3; i++) {
    const yb = sy(i, 0)
    panels += `<line x1="${x0}" y1="${top(i) - 2}" x2="${x0}" y2="${yb}" stroke="var(--text-dim)" stroke-width="1"/>`
    panels += `<line x1="${x0}" y1="${yb}" x2="${x1}" y2="${yb}" stroke="var(--text-dim)" stroke-width="1"/>`
    panels += `<text x="${x0 - 7}" y="${top(i) + 9}" text-anchor="end" font-size="11" font-style="italic" fill="var(--text)">${labels[i]}</text>`
  }
  // P si Pv (umplute), Θ (linie)
  panels += `<path d="${stepPath(0, pOf)}" fill="var(--accent-subtle)" stroke="var(--accent)" stroke-width="1.6"/>`
  panels += `<path d="${stepPath(1, pvOf)}" fill="color-mix(in srgb, var(--accent) 12%, transparent)" stroke="var(--accent)" stroke-width="1.3" opacity="0.8"/>`
  panels += `<line x1="${x0}" y1="${yThMax}" x2="${x1}" y2="${yThMax}" stroke="${HOT}" stroke-width="0.8" stroke-dasharray="3 3" opacity="0.7"/>`
  panels += `<text x="${x1}" y="${yThMax - 3}" text-anchor="end" font-size="9" fill="${HOT}">Θmax</text>`
  panels += `<polyline points="${thPts}" fill="none" stroke="${HOT}" stroke-width="1.8"/>`

  // ghidaje verticale la boundary-urile primului ciclu + brackets Tc/Δtp/Δtr
  let guides = '', brackets = ''
  const cyc = opts.cycleBnd || (bnd.length >= 3 ? [bnd[0], bnd[1], bnd[2]] : [bnd[0], bnd[bnd.length - 1]])
  for (const b of cyc) guides += `<line x1="${sx(b).toFixed(1)}" y1="${top(0) - 4}" x2="${sx(b).toFixed(1)}" y2="${sy(2, 0)}" stroke="var(--border)" stroke-width="0.8" stroke-dasharray="2 3"/>`
  const yb0 = padT + strip - 8
  const bracket = (a, b, lbl) => {
    const xa = sx(a), xb = sx(b), xm = (xa + xb) / 2
    return `<line x1="${xa.toFixed(1)}" y1="${yb0}" x2="${xb.toFixed(1)}" y2="${yb0}" stroke="var(--text-dim)" stroke-width="0.9"/>`
      + `<line x1="${xa.toFixed(1)}" y1="${yb0 - 3}" x2="${xa.toFixed(1)}" y2="${yb0 + 3}" stroke="var(--text-dim)" stroke-width="0.9"/>`
      + `<line x1="${xb.toFixed(1)}" y1="${yb0 - 3}" x2="${xb.toFixed(1)}" y2="${yb0 + 3}" stroke="var(--text-dim)" stroke-width="0.9"/>`
      + `<text x="${xm.toFixed(1)}" y="${yb0 - 4}" text-anchor="middle" font-size="9.5" fill="var(--text-secondary)">${lbl}</text>`
  }
  if (cyc.length >= 3) {
    brackets += bracket(cyc[0], cyc[2], 'Tc')
    // Δtp (faza de lucru) si Δtr (pauza) — pe panoul P, mai jos
    const yp = top(0) + ph + 4
    const seg = (a, b, lbl) => { const xm = (sx(a) + sx(b)) / 2; return `<text x="${xm.toFixed(1)}" y="${yp}" text-anchor="middle" font-size="9" fill="var(--text-dim)">${lbl}</text>` }
    brackets += seg(cyc[0], cyc[1], opts.lblP || 'Δtp')
    brackets += seg(cyc[1], cyc[2], opts.lblR || 'Δtr')
  } else {
    brackets += bracket(cyc[0], cyc[cyc.length - 1], 'T')
  }

  const caption = `<text x="${W / 2}" y="${H - 5}" text-anchor="middle" font-size="10.5" fill="var(--text-secondary)">${opts.caption || ''}</text>`

  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" width="100%" style="max-width:480px" role="img" aria-label="${opts.caption || 'diagrama regim'}">`
    + guides + panels + brackets + caption + `</svg>`
}

// --- definitii de regim (faze pe ~2,5 cicluri) ---
const FIGURES = {
  S1: dutyFigure([{ kind: 'load', w: 10, p: 1 }], { tau: 0.13, cycleBnd: [0, 10], caption: 'S1 — continuu: Θ ajunge la echilibru' }),
  S2: dutyFigure([{ kind: 'load', w: 3, p: 1 }, { kind: 'rest', w: 8 }], { tau: 0.5, cycleBnd: [0, 3, 11], lblP: 'ΔtP', lblR: 'repaus', caption: 'S2 — scurt: sarcina < echilibru, apoi repaus' }),
  S3: dutyFigure([{ kind: 'load', w: 2.2, p: 1 }, { kind: 'rest', w: 2 }, { kind: 'load', w: 2.2, p: 1 }, { kind: 'rest', w: 2 }, { kind: 'load', w: 2.2, p: 1 }, { kind: 'rest', w: 2 }], { tau: 0.42, caption: 'S3 — intermitent, repaus deconectat · CDF = Δtp/Tc' }),
  S6: dutyFigure([{ kind: 'load', w: 2.2, p: 1 }, { kind: 'noload', w: 2 }, { kind: 'load', w: 2.2, p: 1 }, { kind: 'noload', w: 2 }, { kind: 'load', w: 2.2, p: 1 }, { kind: 'noload', w: 2 }], { tau: 0.42, lblR: 'Δtv', caption: 'S6 — continuu cu mers in gol (Pv≠0) · CDF = Δtp/Tc' }),
}

// cheie marime -> figura (afisata in modalul termenului)
const FIG_FOR = {
  Ps1: 'S1', PS2: 'S2', tP: 'S2', PS3: 'S3', DC: 'S3', CDFcalc: 'S3', tload: 'S3', tpauza: 'S3', kp: 'S3',
  PS6: 'S6', k0: 'S6', Pech: 'S6',
}

export { FIGURES, FIG_FOR, dutyFigure }
