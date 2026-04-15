<?php
/**
 * settings-page.php — Google SSO login + credit balance.
 * Merchants sign in with Google and see their remaining free queries.
 *
 * @package Woo_AI_Manager
 * @version 0.1.0
 */

defined( 'ABSPATH' ) || exit;

function wam_render_settings_page() {
    if ( ! current_user_can( 'manage_options' ) ) {
        return;
    }

    // Handle disconnect
    if ( isset( $_POST['wam_disconnect'] ) && check_admin_referer( 'wam_disconnect' ) ) {
        if ( ! current_user_can( 'manage_options' ) ) {
            wp_die( 'Unauthorised.' );
        }
        delete_option( 'wam_merchant_email' );
        delete_option( 'wam_merchant_name' );
        delete_option( 'wam_session_token' );
        delete_option( 'wam_credits_remaining' );
        add_settings_error( 'wam_settings', 'disconnected', 'Signed out successfully.', 'updated' );
    }

    $email           = get_option( 'wam_merchant_email', '' );
    $name            = get_option( 'wam_merchant_name', '' );
    $token           = get_option( 'wam_session_token', '' );
    $credits         = (int) get_option( 'wam_credits_remaining', 0 );
    $backend_url     = WAM_DEFAULT_BACKEND;
    $is_connected    = $email && $token;
    $store_connected = (bool) get_option( 'wam_store_connected', false );

    // Fetch Google Client ID from the backend (cached for 1 hour)
    $google_client_id = get_transient( 'wam_google_client_id' );
    if ( false === $google_client_id ) {
        $resp = wp_remote_get( $backend_url . '/api/plugin/config', [ 'timeout' => 5 ] );
        if ( ! is_wp_error( $resp ) && wp_remote_retrieve_response_code( $resp ) === 200 ) {
            $cfg              = json_decode( wp_remote_retrieve_body( $resp ), true );
            $google_client_id = $cfg['google_client_id'] ?? '';
            set_transient( 'wam_google_client_id', $google_client_id, HOUR_IN_SECONDS );
        } else {
            $google_client_id = '';
        }
    }

    settings_errors( 'wam_settings' );
    ?>
    <div class="wrap">
        <h1>AI Manager — Settings</h1>

        <?php if ( $is_connected ) : ?>

            <!-- ── Connected ─────────────────────────────────────────── -->
            <div class="wam-connected-card">
                <span class="wam-connected-dot"></span>
                <div>
                    <strong>
                        <?php echo $name ? esc_html( $name ) : esc_html( $email ); ?>
                    </strong>
                    <?php if ( $name ) : ?>
                        <span style="color:#666;font-size:12px;">&nbsp;(<?php echo esc_html( $email ); ?>)</span>
                    <?php endif; ?>
                    <br>
                    <?php if ( $credits === 0 ) : ?>
                        <span class="wam-credit-badge wam-credit-empty">No queries remaining</span>
                    <?php elseif ( $credits <= 10 ) : ?>
                        <span class="wam-credit-badge wam-credit-low"><?php echo $credits; ?> queries left</span>
                    <?php else : ?>
                        <span class="wam-credit-badge wam-credit-ok"><?php echo $credits; ?> queries remaining</span>
                    <?php endif; ?>
                </div>
            </div>

            <?php if ( $credits === 0 ) : ?>
                <div class="notice notice-error" style="margin-top:16px;">
                    <p>
                        <strong>You've used all your free queries.</strong>
                        <a href="<?php echo esc_url( WAM_UPGRADE_URL ); ?>" class="button button-primary" style="margin-left:12px;" target="_blank" rel="noopener">
                            Upgrade to continue →
                        </a>
                    </p>
                </div>
            <?php elseif ( $credits <= 10 ) : ?>
                <div class="notice notice-warning" style="margin-top:16px;">
                    <p>
                        Only <strong><?php echo $credits; ?> queries</strong> left on your free plan.
                        <a href="<?php echo esc_url( WAM_UPGRADE_URL ); ?>" target="_blank" rel="noopener">Upgrade for unlimited access →</a>
                    </p>
                </div>
            <?php endif; ?>

            <form method="post" style="margin-top:16px;">
                <?php wp_nonce_field( 'wam_disconnect' ); ?>
                <button type="submit" name="wam_disconnect" class="button">Sign out</button>
            </form>

            <!-- ── Step 2: Connect store ─────────────────────────────── -->
            <div style="margin-top:28px;">
                <h2 style="margin-bottom:4px;">
                    <?php if ( $store_connected ) : ?>
                        <span style="color:#7ad03a;">&#10003;</span> Store connected — Live data mode active
                    <?php else : ?>
                        Step 2: Connect your store <span style="font-size:13px;font-weight:normal;color:#666;">(optional — unlocks smarter answers)</span>
                    <?php endif; ?>
                </h2>

                <?php if ( $store_connected ) : ?>
                    <p style="color:#555;font-size:13px;margin-top:0;">
                        The AI can now call your store's live data directly. No static snapshot needed.
                        <a href="#wam-reconnect" id="wam-reconnect-link" style="margin-left:8px;font-size:12px;">Reconnect with new keys</a>
                    </p>
                    <div id="wam-reconnect" style="display:none;margin-top:12px;">
                <?php else : ?>
                    <p style="color:#555;font-size:13px;margin-top:0;">
                        Give the AI direct access to your store's live data — orders, revenue, products, customers.
                        It will be able to answer complex questions and even take actions like creating coupons.
                    </p>
                    <div id="wam-reconnect">
                <?php endif; ?>

                    <ol style="font-size:13px;color:#444;line-height:1.8;margin-bottom:16px;">
                        <li>Go to <strong>WooCommerce → Settings → Advanced → REST API</strong></li>
                        <li>Click <strong>Add key</strong></li>
                        <li>Set Description to <em>AI Manager</em>, User to your admin, Permissions to <strong>Read/Write</strong></li>
                        <li>Click <strong>Generate API key</strong> and copy both keys below</li>
                    </ol>

                    <table class="form-table" style="max-width:560px;">
                        <tr>
                            <th style="width:140px;"><label for="wam-ck">Consumer Key</label></th>
                            <td><input type="password" id="wam-ck" class="regular-text" placeholder="ck_…" autocomplete="off"></td>
                        </tr>
                        <tr>
                            <th><label for="wam-cs">Consumer Secret</label></th>
                            <td><input type="password" id="wam-cs" class="regular-text" placeholder="cs_…" autocomplete="off"></td>
                        </tr>
                    </table>

                    <p>
                        <button type="button" id="wam-register-btn" class="button button-primary">Connect store</button>
                        <span id="wam-register-loading" style="display:none;margin-left:10px;color:#666;">Connecting…</span>
                    </p>
                    <p id="wam-register-error"  style="color:#cc1818;display:none;"></p>
                    <p id="wam-register-success" style="color:#3a7a1a;display:none;"></p>
                </div>
            </div>

            <script>
            (function () {
                var AJAX_URL = <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>;
                var NONCE    = <?php echo wp_json_encode( wp_create_nonce( 'wam_register_store' ) ); ?>;

                var reconnectLink = document.getElementById('wam-reconnect-link');
                if (reconnectLink) {
                    reconnectLink.addEventListener('click', function (e) {
                        e.preventDefault();
                        document.getElementById('wam-reconnect').style.display = 'block';
                        reconnectLink.style.display = 'none';
                    });
                }

                document.getElementById('wam-register-btn').addEventListener('click', function () {
                    var ck = document.getElementById('wam-ck').value.trim();
                    var cs = document.getElementById('wam-cs').value.trim();

                    document.getElementById('wam-register-error').style.display   = 'none';
                    document.getElementById('wam-register-success').style.display = 'none';

                    if (!ck || !cs) {
                        document.getElementById('wam-register-error').textContent   = 'Both keys are required.';
                        document.getElementById('wam-register-error').style.display = 'block';
                        return;
                    }

                    document.getElementById('wam-register-btn').disabled            = true;
                    document.getElementById('wam-register-loading').style.display   = 'inline';

                    var form = new FormData();
                    form.append('action',          'wam_register_store');
                    form.append('nonce',           NONCE);
                    form.append('consumer_key',    ck);
                    form.append('consumer_secret', cs);

                    fetch(AJAX_URL, { method: 'POST', credentials: 'same-origin', body: form })
                        .then(function (r) { return r.json(); })
                        .then(function (json) {
                            document.getElementById('wam-register-btn').disabled          = false;
                            document.getElementById('wam-register-loading').style.display = 'none';
                            if (json.success) {
                                document.getElementById('wam-register-success').textContent   = 'Store connected! The AI now has live access to your data.';
                                document.getElementById('wam-register-success').style.display = 'block';
                                // Reload after 1.5s to show the connected state
                                setTimeout(function () { window.location.reload(); }, 1500);
                            } else {
                                var msg = json.data && json.data.message ? json.data.message : 'Connection failed. Check your keys and try again.';
                                document.getElementById('wam-register-error').textContent   = msg;
                                document.getElementById('wam-register-error').style.display = 'block';
                            }
                        })
                        .catch(function () {
                            document.getElementById('wam-register-btn').disabled          = false;
                            document.getElementById('wam-register-loading').style.display = 'none';
                            document.getElementById('wam-register-error').textContent     = 'Could not reach the server. Check your connection.';
                            document.getElementById('wam-register-error').style.display   = 'block';
                        });
                });
            }());
            </script>

        <?php elseif ( $google_client_id ) : ?>

            <!-- ── Sign-in ────────────────────────────────────────────── -->
            <div class="wam-signin-box">
                <h2 style="margin-top:0;">Get started free</h2>
                <p>Sign in with your Google account to activate <strong>50 free AI queries</strong> — no credit card, no API key needed.</p>
                <p style="color:#666;font-size:12px;">
                    The AI will read your live WooCommerce data (order totals, products, stock levels)
                    to answer your questions. No customer emails or payment details are ever sent.
                </p>
                <div id="wam-google-btn"></div>
                <p id="wam-signin-error" style="color:#cc1818;display:none;margin-top:8px;"></p>
                <p id="wam-signin-loading" style="display:none;color:#666;">Signing in…</p>
            </div>

            <script src="https://accounts.google.com/gsi/client" async defer></script>
            <script>
            (function () {
                var CLIENT_ID = <?php echo wp_json_encode( $google_client_id ); ?>;
                var AJAX_URL  = <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>;
                var NONCE     = <?php echo wp_json_encode( wp_create_nonce( 'wam_google_signin' ) ); ?>;

                function onGoogleSignIn( response ) {
                    document.getElementById('wam-signin-error').style.display   = 'none';
                    document.getElementById('wam-signin-loading').style.display  = 'block';
                    document.getElementById('wam-google-btn').style.display      = 'none';

                    var form = new FormData();
                    form.append('action',       'wam_google_signin');
                    form.append('nonce',        NONCE);
                    form.append('google_token', response.credential);

                    fetch(AJAX_URL, { method: 'POST', credentials: 'same-origin', body: form })
                        .then(function (r) { return r.json(); })
                        .then(function (json) {
                            if (json.success) {
                                window.location.reload();
                            } else {
                                document.getElementById('wam-signin-loading').style.display = 'none';
                                document.getElementById('wam-google-btn').style.display     = 'block';
                                var msg = json.data && json.data.message ? json.data.message : 'Sign-in failed. Please try again.';
                                var errEl = document.getElementById('wam-signin-error');
                                errEl.textContent   = msg;
                                errEl.style.display = 'block';
                            }
                        })
                        .catch(function () {
                            document.getElementById('wam-signin-loading').style.display = 'none';
                            document.getElementById('wam-google-btn').style.display     = 'block';
                            var errEl = document.getElementById('wam-signin-error');
                            errEl.textContent   = 'Could not reach the server. Check your connection and try again.';
                            errEl.style.display = 'block';
                        });
                }

                window.addEventListener('load', function () {
                    if (typeof google === 'undefined') return;
                    google.accounts.id.initialize({
                        client_id:   CLIENT_ID,
                        callback:    onGoogleSignIn,
                        ux_mode:     'popup',
                        auto_select: false,
                    });
                    google.accounts.id.renderButton(
                        document.getElementById('wam-google-btn'),
                        { theme: 'outline', size: 'large', text: 'signin_with', shape: 'rectangular' }
                    );
                });
            }());
            </script>

        <?php else : ?>
            <div class="notice notice-error inline">
                <p>
                    Cannot reach the server. Make sure the backend is running and reload this page.
                    If this keeps happening, contact <a href="mailto:PLACEHOLDER_SUPPORT_EMAIL">support</a>.
                </p>
            </div>
        <?php endif; ?>
    </div>

    <style>
    .wam-connected-card {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        background: #f6fcf3;
        border: 1px solid #7ad03a;
        border-radius: 6px;
        padding: 14px 18px;
        font-size: 13px;
        margin-top: 8px;
    }
    .wam-connected-dot {
        width: 12px; height: 12px;
        background: #7ad03a;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .wam-credit-badge {
        display: inline-block;
        font-size: 11px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 10px;
        margin-top: 4px;
    }
    .wam-credit-ok    { background: #eaf7e1; color: #3a7a1a; }
    .wam-credit-low   { background: #fef3cd; color: #7a5c00; }
    .wam-credit-empty { background: #fce8e8; color: #8a1f1f; }
    .wam-signin-box {
        max-width: 480px;
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 24px;
        margin-top: 8px;
    }
    </style>
    <?php
}
