/* ══════════════════════════════════════════════════════════════════
   app.js — Quick Run Page Chat Engine
   Handles: file upload, chat messages, results rendering,
            interactive tables, chart config
   ══════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────
let state = {
    sessionId: null,
    datasetInfo: null,
    isLoading: false,
    chartInstances: {},
    currentCode: '',
    highTierEnabled: false,
};
const _codeStore = []; // safe code storage — avoids unsafe JSON in onclick attrs


// ── Init ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Restore session from URL param
    const params = new URLSearchParams(window.location.search);
    const sessionParam = params.get('session');
    if (sessionParam) {
        loadSession(parseInt(sessionParam));
    }

    // Textarea auto-resize
    const ta = document.getElementById('chat-input');
    if (ta) { ta.addEventListener('input', () => autoResize(ta)); }
});

async function loadSession(id) {
    try {
        const res = await fetch(`/api/sessions/${id}/messages`);
        const data = await res.json();
        if (data.dataset) {
            setDataset(data.dataset);
        }
        if (data.messages && data.messages.length > 0) {
            document.getElementById('chat-welcome')?.remove();
            data.messages.forEach(m => {
                if (m.role === 'user') addMessage('user', m.content);
                else if (m.role === 'assistant') {
                    addMessage('ai', m.content || '');
                    if (m.result_type && m.result_data) {
                        appendResult({
                            result_type: m.result_type,
                            result_data: m.result_data,
                            title: m.result_title || m.result_type,
                            code: m.code,
                        });
                    }
                }
            });
        }
    } catch (e) { console.warn('Session load error:', e); }
}

// ── Upload Handler ────────────────────────────────────────────────
async function handleUpload(input) {
    if (!input.files[0]) return;
    const f = input.files[0];
    if (!f.name.endsWith('.csv')) { showChatStatus('Only CSV files supported', 'error'); return; }

    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    showChatStatus('Uploading ' + f.name + '...', 'loading');
    chatInput.disabled = true; sendBtn.disabled = true;

    const fd = new FormData();
    fd.append('file', f);
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (res.ok) {
            setDataset(data.dataset);
            showChatStatus('Ready to analyze', 'ok');
        } else {
            showChatStatus('Upload failed: ' + (data.error || ''), 'error');
            chatInput.disabled = false; sendBtn.disabled = false;
        }
    } catch (e) {
        showChatStatus('Network error', 'error');
        chatInput.disabled = false; sendBtn.disabled = false;
    }
    input.value = '';
}

function setDataset(info) {
    state.sessionId = info.session_id;
    state.datasetInfo = info;

    // Enable chat input
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    if (chatInput) { chatInput.disabled = false; chatInput.focus(); }
    if (sendBtn) sendBtn.disabled = false;

    // Update badge
    document.getElementById('dataset-chip').style.display = 'inline-flex';
    document.getElementById('dataset-badge-name').textContent = info.filename;
    document.getElementById('chat-subtitle').textContent = `${info.filename} · ${info.rows} rows, ${info.columns} cols`;
    document.getElementById('chat-status').textContent = `${info.rows.toLocaleString()} rows · ${info.columns} columns · ${info.missing} missing values`;

    // Show welcome message from AI
    const welcome = document.getElementById('chat-welcome');
    if (welcome) welcome.remove();
    addMessage('ai', `I've loaded **${info.filename}** with ${info.rows.toLocaleString()} rows and **${info.columns}** columns: ${info.column_names.slice(0, 5).join(', ')}${info.column_names.length > 5 ? '...' : ''}. What would you like to analyze?`);

    // Remove results empty state
    document.getElementById('results-empty')?.remove();
}

// ── Chat Send ─────────────────────────────────────────────────────
function sendChat(event) {
    if (event) event.preventDefault();
    if (state.isLoading) return false;
    if (!state.sessionId) { showChatStatus('Upload a dataset first', 'error'); return false; }

    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return false;

    input.value = '';
    autoResize(input);
    addMessage('user', msg);
    showTyping();
    sendMessage(msg);
    return false;
}

function handleChatKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChat(null);
    }
}

function useSuggestion(text) {
    const input = document.getElementById('chat-input');
    if (!input || input.disabled) return;
    input.value = text;
    input.focus();
    sendChat(null);
}

async function sendMessage(msg) {
    state.isLoading = true;
    document.getElementById('send-btn').disabled = true;

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.sessionId, message: msg, high_tier: state.highTierEnabled })
        });
        const data = await res.json();
        removeTyping();

        if (!res.ok) {
            addMessage('ai', '⚠️ Error: ' + (data.error || 'Something went wrong'));
            return;
        }

        // Handle response — backend returns { user_msg, assistant_msg }
        const aMsg = data.assistant_msg;
        if (aMsg) {
            addMessage('ai', aMsg.content || '');
            if (aMsg.result_type && aMsg.result_data) {
                appendResult({
                    result_type: aMsg.result_type,
                    result_data: aMsg.result_data,
                    title: aMsg.result_title || aMsg.result_type,
                    code: aMsg.code,
                });
            }
        }

    } catch (e) {
        removeTyping();
        addMessage('ai', '⚠️ Network error: ' + e.message);
        console.error(e);
    } finally {
        state.isLoading = false;
        const btn = document.getElementById('send-btn');
        if (btn) btn.disabled = !state.sessionId;
    }
}

// ── Chat UI helpers ───────────────────────────────────────────────
function addMessage(role, text) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.innerHTML = `
    <div class="msg-avatar ${role}">${role === 'ai' ? '✦' : 'U'}</div>
    <div>
      <div class="msg-bubble">${formatMsg(text)}</div>
      <div class="msg-time">${fmtTime()}</div>
    </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function showTyping() {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'msg ai'; div.id = 'typing-msg';
    div.innerHTML = `<div class="msg-avatar ai">✦</div><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function removeTyping() {
    document.getElementById('typing-msg')?.remove();
}

function showChatStatus(msg, type) {
    const el = document.getElementById('chat-status');
    if (!el) return;
    el.textContent = msg;
    el.style.color = type === 'error' ? 'var(--error)' : type === 'ok' ? 'var(--success)' : 'var(--text-tertiary)';
}

function formatMsg(txt) {
    return esc(txt)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="font-family:var(--font-mono);background:var(--bg-muted);padding:1px 5px;border-radius:3px;font-size:0.8em;">$1</code>')
        .replace(/\n/g, '<br>');
}

function esc(s) { return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function fmtTime() { return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }); }

function clearChat() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = '';
}

// ── Results rendering ─────────────────────────────────────────────
function appendResult(result) {
    const container = document.getElementById('results-content');
    if (!container) return; // pane not in DOM on this page
    try {
        document.getElementById('results-empty')?.remove();

        const block = document.createElement('div');
        block.className = 'result-block';

        const rtype = result.result_type || result.type || 'text';
        const rdata = result.result_data || result.data || result.result || '';
        const rtitle = result.title || rtype.charAt(0).toUpperCase() + rtype.slice(1);
        const icon = rtype === 'dataframe' ? 'table_chart' : rtype === 'image' || rtype === 'chart' ? 'bar_chart' : rtype === 'error' ? 'error' : 'text_snippet';

        let bodyHtml = '';

        if (rtype === 'dataframe') {
            bodyHtml = buildResultTable(rdata);
        } else if (rtype === 'image' || rtype === 'chart') {
            const imgId = 'chart-' + Date.now();
            const src = typeof rdata === 'string' && rdata.startsWith('data:') ? rdata : `data:image/png;base64,${rdata}`;
            bodyHtml = `
      <img id="${imgId}" src="${src}" alt="Chart" style="width:100%;border-radius:4px;cursor:pointer;" onclick="openImageFull('${imgId}')">
      <div class="chart-config" id="cfg-${imgId}">
        <div class="chart-config-toggle" onclick="toggleChartConfig('cfg-${imgId}')">
          <span>Configure chart</span>
          <span class="material-symbols-rounded">expand_more</span>
        </div>
        <div class="chart-config-body" id="cfg-body-${imgId}">
          <div class="config-row">
            <span class="config-label">Chart type</span>
            <select class="select" style="width:120px;height:28px;font-size:0.75rem;" id="ctype-${imgId}">
              <option value="bar">Bar</option><option value="line">Line</option>
              <option value="pie">Pie</option><option value="scatter">Scatter</option>
              <option value="hist">Histogram</option><option value="box">Box</option>
            </select>
          </div>
        </div>
      </div>`;
        } else if (rtype === 'error') {
            bodyHtml = `<div style="color:var(--error);font-size:0.8125rem;font-family:var(--font-mono);white-space:pre-wrap;padding:4px 0;">${esc(String(rdata))}</div>`;
        } else {
            bodyHtml = `<div style="font-size:0.8125rem;line-height:1.7;white-space:pre-wrap;">${formatMsg(String(rdata))}</div>`;
        }

        // Safe code button: use _codeStore array, not inline JSON
        let codeBtn = '';
        if (result.code) {
            const idx = _codeStore.push(result.code) - 1;
            block.dataset.codeIdx = idx;
            codeBtn = `<button class="btn btn-ghost btn-sm btn-icon" onclick="showCode(_codeStore[this.closest('.result-block').dataset.codeIdx])" title="View code"><span class="material-symbols-rounded">code</span></button>`;
        }

        block.innerHTML = `
        <div class="result-block-header">
          <span class="result-block-icon material-symbols-rounded">${icon}</span>
          <span class="result-block-title">${esc(rtitle)}</span>
          ${codeBtn}
        </div>
        <div class="result-block-body">${bodyHtml}</div>`;

        container.appendChild(block);
        container.scrollTop = container.scrollHeight;
    } catch (err) {
        console.error('[appendResult] Render error:', err, result);
        const fb = document.createElement('div');
        fb.className = 'result-block';
        fb.innerHTML = `<div class="result-block-body"><div style="color:var(--error);font-size:0.8125rem;">⚠ Could not render result. Check console for details.</div></div>`;
        container.appendChild(fb);
    }
}


function buildResultTable(data) {
    if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch (e) { return `<pre style="font-size:0.75rem;overflow-x:auto;">${esc(data)}</pre>`; }
    }
    if (!data || typeof data !== 'object') return esc(String(data));

    const cols = data.columns || Object.keys((Array.isArray(data) ? data[0] : data) || {});
    const rows = data.data || (Array.isArray(data) ? data : []);
    if (!cols.length) return '<em style="color:var(--text-tertiary);">Empty result</em>';

    const tableId = 'tbl-' + Date.now();
    const rendered = `
    <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
      <div class="search-input-wrap" style="width:200px;">
        <span class="material-symbols-rounded">search</span>
        <input type="text" class="input" placeholder="Filter rows..." oninput="filterTable('${tableId}',this.value)" style="height:28px;font-size:0.75rem;">
      </div>
      <span style="font-size:0.75rem;color:var(--text-tertiary);">${rows.length} rows</span>
    </div>
    <div style="overflow-x:auto;max-height:320px;">
      <table class="data-table" id="${tableId}">
        <thead><tr>${cols.map((c, ci) => `<th class="sortable" onclick="sortTable('${tableId}',${ci})">${esc(String(c))}<span class="sort-indicator"></span></th>`).join('')}</tr></thead>
        <tbody>
          ${rows.slice(0, 200).map(row => `<tr>${(Array.isArray(row) ? row : cols.map(c => row[c])).map(v => `<td>${esc(String(v ?? ''))}</td>`).join('')}</tr>`).join('')}
        </tbody>
      </table>
      ${rows.length > 200 ? `<div style="padding:6px;font-size:0.75rem;color:var(--text-tertiary);">Showing 200 of ${rows.length} rows</div>` : ''}
    </div>`;
    return rendered;
}

// ── Table sorting & filtering ─────────────────────────────────────
const _sortStates = {};
function sortTable(tableId, colIndex) {
    const tbl = document.getElementById(tableId);
    if (!tbl) return;
    const key = tableId + '_' + colIndex;
    const dir = _sortStates[key] === 'asc' ? 'desc' : 'asc';
    _sortStates[key] = dir;

    // Update header indicators
    tbl.querySelectorAll('th').forEach((th, i) => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (i === colIndex) th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
    });

    const tbody = tbl.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort((a, b) => {
        const av = a.cells[colIndex]?.textContent || '';
        const bv = b.cells[colIndex]?.textContent || '';
        const an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return dir === 'asc' ? an - bn : bn - an;
        return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    });
    rows.forEach(r => tbody.appendChild(r));
}

function filterTable(tableId, query) {
    const tbl = document.getElementById(tableId);
    if (!tbl) return;
    const q = query.toLowerCase();
    tbl.querySelectorAll('tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
}

// ── Chart config ──────────────────────────────────────────────────
function toggleChartConfig(cfgId) {
    const body = document.getElementById('cfg-body-' + cfgId.replace('cfg-', ''));
    if (!body) return;
    body.classList.toggle('open');
    const toggle = document.querySelector(`#${cfgId} .chart-config-toggle .material-symbols-rounded`);
    if (toggle) toggle.style.transform = body.classList.contains('open') ? 'rotate(180deg)' : '';
}

// ── Code modal ────────────────────────────────────────────────────
function showCode(code) {
    state.currentCode = code;
    document.getElementById('code-modal-code').textContent = code;
    document.getElementById('code-modal-title').textContent = 'Generated Code';
    document.getElementById('code-modal-meta').textContent = 'Auto-generated Python';
    document.getElementById('code-modal').classList.add('open');
}

function closeCodeModal() {
    document.getElementById('code-modal').classList.remove('open');
}

function copyCode() {
    navigator.clipboard.writeText(state.currentCode).then(() => {
        const btn = document.querySelector('#code-modal .btn-ghost');
        if (btn) { btn.innerHTML = '<span class="material-symbols-rounded">check</span> Copied!'; setTimeout(() => { btn.innerHTML = '<span class="material-symbols-rounded">content_copy</span> Copy'; }, 2000); }
    });
}

function openImageFull(imgId) {
    const img = document.getElementById(imgId);
    if (!img) return;
    const modal = document.createElement('div');
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:zoom-out;padding:24px;';
    modal.onclick = () => modal.remove();
    modal.innerHTML = `<img src="${img.src}" style="max-width:90vw;max-height:90vh;object-fit:contain;border-radius:8px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">`;
    document.body.appendChild(modal);
}

function clearResults() {
    const c = document.getElementById('results-content');
    c.innerHTML = '<div class="empty-state" id="results-empty"><div class="empty-icon"><span class="material-symbols-rounded">assessment</span></div><h3>No results yet</h3><p>Ask a question to see results</p></div>';
}

// ── Utils ─────────────────────────────────────────────────────────
function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}
