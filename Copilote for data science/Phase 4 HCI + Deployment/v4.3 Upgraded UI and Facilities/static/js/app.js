/* ═══════════════════════════════════════════════════════════════════════
   DATA SCIENCE COPILOT — Frontend Logic
   ═══════════════════════════════════════════════════════════════════════ */

// ── State ────────────────────────────────────────────────────────────
let currentSessionId = null;
let currentDataset = null;

// ── Init ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadSessions();
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

    // Show loading
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
            appendMessage('assistant', am.content);

            if (am.result_type && am.result_data) {
                appendResult(am.result_title || 'Result', am.result_type, am.result_data);
            }

            // Refresh dataset info for modify operations
            if (am.result_title && am.result_title.includes('Modified')) {
                refreshDatasetInfo();
            }
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
function appendMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const avatar = role === 'user' ? '🧑' : '🤖';
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.innerHTML = `
        <div class="msg-avatar">${avatar}</div>
        <div class="msg-bubble">${escapeHtml(content)}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
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
        // Handle "split" orient
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
