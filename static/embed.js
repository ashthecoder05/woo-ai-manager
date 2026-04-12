/**
 * Blockonomics Merchant Assistant — Drop-in embed script
 *
 * Usage (add to your merchant dashboard HTML):
 *   <script src="https://your-assistant-host.com/embed.js"
 *           data-api="https://your-assistant-host.com"
 *           data-position="bottom-right"
 *           data-theme="dark"></script>
 *
 * Attributes:
 *   data-api       — Base URL of the assistant backend (required)
 *   data-position  — "bottom-right" (default) | "bottom-left"
 *   data-theme     — "dark" (default) | "light"
 *   data-label     — Button label text (default: "Assistant")
 */
(function () {
  'use strict';

  var script  = document.currentScript || (function () {
    var scripts = document.getElementsByTagName('script');
    return scripts[scripts.length - 1];
  })();

  var API_URL  = (script.getAttribute('data-api')      || '').replace(/\/$/, '');
  var POSITION = script.getAttribute('data-position')  || 'bottom-right';
  var LABEL    = script.getAttribute('data-label')     || 'Assistant';
  var MERCHANT = script.getAttribute('data-merchant')  || '';
  // Session token passed by the dashboard so the widget can make authenticated requests
  var SESSION_TOKEN = script.getAttribute('data-token') || localStorage.getItem('blocko_session_token') || '';

  if (!API_URL) {
    console.warn('[Blockonomics Assistant] data-api attribute is required.');
    return;
  }

  /* ─── Inject styles ─────────────────────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = [
    '#bnx-launcher{',
      'position:fixed;',
      (POSITION === 'bottom-left' ? 'left:20px;' : 'right:20px;'),
      'bottom:20px;',
      'z-index:2147483647;',
      'display:flex;flex-direction:column;align-items:',
      (POSITION === 'bottom-left' ? 'flex-start;' : 'flex-end;'),
      'gap:12px;',
    '}',

    '#bnx-panel{',
      'width:360px;height:560px;',
      'border-radius:16px;overflow:hidden;',
      'box-shadow:0 8px 40px rgba(0,0,0,0.45);',
      'border:1px solid #2a2a2a;',
      'display:none;',
      'transform:translateY(12px);opacity:0;',
      'transition:transform 0.2s ease,opacity 0.2s ease;',
    '}',
    '#bnx-panel.open{display:block;}',
    '#bnx-panel.visible{transform:translateY(0);opacity:1;}',

    '#bnx-iframe{width:100%;height:100%;border:none;display:block;}',

    '#bnx-btn{',
      'display:flex;align-items:center;gap:8px;',
      'background:#f7931a;color:#000;',
      'border:none;border-radius:100px;',
      'padding:0 18px;height:48px;',
      'font-size:14px;font-weight:600;',
      'cursor:pointer;',
      'box-shadow:0 4px 20px rgba(247,147,26,0.4);',
      'font-family:system-ui,-apple-system,sans-serif;',
      'transition:transform 0.15s,box-shadow 0.15s;',
      'white-space:nowrap;',
    '}',
    '#bnx-btn:hover{transform:translateY(-1px);box-shadow:0 6px 24px rgba(247,147,26,0.55);}',
    '#bnx-btn .bnx-icon{font-size:18px;line-height:1;}',
    '#bnx-btn .bnx-close{display:none;font-size:20px;line-height:1;}',
    '#bnx-btn.open .bnx-icon{display:none;}',
    '#bnx-btn.open .bnx-close{display:inline;}',
  ].join('');
  document.head.appendChild(style);

  /* ─── Build DOM ─────────────────────────────────────────────────────── */
  var launcher = document.createElement('div');
  launcher.id  = 'bnx-launcher';

  var panel = document.createElement('div');
  panel.id  = 'bnx-panel';
  panel.setAttribute('aria-label', 'Blockonomics Assistant');
  panel.setAttribute('role', 'dialog');

  var iframe = document.createElement('iframe');
  iframe.id    = 'bnx-iframe';
  iframe.title = 'Blockonomics Merchant Assistant';
  iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups');

  panel.appendChild(iframe);

  var toggleBtn = document.createElement('button');
  toggleBtn.id = 'bnx-btn';
  toggleBtn.setAttribute('aria-expanded', 'false');
  toggleBtn.setAttribute('aria-controls', 'bnx-panel');
  toggleBtn.innerHTML =
    '<span class="bnx-icon">₿</span>' +
    '<span class="bnx-label">' + LABEL + '</span>' +
    '<span class="bnx-close" aria-hidden="true">✕</span>';

  launcher.appendChild(panel);
  launcher.appendChild(toggleBtn);
  document.body.appendChild(launcher);

  /* ─── Toggle logic ──────────────────────────────────────────────────── */
  var isOpen    = false;
  var iframeLoaded = false;

  function open() {
    if (!iframeLoaded) {
      iframe.src = API_URL + '/widget?api=' + encodeURIComponent(API_URL) +
                   (MERCHANT       ? '&merchant=' + encodeURIComponent(MERCHANT)       : '') +
                   (SESSION_TOKEN  ? '&token='    + encodeURIComponent(SESSION_TOKEN)  : '') +
                   '&v=' + Date.now();
      iframeLoaded = true;
    }
    panel.style.display = 'block';
    // Next frame → animate in
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { panel.classList.add('visible'); });
    });
    panel.classList.add('open');
    toggleBtn.classList.add('open');
    toggleBtn.setAttribute('aria-expanded', 'true');
    isOpen = true;
  }

  function close() {
    panel.classList.remove('visible');
    toggleBtn.classList.remove('open');
    toggleBtn.setAttribute('aria-expanded', 'false');
    isOpen = false;
    // Hide after transition
    setTimeout(function () {
      if (!isOpen) { panel.classList.remove('open'); }
    }, 220);
  }

  toggleBtn.addEventListener('click', function () {
    isOpen ? close() : open();
  });

  // Close on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) close();
  });

  // Expose API for programmatic control
  window.BlockonomicsAssistant = { open: open, close: close };
})();
