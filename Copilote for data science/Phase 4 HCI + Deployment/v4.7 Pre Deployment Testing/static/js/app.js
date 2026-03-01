/* ═══════════════════════════════════════════════════════════════════════
   DATA SCIENCE COPILOT — Frontend Logic v4.4
   Rich chat messages, alive assistant, code activity bucket
   ═══════════════════════════════════════════════════════════════════════ */

// ── State ────────────────────────────────────────────────────────────
let currentSessionId = null;
let currentDataset = null;
let codeSnippetsCache = [];

// ── Theme Toggle ─────────────────────────────────────────────────────
function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    localStorage.setItem('copilot-theme', next);
    updateThemeButton(next);
}

function updateThemeButton(theme) {
    const icon = document.getElementById('theme-icon');
    const label = document.getElementById('theme-label');
    if (icon) icon.textContent = theme === 'light' ? '☀️' : '🌙';
    if (label) label.textContent = theme === 'light' ? 'Light' : 'Dark';
}

function initTheme() {
    const saved = localStorage.getItem('copilot-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeButton(saved);
}

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadSessions();
    loadCodeSnippets();
});

// ── Auth ─────────────────────────────────────────────────────────────
async function handleLogout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login';
}

// ── File Upload ──────────────────────────────────────────────────────
async function handleUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const uploadZone = document.getElementById('upload-zone');
    const origHTML = uploadZone.innerHTML;
    uploadZone.innerHTML = '<p class="upload-text">⏳ Uploading...</p>';

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            currentSessionId = data.dataset.session_id;
            currentDataset = data.dataset;
            showDatasetInfo(data.dataset);
            showSplitPanel();
            clearChat();
            clearResults();
            loadSessions();
            // Add welcome message from assistant
            appendMessage('assistant', "👋 **Dataset loaded!** I can see your file has **" +
                data.dataset.rows.toLocaleString() + " rows** and **" +
                data.dataset.columns + " columns**. Ask me anything about your data!");
        } else {
            alert(data.error || 'Upload failed');
        }
    } catch (err) {
        alert('Network error during upload');
    } finally {
        uploadZone.innerHTML = origHTML;
        input.value = '';
    }
}

function showDatasetInfo(ds) {
    document.getElementById('dataset-info').style.display = 'block';
    document.getElementById('dataset-name').textContent = ds.filename;
    document.getElementById('metric-rows').textContent = ds.rows.toLocaleString();
    document.getElementById('metric-cols').textContent = ds.columns;
    document.getElementById('metric-missing').textContent = ds.missing.toLocaleString();
    document.getElementById('metric-numeric').textContent = ds.numeric_count;

    const colList = document.getElementById('columns-list');
    colList.innerHTML = ds.column_names.map(c => {
        const icon = ds.dtypes[c].includes('int') || ds.dtypes[c].includes('float') ? '🔢' : '🔤';
        return `<span class="col-badge">${icon} ${c}</span>`;
    }).join('');
}

function showSplitPanel() {
    document.getElementById('welcome-screen').style.display = 'none';
    document.getElementById('split-panel').style.display = 'flex';
    document.getElementById('chat-input').focus();
}

// ── Sessions ─────────────────────────────────────────────────────────
async function loadSessions() {
    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();
        const list = document.getElementById('sessions-list');

        if (data.sessions.length === 0) {
            list.innerHTML = '<p class="muted-text">No sessions yet</p>';
            return;
        }

        list.innerHTML = data.sessions.map(s => {
            const active = s.id === currentSessionId ? 'active' : '';
            const name = s.filename || s.title;
            const date = new Date(s.created_at).toLocaleDateString();
            return `
                <div class="session-item ${active}" onclick="switchSession(${s.id})">
                    <span class="session-icon">💬</span>
                    <span class="session-name" title="${name}">${name}</span>
                    <span class="muted-text" style="font-size:0.65rem;">${date}</span>
                </div>`;
        }).join('');
    } catch (err) {
        console.error('Failed to load sessions:', err);
    }
}

async function switchSession(sessionId) {
    currentSessionId = sessionId;

    try {
        const res = await fetch(`/api/sessions/${sessionId}/messages`);
        const data = await res.json();

        if (data.dataset) {
            currentDataset = data.dataset;
            showDatasetInfo(data.dataset);
        }

        showSplitPanel();
        clearChat();
        clearResults();

        // Render messages
        data.messages.forEach(msg => {
            appendMessage(msg.role, msg.content);
            if (msg.result_type && msg.result_data) {
                appendResult(msg.result_title || 'Result', msg.result_type, msg.result_data);
            }
        });

        // Update active session indicator
        document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
        document.querySelector(`.session-item[onclick="switchSession(${sessionId})"]`)?.classList.add('active');

    } catch (err) {
        console.error('Failed to switch session:', err);
    }
}

// ── Chat ─────────────────────────────────────────────────────────────
async function handleChat(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg || !currentSessionId) return;

    input.value = '';
    input.disabled = true;
    document.getElementById('send-btn').disabled = true;

    // Show user message
    appendMessage('user', msg);

    // Show typing indicator
    const typingEl = showTyping();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg, session_id: currentSessionId }),
        });
        const data = await res.json();

        // Remove typing indicator
        typingEl.remove();

        if (res.ok) {
            const am = data.assistant_msg;
            appendMessage('assistant', am.content, am.result_type);

            if (am.result_type && am.result_data) {
                appendResult(am.result_title || 'Result', am.result_type, am.result_data);
            }

            // Refresh dataset info for modify operations
            if (am.result_title && am.result_title.includes('Modified')) {
                refreshDatasetInfo();
            }

            // Refresh code snippets panel
            loadCodeSnippets();
        } else {
            appendMessage('assistant', data.error || '⚠️ Something went wrong.');
        }
    } catch (err) {
        typingEl.remove();
        appendMessage('assistant', '⚠️ Network error. Please try again.');
    } finally {
        input.disabled = false;
        document.getElementById('send-btn').disabled = false;
        input.focus();
    }
}

function sendSuggestion(text) {
    if (!currentSessionId) {
        alert('Please upload a CSV file first.');
        return;
    }
    document.getElementById('chat-input').value = text;
    document.getElementById('chat-form').dispatchEvent(new Event('submit', { cancelable: true }));
}

// ── Message Rendering ────────────────────────────────────────────────
function appendMessage(role, content, resultType) {
    const container = document.getElementById('chat-messages');
    const avatar = role === 'user' ? '🧑' : '🤖';
    const div = document.createElement('div');
    div.className = `msg ${role}`;

    let bubbleContent = '';
    if (role === 'assistant') {
        // Render markdown for assistant messages
        bubbleContent = renderMarkdown(content);

        // Add status chip for operations
        if (resultType) {
            const chipInfo = getStatusChip(resultType);
            bubbleContent += `<div class="status-chip ${chipInfo.cls}">${chipInfo.icon} ${chipInfo.label}</div>`;
        }
    } else {
        bubbleContent = escapeHtml(content);
    }

    div.innerHTML = `
        <div class="msg-avatar">${avatar}</div>
        <div class="msg-bubble">${bubbleContent}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function getStatusChip(resultType) {
    const chips = {
        'dataframe': { icon: '📊', label: 'Data loaded in results', cls: 'chip-display' },
        'chart': { icon: '📈', label: 'Chart created', cls: 'chip-visualize' },
        'modify': { icon: '✅', label: 'Data modified — preview ready', cls: 'chip-modify' },
        'text': { icon: '💡', label: 'Result ready', cls: 'chip-text' },
    };
    return chips[resultType] || { icon: '✅', label: 'Done', cls: 'chip-default' };
}

function renderMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic: *text* (but not inside bold)
    html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
    // Inline code: `text`
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    // Arrows → stay as is (already escaped)

    return html;
}

function showTyping() {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-bubble">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function clearChat() {
    document.getElementById('chat-messages').innerHTML = '';
}

// ── Results Rendering ────────────────────────────────────────────────
function appendResult(title, type, data) {
    const container = document.getElementById('results-content');

    // Clear empty state
    const empty = container.querySelector('.results-empty');
    if (empty) empty.remove();

    const block = document.createElement('div');
    block.className = 'result-block';

    let content = '';
    if (type === 'chart') {
        content = `<img src="data:image/png;base64,${data}" alt="${title}">`;
    } else if (type === 'modify') {
        content = buildModifyPreview(title, data);
    } else if (type === 'dataframe') {
        content = buildTable(data);
    } else {
        content = `<div class="result-text">${escapeHtml(data)}</div>`;
    }

    block.innerHTML = `<div class="result-title">${escapeHtml(title)}</div>${content}`;

    // Insert at top (newest first)
    container.insertBefore(block, container.firstChild);
}

function buildTable(jsonData) {
    try {
        const parsed = JSON.parse(jsonData);
        const columns = parsed.columns || [];
        const rows = parsed.data || [];

        if (columns.length === 0) return '<div class="result-text">Empty result</div>';

        let html = '<div style="overflow-x:auto; max-height:400px; overflow-y:auto;">';
        html += '<table><thead><tr>';
        columns.forEach(c => { html += `<th>${escapeHtml(String(c))}</th>`; });
        html += '</tr></thead><tbody>';

        rows.forEach(row => {
            html += '<tr>';
            row.forEach(val => {
                const display = val === null ? '—' : String(val);
                html += `<td>${escapeHtml(display)}</td>`;
            });
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        return html;
    } catch (e) {
        return `<div class="result-text">Could not render table</div>`;
    }
}

function clearResults() {
    document.getElementById('results-content').innerHTML = `
        <div class="results-empty">
            <p>📋 Results will appear here</p>
            <p class="muted-text">Ask a question in the chat panel</p>
        </div>`;
}

// ── Modify Output Preview ────────────────────────────────────────────
function buildModifyPreview(title, jsonData) {
    let tableHtml = buildTable(jsonData);
    return `
        <div class="modify-preview">
            <div class="modify-preview-header">
                <span class="modify-preview-icon">📁</span>
                <span class="modify-preview-title">Output Data Preview</span>
                <div class="modify-preview-actions">
                    <button class="btn-icon" onclick="downloadModified()" title="Download modified CSV">
                        ⬇️
                    </button>
                    <button class="btn-icon" onclick="this.closest('.modify-preview').querySelector('.modify-table-wrap').classList.toggle('expanded')" title="Expand">
                        🔍
                    </button>
                </div>
            </div>
            <div class="modify-table-wrap">
                ${tableHtml}
            </div>
        </div>`;
}

async function downloadModified() {
    if (!currentSessionId) return;
    try {
        const res = await fetch(`/api/download-modified?session_id=${currentSessionId}`);
        if (!res.ok) {
            alert('Download failed');
            return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `modified_data.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        alert('Download failed: ' + err.message);
    }
}

// ── Code Activity Panel ──────────────────────────────────────────────
function toggleCodePanel() {
    const list = document.getElementById('code-activity-list');
    const icon = document.getElementById('code-toggle-icon');
    if (list.style.display === 'none') {
        list.style.display = 'block';
        icon.textContent = '▾';
        loadCodeSnippets();
    } else {
        list.style.display = 'none';
        icon.textContent = '▸';
    }
}

async function loadCodeSnippets() {
    try {
        const res = await fetch('/api/code-snippets');
        const data = await res.json();
        codeSnippetsCache = data.snippets || [];
        renderCodeSnippets();
    } catch (err) {
        console.error('Failed to load code snippets:', err);
    }
}

function renderCodeSnippets() {
    const list = document.getElementById('code-activity-list');
    const emptyMsg = document.getElementById('code-empty-msg');

    if (codeSnippetsCache.length === 0) {
        if (emptyMsg) emptyMsg.style.display = 'block';
        // Clear any existing items but keep the empty message
        const items = list.querySelectorAll('.code-snippet-item');
        items.forEach(el => el.remove());
        return;
    }

    if (emptyMsg) emptyMsg.style.display = 'none';

    // Remove old items
    const oldItems = list.querySelectorAll('.code-snippet-item');
    oldItems.forEach(el => el.remove());

    // Render new items (show latest 20)
    const toShow = codeSnippetsCache.slice(0, 20);
    toShow.forEach(snippet => {
        const item = document.createElement('div');
        item.className = 'code-snippet-item';
        item.onclick = () => viewCodeSnippet(snippet);

        const opIcons = { display: '📊', visualize: '📈', modify: '✏️' };
        const opIcon = opIcons[snippet.operation] || '🔧';
        const time = new Date(snippet.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        item.innerHTML = `
            <span class="snippet-icon">${opIcon}</span>
            <span class="snippet-label" title="${escapeHtml(snippet.label)}">${escapeHtml(snippet.label)}</span>
            <span class="snippet-time">${time}</span>`;
        list.appendChild(item);
    });
}

// ── Code Viewer Modal ────────────────────────────────────────────────
let currentModalCode = '';

function viewCodeSnippet(snippet) {
    currentModalCode = snippet.code;
    document.getElementById('code-modal-label').textContent = snippet.label;

    const opLabels = { display: 'Display', visualize: 'Visualize', modify: 'Modify' };
    const date = new Date(snippet.created_at).toLocaleString();
    document.getElementById('code-modal-meta').textContent = `${opLabels[snippet.operation] || snippet.operation} • ${date}`;

    document.getElementById('code-modal-code').textContent = snippet.code;
    document.getElementById('code-modal-overlay').classList.add('visible');
}

function closeCodeModal(event) {
    if (event && event.target !== document.getElementById('code-modal-overlay')) return;
    document.getElementById('code-modal-overlay').classList.remove('visible');
}

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.getElementById('code-modal-overlay').classList.remove('visible');
    }
});

async function copyCode() {
    try {
        await navigator.clipboard.writeText(currentModalCode);
        const btn = document.querySelector('.code-modal-actions .btn-ghost');
        const orig = btn.textContent;
        btn.textContent = '✅ Copied!';
        setTimeout(() => { btn.textContent = orig; }, 1500);
    } catch (err) {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = currentModalCode;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
    }
}

// ── Helpers ──────────────────────────────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function refreshDatasetInfo() {
    if (!currentSessionId) return;
    try {
        const res = await fetch(`/api/sessions/${currentSessionId}/messages`);
        const data = await res.json();
        if (data.dataset) {
            currentDataset = data.dataset;
            showDatasetInfo(data.dataset);
        }
    } catch (err) { }
}

/* ═══════════════════════════════════════════════════════════════════════
   PRO MODE — Frontend Logic
   Mode toggle, plan display, step tracking, approval flow
   ═══════════════════════════════════════════════════════════════════════ */

// Pro Mode state
let proModeActive = false;
let currentPlanId = null;
let currentPlanData = null;
let proPollingTimer = null;

// Node type icons mapping
const NODE_ICONS = {
    analysis: '🔬', transformation: '⚙️', visualization: '📊',
    conditional: '⑂', summary: '📝', operation: '▶'
};

// ── Mode Toggle ─────────────────────────────────────────────────────
function toggleProMode(isActive) {
    proModeActive = isActive;
    const html = document.documentElement;
    const badge = document.getElementById('mode-badge');
    const proPanels = document.getElementById('pro-panels');

    if (isActive) {
        html.setAttribute('data-mode', 'pro');
        badge.textContent = 'Pro';
        badge.classList.add('pro-active');
        if (proPanels) proPanels.style.display = 'flex';
    } else {
        html.removeAttribute('data-mode');
        badge.textContent = 'Normal';
        badge.classList.remove('pro-active');
        if (proPanels) proPanels.style.display = 'none';
        clearProState();
    }
    localStorage.setItem('copilot-mode', isActive ? 'pro' : 'normal');
}

function initProMode() {
    const saved = localStorage.getItem('copilot-mode');
    if (saved === 'pro') {
        const toggle = document.getElementById('mode-toggle');
        if (toggle) {
            toggle.checked = true;
            toggleProMode(true);
        }
    }
}

// Add to DOMContentLoaded
const _origInit = document.addEventListener;
document.addEventListener('DOMContentLoaded', () => { initProMode(); });

function clearProState() {
    currentPlanId = null;
    currentPlanData = null;
    if (proPollingTimer) { clearInterval(proPollingTimer); proPollingTimer = null; }
    const planContent = document.getElementById('pro-plan-content');
    if (planContent) planContent.innerHTML = '<div class="pro-plan-empty"><p>🎯 Enter a complex request in the chat to generate a DAG plan</p></div>';
    const actions = document.getElementById('pro-plan-actions');
    if (actions) actions.style.display = 'none';
    const stepsList = document.getElementById('pro-steps-list');
    if (stepsList) stepsList.innerHTML = '';
    const summary = document.getElementById('pro-summary');
    if (summary) { summary.style.display = 'none'; summary.innerHTML = ''; }
    const status = document.getElementById('pro-plan-status');
    if (status) status.textContent = '';
    const progress = document.getElementById('pro-progress');
    if (progress) progress.textContent = '';
}

// ── Override handleChat for Pro Mode ─────────────────────────────────
const _originalHandleChat = handleChat;

handleChat = async function (e) {
    if (!proModeActive) {
        return _originalHandleChat(e);
    }

    // Pro Mode chat flow
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg || !currentSessionId) return;

    input.value = '';
    input.disabled = true;
    document.getElementById('send-btn').disabled = true;

    appendMessage('user', msg);
    const typingEl = showTyping();

    try {
        // Request plan from Pro engine
        const res = await fetch('/api/pro/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg, session_id: currentSessionId }),
        });
        const data = await res.json();
        typingEl.remove();

        if (data.requires_confirmation) {
            appendMessage('assistant', `⚠️ **Dataset Size Warning**\n\n${data.warning}\n\nSend your request again to proceed.`);
            return;
        }

        if (data.error) {
            appendMessage('assistant', `⚠️ ${data.error}`);
            return;
        }

        if (data.plan_id) {
            currentPlanId = data.plan_id;
            currentPlanData = data;
            appendMessage('assistant', `📍 **DAG Plan Generated** — ${data.node_count} steps\n\nReview the plan in the **Plan Panel** on the right, then click **Approve & Execute** to run it.`);
            renderPlan(data);
        } else {
            appendMessage('assistant', '⚠️ Could not generate a plan. Try rephrasing.');
        }
    } catch (err) {
        typingEl.remove();
        appendMessage('assistant', '⚠️ Network error during plan generation.');
    } finally {
        input.disabled = false;
        document.getElementById('send-btn').disabled = false;
        input.focus();
    }
};

// ── Plan Rendering ──────────────────────────────────────────────────
function renderPlan(data) {
    const planContent = document.getElementById('pro-plan-content');
    const actions = document.getElementById('pro-plan-actions');
    const status = document.getElementById('pro-plan-status');

    if (!data.plan || !data.plan.nodes) return;

    const nodes = data.plan.nodes;
    status.textContent = `v${data.plan.version || 1}`;
    status.style.color = '#c9a84c';

    let html = '';
    nodes.forEach((node, i) => {
        const type = node.type || 'operation';
        const icon = NODE_ICONS[type] || '▶';
        html += `
            <div class="pro-node-item pro-node-type-${type}" id="pro-node-${node.id}">
                <div class="pro-node-icon">${icon}</div>
                <div class="pro-node-info">
                    <div class="pro-node-name">${i + 1}. ${escapeHtml(node.operation || node.type)}</div>
                    <div class="pro-node-desc">${escapeHtml(node.description || '')}</div>
                </div>
                <span class="pro-node-status pending">pending</span>
            </div>`;
    });

    planContent.innerHTML = html;
    actions.style.display = 'flex';
}

// ── Approve & Execute ───────────────────────────────────────────────
async function approvePlan() {
    if (!currentPlanId) return;

    const btn = document.getElementById('btn-approve');
    btn.disabled = true;
    btn.innerHTML = '<span>⏳</span> Executing...';

    document.getElementById('pro-plan-actions').style.display = 'none';

    appendMessage('assistant', '🚀 **Plan approved!** Executing steps...');

    // Initialize step tracker
    if (currentPlanData && currentPlanData.plan) {
        initStepTracker(currentPlanData.plan.nodes);
    }

    try {
        const res = await fetch('/api/pro/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_id: currentPlanId }),
        });
        const result = await res.json();

        if (result.error) {
            appendMessage('assistant', `⚠️ Execution failed: ${result.error}`);
            btn.disabled = false;
            btn.innerHTML = '<span>✓</span> Approve & Execute';
            return;
        }

        // Update all node statuses from result
        updateExecutionResult(result);

        // Show summary
        if (result.summary) {
            showProSummary(result.summary);
            appendMessage('assistant', `✅ **Execution complete!**\n\n${result.status === 'completed' ? 'All steps succeeded.' : result.status === 'partial' ? 'Some steps completed with issues.' : 'Execution had failures.'}\n\nSee the **Step Tracker** for details.`);
        }

        // Render artifacts (charts) in results panel
        if (result.metadata) {
            renderProArtifacts(result);
        }
    } catch (err) {
        appendMessage('assistant', '⚠️ Network error during execution.');
    }

    btn.disabled = false;
    btn.innerHTML = '<span>✓</span> Approve & Execute';
}

function rejectPlan() {
    clearProState();
    appendMessage('assistant', '❌ Plan rejected. You can submit a new request.');
}

// ── Step Tracker ────────────────────────────────────────────────────
function initStepTracker(nodes) {
    const stepsList = document.getElementById('pro-steps-list');
    const progress = document.getElementById('pro-progress');

    progress.textContent = `0 / ${nodes.length}`;

    let html = '';
    nodes.forEach((node, i) => {
        html += `
            <div class="pro-step-item" id="pro-step-${node.id}">
                <div class="pro-step-number">${i + 1}</div>
                <div class="pro-step-info">
                    <div class="pro-step-label">${escapeHtml(node.operation || node.type)}</div>
                    <div class="pro-step-meta">${escapeHtml(node.description || '')}</div>
                    <div class="pro-step-model" id="pro-step-model-${node.id}"></div>
                </div>
                <span class="pro-node-status pending" id="pro-step-status-${node.id}">pending</span>
            </div>`;
    });
    stepsList.innerHTML = html;
}

function updateExecutionResult(result) {
    if (!result.metadata) return;

    let completed = 0;
    let total = 0;

    for (const [nodeId, meta] of Object.entries(result.metadata)) {
        total++;
        const statusClass = meta.status || 'pending';
        const itemEl = document.getElementById(`pro-step-${nodeId}`);
        const statusEl = document.getElementById(`pro-step-status-${nodeId}`);
        const modelEl = document.getElementById(`pro-step-model-${nodeId}`);
        const planNodeEl = document.getElementById(`pro-node-${nodeId}`);

        if (statusEl) {
            statusEl.className = `pro-node-status ${statusClass}`;
            statusEl.textContent = statusClass;
        }

        if (itemEl) {
            itemEl.className = `pro-step-item ${statusClass === 'success' ? 'completed' : statusClass === 'failed' ? 'failed' : statusClass === 'running' ? 'active' : ''}`;
        }

        if (modelEl && meta.model_used) {
            modelEl.textContent = `Model: ${meta.model_used}`;
        }

        if (modelEl && meta.execution_time_ms) {
            modelEl.textContent += ` • ${(meta.execution_time_ms / 1000).toFixed(1)}s`;
        }

        if (meta.warnings && meta.warnings.length > 0) {
            if (modelEl) modelEl.textContent += ` • ⚠ ${meta.warnings.length} warning(s)`;
        }

        // Update plan node status too
        if (planNodeEl) {
            const planStatus = planNodeEl.querySelector('.pro-node-status');
            if (planStatus) {
                planStatus.className = `pro-node-status ${statusClass}`;
                planStatus.textContent = statusClass;
            }
        }

        if (statusClass === 'success') completed++;
    }

    const progress = document.getElementById('pro-progress');
    if (progress) progress.textContent = `${completed} / ${total}`;
}

function showProSummary(summaryText) {
    const summaryEl = document.getElementById('pro-summary');
    if (!summaryEl) return;

    summaryEl.style.display = 'block';
    summaryEl.innerHTML = `
        <h4>📋 Execution Summary</h4>
        <div class="pro-summary-content">${renderMarkdown(summaryText)}</div>`;
}

function renderProArtifacts(result) {
    // Check each step output for charts and render them in results
    if (result.completed_nodes && result.metadata) {
        result.completed_nodes.forEach(nodeId => {
            const meta = result.metadata[nodeId];
            if (meta && meta.output_type === 'artifact') {
                // artifacts are rendered via the regular results panel
                appendResult(`Pro Step: ${nodeId}`, 'chart', meta.value || '');
            }
        });
    }
}
