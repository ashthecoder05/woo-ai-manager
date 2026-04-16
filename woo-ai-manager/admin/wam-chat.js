/* Woo AI Manager — Chat panel JS */
(function () {
    'use strict';

    var messages   = document.getElementById('wam-messages');
    var input      = document.getElementById('wam-input');
    var sendBtn    = document.getElementById('wam-send');
    var quickBtns  = document.querySelectorAll('.wam-quick-btn');
    var creditsEl  = document.getElementById('wam-credits-display');
    var settingsUrl = (wamData.adminUrl || '') + 'admin.php?page=wam-settings';

    if (!messages || !input || !sendBtn) return;

    // ── Quick-action buttons ──────────────────────────────────────────
    quickBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var msg = btn.getAttribute('data-msg');
            if (msg) sendMessage(msg);
        });
    });

    // ── Send on Enter (Shift+Enter = new line) ────────────────────────
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            triggerSend();
        }
    });

    sendBtn.addEventListener('click', triggerSend);

    function triggerSend() {
        var msg = input.value.trim();
        if (!msg) return;
        input.value = '';
        sendMessage(msg);
    }

    // ── Core send logic ───────────────────────────────────────────────
    function sendMessage(text) {
        appendMessage('user', text);

        var thinking = appendThinking();
        setLoading(true);

        if (wamData.storeConnected && wamData.backendUrl) {
            // Streaming mode — two-step secure flow:
            //   Step 1: Ask WordPress for a disposable stream token (nonce-protected AJAX).
            //           PHP holds the real session token; we never see it.
            //   Step 2: Connect directly to the backend SSE stream using that token.
            //           The token is 30s TTL and burns after this one connection.
            var stepsEl    = null;
            var thinkingEl = thinking;
            var settled    = false;

            function ensureSteps() {
                if (!stepsEl) {
                    thinkingEl.remove();
                    stepsEl = document.createElement('div');
                    stepsEl.className = 'wam-steps';
                    messages.appendChild(stepsEl);
                    messages.scrollTop = messages.scrollHeight;
                }
                return stepsEl;
            }

            function handleStreamEvent(event) {
                if (event.type === 'tool_start') {
                    var steps = ensureSteps();
                    var step  = document.createElement('div');
                    step.className    = 'wam-step running';
                    step.dataset.tcId = event.id;
                    step.innerHTML    =
                        '<span class="wam-step-icon">' + escapeHtml(event.icon || '🔍') + '</span>' +
                        '<span class="wam-step-label">' + escapeHtml(event.label) + '</span>' +
                        '<span class="wam-step-status"><span class="wam-step-spinner"></span></span>';
                    steps.appendChild(step);
                    messages.scrollTop = messages.scrollHeight;

                } else if (event.type === 'tool_done') {
                    var steps = ensureSteps();
                    var step  = steps.querySelector('[data-tc-id="' + event.id + '"]');
                    if (step) {
                        step.classList.remove('running');
                        step.classList.add('done');
                        var dur = event.duration_ms < 1000
                            ? event.duration_ms + 'ms'
                            : (event.duration_ms / 1000).toFixed(1) + 's';
                        step.querySelector('.wam-step-status').innerHTML =
                            '<span class="wam-step-check">✓</span> <span class="wam-step-dur">' + dur + '</span>';
                    }

                } else if (event.type === 'reply') {
                    settled = true;
                    if (!stepsEl) thinkingEl.remove();
                    appendMessage('assistant', event.content || '');
                    updateCredits(event.credits_remaining);
                    setLoading(false);

                } else if (event.type === 'error') {
                    settled = true;
                    if (!stepsEl) thinkingEl.remove();
                    handleError(event.message || 'Something went wrong.');
                    setLoading(false);
                }
            }

            // Step 1 — exchange message for a disposable stream token via WordPress AJAX
            var tokenForm = new FormData();
            tokenForm.append('action',  'wam_stream_token');
            tokenForm.append('nonce',   wamData.nonce);
            tokenForm.append('message', text);

            fetch(wamData.ajaxUrl, {
                method:      'POST',
                credentials: 'same-origin',
                body:        tokenForm,
            })
            .then(function (res) { return res.json(); })
            .then(function (json) {
                if (!json.success) {
                    thinkingEl.remove();
                    var msg = json.data && json.data.message ? json.data.message : 'Something went wrong.';
                    handleError(msg);
                    setLoading(false);
                    return;
                }

                // Step 2 — connect to the backend stream with the disposable token
                fetch(json.data.stream_url, {
                    method:  'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body:    JSON.stringify({ stream_token: json.data.stream_token }),
                })
                .then(function (res) {
                    if (!res.ok) {
                        return res.json().then(function (body) {
                            throw new Error(body.detail || 'HTTP ' + res.status);
                        });
                    }
                    var reader  = res.body.getReader();
                    var decoder = new TextDecoder();
                    var buf     = '';

                    function pump() {
                        return reader.read().then(function (chunk) {
                            if (chunk.done) return;
                            buf += decoder.decode(chunk.value, { stream: true });
                            var lines = buf.split('\n');
                            buf = lines.pop();
                            lines.forEach(function (line) {
                                if (!line.startsWith('data: ')) return;
                                try { handleStreamEvent(JSON.parse(line.slice(6))); } catch (_) {}
                            });
                            return pump();
                        });
                    }
                    return pump();
                })
                .catch(function (err) {
                    if (!settled) {
                        if (!stepsEl) thinkingEl.remove();
                        handleError(err.message || 'Network error — could not reach the server.');
                        setLoading(false);
                    }
                });
            })
            .catch(function () {
                thinkingEl.remove();
                handleError('Network error — could not reach WordPress.');
                setLoading(false);
            });

        } else {
            // Fallback: WordPress AJAX → backend (static snapshot mode)
            var data = new FormData();
            data.append('action',  'wam_chat');
            data.append('nonce',   wamData.nonce);
            data.append('message', text);

            fetch(wamData.ajaxUrl, {
                method: 'POST',
                credentials: 'same-origin',
                body: data,
            })
            .then(function (res) { return res.json(); })
            .then(function (json) {
                thinking.remove();
                if (json.success) {
                    appendMessage('assistant', json.data.reply);
                    updateCredits(json.data.credits_remaining);
                } else {
                    var msg = json.data && json.data.message ? json.data.message : 'Something went wrong.';
                    handleError(msg);
                }
            })
            .catch(function () {
                thinking.remove();
                appendMessage('error', 'Network error — could not reach the server. Check your connection and try again.');
            })
            .finally(function () { setLoading(false); });
        }
    }

    // ── Error handler ─────────────────────────────────────────────────
    function handleError(msg) {
        var isSessionError = msg.toLowerCase().indexOf('session') !== -1 ||
                             msg.toLowerCase().indexOf('reconnect') !== -1 ||
                             msg.toLowerCase().indexOf('sign in') !== -1;

        var isCreditsError = msg.toLowerCase().indexOf('queries') !== -1 ||
                             msg.toLowerCase().indexOf('upgrade') !== -1 ||
                             msg.toLowerCase().indexOf('credits') !== -1;

        if (isSessionError) {
            var el = appendMessage('error',
                msg + ' Go to Settings to reconnect.');
            var link = document.createElement('a');
            link.href = settingsUrl;
            link.textContent = ' Go to Settings →';
            link.style.display = 'block';
            link.style.marginTop = '6px';
            el.appendChild(link);
            // Disable input — session is gone, further messages will all fail
            input.disabled  = true;
            sendBtn.disabled = true;
            quickBtns.forEach(function (b) { b.disabled = true; });

        } else if (isCreditsError) {
            var el2 = appendMessage('error', msg);
            var link2 = document.createElement('a');
            link2.href = wamData.upgradeUrl || settingsUrl;
            link2.textContent = ' Upgrade now →';
            link2.style.display = 'block';
            link2.style.marginTop = '6px';
            link2.target = '_blank';
            el2.appendChild(link2);
            // Disable input — no credits left
            input.disabled   = true;
            sendBtn.disabled  = true;
            quickBtns.forEach(function (b) { b.disabled = true; });

        } else {
            appendMessage('error', msg);
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────
    function appendMessage(role, text) {
        var el = document.createElement('div');
        el.className = 'wam-msg ' + role;
        el.textContent = text;
        messages.appendChild(el);
        messages.scrollTop = messages.scrollHeight;
        return el;
    }

    function appendThinking() {
        var el = document.createElement('div');
        el.className = 'wam-msg thinking';
        el.innerHTML = '<span class="wam-dots"><span></span><span></span><span></span></span>';
        messages.appendChild(el);
        messages.scrollTop = messages.scrollHeight;
        return el;
    }

    function setLoading(on) {
        sendBtn.disabled = on;
        input.disabled   = on;
        quickBtns.forEach(function (b) { b.disabled = on; });
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function updateCredits(n) {
        if (!creditsEl || typeof n !== 'number') return;
        creditsEl.textContent = n + ' queries left';
        creditsEl.className   = n <= 10 ? 'wam-credits-low' : '';
        if (n === 0) {
            // Reload to show the upgrade card
            window.location.reload();
        }
    }
}());
