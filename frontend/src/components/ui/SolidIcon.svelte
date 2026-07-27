<script>
  // Solid icon set (custom — Lucide is outline-only). Used for navigation +
  // feature/action icons that read well filled. Small affordance icons
  // (plus, chevron, search, x, paperclip, download…) stay Lucide outline.
  // Color follows `currentColor`; interior detail uses evenodd holes so
  // cutouts stay transparent on any background.
  let { name, size = 20, class: klass = '' } = $props()

  const ICONS = {
    // — navigation —
    home: { d: 'M11.3 2.7a1 1 0 0 1 1.4 0l8.6 7.5a1 1 0 0 1 .34.76V20a1.5 1.5 0 0 1-1.5 1.5h-4.3v-6a1 1 0 0 0-1-1h-3.6a1 1 0 0 0-1 1v6H4.85A1.5 1.5 0 0 1 3.35 20v-9.04a1 1 0 0 1 .34-.76z' },
    projects: { d: 'M4 4h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z M7.5 11h1.6v5H7.5z M11.2 11h1.6v3H11.2z M14.9 11h1.6v6.5H14.9z' },
    tasks: { d: 'M4.5 4h4A1.5 1.5 0 0 1 10 5.5v3A1.5 1.5 0 0 1 8.5 10h-4A1.5 1.5 0 0 1 3 8.5v-3A1.5 1.5 0 0 1 4.5 4z M5.4 6.7l1.1 1.1 2.1-2.3.95.9-3.05 3.3-2-2z', add: ['M13 6h7', 'M13 12h7', 'M13 18h7', 'M4 15h6'] },
    calculator: { d: 'M6 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M8 6h8v3.5H8z M8.5 13a1 1 0 1 0 0 2 1 1 0 0 0 0-2z M12 13a1 1 0 1 0 0 2 1 1 0 0 0 0-2z M15.5 13a1 1 0 1 0 0 2 1 1 0 0 0 0-2z M8.5 16.7a1 1 0 1 0 0 2 1 1 0 0 0 0-2z M12 16.7a1 1 0 1 0 0 2 1 1 0 0 0 0-2z M15.5 16.7a1 1 0 1 0 0 2 1 1 0 0 0 0-2z' },
    notes: { d: 'M5 3h9l6 6v10a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19V4.5A1.5 1.5 0 0 1 5 3z M14 3.4 19.6 9H15a1 1 0 0 1-1-1z' },
    admin: { d: 'M19.4 13a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z M12 9.3a2.7 2.7 0 1 0 0 5.4 2.7 2.7 0 0 0 0-5.4z' },
    menu: { add: ['M4 7h16', 'M4 12h16', 'M4 17h16'] },
    // — feature / action —
    cpu: { d: 'M7 6h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z M10 10h4v4h-4z', add: ['M9 3v3', 'M15 3v3', 'M9 18v3', 'M15 18v3', 'M3 9h3', 'M3 15h3', 'M18 9h3', 'M18 15h3'] },
    // Planificator: calendar cu bare de timeline (gantt) inauntru.
    plan: { d: 'M5 3h1.5v2H5zM17.5 3H19v2h-1.5z M4 6h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z M6.5 10.2h6v1.8h-6z M9.5 13.6h7v1.8h-7z M6.5 17h4.5v1.8H6.5z' },
    // Calendar personal: rama de calendar cu grila de zile (goluri evenodd).
    calendar: { d: 'M5 3h1.5v2H5zM17.5 3H19v2h-1.5z M4 6h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z M6.8 11h2.4v2.3H6.8z M10.8 11h2.4v2.3h-2.4z M14.8 11h2.4v2.3h-2.4z M6.8 15h2.4v2.3H6.8z M10.8 15h2.4v2.3h-2.4z' },
    file: { d: 'M6 2h7l5 5v12.5A1.5 1.5 0 0 1 16.5 21h-9A1.5 1.5 0 0 1 6 19.5V3.5A1.5 1.5 0 0 1 6 2z M13 2.4 18 7.4h-4a1 1 0 0 1-1-1z M8.4 11.3h7.2v1.4H8.4z M8.4 14.6h7.2v1.4H8.4z M8.4 17.9h4.6v1.4H8.4z' },
    pencil: { d: 'M16.7 3.5a1.9 1.9 0 0 1 2.7 0l1.1 1.1a1.9 1.9 0 0 1 0 2.7l-1.3 1.3-3.8-3.8zM13.9 6.3 4 16.2V20h3.8l9.9-9.9z' },
    trash: { d: 'M9 2.5h6a1 1 0 0 1 1 1V5h4v2H4V5h4V3.5a1 1 0 0 1 1-1z M6 8h12l-.9 11.6A1.5 1.5 0 0 1 15.6 21H8.4a1.5 1.5 0 0 1-1.5-1.4zM9.7 11h1.3v7H9.7z M13 11h1.3v7H13z' },
    clock: { d: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M11.2 6.9h1.5v5.4H16v1.5h-4.8z' },
    star: { d: 'M12 2.5l2.9 5.9 6.5.95-4.7 4.6 1.1 6.45L12 17.9 6.1 21l1.1-6.45-4.7-4.6 6.5-.95z' },
    play: { d: 'M7 4.7a1 1 0 0 1 1.5-.87l11 7.3a1 1 0 0 1 0 1.74l-11 7.3A1 1 0 0 1 7 19.3z' },
    stop: { d: 'M7 5h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z' },
    check: { d: 'M12 2.6a9.4 9.4 0 1 0 0 18.8 9.4 9.4 0 0 0 0-18.8z M10.6 14.7 7.6 11.7l1.2-1.2 1.8 1.8 4.2-4.2 1.2 1.2z' },
  }

  const icon = $derived(ICONS[name])
</script>

{#if icon}
  <svg width={size} height={size} viewBox="0 0 24 24" class={klass} aria-hidden="true">
    {#if icon.d}
      <path d={icon.d} fill="currentColor" fill-rule="evenodd" />
    {/if}
    {#if icon.add}
      <g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        {#each icon.add as p}<path d={p} />{/each}
      </g>
    {/if}
  </svg>
{/if}
