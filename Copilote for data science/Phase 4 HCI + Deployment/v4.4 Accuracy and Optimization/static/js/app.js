/* ═══════════════════════════════════════════════════════════════════════
   DATA SCIENCE COPILOT — Frontend Logic v4.4
   Rich chat messages, alive assistant, code activity bucket
   ═══════════════════════════════════════════════════════════════════════ */

// ── State ────────────────────────────────────────────────────────────
let currentSessionId = null;
let currentDataset = null;
let codeSnippetsCache = [];

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
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
