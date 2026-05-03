const API_BASE = '/api';

let currentProjectId = null;
let confirmCallback = null;
let sortCol = null;
let sortDir = 0;
let archiveVisible = false;

// ============ API HELPERS ============

async function apiGet(url) {
    const res = await fetch(API_BASE + url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiPost(url, data) {
    const res = await fetch(API_BASE + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiPut(url, data) {
    const res = await fetch(API_BASE + url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiDelete(url) {
    const res = await fetch(API_BASE + url, { method: 'DELETE' });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiUpload(url, formData) {
    const res = await fetch(API_BASE + url, {
        method: 'POST',
        body: formData
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// ============ THEME MANAGEMENT ============

function initTheme() {
    const savedTheme = localStorage.getItem('pif-theme') || 'dark';
    setTheme(savedTheme);

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('pif-theme', newTheme);
}

function setTheme(theme) {
    const html = document.documentElement;
    html.setAttribute('data-theme', theme);

    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.textContent = theme === 'dark' ? '🌙' : '☀️';
        themeToggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    }
}

// ============ INITIALIZATION ============

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    initTheme();
    switchTab('acasa');

    // Setup filter listeners with debounce
    const debouncedLoad = debounce(loadProjects, 300);
    document.getElementById('filter-status').addEventListener('change', debouncedLoad);
    document.getElementById('filter-type').addEventListener('change', debouncedLoad);
    document.getElementById('filter-producator').addEventListener('change', debouncedLoad);
    document.getElementById('filter-date-from').addEventListener('change', debouncedLoad);
    document.getElementById('filter-date-to').addEventListener('change', debouncedLoad);
    document.getElementById('search-proiecte').addEventListener('input', debouncedLoad);

    // Setup project type selector
    document.querySelectorAll('.project-type-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.project-type-btn').forEach(b => b.classList.remove('selected'));
            this.classList.add('selected');
            const radio = this.querySelector('input[type="radio"]');
            radio.checked = true;
        });
    });

    // Set today's date for jurnal
    document.getElementById('jurnal-data').value = new Date().toISOString().split('T')[0];

    // Global tasks filters
    const debouncedGtLoad = debounce(() => loadGlobalTasks(), 300);
    document.getElementById('gt-filter-status').addEventListener('change', () => { gtFilters.status = document.getElementById('gt-filter-status').value; debouncedGtLoad(); });
    document.getElementById('gt-filter-prioritate').addEventListener('change', () => { gtFilters.prioritate = document.getElementById('gt-filter-prioritate').value; debouncedGtLoad(); });
    document.getElementById('gt-filter-categorie').addEventListener('change', () => { gtFilters.categorie = document.getElementById('gt-filter-categorie').value; debouncedGtLoad(); });
    document.getElementById('gt-search').addEventListener('input', () => { gtFilters.search = document.getElementById('gt-search').value; debouncedGtLoad(); });

    initSortableHeaders();

    // Project form modal event handlers
    document.getElementById('new-project-form').addEventListener('click', function(e) {
        if (e.target === this) hideNewProjectForm();
    });

    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
}

// ============ KEYBOARD SHORTCUTS ============

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Don't trigger shortcuts when typing in inputs/textareas (except Escape)
        const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName);

        // Escape - close modal or go back
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal-overlay.active');
            if (modal) {
                if (modal.id === 'new-project-form') hideNewProjectForm();
                else if (modal.id === 'confirm-modal') closeConfirmModal();
                else if (modal.id === 'preview-modal') closePreview();
                else if (modal.id === 'keyboard-help-overlay') hideKeyboardHelp();
            }
            if (currentProjectId) {
                showProjectList();
            }
            return;
        }

        // If in input, only handle / for search focus
        if (isInput) {
            if (e.key === '/') {
                e.preventDefault();
                document.getElementById('search-proiecte')?.focus();
            }
            return;
        }

        // ? - Show keyboard help
        if (e.key === '?') {
            e.preventDefault();
            showKeyboardHelp();
            return;
        }

        // N - New project
        if (e.key === 'n' || e.key === 'N') {
            e.preventDefault();
            showNewProjectForm();
            return;
        }

        // / - Focus search
        if (e.key === '/') {
            e.preventDefault();
            document.getElementById('search-proiecte')?.focus();
            return;
        }

        // 1-4 - Switch tabs
        if (e.key === '1') { switchTab('acasa'); return; }
        if (e.key === '2') { switchTab('taskuri'); return; }
        if (e.key === '3') { switchTab('proiecte'); return; }
        if (e.key === '4') { switchTab('statistici'); return; }

        // Ctrl+S - Save (if modal is open)
        if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            const modal = document.getElementById('new-project-form');
            if (modal && modal.classList.contains('active')) {
                document.getElementById('project-form')?.requestSubmit();
            }
            return;
        }
    });
}

function showKeyboardHelp() {
    document.getElementById('keyboard-help-overlay')?.classList.add('active');
}

function hideKeyboardHelp() {
    document.getElementById('keyboard-help-overlay')?.classList.remove('active');
}

// ============ EXPORT EXCEL ============

function toggleExportDropdown() {
    const dropdown = document.getElementById('export-dropdown');
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
}

function exportExcel(type) {
    toggleExportDropdown();
    window.open(`${API_BASE}/export/excel?type=${type}`, '_blank');
    showToast(`Export ${type} descărcat!`, 'success');
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    const dropdown = document.getElementById('export-dropdown');
    const exportBtn = document.querySelector('.export-dropdown');
    if (dropdown && exportBtn && !exportBtn.contains(e.target)) {
        dropdown.classList.remove('active');
    }
});

function initSortableHeaders() {
    document.querySelectorAll('th.sortable').forEach(th => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', function() {
            const col = this.getAttribute('data-col');
            if (sortCol === col) {
                sortDir = (sortDir + 1) % 3; // 0=none, 1=asc, 2=desc
            } else {
                sortCol = col;
                sortDir = 1; // default to asc
            }
            // Update indicators
            document.querySelectorAll('th.sortable').forEach(h => {
                const c = h.getAttribute('data-col');
                if (c === sortCol) {
                    h.textContent = h.textContent.replace(/[↕️↑↓]/g, '') + (sortDir === 1 ? ' ↑' : sortDir === 2 ? ' ↓' : ' ↕️');
                } else {
                    h.textContent = h.textContent.replace(/[↕️↑↓]/g, '') + ' ↕️';
                }
            });
            loadProjects();
        });
    });
}

// ============ STATS ============

async function updateStats() {
    try {
        const stats = await apiGet('/stats');
        document.getElementById('stat-total').textContent = stats.total || 0;
        document.getElementById('stat-active').textContent = stats.active || 0;
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

// ============ PROJECTS ============

async function loadProjects() {
    // Show skeleton, hide table
    const skeleton = document.getElementById('projects-skeleton');
    const table = document.getElementById('projects-table');
    if (skeleton) skeleton.classList.remove('hidden');
    if (table) table.style.display = 'none';

    try {
        const status = document.getElementById('filter-status').value;
        const tip = document.getElementById('filter-type').value;
        const producator = document.getElementById('filter-producator').value;
        const search = document.getElementById('search-proiecte').value.trim().toLowerCase();

        let url = '/proiecte?';
        if (status) url += `status=${status}&`;
        if (tip) url += `tip=${tip}&`;
        if (producator) url += `producator=${producator}&`;

        let projects = await apiGet(url);

        // Client-side search filter
        if (search) {
            projects = projects.filter(p =>
                (p.nume || '').toLowerCase().includes(search) ||
                (p.client || '').toLowerCase().includes(search) ||
                (p.echipament_principal || '').toLowerCase().includes(search) ||
                (p.locatie || '').toLowerCase().includes(search) ||
                (p.cod_proiect || '').toLowerCase().includes(search) ||
                (p.producator || '').toLowerCase().includes(search)
            );
        }

        renderProjects(projects);
    } catch (e) {
        console.error('Failed to load projects:', e);
        showToast('Eroare la încărcarea proiectelor', 'error');
    } finally {
        // Hide skeleton after load
        setTimeout(() => {
            if (skeleton) skeleton.classList.add('hidden');
            if (table) table.style.display = 'table';
        }, 300);
    }
}

function renderProjects(projects) {
    const tbody = document.getElementById('projects-tbody');
    const emptyState = document.getElementById('empty-projects');
    const tableContainer = document.getElementById('projects-table-container');

    // Sort if needed
    if (sortCol && sortDir > 0) {
        projects.sort((a, b) => {
            let valA = a[sortCol] || '';
            let valB = b[sortCol] || '';
            if (typeof valA === 'string') valA = valA.toLowerCase();
            if (typeof valB === 'string') valB = valB.toLowerCase();
            let cmp = 0;
            if (valA < valB) cmp = -1;
            else if (valA > valB) cmp = 1;
            return sortDir === 2 ? -cmp : cmp;
        });
    }

    if (projects.length === 0) {
        tableContainer.style.display = 'none';
        emptyState.style.display = 'block';
    } else {
        tableContainer.style.display = 'block';
        emptyState.style.display = 'none';

        tbody.innerHTML = projects.map(p => `
            <tr class="clickable-row" onclick="showProjectDetail('${p.id}')" title="${escapeHtml(p.nume)}">
                <td style="width:40px; text-align:center;">
                    <input type="checkbox" class="batch-checkbox project-row-checkbox" data-project-id="${p.id}" style="display:none;" onclick="event.stopPropagation(); toggleProjectSelection('${p.id}')">
                </td>
                <td title="${escapeHtml(p.nume)}">${escapeHtml(p.nume)}</td>
                <td title="${escapeHtml(p.client)}">${escapeHtml(p.client)}</td>
                <td><span class="badge ${(p.tip || 'pif').toLowerCase()}">${p.tip || 'PIF'}</span></td>
                <td title="${escapeHtml(p.producator)}">${escapeHtml(p.producator)}</td>
                <td><span class="badge ${p.status}">${getStatusLabel(p.status)}</span></td>
                <td>${p.data_incepere || '-'}</td>
            </tr>
        `).join('');

        // Mobile card view
        let cardList = document.getElementById('projects-card-list');
        if (!cardList) {
            cardList = document.createElement('div');
            cardList.id = 'projects-card-list';
            cardList.className = 'projects-card-list';
            document.getElementById('projects-table-container').parentNode
                .insertBefore(cardList, document.getElementById('projects-table-container'));
        }
        cardList.innerHTML = projects.map(p => `
            <div class="project-card-mobile" onclick="showProjectDetail('${p.id}')">
                <div class="pcm-header">
                    <div class="pcm-name">${escapeHtml(p.nume)}</div>
                    <span class="badge ${p.status}">${getStatusLabel(p.status)}</span>
                </div>
                <div class="pcm-meta">
                    <span>👤 ${escapeHtml(p.client || '-')}</span>
                    <span class="badge ${(p.tip||'pif').toLowerCase()}">${p.tip||'PIF'}</span>
                    <span>⚙️ ${escapeHtml(p.producator || '-')}</span>
                    ${p.data_incepere ? `<span>📅 ${p.data_incepere}</span>` : ''}
                </div>
            </div>
        `).join('');
    }
}

function showNewProjectForm() {
    document.getElementById('project-id').value = '';
    document.getElementById('project-form').reset();
    document.querySelectorAll('.project-type-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById('form-title').textContent = 'Proiect nou';
    document.getElementById('jurnal-data').value = new Date().toISOString().split('T')[0];
    document.getElementById('new-project-form').classList.add('active');
}

function hideNewProjectForm() {
    document.getElementById('new-project-form').classList.remove('active');
}

async function saveProject(event) {
    event.preventDefault();

    const typeEl = document.querySelector('input[name="project-type"]:checked');
    if (!typeEl) {
        showToast('Selectați tipul proiectului!', true);
        return;
    }

    const id = document.getElementById('project-id').value;
    const projectType = typeEl.value;

    const projectData = {
        tip: projectType,
        nume: document.getElementById('p-nume').value,
        client: document.getElementById('p-client').value,
        locatie: document.getElementById('p-locatie').value,
        status: document.getElementById('p-status').value,
        producator: document.getElementById('p-producator').value,
        echipament_principal: document.getElementById('p-tip').value,
        data_incepere: document.getElementById('p-data-start').value,
        deadline: document.getElementById('p-data-est').value,
        observatii: document.getElementById('p-observatii').value,
        nr_comanda: document.getElementById('p-nr-comanda').value,
        nr_contract: document.getElementById('p-nr-contract').value
    };

    try {
        if (id) {
            await apiPut(`/proiecte/${id}`, projectData);
            showToast('Proiect actualizat!');
        } else {
            await apiPost('/proiecte', projectData);
            showToast('Proiect creat!');
        }

        hideNewProjectForm();
        await loadProjects();
        await updateStats();
        if (id && currentProjectId) {
            await showProjectDetail(currentProjectId);
        }
    } catch (e) {
        console.error('Failed to save project:', e);
        showToast('Eroare la salvarea proiectului', true);
    }
}

async function showProjectDetail(projectId) {
    currentProjectId = projectId;

    try {
        const project = await apiGet(`/proiecte/${projectId}`);

        // Fill detail view
        document.getElementById('detail-nume').textContent = project.nume;
        document.getElementById('detail-client').textContent = project.client || '';

        // Set print attributes
        const detailView = document.getElementById('project-detail-view');
        detailView.setAttribute('data-print-date', new Date().toLocaleDateString('ro-RO'));
        detailView.setAttribute('data-project-name', project.nume);

        // Show/hide sections based on type
        const isPIF = project.tip === 'PIF';
        const isService = project.tip === 'Service';
        document.getElementById('pif-observatii-section').style.display = isPIF ? 'block' : 'none';
        document.getElementById('before-after-section').style.display = isService ? 'grid' : 'none';
        const toHide = ['service-fields', 'observations-section'];
        toHide.forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });

        // Service fields
        if (isService) {
            document.getElementById('detail-confirmat-client').checked = project.confirmat_client == 1;
            document.getElementById('detail-client-nume').value = project.client_nume_confirmare || '';
            document.getElementById('service-before').value = project.service_before || '';
            document.getElementById('service-after').value = project.service_after || '';
        }

        // PIF fields
        if (isPIF) {
            document.getElementById('pif-observatii').value = project.observatii || '';
        }

        // Show/hide checklist section (only for PIF)
        document.getElementById('checklist-section').style.display = isPIF ? 'block' : 'none';

        // Load related data
        await Promise.all([
            loadTodos(projectId),
            loadJurnal(projectId),
            loadAttachments(projectId),
            isPIF ? loadChecklist(projectId) : Promise.resolve(),
            loadTimerSessions(projectId)
        ]);

        // Switch views
        document.getElementById('project-list-view').classList.add('hidden');
        document.getElementById('project-detail-view').classList.add('active');

    } catch (e) {
        console.error('Failed to load project:', e);
        showToast('Eroare la încărcarea detaliilor', true);
    }

    // Mobile: add back button at top if not exists
    if (!document.getElementById('mobile-back-btn')) {
        const backBtn = document.createElement('button');
        backBtn.id = 'mobile-back-btn';
        backBtn.className = 'btn btn-secondary btn-back-mobile';
        backBtn.innerHTML = '← Înapoi la Proiecte';
        backBtn.onclick = showProjectList;
        document.getElementById('project-detail-view').prepend(backBtn);
    }
    // Initialize accordions for mobile
    initAccordions();
}

function showProjectList() {
    currentProjectId = null;
    document.getElementById('project-list-view').classList.remove('hidden');
    document.getElementById('project-detail-view').classList.remove('active');
    loadProjects();
    updateStats();
}

function goHome() {
    const detailView = document.getElementById('project-detail-view');
    if (detailView && detailView.classList.contains('active')) {
        showProjectList();
    }
    switchTab('taskuri');
}

async function editCurrentProject() {
    if (!currentProjectId) return;

    try {
        const project = await apiGet(`/proiecte/${currentProjectId}`);
        document.getElementById('project-id').value = project.id;
        document.getElementById('p-nume').value = project.nume || '';
        document.getElementById('p-client').value = project.client || '';
        document.getElementById('p-locatie').value = project.locatie || '';
        document.getElementById('p-status').value = project.status || 'in_lucru';
        document.getElementById('p-producator').value = project.producator || 'Altul';
        document.getElementById('p-tip').value = project.echipament_principal || '';
        document.getElementById('p-data-start').value = project.data_incepere || '';
        document.getElementById('p-data-est').value = project.deadline || '';
        document.getElementById('p-observatii').value = project.observatii || '';
        document.getElementById('p-nr-comanda').value = project.nr_comanda || '';
        document.getElementById('p-nr-contract').value = project.nr_contract || '';

        const typeBtn = document.getElementById(
            project.tip === 'Service' ? 'type-service-btn' : 'type-pif-btn'
        );
        if (typeBtn) {
            document.querySelectorAll('.project-type-btn').forEach(b => b.classList.remove('selected'));
            typeBtn.classList.add('selected');
            typeBtn.querySelector('input[type="radio"]').checked = true;
        }

        document.getElementById('form-title').textContent = 'Editează proiect';
        document.getElementById('new-project-form').classList.add('active');
    } catch (e) {
        console.error('Failed to load project:', e);
        showToast('Eroare la încărcarea proiectului', true);
    }
}

async function deleteCurrentProject() {
    if (!currentProjectId) return;

    showConfirm('Sigur doriți să ștergeți acest proiect? Această acțiune nu poate fi anulată.', async () => {
        try {
            await apiDelete(`/proiecte/${currentProjectId}`);
            showToast('Proiect șters!');
            showProjectList();
        } catch (e) {
            console.error('Failed to delete project:', e);
            showToast('Eroare la ștergerea proiectului', true);
        }
    });
}

async function saveServiceField(field, value) {
    if (!currentProjectId) return;

    try {
        await apiPut(`/proiecte/${currentProjectId}`, { [field]: value });
        showToast('Salvat!');
    } catch (e) {
        console.error('Failed to update service field:', e);
        showToast('Eroare la salvare', true);
    }
}

// ============ TASKS / TODOS ============

let draggedTaskId = null;

async function loadTodos(projectId) {
    try {
        const tasks = await apiGet(`/proiecte/${projectId}/tasks`);
        renderTodos(tasks);
    } catch (e) {
        console.error('Failed to load tasks:', e);
    }
}

function renderTodos(tasks) {
    const container = document.getElementById('todo-list');

    if (!tasks.length) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există task-uri.</p>';
        return;
    }

    container.innerHTML = tasks.map(task => `
        <div class="todo-item priority-${task.prioritate || 'normal'} ${task.status === 'done' ? 'completed' : ''}" 
             draggable="true" 
             data-task-id="${task.id}"
             data-ordine="${task.ordine || 0}">
            <input type="checkbox" class="todo-checkbox" ${task.status === 'done' ? 'checked' : ''} onchange="toggleTodo('${task.id}', this.checked)">
            <div class="todo-content">
                <div class="todo-title">${escapeHtml(task.titlu)}</div>
                <div class="todo-meta">${task.data_scadenta ? '📅 ' + task.data_scadenta : ''}</div>
            </div>
            <span class="todo-priority ${task.prioritate || 'normal'}">${task.prioritate || 'normal'}</span>
            <span class="todo-status ${task.status}">${getStatusLabel(task.status)}</span>
            <button class="btn btn-small btn-danger todo-delete" onclick="deleteTodo('${task.id}')">×</button>
        </div>
    `).join('');

    // Add drag-and-drop event listeners
    initTaskDragDrop();
}

function initTaskDragDrop() {
    const container = document.getElementById('todo-list');
    const items = container.querySelectorAll('.todo-item');

    items.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragleave', handleDragLeave);
    });
}

function handleDragStart(e) {
    draggedTaskId = e.target.dataset.taskId;
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    document.querySelectorAll('.todo-item').forEach(item => {
        item.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const item = e.target.closest('.todo-item');
    if (item && !item.classList.contains('dragging')) {
        item.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    const item = e.target.closest('.todo-item');
    if (item) {
        item.classList.remove('drag-over');
    }
}

async function handleDrop(e) {
    e.preventDefault();
    const targetItem = e.target.closest('.todo-item');
    if (!targetItem || !draggedTaskId) return;

    targetItem.classList.remove('drag-over');

    const draggedItem = document.querySelector(`[data-task-id="${draggedTaskId}"]`);
    if (!draggedItem) return;

    const allItems = Array.from(document.querySelectorAll('.todo-item:not(.completed)'));
    const draggedIndex = allItems.indexOf(draggedItem);
    const targetIndex = allItems.indexOf(targetItem);

    if (draggedIndex === targetIndex) return;

    // Update ordine for all affected tasks
    const updates = [];
    if (draggedIndex < targetIndex) {
        // Moving down: decrease ordine for items between old and new position
        for (let i = draggedIndex + 1; i <= targetIndex; i++) {
            updates.push({ id: allItems[i].dataset.taskId, ordine: i - 1 });
        }
    } else {
        // Moving up: increase ordine for items between new and old position
        for (let i = targetIndex; i < draggedIndex; i++) {
            updates.push({ id: allItems[i].dataset.taskId, ordine: i + 1 });
        }
    }
    updates.push({ id: draggedTaskId, ordine: targetIndex });

    // Apply updates
    for (const update of updates) {
        try {
            await apiPut(`/tasks/${update.id}`, { ordine: update.ordine });
        } catch (err) {
            console.error('Failed to update task order:', err);
        }
    }

    // Reload todos to reflect new order
    loadTodos(currentProjectId);
}

async function addTodo() {
    const titlu = document.getElementById('todo-title').value.trim();
    if (!titlu) return;

    const prioritate = document.getElementById('todo-priority').value;
    const status = document.getElementById('todo-status').value;

    try {
        await apiPost(`/proiecte/${currentProjectId}/tasks`, {
            titlu,
            prioritate,
            status
        });

        document.getElementById('todo-title').value = '';
        loadTodos(currentProjectId);
        showToast('Task adăugat!');
    } catch (e) {
        console.error('Failed to add todo:', e);
        showToast('Eroare la adăugarea task-ului', true);
    }
}

async function toggleTodo(taskId, checked) {
    try {
        await apiPut(`/tasks/${taskId}`, {
            status: checked ? 'done' : 'to_do',
            data_finalizare: checked ? new Date().toISOString() : ''
        });
        loadTodos(currentProjectId);
    } catch (e) {
        console.error('Failed to toggle todo:', e);
    }
}

async function deleteTodo(taskId) {
    try {
        await apiDelete(`/tasks/${taskId}`);
        loadTodos(currentProjectId);
    } catch (e) {
        console.error('Failed to delete todo:', e);
    }
}

// ============ JURNAL ============

async function loadJurnal(projectId) {
    try {
        const entries = await apiGet(`/proiecte/${projectId}/jurnal`);
        renderJurnal(entries);
    } catch (e) {
        console.error('Failed to load jurnal:', e);
    }
}

function renderJurnal(entries) {
    const container = document.getElementById('jurnal-list');

    if (!entries.length) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există intrări în jurnal.</p>';
        return;
    }

    container.innerHTML = entries.map(entry => `
        <div class="jurnal-item">
            <div class="jurnal-date">${entry.data}</div>
            <div class="jurnal-content">${escapeHtml(entry.continut)}</div>
            <button class="btn btn-small btn-danger" onclick="deleteJurnalEntry('${entry.id}')" style="margin-top: 5px;">Șterge</button>
        </div>
    `).join('');
}

async function addJurnalEntry() {
    const data = document.getElementById('jurnal-data').value;
    const continut = document.getElementById('jurnal-continut').value.trim();

    if (!continut) return;

    try {
        await apiPost(`/proiecte/${currentProjectId}/jurnal`, { data, continut });
        document.getElementById('jurnal-continut').value = '';
        loadJurnal(currentProjectId);
        showToast('Intrare adăugată!');
    } catch (e) {
        console.error('Failed to add jurnal entry:', e);
        showToast('Eroare la adăugarea intrării', true);
    }
}

async function deleteJurnalEntry(entryId) {
    try {
        await apiDelete(`/jurnal/${entryId}`);
        loadJurnal(currentProjectId);
    } catch (e) {
        console.error('Failed to delete jurnal entry:', e);
    }
}

// ============ ATTACHMENTS ============

async function loadAttachments(projectId) {
    try {
        const attachments = await apiGet(`/proiecte/${projectId}/atasamente`);
        renderAttachments(attachments);
    } catch (e) {
        console.error('Failed to load attachments:', e);
    }
}

function renderAttachments(attachments) {
    const container = document.getElementById('attachment-list');

    if (!attachments.length) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există atașamente.</p>';
        return;
    }

    const icons = {
        'PDF': '📄',
        'IMG': '🖼️',
        'EMAIL': '✉️',
        'DOC': '📝',
        'XLS': '📊',
        'ZIP': '🗜️',
        'ALT': '📎'
    };

    container.innerHTML = attachments.map(att => `
        <div class="attachment-item">
            <div class="attachment-icon">${icons[att.tip_fisier] || '📎'}</div>
            <div class="attachment-info">
                <div class="attachment-name">${escapeHtml(att.nume_fisier)}</div>
                <div class="attachment-meta">${formatFileSize(att.dimensiune)} - ${att.data}</div>
            </div>
            <div class="attachment-actions">
                ${att.tip_fisier === 'PDF' || att.tip_fisier === 'IMG' ? `<button class="btn btn-small btn-secondary" onclick="openPreview('${att.id}', '${escapeHtml(att.nume_fisier)}', '${att.tip_fisier}')">👁 Preview</button>` : ''}
                <button class="btn btn-small btn-secondary" onclick="downloadAttachment('${att.id}')">⬇️ Download</button>
                <button class="btn btn-small btn-danger" onclick="deleteAttachment('${att.id}')">× Șterge</button>
            </div>
        </div>
    `).join('');
}

function openPreview(attachmentId, filename, tipFisier) {
    const url = `${API_BASE}/atasamente/${attachmentId}/download`;
    const content = document.getElementById('preview-content');
    document.getElementById('preview-filename').textContent = filename;

    if (tipFisier === 'IMG') {
        content.innerHTML = `<img src="${url}" alt="${filename}">`;
    } else if (tipFisier === 'PDF') {
        content.innerHTML = `<iframe src="${url}" title="${filename}"></iframe>`;
    }

    document.getElementById('preview-modal').classList.add('active');
}

function closePreview() {
    document.getElementById('preview-modal').classList.remove('active');
    document.getElementById('preview-content').innerHTML = '';
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function handleFileUpload(event) {
    const files = event.target.files;
    if (!files.length) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            await apiUpload(`/proiecte/${currentProjectId}/atasamente`, formData);
            showToast(`Fișier încărcat: ${file.name}`);
        } catch (e) {
            console.error('Failed to upload file:', e);
            showToast(`Eroare la încărcarea fișierului`, true);
        }
    }

    event.target.value = '';
    loadAttachments(currentProjectId);
}

function downloadAttachment(attachmentId) {
    window.open(`${API_BASE}/atasamente/${attachmentId}/download`, '_blank');
}

async function deleteAttachment(attachmentId) {
    try {
        await apiDelete(`/atasamente/${attachmentId}`);
        loadAttachments(currentProjectId);
        showToast('Atașament șters!');
    } catch (e) {
        console.error('Failed to delete attachment:', e);
        showToast('Eroare la ștergerea atașamentului', true);
    }
}

// ============ BACKUP / RESTORE ============

async function exportBackup() {
    try {
        const data = await apiGet('/backup');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pif_backup_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Backup descărcat!');
    } catch (e) {
        console.error('Failed to export backup:', e);
        showToast('Eroare la exportarea backup-ului', true);
    }
}

async function importBackup(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            await fetch(`${API_BASE}/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            showToast('Backup restaurat cu succes!');
            loadProjects();
            updateStats();
            if (currentProjectId) {
                showProjectDetail(currentProjectId);
            }
        } catch (err) {
            console.error('Failed to import backup:', err);
            showToast('Eroare la restaurarea backup-ului', true);
        }
    };
    reader.readAsText(file);
    event.target.value = '';
}

// ============ EXPORT ============

async function exportMarkdown() {
    if (!currentProjectId) return;

    try {
        const [project, tasks, jurnal, attachments] = await Promise.all([
            apiGet(`/proiecte/${currentProjectId}`),
            apiGet(`/proiecte/${currentProjectId}/tasks`),
            apiGet(`/proiecte/${currentProjectId}/jurnal`),
            apiGet(`/proiecte/${currentProjectId}/atasamente`)
        ]);

        const isPIF = project.tip === 'PIF';
        const isService = project.tip === 'Service';
        const today = new Date().toISOString().split('T')[0];

        let md = '';

        // FRONTMATTER YAML
        md += `---\n`;
        md += `tags:\n`;
        if (isPIF) md += `  - proiect\n  - pif\n`;
        if (isService) md += `  - service\n  - interventie\n`;
        if (project.producator && project.producator !== 'Altul')
            md += `  - ${project.producator.toLowerCase()}\n`;
        md += `client: ${project.client || ''}\n`;
        md += `locatie: ${project.locatie || ''}\n`;
        md += `echipament_principal: ${project.echipament_principal || ''}\n`;
        if (isPIF) {
            md += `data_incepere: ${project.data_incepere || ''}\n`;
            md += `deadline: ${project.deadline || ''}\n`;
        }
        if (isService) md += `data_crearii: ${project.data_crearii || today}\n`;
        md += `status: ${project.status || 'activ'}\n`;
        if (project.cod_proiect) md += `cod_proiect: ${project.cod_proiect}\n`;
        md += `---\n\n`;

        // TITLU
        md += isPIF
            ? `# PIF: ${project.nume}\n\n`
            : `# Service: ${project.nume}\n\n`;

        // DETALII ADMINISTRATIVE
        md += `### 1. Detalii Administrative\n`;
        if (project.pm) md += `- **PM:** ${project.pm}\n`;
        if (project.nr_comanda) md += `- **Nr. Comandă:** ${project.nr_comanda}\n`;
        if (project.nr_contract) md += `- **Nr. Contract:** ${project.nr_contract}\n`;
        if (project.folder_server) md += `- **Folder Server/Cloud:** ${project.folder_server}\n`;
        if (project.cod_proiect) md += `- **Cod proiect:** ${project.cod_proiect}\n`;
        md += `\n`;

        // SECȚIUNI PIF
        if (isPIF && project.observatii) {
            md += `### 2. Observații Tehnice\n`;
            md += `${project.observatii}\n\n`;
        }

        // SECȚIUNI SERVICE
        if (isService) {
            md += `### 2. Fișă Intervenție\n\n`;
            if (project.service_before) {
                md += `#### Constatări înainte de intervenție\n`;
                md += `${project.service_before}\n\n`;
            }
            if (project.service_after) {
                md += `#### Acțiuni și rezultat\n`;
                md += `${project.service_after}\n\n`;
            }
        }

        // LISTA TASK-URI
        if (tasks.length > 0) {
            md += `### 3. LISTA TASK-URI\n`;
            const priorityOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
            const prioEmoji = { 'Urgent': '⏫', 'Normal': '🔼', 'Minor': '⏬' };
            const sorted = [...tasks].sort((a, b) =>
                (priorityOrder[a.prioritate] ?? 1) - (priorityOrder[b.prioritate] ?? 1));

            const pending = sorted.filter(t => t.status !== 'done');
            const done = sorted.filter(t => t.status === 'done');

            if (pending.length > 0) {
                md += `#### To Do\n`;
                pending.forEach(t => {
                    const emoji = prioEmoji[t.prioritate] || '';
                    const scadenta = t.data_scadenta ? ` 📅 ${t.data_scadenta}` : '';
                    md += `- [ ] ${t.titlu} ${emoji}${scadenta}\n`;
                });
                md += `\n`;
            }
            if (done.length > 0) {
                md += `#### Finalizate\n`;
                done.forEach(t => {
                    const emoji = prioEmoji[t.prioritate] || '';
                    const finalizat = t.data_finalizare
                        ? ` ✅ ${t.data_finalizare.split('T')[0]}` : ' ✅';
                    md += `- [x] ${t.titlu} ${emoji}${finalizat}\n`;
                });
                md += `\n`;
            }
        }

        // JURNAL DE LUCRU
        if (jurnal.length > 0) {
            md += `### 4. JURNAL DE LUCRU\n`;
            [...jurnal].reverse().forEach(entry => {
                md += `**${entry.data}**:\n${entry.continut}\n\n`;
            });
        }

        // ATAȘAMENTE
        if (attachments.length > 0) {
            md += `### 5. Atașamente\n`;
            attachments.forEach(att => {
                md += `- ${att.nume_fisier} (${att.tip_fisier}, ${formatFileSize(att.dimensiune)}, ${att.data})\n`;
            });
            md += `\n`;
        }

        // FOOTER
        md += `---\n*Exportat din PIF Dashboard — ${today}*\n`;

        // DOWNLOAD
        const filename = project.cod_proiect
            ? `${project.cod_proiect}_${project.nume.replace(/[^a-z0-9]/gi, '_')}.md`
            : `${project.nume.replace(/[^a-z0-9]/gi, '_')}.md`;

        const blob = new Blob([md], { type: 'text/markdown; charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Export Markdown descărcat!');

    } catch (e) {
        console.error('Export failed:', e);
        showToast('Eroare la export', true);
    }
}

// ============ PHASE 2c: PDF EXPORT ============

async function exportCurrentProjectPDF() {
    if (!currentProjectId) {
        showToast('Niciun proiect selectat', true);
        return;
    }

    try {
        // Use window.open for PDF download via API
        const response = await fetch(`${API_BASE}/export/pdf?project_id=${currentProjectId}`, {
            method: 'GET',
            headers: { ...getHeaders() }
        });

        if (!response.ok) {
            throw new Error('PDF export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `pif_report_${currentProjectId}.pdf`;
        if (contentDisposition) {
            const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (match) {
                filename = match[1].replace(/['"]/g, '');
            }
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast('PDF exportat cu succes!');
    } catch (e) {
        console.error('PDF export failed:', e);
        showToast('Eroare la export PDF', true);
    }
}

// ============ PHASE 2c: TELEGRAM NOTIFICATIONS ============

async function testTelegramNotification() {
    if (!currentProjectId) {
        showToast('Niciun proiect selectat', true);
        return;
    }

    try {
        const project = await apiGet(`/proiecte/${currentProjectId}`);
        const response = await fetch(`${API_BASE}/notify/telegram`, {
            method: 'POST',
            headers: { ...getHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: `🔔 Test din PIF Dashboard\n📁 Proiect: ${project.nume}\n🆔 ${project.id}\n🕐 ${new Date().toLocaleString('ro-RO')}`
            })
        });

        if (response.ok) {
            showToast('Notificare trimisă!');
        } else {
            const data = await response.json();
            showToast(data.error || 'Eroare la trimiterea notificării', true);
        }
    } catch (e) {
        console.error('Telegram notification failed:', e);
        showToast('Eroare la trimiterea notificării', true);
    }
}

// ============ GLOBAL TASKS ============

let gtFilters = { status: '', prioritate: '', categorie: '', search: '' };

function switchTab(tab) {
    document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.main-tab[data-tab="${tab}"]`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Update bottom nav active state
    document.querySelectorAll('.bottom-nav-item').forEach(item => {
        item.classList.toggle('active', item.getAttribute('data-tab') === tab);
    });

    if (tab === 'taskuri') {
        loadGlobalTasks();
        setTimeout(() => document.getElementById('quick-task-input')?.focus(), 100);
    }
    if (tab === 'proiecte') {
        loadProjects();
        updateStats();
    }
    if (tab === 'acasa') {
        updateHomeStats();
        loadRecentActivity();
    }
    if (tab === 'statistici') {
        loadExtendedStats();
    }
}

async function loadGlobalTasks() {
    try {
        let url = '/global-tasks?';
        if (gtFilters.status) url += `status=${gtFilters.status}&`;
        if (gtFilters.prioritate) url += `prioritate=${gtFilters.prioritate}&`;
        if (gtFilters.categorie) url += `categorie=${gtFilters.categorie}&`;

        const tasks = await apiGet(url);
        renderGlobalTasks(tasks);
        updateGtStats(tasks);

        // Update archive count
        const archived = await apiGet('/global-tasks?arhiva=true');
        document.getElementById('archive-count').textContent = archived.length;
    } catch (e) {
        console.error('Failed to load global tasks:', e);
    }
}

function updateGtStats(tasks) {
    const today = new Date().toISOString().split('T')[0];
    const total = tasks.filter(t => !t.data_scadenta || t.data_scadenta === today).length;
    const finalizate = tasks.filter(t => t.status === 'done' && t.data_finalizare && t.data_finalizare.startsWith(today)).length;

    document.getElementById('gt-stat-total').textContent = total;
    document.getElementById('gt-stat-finalizate').textContent = finalizate;
}

function renderGlobalTasks(tasks) {
    const container = document.getElementById('gt-task-list');
    const search = gtFilters.search.toLowerCase();

    // Filter by search
    if (search) {
        tasks = tasks.filter(t =>
            (t.titlu && t.titlu.toLowerCase().includes(search)) ||
            (t.descriere && t.descriere.toLowerCase().includes(search))
        );
    }

    // Sort: Urgent first, then by data_scadenta asc
    const priorityOrder = { 'Urgent': 0, 'Normal': 1, 'Minor': 2 };
    tasks.sort((a, b) => {
        if (a.status === 'done' && b.status !== 'done') return 1;
        if (a.status !== 'done' && b.status === 'done') return -1;
        const pDiff = (priorityOrder[a.prioritate] || 1) - (priorityOrder[b.prioritate] || 1);
        if (pDiff !== 0) return pDiff;
        if (a.data_scadenta && b.data_scadenta) return a.data_scadenta.localeCompare(b.data_scadenta);
        if (a.data_scadenta) return -1;
        if (b.data_scadenta) return 1;
        return 0;
    });

    const today = new Date().toISOString().split('T')[0];

    if (!tasks.length) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există task-uri.</p>';
        return;
    }

    container.innerHTML = tasks.map(task => {
        const isOverdue = task.data_scadenta && task.data_scadenta < today && task.status !== 'done';
        const isDueToday = task.data_scadenta === today && task.status !== 'done';
        const classes = ['gt-task-card'];
        if (task.status === 'done') classes.push('completed');
        if (isOverdue) classes.push('overdue');
        else if (isDueToday) classes.push('due-today');

        return `
            <div class="${classes.join(' ')}">
                <input type="checkbox" class="todo-checkbox" ${task.status === 'done' ? 'checked' : ''} onchange="toggleGtTask('${task.id}', this.checked)">
                <div class="todo-content">
                    <div class="gt-task-title">${escapeHtml(task.titlu)}</div>
                    ${task.descriere ? `<div class="todo-meta">${escapeHtml(task.descriere)}</div>` : ''}
                    <div class="todo-meta">${task.data_scadenta ? '📅 ' + task.data_scadenta : ''} ${task.categorie ? ' | ' + task.categorie : ''}</div>
                </div>
                <span class="todo-priority ${task.prioritate || 'normal'}">${task.prioritate || 'Normal'}</span>
                <span class="todo-status ${task.status}">${getStatusLabel(task.status)}</span>
                <button class="btn btn-small btn-secondary" onclick="editGtTask('${task.id}')">✏️</button>
                <button class="btn btn-small btn-danger" onclick="deleteGtTask('${task.id}')">×</button>
            </div>
        `;
    }).join('');
}

async function toggleGtTask(taskId, checked) {
    try {
        await apiPut(`/global-tasks/${taskId}`, {
            status: checked ? 'done' : 'to_do',
            data_finalizare: checked ? new Date().toISOString() : ''
        });
        await loadGlobalTasks();
        // Update archive badge count
        const archived = await apiGet('/global-tasks?arhiva=true');
        document.getElementById('archive-count').textContent = archived.length;
        if (archiveVisible) renderArchive(archived);
    } catch (e) {
        console.error('Failed to toggle global task:', e);
    }
}

async function editGtTask(taskId) {
    try {
        const task = await apiGet(`/global-tasks/${taskId}`);
        const input = document.getElementById('quick-task-input');
        input.value = task.titlu || '';
        document.getElementById('quick-prioritate').value = task.prioritate || 'medie';
        document.getElementById('quick-categorie').value = task.categorie || '';
        document.getElementById('quick-scadenta').value = task.data_scadenta || '';
        input.focus();
        await apiDelete(`/global-tasks/${taskId}`);
        await loadGlobalTasks();
    } catch (e) {
        console.error('Failed to edit global task:', e);
    }
}

async function deleteGtTask(taskId) {
    try {
        await apiDelete(`/global-tasks/${taskId}`);
        loadGlobalTasks();
        showToast('Task șters!');
    } catch (e) {
        console.error('Failed to delete global task:', e);
    }
}

// ============ ARCHIVE SECTION ============

function toggleArchive() {
    archiveVisible = !archiveVisible;
    document.getElementById('archive-body').style.display = archiveVisible ? 'block' : 'none';
    document.getElementById('archive-chevron').textContent = archiveVisible ? '▲' : '▼';
    if (archiveVisible) loadArchive();
}

async function loadArchive() {
    try {
        const tasks = await apiGet('/global-tasks?arhiva=true');
        document.getElementById('archive-count').textContent = tasks.length;
        renderArchive(tasks);
    } catch (e) {
        console.error('Failed to load archive:', e);
    }
}

function renderArchive(tasks) {
    const container = document.getElementById('archive-list');
    if (!tasks.length) {
        container.innerHTML = '<p style="color:var(--text2); font-size:0.9rem; text-align:center; padding:16px 0;">Niciun task finalizat.</p>';
        return;
    }
    container.innerHTML = tasks.map(t => `
        <div class="archive-item">
            <span class="archive-title">${escapeHtml(t.titlu)}</span>
            <span class="archive-meta">${t.categorie || ''} · ${t.data_finalizare ? t.data_finalizare.split('T')[0] : ''}</span>
            <button class="btn btn-small btn-secondary" onclick="restoreTask('${t.id}')" title="Redeschide task">↩️</button>
            <button class="btn btn-small btn-danger" onclick="deleteGtTask('${t.id}')" title="Șterge definitiv">×</button>
        </div>
    `).join('');
}

async function restoreTask(taskId) {
    try {
        await apiPut(`/global-tasks/${taskId}`, { status: 'to_do', data_finalizare: '' });
        await loadGlobalTasks();
        if (archiveVisible) await loadArchive();
        showToast('Task redeschis!');
    } catch (e) {
        showToast('Eroare la redeschiderea taskului', true);
    }
}

async function clearArchive() {
    if (!confirm('Ștergi definitiv toate taskurile finalizate?')) return;
    try {
        const tasks = await apiGet('/global-tasks?arhiva=true');
        await Promise.all(tasks.map(t => apiDelete(`/global-tasks/${t.id}`)));
        await loadArchive();
        showToast('Arhivă curățată!');
    } catch (e) {
        showToast('Eroare la ștergerea arhivei', true);
    }
}

// ============ QUICK ADD TASK ============

async function quickAddTask() {
    const input = document.getElementById('quick-task-input');
    const titlu = input.value.trim();
    if (!titlu) { input.focus(); return; }

    const prioritate = document.getElementById('quick-prioritate').value;
    const categorie = document.getElementById('quick-categorie').value;
    const scadenta = document.getElementById('quick-scadenta').value;

    input.disabled = true;
    document.getElementById('quick-add-btn').textContent = '✓';

    try {
        await apiPost('/global-tasks', {
            titlu, prioritate, categorie,
            data_scadenta: scadenta || '',
            status: 'to_do'
        });
        input.value = '';
        document.getElementById('quick-scadenta').value = '';
        await loadGlobalTasks();
    } catch (e) {
        showToast('Eroare la adăugarea taskului', true);
    } finally {
        input.disabled = false;
        document.getElementById('quick-add-btn').textContent = '+';
        input.focus();
    }
}

document.getElementById('quick-task-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); quickAddTask(); }
});

// ============ LOGOUT ============

async function logout() {
    try {
        await fetch('/logout');
        window.location.href = '/login';
    } catch (e) {
        console.error('Logout failed:', e);
        window.location.href = '/login';
    }
}

// ============ HOME PAGE ============

async function updateHomeStats() {
    try {
        const [stats, extStats] = await Promise.all([
            apiGet('/stats'),
            apiGet('/stats/extended')
        ]);
        document.getElementById('home-stat-total').textContent = stats.total || 0;
        document.getElementById('home-stat-active').textContent = stats.active || 0;
        document.getElementById('home-stat-finished').textContent = stats.finished || 0;
        document.getElementById('home-stat-hours').textContent = (extStats.total_billable_hours || 0) + 'h';
    } catch (e) {
        console.error('Failed to load home stats:', e);
    }
}

async function loadRecentActivity() {
    try {
        const container = document.getElementById('recent-activity-list');
        
        // Get recent projects
        const projects = await apiGet('/proiecte');
        const recentProjects = projects.slice(0, 5);
        
        // Get recent tasks completed today
        const today = new Date().toISOString().split('T')[0];
        const tasks = await apiGet('/global-tasks?arhiva=true');
        const recentTasks = tasks.filter(t => t.data_finalizare && t.data_finalizare.startsWith(today)).slice(0, 5);
        
        // Build activity list
        const activities = [];
        
        recentProjects.forEach(p => {
            activities.push({
                type: 'project',
                icon: p.tip === 'PIF' ? '🔧' : '🔧',
                title: `Proiect nou: ${p.nume}`,
                meta: `${p.client || ''} • ${p.status === 'finalizat' ? 'Finalizat' : 'În lucru'}`,
                time: p.created_at
            });
        });
        
        recentTasks.forEach(t => {
            activities.push({
                type: 'task',
                icon: '✅',
                title: `Task finalizat: ${t.titlu}`,
                meta: t.categorie || 'General',
                time: t.data_finalizare
            });
        });
        
        // Sort by time (newest first)
        activities.sort((a, b) => (b.time || '').localeCompare(a.time || ''));
        
        if (activities.length === 0) {
            container.innerHTML = '<p style="color: var(--text2);">Nicio activitate recentă.</p>';
            return;
        }
        
        container.innerHTML = activities.slice(0, 5).map(a => `
            <div class="gt-task-card" style="border-left-color: var(--accent);">
                <span style="font-size: 1.2rem;">${a.icon}</span>
                <div class="todo-content">
                    <div class="gt-task-title">${escapeHtml(a.title)}</div>
                    <div class="todo-meta">${a.meta}</div>
                </div>
            </div>
        `).join('');
        
    } catch (e) {
        console.error('Failed to load recent activity:', e);
        document.getElementById('recent-activity-list').innerHTML = 
            '<p style="color: var(--text2);">Eroare la încărcarea activității.</p>';
    }
}

function quickAddTaskFromHome() {
    switchTab('taskuri');
    setTimeout(() => {
        const input = document.getElementById('quick-task-input');
        if (input) input.focus();
    }, 100);
}

// ============ CHECKLIST PIF ============

async function loadChecklist(projectId) {
    try {
        const items = await apiGet(`/proiecte/${projectId}/checklist`);
        renderChecklist(items);
    } catch (e) {
        console.error('Failed to load checklist:', e);
    }
}

function renderChecklist(items) {
    const container = document.getElementById('checklist-list');
    const progressFill = document.getElementById('checklist-progress-fill');
    const progressText = document.getElementById('checklist-progress-text');
    
    if (!items || items.length === 0) {
        container.innerHTML = '<p style="color: var(--text2);">Nu există item-uri în checklist.</p>';
        progressFill.style.width = '0%';
        progressText.textContent = '0% completat';
        return;
    }
    
    const completed = items.filter(i => i.completed).length;
    const percent = Math.round((completed / items.length) * 100);
    
    progressFill.style.width = percent + '%';
    progressText.textContent = `${percent}% completat (${completed}/${items.length})`;
    
    container.innerHTML = items.map(item => `
        <div class="checklist-item">
            <input type="checkbox" ${item.completed ? 'checked' : ''} 
                   onchange="toggleChecklistItem('${item.id}', this.checked)">
            <div class="checklist-content">
                <div class="checklist-title" style="${item.completed ? 'text-decoration: line-through; opacity: 0.6;' : ''}">${escapeHtml(item.titlu)}</div>
                ${item.note ? `<div class="checklist-notes">${escapeHtml(item.note)}</div>` : ''}
            </div>
            <button class="btn btn-small btn-danger" onclick="deleteChecklistItem('${item.id}')">×</button>
        </div>
    `).join('');
}

async function addChecklistItem() {
    const title = document.getElementById('checklist-title').value.trim();
    if (!title || !currentProjectId) return;
    
    try {
        await apiPost(`/proiecte/${currentProjectId}/checklist`, {
            titlu: title,
            completed: 0,
            ordine: 0
        });
        document.getElementById('checklist-title').value = '';
        loadChecklist(currentProjectId);
        showToast('Item adăugat!');
    } catch (e) {
        console.error('Failed to add checklist item:', e);
        showToast('Eroare la adăugarea item-ului', true);
    }
}

async function toggleChecklistItem(itemId, checked) {
    try {
        await apiPut(`/checklist/${itemId}`, {
            completed: checked ? 1 : 0
        });
        loadChecklist(currentProjectId);
    } catch (e) {
        console.error('Failed to toggle checklist item:', e);
    }
}

async function deleteChecklistItem(itemId) {
    try {
        await apiDelete(`/checklist/${itemId}`);
        loadChecklist(currentProjectId);
        showToast('Item șters!');
    } catch (e) {
        console.error('Failed to delete checklist item:', e);
    }
}

// ============ TIMER ============

let timerInterval = null;
let activeSessionId = null;

async function loadTimerSessions(projectId) {
    try {
        const data = await apiGet(`/proiecte/${projectId}/timer`);
        renderTimerSessions(data.sessions, data.total_secunde);
    } catch (e) {
        console.error('Failed to load timer sessions:', e);
    }
}

function renderTimerSessions(sessions, totalSeconds) {
    const container = document.getElementById('timer-sessions-list');
    const totalEl = document.getElementById('timer-total');
    
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    totalEl.textContent = `Total: ${hours}h ${minutes}m`;
    
    if (!sessions || sessions.length === 0) {
        container.innerHTML = '<p style="color: var(--text2); font-size: 0.85rem;">Nu există sesiuni timer.</p>';
        return;
    }
    
    container.innerHTML = sessions.map(s => `
        <div class="timer-session">
            <div>
                <span style="font-weight: 500;">${formatTimerDuration(s.durata_secunde)}</span>
                <span style="color: var(--text2); font-size: 0.8rem; margin-left: 8px;">
                    ${s.start_time ? new Date(s.start_time).toLocaleDateString('ro-RO') : ''}
                </span>
            </div>
            <button class="btn btn-small btn-danger" onclick="deleteTimerSession('${s.id}')">×</button>
        </div>
    `).join('');
}

function formatTimerDuration(seconds) {
    if (!seconds) return '0m';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

async function startTimer() {
    if (!currentProjectId) return;
    
    try {
        const data = await apiPost(`/proiecte/${currentProjectId}/timer/start`, {});
        activeSessionId = data.id;
        
        document.getElementById('timer-start-btn').style.display = 'none';
        document.getElementById('timer-stop-btn').style.display = 'inline-flex';
        
        // Start interval to update display
        const startTime = new Date(data.start_time);
        timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            document.getElementById('timer-display').textContent = formatTime(elapsed);
        }, 1000);
        
        showToast('Timer pornit!');
    } catch (e) {
        console.error('Failed to start timer:', e);
        showToast('Eroare la pornirea timer-ului', true);
    }
}

async function stopTimer() {
    if (!currentProjectId) return;
    
    try {
        const data = await apiPost(`/proiecte/${currentProjectId}/timer/stop`, {});
        
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        
        document.getElementById('timer-display').textContent = '00:00:00';
        document.getElementById('timer-start-btn').style.display = 'inline-flex';
        document.getElementById('timer-stop-btn').style.display = 'none';
        
        loadTimerSessions(currentProjectId);
        showToast('Timer oprit!');
    } catch (e) {
        console.error('Failed to stop timer:', e);
        showToast('Eroare la oprirea timer-ului', true);
    }
}

async function deleteTimerSession(sessionId) {
    try {
        await apiDelete(`/timer/${sessionId}`);
        loadTimerSessions(currentProjectId);
        showToast('Sesiune ștearsă!');
    } catch (e) {
        console.error('Failed to delete timer session:', e);
    }
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// ============ EXTENDED STATS & CHARTS ============

let charts = {};

async function loadExtendedStats() {
    try {
        const [stats, extStats, projects] = await Promise.all([
            apiGet('/stats'),
            apiGet('/stats/extended'),
            apiGet('/proiecte?limit=100')
        ]);

        // Update stat cards
        document.getElementById('stats-total').textContent = stats.total || 0;
        document.getElementById('stats-active').textContent = stats.active || 0;
        document.getElementById('stats-finished').textContent = stats.finished || 0;
        document.getElementById('stats-hours').textContent = (extStats.total_billable_hours || 0) + 'h';

        // Initialize or update charts
        initCharts(extStats);

        // Load timeline
        renderTimeline(projects);

    } catch (e) {
        console.error('Failed to load extended stats:', e);
    }
}

function initCharts(data) {
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    const textColor = theme === 'dark' ? '#e2e8f0' : '#0f172a';
    const gridColor = theme === 'dark' ? '#1e293b' : '#e2e8f0';
    
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: textColor }
            }
        },
        scales: {
            x: {
                ticks: { color: textColor },
                grid: { color: gridColor }
            },
            y: {
                ticks: { color: textColor },
                grid: { color: gridColor }
            }
        }
    };
    
    // Status Pie Chart
    const statusCtx = document.getElementById('chart-status');
    if (charts.status) charts.status.destroy();
    if (data.by_status && data.by_status.length > 0) {
        charts.status = new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: data.by_status.map(s => getStatusLabel(s.status)),
                datasets: [{
                    data: data.by_status.map(s => s.count),
                    backgroundColor: ['#3b82f6', '#10b981', '#f97316', '#8b5cf6', '#ef4444']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor }
                    }
                }
            }
        });
    }
    
    // Manufacturer Bar Chart
    const mfrCtx = document.getElementById('chart-manufacturer');
    if (charts.manufacturer) charts.manufacturer.destroy();
    if (data.by_manufacturer && data.by_manufacturer.length > 0) {
        charts.manufacturer = new Chart(mfrCtx, {
            type: 'bar',
            data: {
                labels: data.by_manufacturer.map(m => m.producator),
                datasets: [{
                    label: 'Proiecte',
                    data: data.by_manufacturer.map(m => m.count),
                    backgroundColor: '#00d4ff'
                }]
            },
            options: chartOptions
        });
    }
    
    // Monthly Line Chart
    const monthlyCtx = document.getElementById('chart-monthly');
    if (charts.monthly) charts.monthly.destroy();
    if (data.by_month && data.by_month.length > 0) {
        charts.monthly = new Chart(monthlyCtx, {
            type: 'line',
            data: {
                labels: data.by_month.map(m => m.month),
                datasets: [{
                    label: 'Proiecte',
                    data: data.by_month.map(m => m.count),
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: chartOptions
        });
    } else {
        // Show empty state
        const ctx = monthlyCtx.getContext('2d');
        ctx.fillStyle = textColor;
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Nu există date pentru ultimele 12 luni', monthlyCtx.width / 2, monthlyCtx.height / 2);
    }
    
    // Hours Bar Chart
    const hoursCtx = document.getElementById('chart-hours');
    if (charts.hours) charts.hours.destroy();
    if (data.hours_per_project && data.hours_per_project.length > 0) {
        charts.hours = new Chart(hoursCtx, {
            type: 'bar',
            data: {
                labels: data.hours_per_project.map(h => h.nume.substring(0, 15) + (h.nume.length > 15 ? '...' : '')),
                datasets: [{
                    label: 'Ore',
                    data: data.hours_per_project.map(h => h.hours),
                    backgroundColor: '#10b981'
                }]
            },
            options: {
                ...chartOptions,
                indexAxis: 'y'
            }
        });
    } else {
        const ctx = hoursCtx.getContext('2d');
        ctx.fillStyle = textColor;
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Nu există sesiuni timer', hoursCtx.width / 2, hoursCtx.height / 2);
    }
}

// ============ TIMELINE ============

function renderTimeline(projects) {
    const container = document.getElementById('timeline-container');
    if (!container || !projects || projects.length === 0) return;

    const withDates = projects.filter(p => p.data_incepere || p.deadline);
    if (withDates.length === 0) {
        container.innerHTML = '<p style="color:var(--text2);padding:20px;">Nu există proiecte cu date.</p>';
        return;
    }

    const today = new Date();
    let minDate = new Date(today);
    let maxDate = new Date(today);
    withDates.forEach(p => {
        if (p.data_incepere) { const d = new Date(p.data_incepere); if (d < minDate) minDate = d; }
        if (p.deadline) { const d = new Date(p.deadline); if (d > maxDate) maxDate = d; }
    });
    minDate = new Date(Math.min(minDate.getTime(), today.getTime() - 90 * 24 * 60 * 60 * 1000));
    maxDate = new Date(Math.max(maxDate.getTime(), today.getTime() + 30 * 24 * 60 * 60 * 1000));

    let html = '';
    withDates.forEach(p => {
        const start = p.data_incepere ? new Date(p.data_incepere) : minDate;
        const end = p.deadline ? new Date(p.deadline) : maxDate;
        const totalRange = maxDate - minDate;
        const left = Math.max(0, ((start - minDate) / totalRange) * 100);
        const width = Math.min(100 - left, ((end - start) / totalRange) * 100);
        const status = p.status || 'in_lucru';
        const statusColors = { in_lucru: '#3b82f6', finalizat: '#10b981', blocat: '#ef4444', in_asteptare: '#f97316' };
        const color = statusColors[status] || '#3b82f6';
        html += `<div class="timeline-row">
            <div class="timeline-label" title="${escapeHtml(p.nume)}">${escapeHtml(p.nume.substring(0,30))}${p.nume.length>30?'…':''}</div>
            <div class="timeline-bar-container">
                <div class="timeline-bar ${status}" style="left:${left}%;width:${Math.max(width,3)}%;background:${color}" 
                     onclick="showProjectDetail('${p.id}')" title="${escapeHtml(p.nume)}">
                    ${escapeHtml(p.nume.substring(0,20))}${p.nume.length>20?'…':''}
                </div>
            </div>
        </div>`;
    });

    const todayPos = ((today - minDate) / (maxDate - minDate)) * 100;
    html += `<div class="timeline-today" style="left:${todayPos}%"></div>`;
    container.innerHTML = html;
}

// ============ SWIPE TO COMPLETE (Mobile) ============

let touchStartX = 0;
let touchStartY = 0;

document.addEventListener('touchstart', function(e) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
}, { passive: true });

document.addEventListener('touchend', function(e) {
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    const deltaX = touchEndX - touchStartX;
    const deltaY = touchEndY - touchStartY;
    
    // Swipe right to complete task (only if horizontal swipe > 50px and small vertical)
    if (deltaX > 50 && Math.abs(deltaY) < 30) {
        const target = e.target.closest('.todo-item, .gt-task-card');
        if (target) {
            const checkbox = target.querySelector('input[type="checkbox"]');
            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
                checkbox.dispatchEvent(new Event('change'));
            }
        }
    }
}, { passive: true });

// ============ UTILITIES ============

function debounce(fn, delay) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getStatusLabel(status) {
    const labels = {
        'in_lucru': 'În Lucru',
        'finalizat': 'Finalizat',
        'blocat': 'Blocat',
        'in_așteptare': 'În Așteptare',
        'to_do': 'To Do',
        'done': 'Finalizat'
    };
    return labels[status] || status;
}

const toastQueue = [];
const MAX_TOASTS = 3;

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
        'success': '✓',
        'error': '✗',
        'warning': '⚠',
        'info': 'ℹ'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.success}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);

    // Limit to MAX_TOASTS visible
    while (container.children.length > MAX_TOASTS) {
        const oldest = container.firstChild;
        if (oldest) {
            oldest.classList.remove('show');
            setTimeout(() => {
                if (oldest.parentNode) {
                    oldest.parentNode.removeChild(oldest);
                }
            }, 300);
        }
    }
}

function showConfirm(message, callback) {
    document.getElementById('confirm-message').textContent = message;
    confirmCallback = callback;
    document.getElementById('confirm-modal').classList.add('active');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.remove('active');
    confirmCallback = null;
}

function confirmAction() {
    if (confirmCallback) {
        confirmCallback();
    }
    closeConfirmModal();
}

// Drag and drop for file upload
const dropZone = document.getElementById('drop-zone');
if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const input = document.getElementById('file-input');
            const dt = new DataTransfer();
            for (const f of files) dt.items.add(f);
            input.files = dt.files;
            handleFileUpload({ target: input });
        }
    });
}

function initAccordions() {
    if (window.innerWidth > 768) return;
    document.querySelectorAll('.detail-section-header').forEach(header => {
        // Remove existing listeners by cloning
        const newHeader = header.cloneNode(true);
        header.parentNode.replaceChild(newHeader, header);
        newHeader.addEventListener('click', () => {
            const section = newHeader.parentElement;
            section.classList.toggle('collapsed');
        });
    });
    // On mobile, collapse all sections except the first one
    document.querySelectorAll('.detail-section').forEach((s, i) => {
        if (i > 0) s.classList.add('collapsed');
    });
}

// ============ CLIENTI (CLIENT DATABASE) ============

let clientListCache = [];

async function loadClientList() {
    try {
        clientListCache = await apiGet('/clienti');
        return clientListCache;
    } catch (e) {
        console.error('Failed to load client list:', e);
        return [];
    }
}

function onClientSearch() {
    const input = document.getElementById('p-client');
    const dropdown = document.getElementById('client-dropdown');
    const searchText = input.value.toLowerCase().trim();
    
    if (searchText.length === 0) {
        dropdown.classList.remove('active');
        return;
    }
    
    // Filter clients
    const filtered = clientListCache.filter(c => 
        (c.nume && c.nume.toLowerCase().includes(searchText)) ||
        (c.adresa && c.adresa.toLowerCase().includes(searchText)) ||
        (c.telefon && c.telefon.includes(searchText))
    );
    
    if (filtered.length === 0 && searchText.length > 0) {
        dropdown.innerHTML = `
            <div class="client-add-new" onclick="addNewClientFromAutocomplete('${escapeHtml(searchText)}')">
                + Adaugă "${escapeHtml(searchText)}" ca client nou
            </div>
        `;
    } else {
        dropdown.innerHTML = filtered.slice(0, 10).map(c => `
            <div class="client-option" onclick="selectClient('${c.id}', '${escapeHtml(c.nume)}')">
                <div class="client-option-name">${escapeHtml(c.nume)}</div>
                <div class="client-option-meta">${escapeHtml(c.adresa || '')} ${c.telefon ? '| ' + c.telefon : ''}</div>
            </div>
        `).join('') + `
            <div class="client-add-new" onclick="addNewClientFromAutocomplete('${escapeHtml(searchText)}')">
                + Adaugă "${escapeHtml(searchText)}" ca client nou
            </div>
        `;
    }
    
    dropdown.classList.add('active');
}

function selectClient(clientId, clientName) {
    document.getElementById('p-client').value = clientName;
    document.getElementById('p-client-id').value = clientId;
    document.getElementById('client-dropdown').classList.remove('active');
}

async function addNewClientFromAutocomplete(name) {
    document.getElementById('client-dropdown').classList.remove('active');
    document.getElementById('p-client').value = name;
    document.getElementById('p-client-id').value = '';
    
    // Try to add the client automatically
    try {
        await apiPost('/clienti', { nume: name });
        await loadClientList();
        const newClient = clientListCache.find(c => c.nume.toLowerCase() === name.toLowerCase());
        if (newClient) {
            document.getElementById('p-client-id').value = newClient.id;
        }
    } catch (e) {
        console.error('Failed to add client:', e);
    }
}

function hideClientDropdown() {
    setTimeout(() => {
        document.getElementById('client-dropdown').classList.remove('active');
    }, 200);
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
    const autocomplete = document.querySelector('.client-autocomplete');
    if (autocomplete && !autocomplete.contains(e.target)) {
        document.getElementById('client-dropdown').classList.remove('active');
    }
});

// ============ CLIENT LIST MODAL ============

async function showClientList() {
    await loadClientList();
    renderClientList(clientListCache);
    document.getElementById('client-list-modal').classList.add('active');
}

function closeClientListModal() {
    document.getElementById('client-list-modal').classList.remove('active');
}

function renderClientList(clients) {
    const container = document.getElementById('client-list-container');
    
    if (clients.length === 0) {
        container.innerHTML = '<p style="color: var(--text2); text-align: center; padding: 24px;">Nu există clienți. Adaugă primul client!</p>';
        return;
    }
    
    container.innerHTML = clients.map(c => `
        <div class="client-list-item" onclick="editClientFromList('${c.id}')">
            <div class="client-list-info">
                <div class="client-list-name">${escapeHtml(c.nume)}</div>
                <div class="client-list-details">
                    ${c.adresa ? escapeHtml(c.adresa) + ' | ' : ''}
                    ${c.telefon || ''}
                    ${c.email ? ' | ' + c.email : ''}
                </div>
            </div>
            <div class="client-list-actions">
                <button class="btn btn-small btn-secondary" onclick="event.stopPropagation(); editClientFromList('${c.id}')">✏️</button>
                <button class="btn btn-small btn-danger" onclick="event.stopPropagation(); deleteClientFromList('${c.id}')">×</button>
            </div>
        </div>
    `).join('');
}

function filterClientList() {
    const search = document.getElementById('client-list-search').value.toLowerCase().trim();
    if (!search) {
        renderClientList(clientListCache);
        return;
    }
    const filtered = clientListCache.filter(c =>
        (c.nume && c.nume.toLowerCase().includes(search)) ||
        (c.adresa && c.adresa.toLowerCase().includes(search)) ||
        (c.telefon && c.telefon.includes(search)) ||
        (c.email && c.email.toLowerCase().includes(search))
    );
    renderClientList(filtered);
}

function showAddClientForm(clientId = null) {
    document.getElementById('add-client-form').reset();
    document.getElementById('edit-client-id').value = clientId || '';
    
    if (clientId) {
        const client = clientListCache.find(c => c.id === clientId);
        if (client) {
            document.getElementById('add-client-title').textContent = 'Editează Client';
            document.getElementById('client-nume').value = client.nume || '';
            document.getElementById('client-adresa').value = client.adresa || '';
            document.getElementById('client-telefon').value = client.telefon || '';
            document.getElementById('client-email').value = client.email || '';
            document.getElementById('client-contact').value = client.contact_principal || '';
            document.getElementById('client-note').value = client.note || '';
        }
    } else {
        document.getElementById('add-client-title').textContent = 'Adaugă Client Nou';
    }
    
    document.getElementById('add-client-modal').classList.add('active');
}

function closeAddClientModal() {
    document.getElementById('add-client-modal').classList.remove('active');
}

async function saveClient(event) {
    event.preventDefault();
    
    const clientId = document.getElementById('edit-client-id').value;
    const clientData = {
        nume: document.getElementById('client-nume').value,
        adresa: document.getElementById('client-adresa').value,
        telefon: document.getElementById('client-telefon').value,
        email: document.getElementById('client-email').value,
        contact_principal: document.getElementById('client-contact').value,
        note: document.getElementById('client-note').value
    };
    
    try {
        if (clientId) {
            await apiPut(`/clienti/${clientId}`, clientData);
            showToast('Client actualizat!');
        } else {
            await apiPost('/clienti', clientData);
            showToast('Client adăugat!');
        }
        
        await loadClientList();
        closeAddClientModal();
        renderClientList(clientListCache);
    } catch (e) {
        console.error('Failed to save client:', e);
        showToast('Eroare la salvarea clientului', true);
    }
}

function editClientFromList(clientId) {
    showAddClientForm(clientId);
}

async function deleteClientFromList(clientId) {
    showConfirm('Sigur doriți să ștergeți acest client?', async () => {
        try {
            await apiDelete(`/clienti/${clientId}`);
            showToast('Client șters!');
            await loadClientList();
            renderClientList(clientListCache);
        } catch (e) {
            console.error('Failed to delete client:', e);
            showToast('Eroare la ștergerea clientului', true);
        }
    });
}

// ============ PROJECT TEMPLATES ============

let templateCache = [];

async function loadTemplates() {
    try {
        templateCache = await apiGet('/templates');
        return templateCache;
    } catch (e) {
        console.error('Failed to load templates:', e);
        return [];
    }
}

async function initTemplateSelector() {
    const templates = await loadTemplates();
    const select = document.getElementById('p-template');
    select.innerHTML = '<option value="">-- Fără template --</option>' + 
        templates.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
}

async function onTemplateChange() {
    const templateId = document.getElementById('p-template').value;
    if (!templateId) return;
    
    const template = templateCache.find(t => t.id === templateId);
    if (!template) return;
    
    // Set project type
    const typeRadio = document.querySelector(`input[name="project-type"][value="${template.tip}"]`);
    if (typeRadio) {
        typeRadio.checked = true;
        document.querySelectorAll('.project-type-btn').forEach(b => b.classList.remove('selected'));
        typeRadio.closest('.project-type-btn').classList.add('selected');
    }
}

// ============ EQUIPMENT (ECHIPAMENTE) ============

async function loadEchipamente(projectId) {
    try {
        const echipamente = await apiGet(`/proiecte/${projectId}/echipamente`);
        renderEchipamente(echipamente);
    } catch (e) {
        console.error('Failed to load echipamente:', e);
    }
}

function renderEchipamente(echipamente) {
    const container = document.getElementById('echipamente-list');
    
    if (!echipamente || echipamente.length === 0) {
        container.innerHTML = '<p style="color: var(--text2); font-size: 0.9rem;">Nu există echipamente adăugate.</p>';
        return;
    }
    
    container.innerHTML = echipamente.map(e => {
        let params = {};
        try {
            params = JSON.parse(e.params_json || '{}');
        } catch (err) {}
        
        const hasParams = Object.keys(params).length > 0;
        const paramsRows = Object.entries(params).map(([key, value]) => 
            `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(value)}</td></tr>`
        ).join('');
        
        return `
            <div class="echipament-card">
                <div class="echipament-header">
                    <span class="echipament-name">${escapeHtml(e.nume)}</span>
                    <div class="echipament-actions">
                        <button class="btn btn-small btn-secondary" onclick="editEchipament('${e.id}')">✏️</button>
                        <button class="btn btn-small btn-danger" onclick="deleteEchipament('${e.id}')">×</button>
                    </div>
                </div>
                <div class="echipament-meta">
                    ${e.producator ? `<span>${escapeHtml(e.producator)}</span>` : ''}
                    ${e.model ? `<span>${escapeHtml(e.model)}</span>` : ''}
                    ${e.serial_number ? `<span>S/N: ${escapeHtml(e.serial_number)}</span>` : ''}
                </div>
                ${hasParams ? `
                    <div class="echipament-params">
                        <div class="echipament-toggle" onclick="toggleEchipamentParams(this)">▼ Parametri</div>
                        <div class="echipament-expanded" style="display: none;">
                            <table class="echipament-params-table">
                                ${paramsRows}
                            </table>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

function toggleEchipamentParams(element) {
    const expanded = element.nextElementSibling;
    if (expanded.style.display === 'none') {
        expanded.style.display = 'block';
        element.textContent = '▲ Ascunde parametri';
    } else {
        expanded.style.display = 'none';
        element.textContent = '▼ Parametri';
    }
}

function showAddEquipmentForm() {
    if (!currentProjectId) return;
    
    // Remove existing form if any
    const existingForm = document.querySelector('.echipament-form');
    if (existingForm) existingForm.remove();
    
    const container = document.getElementById('echipamente-list');
    const formHtml = `
        <div class="echipament-form" id="echipament-form-container">
            <h4 style="margin-bottom: 12px; color: var(--text);">Adaugă Echipament Nou</h4>
            <div class="form-group">
                <label>Nume Echipament *</label>
                <input type="text" id="eq-nume" placeholder="ex: Convertizor de Frecvență" required>
            </div>
            <div class="form-group">
                <label>Producător</label>
                <select id="eq-producator">
                    <option value="ABB">ABB</option>
                    <option value="Siemens">Siemens</option>
                    <option value="Danfoss">Danfoss</option>
                    <option value="Lenze">Lenze</option>
                    <option value="Altul" selected>Altul</option>
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Model</label>
                    <input type="text" id="eq-model" placeholder="ex: ACS880-01">
                </div>
                <div class="form-group">
                    <label>Număr Serie</label>
                    <input type="text" id="eq-serial" placeholder="ex: 3AXD10012345">
                </div>
            </div>
            <div class="form-group">
                <label>Parametri (pXXXX=valoare, unul pe linie)</label>
                <textarea id="eq-params" rows="4" placeholder="p100=50Hz
p101=0
p102=100
..."></textarea>
            </div>
            <div class="echipament-form-actions">
                <button type="button" class="btn btn-secondary btn-small" onclick="hideEchipamentForm()">Anulează</button>
                <button type="button" class="btn btn-primary btn-small" onclick="saveEchipament()">Salvează</button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', formHtml);
}

function hideEchipamentForm() {
    const form = document.querySelector('.echipament-form');
    if (form) form.remove();
}

let editingEchipamentId = null;

async function editEchipament(echipamentId) {
    try {
        const eq = await apiGet(`/echipamente/${echipamentId}`);
        editingEchipamentId = echipamentId;
        
        // Remove existing form if any
        const existingForm = document.querySelector('.echipament-form');
        if (existingForm) existingForm.remove();
        
        const container = document.getElementById('echipamente-list');
        
        // Convert params_json back to text format
        let paramsText = '';
        try {
            const params = JSON.parse(eq.params_json || '{}');
            paramsText = Object.entries(params).map(([k, v]) => `${k}=${v}`).join('\n');
        } catch (err) {}
        
        const formHtml = `
            <div class="echipament-form" id="echipament-form-container">
                <h4 style="margin-bottom: 12px; color: var(--text);">Editează Echipament</h4>
                <div class="form-group">
                    <label>Nume Echipament *</label>
                    <input type="text" id="eq-nume" value="${escapeHtml(eq.nume || '')}" required>
                </div>
                <div class="form-group">
                    <label>Producător</label>
                    <select id="eq-producator">
                        <option value="ABB" ${eq.producator === 'ABB' ? 'selected' : ''}>ABB</option>
                        <option value="Siemens" ${eq.producator === 'Siemens' ? 'selected' : ''}>Siemens</option>
                        <option value="Danfoss" ${eq.producator === 'Danfoss' ? 'selected' : ''}>Danfoss</option>
                        <option value="Lenze" ${eq.producator === 'Lenze' ? 'selected' : ''}>Lenze</option>
                        <option value="Altul" ${!eq.producator || eq.producator === 'Altul' ? 'selected' : ''}>Altul</option>
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Model</label>
                        <input type="text" id="eq-model" value="${escapeHtml(eq.model || '')}">
                    </div>
                    <div class="form-group">
                        <label>Număr Serie</label>
                        <input type="text" id="eq-serial" value="${escapeHtml(eq.serial_number || '')}">
                    </div>
                </div>
                <div class="form-group">
                    <label>Parametri (pXXXX=valoare, unul pe linie)</label>
                    <textarea id="eq-params" rows="4">${escapeHtml(paramsText)}</textarea>
                </div>
                <div class="echipament-form-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="hideEchipamentForm()">Anulează</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="saveEchipament()">Salvează</button>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', formHtml);
    } catch (e) {
        console.error('Failed to load echipament:', e);
        showToast('Eroare la încărcarea echipamentului', true);
    }
}

async function saveEchipament() {
    const nume = document.getElementById('eq-nume').value.trim();
    if (!nume) {
        showToast('Completați numele echipamentului', true);
        return;
    }
    
    const data = {
        nume: nume,
        producator: document.getElementById('eq-producator').value,
        model: document.getElementById('eq-model').value,
        serial_number: document.getElementById('eq-serial').value,
        params_text: document.getElementById('eq-params').value
    };
    
    try {
        if (editingEchipamentId) {
            await apiPut(`/echipamente/${editingEchipamentId}`, data);
            showToast('Echipament actualizat!');
            editingEchipamentId = null;
        } else {
            await apiPost(`/proiecte/${currentProjectId}/echipamente`, data);
            showToast('Echipament adăugat!');
        }
        
        hideEchipamentForm();
        loadEchipamente(currentProjectId);
    } catch (e) {
        console.error('Failed to save echipament:', e);
        showToast('Eroare la salvarea echipamentului', true);
    }
}

async function deleteEchipament(echipamentId) {
    showConfirm('Sigur doriți să ștergeți acest echipament?', async () => {
        try {
            await apiDelete(`/echipamente/${echipamentId}`);
            showToast('Echipament șters!');
            loadEchipamente(currentProjectId);
        } catch (e) {
            console.error('Failed to delete echipament:', e);
            showToast('Eroare la ștergerea echipamentului', true);
        }
    });
}

// ============ PROJECT DETAIL - LOAD EQUIPMENT ============

// Override showProjectDetail to also load equipment
const originalShowProjectDetail = showProjectDetail;
showProjectDetail = async function(projectId) {
    await originalShowProjectDetail(projectId);
    await loadEchipamente(projectId);
};

// Initialize template selector when showing new project form
const originalShowNewProjectForm = showNewProjectForm;
showNewProjectForm = async function() {
    originalShowNewProjectForm();
    await initTemplateSelector();
    await loadClientList();
};

// ============ BATCH OPERATIONS ============

let batchMode = false;
let selectedProjects = new Set();

function toggleBatchMode() {
    batchMode = !batchMode;
    selectedProjects.clear();
    
    const batchBtn = document.getElementById('batch-mode-btn');
    const batchBar = document.getElementById('batch-action-bar');
    const headerCheckbox = document.getElementById('batch-select-all');
    
    if (batchBtn) {
        batchBtn.classList.toggle('active', batchMode);
        batchBtn.textContent = batchMode ? '✓ Mod Selectare' : 'Mod Selectare';
    }
    
    if (batchBar) {
        batchBar.style.display = batchMode ? 'flex' : 'none';
    }
    
    // Toggle checkbox column visibility
    document.querySelectorAll('.batch-checkbox').forEach(cb => {
        cb.style.display = batchMode ? 'inline-block' : 'none';
    });
    
    if (headerCheckbox) {
        headerCheckbox.style.display = batchMode ? 'inline-block' : 'none';
    }
    
    if (!batchMode) {
        updateBatchActionBar();
    }
}

function toggleProjectSelection(projectId) {
    if (selectedProjects.has(projectId)) {
        selectedProjects.delete(projectId);
    } else {
        selectedProjects.add(projectId);
    }
    updateBatchActionBar();
}

function selectAllProjects() {
    const checkboxes = document.querySelectorAll('.project-row-checkbox');
    const headerCheckbox = document.getElementById('batch-select-all');
    const allSelected = headerCheckbox?.checked;
    
    checkboxes.forEach(cb => {
        cb.checked = allSelected;
        const pid = cb.dataset.projectId;
        if (allSelected) {
            selectedProjects.add(pid);
        } else {
            selectedProjects.delete(pid);
        }
    });
    updateBatchActionBar();
}

function updateBatchActionBar() {
    const count = selectedProjects.size;
    const countEl = document.getElementById('batch-selected-count');
    const actionBtns = document.getElementById('batch-action-buttons');
    
    if (countEl) countEl.textContent = `${count} selectat${count !== 1 ? 'e' : ''}`;
    if (actionBtns) {
        actionBtns.style.display = count > 0 ? 'flex' : 'none';
    }
}

async function batchUpdateStatus(newStatus) {
    if (selectedProjects.size === 0) return;
    
    const action = newStatus === 'finalizat' ? 'Marchează Finalizat' : 
                   newStatus === 'in_lucru' ? 'Marchează În Lucru' : newStatus;
    
    showConfirm(`Doriți să ${action} proiectele selectate?`, async () => {
        try {
            await apiPost('/proiecte/batch', {
                action: 'update_status',
                project_ids: Array.from(selectedProjects),
                status: newStatus
            });
            showToast(`${selectedProjects.size} proiecte actualizate!`);
            toggleBatchMode();
            await loadProjects();
        } catch (e) {
            console.error('Batch update failed:', e);
            showToast('Eroare la actualizarea proiectelor', true);
        }
    });
}

async function batchDeleteProjects() {
    if (selectedProjects.size === 0) return;
    
    showConfirm(`Sigur doriți să ștergeți ${selectedProjects.size} proiecte? Această acțiune nu poate fi anulată!`, async () => {
        try {
            await apiPost('/proiecte/batch', {
                action: 'delete',
                project_ids: Array.from(selectedProjects)
            });
            showToast(`${selectedProjects.size} proiecte șterse!`);
            toggleBatchMode();
            await loadProjects();
            await updateStats();
        } catch (e) {
            console.error('Batch delete failed:', e);
            showToast('Eroare la ștergerea proiectelor', true);
        }
    });
}

// ============ UNDO/REDO SYSTEM ============

const MAX_UNDO_STACK = 10;
let undoStack = [];
let redoStack = [];

function pushUndo(action) {
    undoStack.push(action);
    if (undoStack.length > MAX_UNDO_STACK) {
        undoStack.shift();
    }
    redoStack = []; // Clear redo stack on new action
    updateUndoRedoButtons();
}

function updateUndoRedoButtons() {
    const undoBtn = document.getElementById('undo-btn');
    const redoBtn = document.getElementById('redo-btn');
    
    if (undoBtn) {
        undoBtn.style.display = undoStack.length > 0 ? 'flex' : 'none';
        undoBtn.title = undoStack.length > 0 ? `Anulează: ${undoStack[undoStack.length - 1].description}` : '';
    }
    if (redoBtn) {
        redoBtn.style.display = redoStack.length > 0 ? 'flex' : 'none';
        redoBtn.title = redoStack.length > 0 ? `Refă: ${redoStack[redoStack.length - 1].description}` : '';
    }
}

async function undo() {
    if (undoStack.length === 0) return;
    
    const action = undoStack.pop();
    redoStack.push(action);
    
    try {
        if (action.type === 'task_toggle') {
            await apiPut(`/global-tasks/${action.taskId}`, {
                status: action.previousState.status,
                data_finalizare: action.previousState.data_finalizare || ''
            });
            showToast(`Acțiune anulată: ${action.description}`);
        } else if (action.type === 'task_delete') {
            // Recreate the deleted task
            await apiPost('/global-tasks', action.previousState);
            showToast(`Acțiune anulată: ${action.description}`);
        } else if (action.type === 'task_create') {
            // Delete the created task
            await apiDelete(`/global-tasks/${action.taskId}`);
            showToast(`Acțiune anulată: ${action.description}`);
        } else if (action.type === 'checklist_toggle') {
            await apiPut(`/proiecte/${action.projectId}/checklist/${action.itemId}`, {
                completat: action.previousState ? 0 : 1
            });
            showToast(`Acțiune anulată: ${action.description}`);
        }
        
        await loadGlobalTasks();
        updateUndoRedoButtons();
    } catch (e) {
        console.error('Undo failed:', e);
        showToast('Eroare la anularea acțiunii', true);
    }
}

async function redo() {
    if (redoStack.length === 0) return;
    
    const action = redoStack.pop();
    undoStack.push(action);
    
    try {
        if (action.type === 'task_toggle') {
            await apiPut(`/global-tasks/${action.taskId}`, {
                status: action.newState.status,
                data_finalizare: action.newState.data_finalizare || ''
            });
            showToast(`Acțiune refăcută: ${action.description}`);
        } else if (action.type === 'task_delete') {
            // Delete the task again
            await apiDelete(`/global-tasks/${action.taskId}`);
            showToast(`Acțiune refăcută: ${action.description}`);
        } else if (action.type === 'task_create') {
            // Recreate the task
            await apiPost('/global-tasks', action.newState);
            showToast(`Acțiune refăcută: ${action.description}`);
        } else if (action.type === 'checklist_toggle') {
            await apiPut(`/proiecte/${action.projectId}/checklist/${action.itemId}`, {
                completat: action.previousState ? 0 : 1
            });
            showToast(`Acțiune refăcută: ${action.description}`);
        }
        
        await loadGlobalTasks();
        updateUndoRedoButtons();
    } catch (e) {
        console.error('Redo failed:', e);
        showToast('Eroare la refacerea acțiunii', true);
    }
}

// Override task functions to track undo

const originalToggleGtTask = toggleGtTask;
toggleGtTask = async function(taskId, checked) {
    // Get current task state before toggle for undo
    try {
        const task = await apiGet(`/global-tasks/${taskId}`);
        const previousState = {
            status: task.status,
            data_finalizare: task.data_finalizare
        };
        const newState = {
            status: checked ? 'done' : 'to_do',
            data_finalizare: checked ? new Date().toISOString() : ''
        };
        
        pushUndo({
            type: 'task_toggle',
            taskId: taskId,
            description: `Toggle task: ${task.titlu}`,
            previousState: previousState,
            newState: newState
        });
    } catch (e) {
        console.error('Failed to capture task state for undo:', e);
    }
    
    await originalToggleGtTask(taskId, checked);
};

const originalDeleteGtTask = deleteGtTask;
deleteGtTask = async function(taskId) {
    // Get task data before delete for undo
    try {
        const task = await apiGet(`/global-tasks/${taskId}`);
        if (task) {
            pushUndo({
                type: 'task_delete',
                taskId: taskId,
                description: `Ștergere task: ${task.titlu}`,
                previousState: task
            });
        }
    } catch (e) {
        console.error('Failed to capture task state for undo:', e);
    }
    
    await originalDeleteGtTask(taskId);
};

const originalQuickAddTask = quickAddTask;
quickAddTask = async function() {
    const input = document.getElementById('quick-task-input');
    const titlu = input.value.trim();
    
    // Capture the task data that will be created
    const taskData = {
        titlu: titlu,
        prioritate: document.getElementById('quick-prioritate').value,
        categorie: document.getElementById('quick-categorie').value,
        data_scadenta: document.getElementById('quick-scadenta').value || '',
        status: 'to_do'
    };
    
    await originalQuickAddTask();
    
    // Find the created task and push to undo stack
    // Since we can't easily get the ID, we'll push with a placeholder
    // The undo will still work by matching title
    setTimeout(async () => {
        try {
            const tasks = await apiGet('/global-tasks');
            const created = tasks.find(t => t.titlu === titlu && t.status === 'to_do');
            if (created) {
                // Remove the auto-pushed undo and replace with correct one
                undoStack.pop();
                pushUndo({
                    type: 'task_create',
                    taskId: created.id,
                    description: `Creare task: ${titlu}`,
                    newState: created
                });
            }
        } catch (e) {
            console.error('Failed to capture created task for undo:', e);
        }
    }, 100);
};

// ============ PWA / OFFLINE SUPPORT ============

let deferredPrompt = null;

function initPWA() {
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/static/service-worker.js')
                .then(registration => {
                    console.log('SW registered:', registration.scope);
                })
                .catch(error => {
                    console.error('SW registration failed:', error);
                });
        });
    }
    
    // Capture install prompt
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        console.log('Install prompt captured');
        // Show the install button
        const installBtn = document.getElementById('install-pwa-btn');
        if (installBtn) installBtn.style.display = 'flex';
    });
}

async function installPWA() {
    if (!deferredPrompt) {
        showToast('Instalare nu este disponibilă', true);
        return;
    }
    
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
        showToast('PIF Dashboard instalat!', 'success');
    }
    deferredPrompt = null;
}

// Initialize PWA on load
document.addEventListener('DOMContentLoaded', initPWA);

// Keyboard shortcuts for undo/redo
document.addEventListener('keydown', function(e) {
    const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName);
    
    // Ctrl+Z - Undo
    if (e.key === 'z' && (e.ctrlKey || e.metaKey) && !e.shiftKey && !isInput) {
        e.preventDefault();
        undo();
        return;
    }
    
    // Ctrl+Shift+Z or Ctrl+Y - Redo
    if ((e.key === 'z' && (e.ctrlKey || e.metaKey) && e.shiftKey) || 
        (e.key === 'y' && (e.ctrlKey || e.metaKey)) && !isInput) {
        e.preventDefault();
        redo();
        return;
    }
});
