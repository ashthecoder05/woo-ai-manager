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

    $email        = get_option( 'wam_merchant_email', '' );
    $name         = get_option( 'wam_merchant_name', '' );
    $token        = get_option( 'wam_session_token', '' );
    $credits      = (int) get_option( 'wam_credits_remaining', 0 );
    $backend_url  = WAM_DEFAULT_BACKEND;
    $is_connected = $email && $token;

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
