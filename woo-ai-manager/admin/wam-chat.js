/* Woo AI Manager — Chat panel JS */
(function () {
    'use strict';

    var messages  = document.getElementById('wam-messages');
    var input     = document.getElementById('wam-input');
    var sendBtn   = document.getElementById('wam-send');
    var quickBtns = document.querySelectorAll('.wam-quick-btn');

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

        var thinking = appendMessage('thinking', 'Thinking…');
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
            } else {
                var errMsg = (json.data && json.data.message) ? json.data.message : 'Something went wrong.';
                appendMessage('error', errMsg);
            }
        })
        .catch(function () {
            thinking.remove();
            appendMessage('error', 'Network error — please try again.');
        })
        .finally(function () {
            setLoading(false);
        });
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

    function setLoading(on) {
        sendBtn.disabled = on;
        input.disabled   = on;
        quickBtns.forEach(function (b) { b.disabled = on; });
    }
}());
