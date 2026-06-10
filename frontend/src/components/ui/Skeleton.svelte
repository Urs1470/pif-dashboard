<script>
  let { width = '100%', height = '20px', rounded = false } = $props()
</script>

<div
  class="skeleton"
  class:rounded
  style="width: {width}; height: {height}"
></div>

<style>
  .skeleton {
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    position: relative;
    overflow: hidden;
  }
  .skeleton::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent 0%, var(--bg-hover) 50%, transparent 100%);
    animation: shimmer 1.5s infinite;
  }
  .rounded {
    border-radius: var(--radius-full);
  }
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
</style>
