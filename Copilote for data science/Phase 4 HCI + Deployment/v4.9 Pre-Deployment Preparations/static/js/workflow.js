/* ══════════════════════════════════════════════════════════════════
   workflow.js — Pro Mode Workflow Studio Engine
   Handles: plan generation, DAG visualization, step execution,
            results rendering, and Pro mode results FIX
   ══════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────
let wfState = {
    sessionId: null,
    planData: null,
    steps: [],
    isExecuting: false,
    stepResults: {},
};

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Add workflow-page class for dark styling
    document.body.classList.add('workflow-page');

    // Check URL for session param
    const params = new URLSearchParams(window.location.search);
    if (params.get('session')) {
        wfState.sessionId = parseInt(params.get('session'));
        loadExistingSession(wfState.sessionId);
    }

    // Allow Enter in plan textarea (Shift+Enter for newline)
    document.getElementById('plan-input')?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
            e.preventDefault();
            generatePlan();
        }
    });
});

// ── Upload Dataset (for workflow header button) ───────────────────
async function wfHandleUpload(input) {
    if (!input.files[0]) return;
    const f = input.files[0];
    const fd = new FormData();
    fd.append('file', f);
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (res.ok) {
            wfState.sessionId = data.dataset.session_id;
            document.getElementById('wf-dataset-badge').style.display = 'inline-flex';
            document.getElementById('wf-dataset-name').textContent = data.dataset.filename;
            showToast('Dataset loaded: ' + data.dataset.filename, 'success');
        } else {
            showToast(data.error || 'Upload failed', 'error');
        }
    } catch (e) {
        showToast('Network error during upload', 'error');
    }
    input.value = '';
}

async function loadExistingSession(id) {
    try {
        const res = await fetch(`/api/sessions/${id}/messages`);
        const data = await res.json();
        if (data.dataset) {
            document.getElementById('wf-dataset-badge').style.display = 'inline-flex';
            document.getElementById('wf-dataset-name').textContent = data.dataset.filename;
        }
    } catch (e) { }
}

// ── Plan Generation ───────────────────────────────────────────────
async function generatePlan() {
    if (!wfState.sessionId) {
        showToast('Please upload a dataset first', 'error');
        return;
    }
    const goal = document.getElementById('plan-input').value.trim();
    if (!goal) { showToast('Enter a goal to generate a plan', 'error'); return; }

    const btn = document.getElementById('plan-generate-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner sm" style="border-color:rgba(255,255,255,0.2);border-top-color:#fff;"></span> Generating...';

    clearWorkflowUI();

    try {
        const res = await fetch('/api/pro/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // API expects `message`, not `goal`
            body: JSON.stringify({ session_id: wfState.sessionId, message: goal })
        });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || 'Plan generation failed', 'error');
            return;
        }

        wfState.planData = data;          // response root: { plan_id, plan: {...}, node_count }
        // API returns plan inside data.plan; steps are nodes inside data.plan.nodes
        const planObj = data.plan || data;
        wfState.steps = planObj.nodes || [];
        renderPlan(data);

    } catch (e) {
        showToast('Network error: ' + e.message, 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-rounded" style="font-size:14px;">auto_awesome</span> Generate Plan';
    }
}

// ── Render Plan in left panel + DAG center ──────────────────────
function renderPlan(data) {
    // API response shape:
    //   { plan_id, plan: { nodes: [{id, type, description, operation, ...}], user_goal, ... }, node_count }
    const planObj = data.plan || data;
    const nodes = planObj.nodes || data.steps || [];
    const userGoal = planObj.user_goal || '';

    const stepsEl = document.getElementById('steps-list');
    const dagLinear = document.getElementById('dag-linear');
    const dagCanvas = document.getElementById('dag-canvas');

    if (!stepsEl) return;

    if (nodes.length === 0) {
        stepsEl.innerHTML = '<div style="padding:16px;color:var(--text-tertiary);font-size:0.8rem;text-align:center;">No steps returned by the planner. Try a more detailed goal.</div>';
        // Still show plan summary if we got one
    } else {
        // Left panel — step cards
        stepsEl.innerHTML = nodes.map((node, i) => `
        <div class="step-item" id="step-${i}" onclick="selectStep(${i})">
          <div class="step-item-header">
            <div class="step-number">${i + 1}</div>
            <div class="step-name">${esc(node.description || node.operation || node.action || node.name || `Step ${i + 1}`)}</div>
            <span class="step-status-icon" id="step-icon-${i}">○</span>
          </div>
          <div class="step-desc">${esc(node.type || node.tool || '')}</div>
        </div>`).join('');
    }

    // Show approve bar
    document.getElementById('approve-bar').style.display = 'block';

    // DAG center — linear execution timeline
    if (dagCanvas) dagCanvas.style.display = 'none';
    if (dagLinear) {
        dagLinear.style.display = 'flex';
        dagLinear.innerHTML = nodes.map((node, i) => `
        <div class="dag-step-row" id="dag-step-${i}">
          <div class="dag-step-icon" id="dag-icon-${i}">
            <span class="material-symbols-rounded">${stepIcon(node)}</span>
          </div>
          <div class="dag-step-body">
            <div class="dag-step-name">${esc(node.description || node.operation || `Step ${i + 1}`)}</div>
            <div class="dag-step-desc" style="color:var(--text-tertiary);font-size:0.7rem;">${esc(node.type || '')}</div>
          </div>
        </div>`).join('');
    }

    // Output panel — plan summary
    const outputScroll = document.getElementById('output-scroll');
    if (!outputScroll) return;
    const outputEmpty = document.getElementById('output-empty');
    if (outputEmpty) outputEmpty.style.display = 'none';
    outputScroll.insertAdjacentHTML('afterbegin', `
    <div class="output-block">
      <div class="output-block-header">
        <span class="output-block-label">📋 Execution Plan — ${nodes.length} step${nodes.length !== 1 ? 's' : ''}</span>
      </div>
      <div class="output-block-body" style="white-space:pre-wrap;font-size:0.8rem;color:var(--text-secondary);">${userGoal ? esc(userGoal) : 'Plan generated — review steps and approve to execute.'}</div>
      ${nodes.length > 0 ? `
      <div style="padding:8px 14px 12px;border-top:1px solid var(--border);">
        ${nodes.map((n, i) => `
        <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px;">
          <span style="min-width:20px;height:20px;border-radius:50%;background:rgba(99,102,241,0.25);color:var(--accent-400);font-size:0.65rem;font-weight:700;display:inline-flex;align-items:center;justify-content:center;">${i + 1}</span>
          <div>
            <div style="font-size:0.8rem;color:var(--text-primary);font-weight:500;">${esc(n.description || n.operation || '')}</div>
            <div style="font-size:0.7rem;color:var(--text-tertiary);">${esc(n.type || '')}</div>
          </div>
        </div>`).join('')}
      </div>` : ''}
    </div>`);
}

// ── Approve & Execute ─────────────────────────────────────────────
async function approvePlan() {
    if (!wfState.planData || wfState.isExecuting) return;
    wfState.isExecuting = true;

    const approveBtn = document.getElementById('approve-btn');
    approveBtn.disabled = true;
    approveBtn.innerHTML = '<span class="spinner sm" style="border-color:rgba(5,150,105,0.3);border-top-color:var(--success);"></span> Executing...';

    const progressWrap = document.getElementById('wf-progress-wrap');
    progressWrap.style.display = 'block';
    setProgress(0, 'Starting execution...');

    try {
        const plan_id = wfState.planData?.plan_id;
        if (!plan_id) {
            showToast('Plan ID missing — please regenerate the plan', 'error');
            resetApproveBtn();
            wfState.isExecuting = false;
            return;
        }

        // Step 1: Kick off async execution (returns 202 immediately)
        const res = await fetch('/api/pro/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_id })
        });
        const kickoff = await res.json();

        if (!res.ok) {
            showToast(kickoff.error || 'Could not start execution', 'error');
            resetApproveBtn();
            wfState.isExecuting = false;
            return;
        }

        // res.status === 202 → execution started, begin polling
        setProgress(5, 'Execution in progress...');
        showToast('Execution started — running steps...', 'info');

        // Step 2: Poll status until done or timeout (10 min max)
        const MAX_POLLS = 200;   // 200 × 3s = 10 minutes
        const POLL_INTERVAL_MS = 3000;
        let polls = 0;
        let renderedNodes = new Set();

        const poll = async () => {
            if (polls >= MAX_POLLS) {
                showToast('Execution timed out after 10 minutes', 'error');
                resetApproveBtn();
                wfState.isExecuting = false;
                return;
            }
            polls++;

            let statusData;
            try {
                const statusRes = await fetch(`/api/pro/status/${plan_id}`);
                statusData = await statusRes.json();
                if (!statusRes.ok) {
                    showToast(statusData.error || 'Status check failed', 'error');
                    resetApproveBtn();
                    wfState.isExecuting = false;
                    return;
                }
            } catch (e) {
                // Network hiccup — retry
                setTimeout(poll, POLL_INTERVAL_MS);
                return;
            }

            const nodes = statusData.nodes || [];
            const totalNodes = nodes.length || wfState.steps.length || 1;
            const completedCount = nodes.filter(n => n.status === 'success').length;
            const failedCount = nodes.filter(n => n.status === 'failed').length;

            // Update step icons and progress bar for each node
            nodes.forEach((node, i) => {
                const icon = document.getElementById(`step-icon-${i}`);
                const dagRow = document.getElementById(`dag-step-${i}`);
                if (node.status === 'success') {
                    if (icon) icon.textContent = '✓';
                    if (dagRow) dagRow.classList.add('done');
                } else if (node.status === 'failed') {
                    if (icon) icon.textContent = '✗';
                    if (dagRow) dagRow.classList.add('failed');
                } else if (node.status === 'running' || node.status === 'retrying') {
                    if (icon) icon.innerHTML = '<span class="spinner sm"></span>';
                }

                // Render output for newly completed nodes
                if ((node.status === 'success' || node.status === 'failed') && !renderedNodes.has(node.id)) {
                    renderedNodes.add(node.id);
                    appendStepResult(i, node);
                }
            });

            const pct = Math.max(10, Math.round((completedCount / totalNodes) * 90));
            setProgress(pct, `${completedCount}/${totalNodes} steps complete`);

            // Check if execution is done
            const isRunning = statusData.running;
            const execError = statusData.exec_error;
            const planStatus = statusData.plan_status;
            const isDone = !isRunning && (planStatus === 'completed' || planStatus === 'failed' || planStatus === 'executing' && completedCount + failedCount >= totalNodes);

            if (isDone || (!isRunning && planStatus !== 'planned' && planStatus !== 'approved' && planStatus !== 'executing')) {
                setProgress(100, 'Execution complete');

                if (execError) {
                    showToast('Execution error: ' + execError, 'error');
                } else {
                    const result = statusData.result;
                    const summary = result?.summary || '';
                    if (summary) {
                        appendSummaryBlock(summary, result);
                    }
                    const failedNodes = result?.failed_nodes || [];
                    if (failedNodes.length) {
                        showToast(`⚠ ${failedNodes.length} step(s) failed — see output for details`, 'warn');
                    } else {
                        showToast('Workflow completed successfully ✓', 'success');
                    }
                }

                wfState.isExecuting = false;
                resetApproveBtn();
                return;
            }

            // Still running — poll again
            setTimeout(poll, POLL_INTERVAL_MS);
        };

        setTimeout(poll, 1500); // First poll after 1.5s

    } catch (e) {
        showToast('Execution error: ' + e.message, 'error');
        console.error(e);
        wfState.isExecuting = false;
        resetApproveBtn();
    }
}

function appendSummaryBlock(summary, result) {
    const outputScroll = document.getElementById('output-scroll');
    if (!outputScroll) return;
    const block = document.createElement('div');
    block.className = 'output-block';
    const status = result?.status || 'completed';
    const icon = status === 'completed' ? '✅' : '⚠';
    block.innerHTML = `
    <div class="output-block-header">
      <span class="output-block-label">${icon} Execution Summary</span>
      <span style="margin-left:auto;font-size:0.65rem;color:var(--text-tertiary);">${status}</span>
    </div>
    <div class="output-block-body" style="white-space:pre-wrap;font-size:0.8125rem;color:var(--text-primary);line-height:1.7;">${esc(summary)}</div>`;
    outputScroll.appendChild(block);
    block.scrollIntoView({ behavior: 'smooth', block: 'end' });
}



// ── Append Step Result to Output Panel ───────────────────────────
function appendStepResult(stepIndex, stepData) {
    const outputScroll = document.getElementById('output-scroll');
    const outputEmpty = document.getElementById('output-empty');
    if (!outputScroll) return;
    if (outputEmpty) outputEmpty.style.display = 'none';

    // Support new polling node format: { id, description, operation, status, output: {type, data} }
    // as well as legacy format: { result_type, result_data, type, data }
    const nodeOutput = stepData.output || {};
    const stepName = stepData.description || stepData.operation
        || (wfState.steps[stepIndex] || {}).description
        || (wfState.steps[stepIndex] || {}).operation
        || `Step ${stepIndex + 1}`;

    // Determine type and data from whichever format is present
    const rtype = nodeOutput.type || stepData.result_type || stepData.type || 'text';
    const rdata = nodeOutput.data || stepData.result_data || stepData.data || stepData.result || '';
    const failed = stepData.status === 'failed';

    let bodyHtml = '';
    if (failed && !rdata) {
        const err = stepData.metadata?.error || 'Step failed';
        bodyHtml = `<div style="color:var(--error);font-size:0.8rem;font-family:var(--font-mono);white-space:pre-wrap;">${esc(err)}</div>`;
    } else if (rtype === 'dataframe' || rtype === 'table') {
        bodyHtml = buildTableHtml(rdata);
    } else if (rtype === 'chart' || rtype === 'image' || rtype === 'figure') {
        const src = typeof rdata === 'string' && rdata.startsWith('data:') ? rdata : `data:image/png;base64,${rdata}`;
        bodyHtml = `<img src="${src}" alt="Chart" style="width:100%;border-radius:4px;">`;
    } else if (rtype === 'error') {
        bodyHtml = `<div style="color:var(--error);font-size:0.8rem;font-family:var(--font-mono);white-space:pre-wrap;">${esc(String(rdata))}</div>`;
    } else if (rtype === 'none' || !rdata) {
        bodyHtml = `<div style="color:var(--text-tertiary);font-size:0.8rem;font-style:italic;">No displayable output for this step.</div>`;
    } else {
        bodyHtml = `<div style="white-space:pre-wrap;font-size:0.8125rem;color:var(--text-primary);line-height:1.6;">${esc(String(rdata))}</div>`;
    }

    // Don't duplicate an existing block for this step
    const existingId = `output-step-${stepData.id || stepIndex}`;
    if (document.getElementById(existingId)) return;

    const block = document.createElement('div');
    block.className = 'output-block';
    block.id = existingId;
    const statusBadge = failed
        ? `<span style="background:rgba(225,29,72,0.15);color:#f87171;font-size:0.6rem;padding:1px 6px;border-radius:4px;font-weight:600;">FAILED</span>`
        : `<span style="background:rgba(5,150,105,0.15);color:#34d399;font-size:0.6rem;padding:1px 6px;border-radius:4px;font-weight:600;">DONE</span>`;
    block.innerHTML = `
    <div class="output-block-header">
      <span class="output-block-label">Step ${stepIndex + 1} · ${esc(stepName)}</span>
      <span style="margin-left:auto;display:flex;align-items:center;gap:6px;">
        <span style="font-size:0.65rem;color:var(--text-tertiary);">${rtype}</span>
        ${statusBadge}
      </span>
    </div>
    <div class="output-block-body">${bodyHtml}</div>`;
    outputScroll.appendChild(block);
    block.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

// ── Build sortable + filterable HTML table from dataframe data ───
function buildTableHtml(data) {
    if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch (e) { return `<pre style="color:var(--text-primary);font-size:0.75rem;overflow-x:auto;">${esc(data)}</pre>`; }
    }
    if (!data || typeof data !== 'object') return esc(String(data));

    // Support pandas split format { columns, data } or array of objects
    const cols = data.columns || Object.keys((Array.isArray(data) ? data[0] : data) || {});
    const rows = data.data || (Array.isArray(data) ? data : []);

    if (!cols.length) return '<em style="color:var(--text-tertiary);">Empty result</em>';

    const tableId = 'wf-tbl-' + Date.now();
    return `
    <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px;">
      <div style="position:relative;flex:1;max-width:220px;">
        <span class="material-symbols-rounded" style="position:absolute;left:8px;top:50%;transform:translateY(-50%);font-size:14px;color:var(--text-tertiary);pointer-events:none;">search</span>
        <input type="text" placeholder="Filter rows..." oninput="wfFilterTable('${tableId}',this.value)"
          style="width:100%;background:var(--bg-subtle);border:1px solid var(--border);border-radius:6px;padding:5px 10px 5px 28px;color:var(--text-primary);font-size:0.75rem;outline:none;font-family:var(--font-sans);">
      </div>
      <span style="font-size:0.7rem;color:var(--text-tertiary);">${rows.length} rows</span>
    </div>
    <div style="overflow-x:auto;max-height:320px;overflow-y:auto;">
      <table class="data-table" id="${tableId}" style="background:transparent;">
        <thead>
          <tr>
            ${cols.map((c, ci) => `<th class="sortable" onclick="wfSortTable('${tableId}',${ci})" style="background:var(--bg-muted);color:var(--text-secondary);border-color:var(--border);">${esc(String(c))}<span class="sort-indicator"></span></th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows.slice(0, 200).map(row => `<tr>${(Array.isArray(row) ? row : cols.map(c => row[c])).map(v => `<td style="border-color:var(--border);color:var(--text-primary);">${esc(String(v ?? ''))}</td>`).join('')}</tr>`).join('')}
        </tbody>
      </table>
      ${rows.length > 200 ? `<div style="padding:6px 10px;font-size:0.7rem;color:var(--text-tertiary);">Showing 200 of ${rows.length} rows</div>` : ''}
    </div>`;
}

// ── Workflow table sort/filter (mirrors app.js logic) ─────────────
const _wfSortStates = {};
function wfSortTable(tableId, colIndex) {
    const tbl = document.getElementById(tableId);
    if (!tbl) return;
    const key = tableId + '_' + colIndex;
    const dir = _wfSortStates[key] === 'asc' ? 'desc' : 'asc';
    _wfSortStates[key] = dir;
    tbl.querySelectorAll('th').forEach((th, i) => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (i === colIndex) th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
    });
    const tbody = tbl.querySelector('tbody');
    if (!tbody) return;
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

function wfFilterTable(tableId, query) {
    const tbl = document.getElementById(tableId);
    if (!tbl) return;
    const q = query.toLowerCase();
    tbl.querySelectorAll('tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
}

// ── Step marker helpers ───────────────────────────────────────────
function markStepStatus(i, status) {
    const stepEl = document.getElementById(`step-${i}`);
    const dagIcon = document.getElementById(`dag-icon-${i}`);
    const iconEl = document.getElementById(`step-icon-${i}`);
    if (!stepEl) return;

    stepEl.classList.remove('running', 'done', 'error');
    stepEl.classList.add(status);

    if (iconEl) {
        iconEl.className = `step-status-icon ${status}`;
        iconEl.textContent = status === 'done' ? 'check_circle' : status === 'running' ? 'progress_activity' : 'error';
    }
    if (dagIcon) {
        dagIcon.classList.remove('running', 'done', 'error');
        dagIcon.classList.add(status);
    }
}

function setProgress(pct, label) {
    const bar = document.getElementById('exec-progress-bar');
    const lblEl = document.getElementById('exec-step-label');
    const pctEl = document.getElementById('exec-pct-label');
    if (bar) bar.style.width = pct + '%';
    if (lblEl) lblEl.textContent = label;
    if (pctEl) pctEl.textContent = pct + '%';
    document.getElementById('wf-progress-label').textContent = label;
}

function resetApproveBtn() {
    const btn = document.getElementById('approve-btn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-symbols-rounded" style="font-size:14px;">check_circle</span> Approve & Execute';
    }
}

// ── Reject / Clear ────────────────────────────────────────────────
function rejectPlan() {
    wfState.planData = null;
    wfState.steps = [];
    clearWorkflowUI();
    showToast('Plan rejected', 'neutral');
}

function clearWorkflow() {
    document.getElementById('plan-input').value = '';
    wfState.planData = null;
    wfState.steps = [];
    wfState.stepResults = {};
    clearWorkflowUI();
}

function clearWorkflowUI() {
    document.getElementById('steps-list').innerHTML = '<div class="output-empty" style="height:160px;"><span class="material-symbols-rounded">account_tree</span><span>Plan will appear here</span></div>';
    document.getElementById('approve-bar').style.display = 'none';
    document.getElementById('dag-canvas').style.display = 'flex';
    document.getElementById('dag-linear').style.display = 'none';
    document.getElementById('dag-linear').innerHTML = '';
    document.getElementById('wf-progress-wrap').style.display = 'none';
    setProgress(0, '');
}

function clearOutput() {
    const scroll = document.getElementById('output-scroll');
    scroll.innerHTML = '<div class="output-empty" id="output-empty"><span class="material-symbols-rounded">assessment</span><span>Step results will appear here</span></div>';
}

function selectStep(i) {
    document.querySelectorAll('.step-item').forEach(s => s.classList.remove('active'));
    document.getElementById(`step-${i}`)?.classList.add('active');
    // Scroll to corresponding output block
    const ob = document.getElementById(`output-step-${i}`);
    if (ob) ob.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ── Utilities ─────────────────────────────────────────────────────
function esc(s) { return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function stepIcon(node) {
    // DAGNode has: type (visualization/analysis/transformation/operation/summary/conditional)
    // and operation field. Try both.
    const t = ((node.type || '') + ' ' + (node.operation || '') + ' ' + (node.description || '')).toLowerCase();
    if (t.includes('visual') || t.includes('chart') || t.includes('plot') || t.includes('graph')) return 'bar_chart';
    if (t.includes('table') || t.includes('display') || t.includes('show') || t.includes('dataframe')) return 'table_chart';
    if (t.includes('transform') || t.includes('modif') || t.includes('clean') || t.includes('preprocess')) return 'edit';
    if (t.includes('stat') || t.includes('summary') || t.includes('describe') || t.includes('analysis')) return 'analytics';
    if (t.includes('filter') || t.includes('select') || t.includes('conditional')) return 'filter_list';
    if (t.includes('correlat')) return 'scatter_plot';
    if (t.includes('model') || t.includes('predict') || t.includes('ml')) return 'model_training';
    return 'code';
}

function showToast(msg, type = 'neutral') {
    let el = document.getElementById('_wf_toast');
    if (!el) {
        el = document.createElement('div');
        el.id = '_wf_toast';
        el.style.cssText = 'position:fixed;bottom:24px;right:24px;padding:10px 16px;border-radius:8px;font-size:0.8125rem;font-weight:500;z-index:9999;transition:all 0.2s;box-shadow:0 4px 12px rgba(0,0,0,0.4);';
        document.body.appendChild(el);
    }
    const colors = { success: '#059669', error: '#E11D48', neutral: '#6366F1' };
    el.style.background = colors[type] || colors.neutral;
    el.style.color = '#fff';
    el.textContent = msg;
    el.style.opacity = '1';
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.style.opacity = '0'; }, 3500);
}
