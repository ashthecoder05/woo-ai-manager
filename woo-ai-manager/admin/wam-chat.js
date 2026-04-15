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
        .finally(function () {
            setLoading(false);
        });
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
