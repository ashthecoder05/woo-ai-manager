<?php
/**
 * settings-page.php — Google SSO login + credit balance.
 */

defined( 'ABSPATH' ) || exit;

function wam_render_settings_page() {
    if ( ! current_user_can( 'manage_options' ) ) {
        return;
    }

    // Handle disconnect
    if ( isset( $_POST['wam_disconnect'] ) && check_admin_referer( 'wam_disconnect' ) ) {
        delete_option( 'wam_merchant_email' );
        delete_option( 'wam_merchant_name' );
        delete_option( 'wam_session_token' );
        delete_option( 'wam_credits_remaining' );
        add_settings_error( 'wam_settings', 'disconnected', 'Disconnected.', 'updated' );
    }

    // Handle backend URL save
    if ( isset( $_POST['wam_save_backend'] ) && check_admin_referer( 'wam_backend' ) ) {
        update_option( 'wam_backend_url', esc_url_raw( wp_unslash( $_POST['wam_backend_url'] ?? '' ) ) );
        add_settings_error( 'wam_settings', 'saved', 'Backend URL saved.', 'updated' );
    }

    $email        = get_option( 'wam_merchant_email', '' );
    $name         = get_option( 'wam_merchant_name', '' );
    $token        = get_option( 'wam_session_token', '' );
    $credits      = (int) get_option( 'wam_credits_remaining', 0 );
    $backend_url  = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );
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

            <div class="wam-connected-card">
                <span class="wam-connected-dot"></span>
                <strong>Connected</strong>
                <?php if ( $name ) : ?>
                    as <strong><?php echo esc_html( $name ); ?></strong>
                    (<code><?php echo esc_html( $email ); ?></code>)
                <?php else : ?>
                    as <code><?php echo esc_html( $email ); ?></code>
                <?php endif; ?>
                &nbsp;—&nbsp;
                <strong style="color:<?php echo $credits <= 5 ? '#cc1818' : '#1d2327'; ?>">
                    <?php echo $credits; ?> queries remaining
                </strong>
                <?php if ( $credits === 0 ) : ?>
                    <span style="color:#cc1818;"> — contact us to top up</span>
                <?php endif; ?>
            </div>

            <form method="post" style="margin-top:12px;">
                <?php wp_nonce_field( 'wam_disconnect' ); ?>
                <button type="submit" name="wam_disconnect" class="button">Sign out</button>
            </form>

        <?php elseif ( $google_client_id ) : ?>

            <p>Sign in with your Google account to get <strong>50 free AI queries</strong>. No credit card needed.</p>

            <div id="wam-signin-area">
                <div id="wam-google-btn"></div>
                <p id="wam-signin-error" style="color:#cc1818;display:none;margin-top:8px;"></p>
                <p id="wam-signin-loading" style="display:none;color:#666;">Signing in…</p>
            </div>

            <!-- Google Identity Services -->
            <script src="https://accounts.google.com/gsi/client" async defer></script>
            <script>
            (function () {
                var CLIENT_ID  = <?php echo wp_json_encode( $google_client_id ); ?>;
                var BACKEND    = <?php echo wp_json_encode( $backend_url ); ?>;
                var AJAX_URL   = <?php echo wp_json_encode( admin_url( 'admin-ajax.php' ) ); ?>;
                var NONCE      = <?php echo wp_json_encode( wp_create_nonce( 'wam_google_signin' ) ); ?>;

                function onGoogleSignIn(response) {
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
                                // Reload the settings page to show the connected state
                                window.location.reload();
                            } else {
                                document.getElementById('wam-signin-loading').style.display = 'none';
                                document.getElementById('wam-google-btn').style.display     = 'block';
                                var errEl = document.getElementById('wam-signin-error');
                                errEl.textContent = json.data && json.data.message ? json.data.message : 'Sign-in failed. Please try again.';
                                errEl.style.display = 'block';
                            }
                        })
                        .catch(function () {
                            document.getElementById('wam-signin-loading').style.display = 'none';
                            document.getElementById('wam-google-btn').style.display     = 'block';
                            document.getElementById('wam-signin-error').textContent    = 'Network error. Is the backend running?';
                            document.getElementById('wam-signin-error').style.display  = 'block';
                        });
                }

                window.addEventListener('load', function () {
                    if (typeof google === 'undefined') return;
                    google.accounts.id.initialize({
                        client_id:         CLIENT_ID,
                        callback:          onGoogleSignIn,
                        ux_mode:           'popup',
                        auto_select:       false,
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
                <p>Cannot reach the backend at <code><?php echo esc_html( $backend_url ); ?></code>. Make sure it is running, then reload this page.</p>
            </div>
        <?php endif; ?>

        <hr>
        <h2>Advanced</h2>
        <form method="post">
            <?php wp_nonce_field( 'wam_backend' ); ?>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row"><label for="wam_backend_url">Backend URL</label></th>
                    <td>
                        <input type="url"
                               id="wam_backend_url"
                               name="wam_backend_url"
                               value="<?php echo esc_attr( $backend_url ); ?>"
                               class="regular-text" />
                        <p class="description">
                            <code><?php echo esc_html( WAM_DEFAULT_BACKEND ); ?></code> for local dev.
                            Change to your production URL before going live.
                        </p>
                    </td>
                </tr>
            </table>
            <p class="submit">
                <button type="submit" name="wam_save_backend" class="button">Save</button>
            </p>
        </form>
    </div>

    <style>
    .wam-connected-card {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #f0faf0;
        border: 1px solid #7ad03a;
        border-radius: 5px;
        padding: 12px 18px;
        font-size: 13px;
    }
    .wam-connected-dot {
        width: 10px; height: 10px;
        background: #7ad03a;
        border-radius: 50%;
        flex-shrink: 0;
    }
    #wam-signin-area { margin-top: 12px; }
    </style>
    <?php
}
