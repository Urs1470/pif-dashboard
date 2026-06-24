<script>
  // Grafic linie SVG, fara dependinte. Primeste un obiect `chart`:
  //   { xLabel, yLabel, series:[{label,color,dash?,points:[{x,y}]}], markers?:[{label,color,x,y}] }
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
    if (xmax === xmin) xmax = xmin + 1
    if (ymax === ymin) ymax = ymin + 1
    ymax += (ymax - ymin) * 0.08
    const plotW = W - L - R, plotH = H - T - B
    const xp = (x) => L + ((x - xmin) / (xmax - xmin)) * plotW
    const yp = (y) => T + plotH - ((y - ymin) / (ymax - ymin)) * plotH
    const path = (pts) => pts.map((p, i) => (i ? 'L' : 'M') + xp(p.x).toFixed(1) + ' ' + yp(p.y).toFixed(1)).join(' ')
    const ticks = (lo, hi, n) => Array.from({ length: n + 1 }, (_, i) => lo + ((hi - lo) * i) / n)
    const fmt = (v) => { const a = Math.abs(v); const dec = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 1 : 2; return v.toLocaleString('ro-RO', { maximumFractionDigits: dec }) }
    // grila majora = la diviziunile etichetate; grila minora = fiecare diviziune impartita in 5 (aspect milimetric)
    return { c, xp, yp, path, xticks: ticks(xmin, xmax, 5), yticks: ticks(ymin, ymax, 4), xminor: ticks(xmin, xmax, 50), yminor: ticks(ymin, ymax, 20), fmt, xlbl: parseLabel(c.xLabel || ''), ylbl: parseLabel(c.yLabel || '') }
  })
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
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="{d.c.yLabel} in functie de {d.c.xLabel}">
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
  .chart-desc { font-size: var(--font-tiny); color: var(--text-secondary); line-height: 1.45; margin-top: 6px; }
  .cd-l { font-weight: 700; color: var(--text); }
  .cd-w { color: #e69875; margin-left: 2px; }
  .grid-minor { stroke: var(--border); stroke-width: 0.5; opacity: 0.2; }
  .grid-major { stroke: var(--border); stroke-width: 1; opacity: 0.5; }
  .axis { stroke: var(--border); stroke-width: 1.2; }
  .tick { fill: var(--text-dim); font-size: 10px; font-family: var(--font-mono); }
  .axlbl { fill: var(--text-secondary); font-size: 11px; }
  .ss { font-size: 0.72em; }
</style>
