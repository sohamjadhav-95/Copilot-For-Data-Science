/**
 * logger.js — Universal Frontend Logger for DataCopilot
 * ──────────────────────────────────────────────────────────────────────
 * Captures:
 *   1. Uncaught JS errors          (window.onerror)
 *   2. Unhandled Promise rejections (window.onunhandledrejection)
 *   3. Console.error / warn        (monkey-patched)
 *   4. Page navigation             (history API + popstate)
 *   5. Manual events               (DC_LOG.info / warn / error)
 *
 * Sends to:  POST /api/log/frontend  (no auth needed)
 * Batch size: up to 10 events queued, flushed every 3 s or on page unload
 *
 * Usage (anywhere in JS):
 *   DC_LOG.info('page_load', 'quick-run',  { component: 'chat' });
 *   DC_LOG.warn('slow_render', 'workflow', { component: 'dag-canvas', ms: 1200 });
 *   DC_LOG.error('api_failed', 'workflow',  { component: 'approvePlan', msg: err.message });
 */

(function () {
    'use strict';

    // ── Config ─────────────────────────────────────────────────────────
    const ENDPOINT = '/api/log/frontend';
    const FLUSH_INTERVAL_MS = 3000;
    const MAX_QUEUE = 20;           // max events before forced flush
    const MAX_MSG_LEN = 500;
    const MAX_STACK_LEN = 1200;

    // ── Helpers ────────────────────────────────────────────────────────
    const _page = () => window.location.pathname;
    const _browser = () => `${navigator.userAgent.slice(0, 100)}`;
    const _viewport = () => `${window.innerWidth}x${window.innerHeight}`;
    const _userId = () => {
        // Try to read user ID from a meta tag (optionally set in base.html)
        const el = document.querySelector('meta[name="dc-user-id"]');
        return el ? el.content : null;
    };
    const _sessionId = () => {
        // Try to read session ID from a meta tag
        const el = document.querySelector('meta[name="dc-session-id"]');
        return el ? el.content : null;
    };
    const _clamp = (s, n) => (typeof s === 'string' ? s.slice(0, n) : String(s || '').slice(0, n));

    // ── Queue & flush ──────────────────────────────────────────────────
    let _queue = [];
    let _flushTimer = null;

    function _enqueue(event) {
        _queue.push(event);
        if (_queue.length >= MAX_QUEUE) {
            _flush();
        } else if (!_flushTimer) {
            _flushTimer = setTimeout(_flush, FLUSH_INTERVAL_MS);
        }
    }

    function _flush() {
        clearTimeout(_flushTimer);
        _flushTimer = null;
        if (!_queue.length) return;
        const batch = _queue.splice(0, _queue.length);
        // Send last-resort beacon on page unload, fetch otherwise
        const payload = JSON.stringify(batch.length === 1 ? batch[0] : { batch });
        try {
            if (navigator.sendBeacon) {
                // sendBeacon works even during page unload
                const blob = new Blob([payload], { type: 'application/json' });
                navigator.sendBeacon(ENDPOINT, blob);
            } else {
                fetch(ENDPOINT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: payload,
                    keepalive: true,
                }).catch(() => { }); // silently ignore network errors
            }
        } catch (_) { /* never throw from logger */ }
    }

    // Flush on page unload
    window.addEventListener('pagehide', _flush);
    window.addEventListener('beforeunload', _flush);

    // ── Core log function ──────────────────────────────────────────────
    function _log(level, event_type, page, options) {
        const evt = {
            level: level,
            event_type: _clamp(event_type, 60),
            page: _clamp(page || _page(), 120),
            component: _clamp(options.component || '', 80),
            message: _clamp(options.message || options.msg || event_type, MAX_MSG_LEN),
            browser: _browser(),
            viewport: _viewport(),
            user_id: _userId(),
            session_id: _sessionId(),
        };
        if (options.stack_trace) {
            evt.stack_trace = _clamp(options.stack_trace, MAX_STACK_LEN);
        }
        _enqueue(evt);
    }

    // ── Public API ─────────────────────────────────────────────────────
    window.DC_LOG = {
        debug: (type, page, opts = {}) => _log('debug', type, page, opts),
        info: (type, page, opts = {}) => _log('info', type, page, opts),
        warn: (type, page, opts = {}) => _log('warning', type, page, opts),
        error: (type, page, opts = {}) => _log('error', type, page, opts),

        /** Manually flush the queue (useful after critical errors) */
        flush: _flush,
    };

    // ── Auto-capture: Uncaught JS errors ───────────────────────────────
    const _prevOnerror = window.onerror;
    window.onerror = function (message, source, lineno, colno, error) {
        _log('error', 'uncaught_error', _page(), {
            component: `${source || ''}:${lineno}:${colno}`,
            message: _clamp(String(message), MAX_MSG_LEN),
            stack_trace: error && error.stack ? _clamp(error.stack, MAX_STACK_LEN) : '',
        });
        _flush(); // always flush immediately on error
        if (typeof _prevOnerror === 'function') _prevOnerror.apply(this, arguments);
        return false; // don't suppress default
    };

    // ── Auto-capture: Unhandled Promise rejections ─────────────────────
    window.addEventListener('unhandledrejection', function (evt) {
        const reason = evt.reason;
        _log('error', 'unhandled_promise_rejection', _page(), {
            message: _clamp(reason && (reason.message || String(reason)), MAX_MSG_LEN),
            stack_trace: reason && reason.stack ? _clamp(reason.stack, MAX_STACK_LEN) : '',
        });
        _flush();
    });

    // ── Auto-capture: console.error / console.warn ─────────────────────
    (function patchConsole() {
        ['error', 'warn'].forEach(method => {
            const _orig = console[method].bind(console);
            console[method] = function (...args) {
                _orig.apply(console, args);
                try {
                    const msg = args.map(a =>
                        (typeof a === 'object') ? JSON.stringify(a).slice(0, 200) : String(a)
                    ).join(' ');
                    _log(method === 'error' ? 'error' : 'warning',
                        `console_${method}`, _page(), { message: _clamp(msg, MAX_MSG_LEN) });
                } catch (_) { }
            };
        });
    })();

    // ── Auto-capture: Page navigation (SPA route changes) ─────────────
    (function patchHistory() {
        const _orig_pushState = history.pushState.bind(history);
        const _orig_replaceState = history.replaceState.bind(history);

        function _onNav(to) {
            _log('info', 'navigate', to, { message: `Navigated to ${to}` });
        }

        history.pushState = function (state, title, url) {
            _orig_pushState(state, title, url);
            _onNav(url || _page());
        };
        history.replaceState = function (state, title, url) {
            _orig_replaceState(state, title, url);
        };
        window.addEventListener('popstate', () => _onNav(_page()));
    })();

    // ── Auto-capture: Page load performance ───────────────────────────
    window.addEventListener('load', function () {
        try {
            const perf = performance.getEntriesByType('navigation')[0];
            if (perf) {
                const loadMs = Math.round(perf.loadEventEnd - perf.startTime);
                const domMs = Math.round(perf.domContentLoadedEventEnd - perf.startTime);
                _log('info', 'page_load_perf', _page(), {
                    component: 'performance-observer',
                    message: `load=${loadMs}ms dom=${domMs}ms`,
                });
            }
        } catch (_) { }
    });

    // ── Log the initial page hit ───────────────────────────────────────
    _log('info', 'page_view', _page(), { message: `Viewed ${_page()}` });

})();
