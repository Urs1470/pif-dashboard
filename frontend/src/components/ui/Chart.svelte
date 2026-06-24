<script>
  // Grafic linie SVG interactiv. Primeste un obiect `chart`:
  //   { xLabel, yLabel, series:[{label,color,dash?,points:[{x,y}]}],
  //     markers?:[{label,color,x,y}], zones?:[{x0,x1,label,color}], desc?:{ce,atentie} }
  let { chart } = $props()

  const W = 520, H = 240, L = 48, R = 14, T = 12, B = 32

  // imparte o eticheta in segmente normale/indice/exponent: "I_2", "f_{sw}", "n^2"
  function parseLabel(s) {
    const segs = []
    let i = 0
    while (i < s.length) {
      const ch = s[i]
      if (ch === '_' || ch === '^') {
        const kind = ch === '_' ? 'sub' : 'sup'
        i++
        let t = ''
        if (s[i] === '{') { i++; while (i < s.length && s[i] !== '}') t += s[i++]; i++ }
        else { t = s[i] || ''; i++ }
        segs.push({ kind, t })
      } else {
        let t = ''
        while (i < s.length && s[i] !== '_' && s[i] !== '^') t += s[i++]
        segs.push({ kind: 'n', t })
      }
    }
    return segs
  }

  // axa cu valori rotunde (1/2/5 ×10^n)
  function niceNum(x, round) {
    const v = x > 0 ? x : 1
    const exp = Math.floor(Math.log10(v))
    const f = v / 10 ** exp
    let nf
    if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10
    else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10
    return nf * 10 ** exp
  }
  function niceAxis(lo, hi, maxTicks) {
    if (!(hi > lo)) hi = lo + 1
    const step = niceNum(niceNum(hi - lo, false) / Math.max(1, maxTicks - 1), true)
    const nlo = Math.floor(lo / step) * step
    const nhi = Math.ceil(hi / step) * step
    const ticks = []
    for (let t = nlo; t <= nhi + step * 0.5; t += step) ticks.push(+t.toPrecision(12))
    const minor = []
    for (let t = nlo; t <= nhi + 1e-9; t += step / 5) minor.push(t)
    return { lo: nlo, hi: nhi, step, ticks, minor }
  }

  let hover = $state(null)
  let svgEl

  const d = $derived.by(() => {
    const c = chart
    if (!c) return null
    const all = []
    for (const s of c.series || []) for (const p of s.points || []) all.push(p)
    for (const m of c.markers || []) all.push(m)
    if (all.length < 2) return null
    let xmin = Math.min(...all.map((p) => p.x)), xmax = Math.max(...all.map((p) => p.x))
    let ymin = Math.min(...all.map((p) => p.y)), ymax = Math.max(...all.map((p) => p.y))
    if (xmin > 0) xmin = 0
    if (ymin > 0) ymin = 0
    for (const z of c.zones || []) { xmin = Math.min(xmin, z.x0); xmax = Math.max(xmax, z.x1) }
    const ax = niceAxis(xmin, xmax, 6), ay = niceAxis(ymin, ymax, 5)
    const plotW = W - L - R, plotH = H - T - B
    const xp = (x) => L + ((x - ax.lo) / (ax.hi - ax.lo)) * plotW
    const yp = (y) => T + plotH - ((y - ay.lo) / (ay.hi - ay.lo)) * plotH
    const xinv = (px) => ax.lo + ((px - L) / plotW) * (ax.hi - ax.lo)
    const path = (pts) => pts.map((p, i) => (i ? 'L' : 'M') + xp(p.x).toFixed(1) + ' ' + yp(p.y).toFixed(1)).join(' ')
    const fmt = (v) => { const a = Math.abs(v); const dec = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 1 : a > 0 ? 2 : 0; return v.toLocaleString('ro-RO', { maximumFractionDigits: dec }) }
    return { c, xp, yp, xinv, path, xticks: ax.ticks, yticks: ay.ticks, xminor: ax.minor, yminor: ay.minor, fmt, xlbl: parseLabel(c.xLabel || ''), ylbl: parseLabel(c.yLabel || ''), plotW, plotH }
  })

  function onMove(e) {
    if (!d || !svgEl) return
    const rect = svgEl.getBoundingClientRect()
    const vbx = ((e.clientX - rect.left) / rect.width) * W
    if (vbx < L - 1 || vbx > W - R + 1) { hover = null; return }
    const dataX = d.xinv(vbx)
    let snapX = dataX, bd0 = Infinity
    const s0 = (d.c.series || [])[0]
    if (s0) for (const p of s0.points || []) { const dd = Math.abs(p.x - dataX); if (dd < bd0) { bd0 = dd; snapX = p.x } }
    const items = (d.c.series || []).map((s) => {
      let best = (s.points || [])[0], bd = Infinity
      for (const p of s.points || []) { const dd = Math.abs(p.x - snapX); if (dd < bd) { bd = dd; best = p } }
      return { label: s.label, color: s.color, y: best ? best.y : null }
    })
    hover = { x: snapX, px: d.xp(snapX), items }
  }
  function onLeave() { hover = null }
</script>

{#if d}
  <div class="chart">
    <div class="legend">
      {#each d.c.series as s}
        <span class="lg"><span class="sw" class:dash={s.dash} style="--c:{s.color}"></span>{s.label}</span>
      {/each}
      {#each d.c.markers || [] as m}
        <span class="lg"><span class="dot" style="--c:{m.color}"></span>{m.label}</span>
      {/each}
    </div>
    <svg bind:this={svgEl} viewBox="0 0 {W} {H}" role="img" aria-label="{d.c.yLabel} in functie de {d.c.xLabel}" onmousemove={onMove} onmouseleave={onLeave}>
      {#each d.c.zones || [] as z}
        <rect x={d.xp(z.x0)} y={T} width={Math.max(0, d.xp(z.x1) - d.xp(z.x0))} height={H - T - B} fill={z.color || 'var(--accent)'} opacity="0.07" />
        <text x={(d.xp(z.x0) + d.xp(z.x1)) / 2} y={T + 10} class="zone-lbl" text-anchor="middle" fill={z.color || 'var(--accent)'}>{z.label}</text>
      {/each}
      {#each d.xminor as gx}
        <line x1={d.xp(gx)} y1={T} x2={d.xp(gx)} y2={H - B} class="grid-minor" />
      {/each}
      {#each d.yminor as gy}
        <line x1={L} y1={d.yp(gy)} x2={W - R} y2={d.yp(gy)} class="grid-minor" />
      {/each}
      {#each d.xticks as tx}
        <line x1={d.xp(tx)} y1={T} x2={d.xp(tx)} y2={H - B} class="grid-major" />
        <text x={d.xp(tx)} y={H - B + 16} class="tick" text-anchor="middle">{d.fmt(tx)}</text>
      {/each}
      {#each d.yticks as ty}
        <line x1={L} y1={d.yp(ty)} x2={W - R} y2={d.yp(ty)} class="grid-major" />
        <text x={L - 6} y={d.yp(ty) + 3} class="tick" text-anchor="end">{d.fmt(ty)}</text>
      {/each}
      <line x1={L} y1={T} x2={L} y2={H - B} class="axis" />
      <line x1={L} y1={H - B} x2={W - R} y2={H - B} class="axis" />
      {#each d.c.series as s}
        <path d={d.path(s.points)} fill="none" stroke={s.color} stroke-width="2.2" stroke-dasharray={s.dash ? '6 4' : null} stroke-linejoin="round" />
      {/each}
      {#each d.c.markers || [] as m}
        <circle cx={d.xp(m.x)} cy={d.yp(m.y)} r="4.5" fill={m.color} stroke="var(--bg-surface)" stroke-width="1.5" />
      {/each}
      {#if hover}
        <line x1={hover.px} y1={T} x2={hover.px} y2={H - B} class="cross" />
        {#each hover.items as it}
          {#if it.y != null}<circle cx={hover.px} cy={d.yp(it.y)} r="3.5" fill={it.color} stroke="var(--bg-surface)" stroke-width="1.2" />{/if}
        {/each}
        <g transform="translate({hover.px > W / 2 ? L + 4 : W - R - 116}, {T + 4})">
          <rect width="112" height={14 + hover.items.length * 12} rx="3" class="tip-bg" />
          <text x="6" y="11" class="tip-x">{d.c.xLabel.replace(/[_^{}]/g, '')}: {d.fmt(hover.x)}</text>
          {#each hover.items as it, i}
            <text x="6" y={24 + i * 12} class="tip-v"><tspan fill={it.color}>■ </tspan>{d.fmt(it.y)}</text>
          {/each}
        </g>
      {/if}
      <text x={(L + W - R) / 2} y={H - 4} class="axlbl" text-anchor="middle">{#each d.xlbl as g}{#if g.kind === 'sub'}<tspan class="ss" baseline-shift="sub">{g.t}</tspan>{:else if g.kind === 'sup'}<tspan class="ss" baseline-shift="super">{g.t}</tspan>{:else}<tspan>{g.t}</tspan>{/if}{/each}</text>
      <text x="11" y={(T + H - B) / 2} class="axlbl" text-anchor="middle" transform="rotate(-90 11 {(T + H - B) / 2})">{#each d.ylbl as g}{#if g.kind === 'sub'}<tspan class="ss" baseline-shift="sub">{g.t}</tspan>{:else if g.kind === 'sup'}<tspan class="ss" baseline-shift="super">{g.t}</tspan>{:else}<tspan>{g.t}</tspan>{/if}{/each}</text>
    </svg>
    {#if d.c.desc}
      <p class="chart-desc"><span class="cd-l">Ce arata:</span> {d.c.desc.ce} <span class="cd-l cd-w">Atentie:</span> {d.c.desc.atentie}</p>
    {/if}
  </div>
{/if}

<style>
  .chart { margin-top: var(--space-sm); border-top: 1px solid var(--border); padding-top: var(--space-sm); }
  .legend { display: flex; flex-wrap: wrap; gap: 10px; font-size: var(--font-tiny); color: var(--text-secondary); margin-bottom: 4px; }
  .lg { display: flex; align-items: center; gap: 5px; }
  .sw { width: 14px; height: 3px; border-radius: 2px; background: var(--c); }
  .sw.dash { background: repeating-linear-gradient(90deg, var(--c) 0 5px, transparent 5px 9px); }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--c); }
  svg { width: 100%; height: auto; display: block; }
  .grid-minor { stroke: var(--border); stroke-width: 0.5; opacity: 0.2; }
  .grid-major { stroke: var(--border); stroke-width: 1; opacity: 0.5; }
  .axis { stroke: var(--border); stroke-width: 1.2; }
  .tick { fill: var(--text-dim); font-size: 10px; font-family: var(--font-mono); }
  .axlbl { fill: var(--text-secondary); font-size: 11px; }
  .ss { font-size: 0.72em; }
  .zone-lbl { font-size: 9px; font-weight: 600; opacity: 0.85; }
  .cross { stroke: var(--text-dim); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0.7; }
  .tip-bg { fill: var(--bg-surface); stroke: var(--border); stroke-width: 1; opacity: 0.96; }
  .tip-x { fill: var(--text); font-size: 9.5px; font-weight: 600; font-family: var(--font-mono); }
  .tip-v { fill: var(--text-secondary); font-size: 9.5px; font-family: var(--font-mono); }
  .chart-desc { font-size: var(--font-tiny); color: var(--text-secondary); line-height: 1.45; margin-top: 6px; }
  .cd-l { font-weight: 700; color: var(--text); }
  .cd-w { color: #e69875; margin-left: 2px; }
</style>
