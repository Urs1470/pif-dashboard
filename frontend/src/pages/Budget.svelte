<script>
  import { onMount } from 'svelte'
  import { Wallet } from '@lucide/svelte'
  import { budget, loadBudget } from '../stores/budget.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import BudgetDashboard from '../components/budget/BudgetDashboard.svelte'
  import BudgetCashFlow from '../components/budget/BudgetCashFlow.svelte'
  import BudgetCredit from '../components/budget/BudgetCredit.svelte'
  import BudgetInvestments from '../components/budget/BudgetInvestments.svelte'
  import BudgetGoals from '../components/budget/BudgetGoals.svelte'
  import BudgetSettings from '../components/budget/BudgetSettings.svelte'

  let activeTab = $state('dashboard')

  const tabs = [
    { id: 'dashboard', label: 'Buget Lunar' },
    { id: 'cashflow', label: 'Venituri' },
    { id: 'credit', label: 'Credit' },
    { id: 'investments', label: 'Investitii' },
    { id: 'goals', label: 'Obiective' },
    { id: 'settings', label: 'Setari' },
  ]

  const saveLabel = $derived(
    budget.saveStatus === 'saved' ? 'Salvat' :
    budget.saveStatus === 'pending' ? 'Se salveaza...' :
    budget.saveStatus === 'error' ? 'Eroare salvare' : 'Conflict'
  )

  onMount(() => { loadBudget() })
</script>

<div class="page">
  <div class="page-header">
    <Wallet size={22} />
    <h1>Budget</h1>
    {#if budget.data}
      <span class="save-status" class:pending={budget.saveStatus === 'pending'} class:error={budget.saveStatus === 'error'}>{saveLabel}</span>
    {/if}
  </div>

  {#if budget.loading}
    <div class="loading"><Skeleton height="40px" /><Skeleton height="300px" /></div>
  {:else if budget.data}
    <div class="tabs">
      {#each tabs as tab}
        <button class="tab" class:active={activeTab === tab.id} onclick={() => activeTab = tab.id}>{tab.label}</button>
      {/each}
    </div>

    <div class="tab-content">
      {#if activeTab === 'dashboard'}
        <BudgetDashboard />
      {:else if activeTab === 'cashflow'}
        <BudgetCashFlow />
      {:else if activeTab === 'credit'}
        <BudgetCredit />
      {:else if activeTab === 'investments'}
        <BudgetInvestments />
      {:else if activeTab === 'goals'}
        <BudgetGoals />
      {:else if activeTab === 'settings'}
        <BudgetSettings />
      {/if}
    </div>
  {:else}
    <p class="error-text">Eroare: {budget.error || 'Nu s-au putut incarca datele.'}</p>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); max-width: 1000px; }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .save-status { margin-left: auto; font-size: var(--font-tiny); color: var(--text-dim); }
  .save-status.pending { color: var(--warning); }
  .save-status.error { color: var(--danger); }
  .loading { display: flex; flex-direction: column; gap: var(--space-md); }
  .error-text { color: var(--danger); }

  .tabs {
    display: flex;
    gap: 2px;
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--space-lg);
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .tabs::-webkit-scrollbar { display: none; }

  .tab {
    padding: var(--space-sm) var(--space-md);
    font-size: var(--font-small);
    font-weight: 500;
    color: var(--text-dim);
    white-space: nowrap;
    border-bottom: 2px solid transparent;
    transition: color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease);
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .tab-content { min-height: 300px; }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .tab { padding: var(--space-xs) var(--space-sm); font-size: var(--font-tiny); min-height: 44px; }
  }
</style>
