<?php
/**
 * ai-client.php — Calls the Woo AI Manager backend.
 *
 * The plugin never touches OpenAI directly. It sends the merchant's
 * session token + store context to the backend, which handles the
 * Azure OpenAI call and credit deduction server-side.
 */

defined( 'ABSPATH' ) || exit;

// Your backend URL — change this before distributing the plugin
define( 'WAM_DEFAULT_BACKEND', 'https://heysarva.com' );

// ── Security helpers ──────────────────────────────────────────────────────────

/**
 * Returns true if the URL is safe to use as a backend endpoint.
 * localhost / 127.0.0.1 / ::1 are allowed over plain HTTP (dev mode).
 * Every other host MUST use HTTPS.
 */
function wam_is_safe_backend_url( string $url ): bool {
    $parsed = wp_parse_url( $url );
    if ( ! $parsed || empty( $parsed['host'] ) || empty( $parsed['scheme'] ) ) {
        return false;
    }
    $local = [ 'localhost', '127.0.0.1', '::1' ];
    if ( in_array( $parsed['host'], $local, true ) ) {
        return in_array( $parsed['scheme'], [ 'http', 'https' ], true );
    }
    return $parsed['scheme'] === 'https';
}

/**
 * Derives a 32-byte AES key from the site's WordPress secret keys.
 * The key is installation-specific and rotates with wp-config.php regeneration.
 */
function wam_encryption_key(): string {
    return substr( hash( 'sha256', LOGGED_IN_KEY . LOGGED_IN_SALT, true ), 0, 32 );
}

/**
 * Encrypts a session token before writing to wp_options.
 * Returns a prefixed base64 string: "wam:v1:<base64(iv+ciphertext)>".
 * Falls back to plain-text storage if OpenSSL is unavailable.
 */
function wam_encrypt_token( string $token ): string {
    if ( empty( $token ) || ! extension_loaded( 'openssl' ) ) {
        return $token;
    }
    $iv     = random_bytes( 16 );
    $cipher = openssl_encrypt( $token, 'AES-256-CBC', wam_encryption_key(), OPENSSL_RAW_DATA, $iv );
    if ( false === $cipher ) {
        return $token;
    }
    return 'wam:v1:' . base64_encode( $iv . $cipher );
}

/**
 * Decrypts a session token read from wp_options.
 * Handles both encrypted ("wam:v1:" prefix) and legacy plain-text tokens
 * so existing installs keep working without a forced re-login.
 */
function wam_decrypt_token( string $stored ): string {
    if ( empty( $stored ) ) {
        return '';
    }
    // Legacy plain-text token — return as-is (will be re-encrypted on next sign-in)
    if ( strpos( $stored, 'wam:v1:' ) !== 0 ) {
        return $stored;
    }
    if ( ! extension_loaded( 'openssl' ) ) {
        return '';
    }
    $raw = base64_decode( substr( $stored, 7 ), true );
    if ( false === $raw || strlen( $raw ) < 17 ) {
        return '';
    }
    $plain = openssl_decrypt(
        substr( $raw, 16 ),
        'AES-256-CBC',
        wam_encryption_key(),
        OPENSSL_RAW_DATA,
        substr( $raw, 0, 16 )
    );
    return $plain !== false ? $plain : '';
}

/**
 * Send a chat message to the backend and return the reply.
 *
 * @param string $user_message  The merchant's question.
 * @param string $store_context Live store data (injected into system prompt on the backend).
 * @return array{reply: string, credits_remaining: int}|WP_Error
 */
function wam_chat( string $user_message, string $store_context = '' ) {
    $email   = get_option( 'wam_merchant_email', '' );
    $token   = wam_decrypt_token( get_option( 'wam_session_token', '' ) );
    $backend = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );

    if ( ! $email || ! $token ) {
        return new WP_Error(
            'wam_not_connected',
            'Not connected. Go to AI Manager → Settings and sign in with your email.'
        );
    }

    if ( ! wam_is_safe_backend_url( $backend ) ) {
        return new WP_Error( 'wam_insecure_url', 'Backend URL must use HTTPS for non-local hosts.' );
    }

    $response = wp_remote_post( $backend . '/api/plugin/chat', [
        'timeout'     => 90,
        'headers'     => [ 'Content-Type' => 'application/json' ],
        'body'        => wp_json_encode( [
            'email'         => $email,
            'token'         => $token,
            'message'       => $user_message,
            'store_context' => $store_context,
        ] ),
    ] );

    if ( is_wp_error( $response ) ) {
        return $response;
    }

    $code = wp_remote_retrieve_response_code( $response );
    $data = json_decode( wp_remote_retrieve_body( $response ), true );

    if ( $code === 401 ) {
        // Token expired — clear it so the settings page prompts re-login
        delete_option( 'wam_session_token' );
        return new WP_Error( 'wam_session_expired', 'Session expired. Please reconnect in Settings.' );
    }

    if ( $code === 402 ) {
        return new WP_Error( 'wam_no_credits', $data['detail'] ?? 'No credits remaining.' );
    }

    if ( $code !== 200 ) {
        $msg = $data['detail'] ?? 'Backend error (HTTP ' . $code . ').';
        return new WP_Error( 'wam_backend_error', $msg );
    }

    // Persist the updated credit count so the UI reflects it immediately
    if ( isset( $data['credits_remaining'] ) ) {
        update_option( 'wam_credits_remaining', (int) $data['credits_remaining'] );
    }

    return [
        'reply'             => $data['reply'] ?? '',
        'credits_remaining' => $data['credits_remaining'] ?? 0,
    ];
}

/**
 * Register the merchant's WC store with the backend.
 *
 * Sends the store URL + WC REST API consumer key/secret.
 * The backend validates them against the live store before saving.
 *
 * @param string $consumer_key    WC REST API consumer key.
 * @param string $consumer_secret WC REST API consumer secret.
 * @return array|WP_Error  Array with 'status' and 'message' on success.
 */
function wam_register_store( string $consumer_key, string $consumer_secret ) {
    $email   = get_option( 'wam_merchant_email', '' );
    $token   = wam_decrypt_token( get_option( 'wam_session_token', '' ) );
    $backend = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );

    if ( ! $email || ! $token ) {
        return new WP_Error( 'wam_not_connected', 'Not connected. Sign in first.' );
    }

    if ( ! wam_is_safe_backend_url( $backend ) ) {
        return new WP_Error( 'wam_insecure_url', 'Backend URL must use HTTPS for non-local hosts.' );
    }

    $response = wp_remote_post( $backend . '/api/plugin/register', [
        'timeout' => 20,
        'headers' => [ 'Content-Type' => 'application/json' ],
        'body'    => wp_json_encode( [
            'email'           => $email,
            'token'           => $token,
            'store_url'       => get_site_url(),
            'consumer_key'    => $consumer_key,
            'consumer_secret' => $consumer_secret,
        ] ),
    ] );

    if ( is_wp_error( $response ) ) {
        return $response;
    }

    $code = wp_remote_retrieve_response_code( $response );
    $data = json_decode( wp_remote_retrieve_body( $response ), true );

    if ( $code === 400 ) {
        return new WP_Error( 'wam_invalid_credentials', $data['detail'] ?? 'Invalid credentials.' );
    }
    if ( $code === 401 ) {
        delete_option( 'wam_session_token' );
        return new WP_Error( 'wam_session_expired', 'Session expired. Please reconnect in Settings.' );
    }
    if ( $code !== 200 ) {
        return new WP_Error( 'wam_register_failed', $data['detail'] ?? 'Registration failed (HTTP ' . $code . ').' );
    }

    // Mark store as connected so the UI reflects it
    update_option( 'wam_store_connected', 1 );
    update_option( 'wam_store_url', get_site_url() );

    return $data;
}

/**
 * Exchange the long-lived session token for a single-use, short-lived
 * stream token the browser can use to connect to /api/plugin/chat/stream.
 *
 * This is the core of the token security model:
 *   - The real session token (24h TTL, reusable) stays in PHP. Never sent to the browser.
 *   - The returned stream_token (30s TTL, single-use) is given to the browser.
 *   - Even if the stream_token is extracted via XSS, it is already burned after one use.
 *
 * @param string $user_message  The chat message to be streamed.
 * @return array{stream_token: string, credits_remaining: int, stream_url: string}|WP_Error
 */
function wam_get_stream_token( string $user_message ) {
    $email   = get_option( 'wam_merchant_email', '' );
    $token   = wam_decrypt_token( get_option( 'wam_session_token', '' ) );
    $backend = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );

    if ( ! $email || ! $token ) {
        return new WP_Error(
            'wam_not_connected',
            'Not connected. Go to AI Manager → Settings and sign in.'
        );
    }

    if ( ! wam_is_safe_backend_url( $backend ) ) {
        return new WP_Error( 'wam_insecure_url', 'Backend URL must use HTTPS for non-local hosts.' );
    }

    $response = wp_remote_post( $backend . '/api/plugin/stream-token', [
        'timeout' => 15,
        'headers' => [ 'Content-Type' => 'application/json' ],
        'body'    => wp_json_encode( [
            'email'   => $email,
            'token'   => $token,
            'message' => $user_message,
        ] ),
    ] );

    if ( is_wp_error( $response ) ) {
        return $response;
    }

    $code = wp_remote_retrieve_response_code( $response );
    $data = json_decode( wp_remote_retrieve_body( $response ), true );

    if ( $code === 401 ) {
        delete_option( 'wam_session_token' );
        return new WP_Error( 'wam_session_expired', 'Session expired. Please reconnect in Settings.' );
    }
    if ( $code === 402 ) {
        return new WP_Error( 'wam_no_credits', $data['detail'] ?? 'No credits remaining.' );
    }
    if ( $code !== 200 ) {
        return new WP_Error( 'wam_backend_error', $data['detail'] ?? 'Backend error (HTTP ' . $code . ').' );
    }

    return [
        'stream_token'      => $data['stream_token'],
        'credits_remaining' => $data['credits_remaining'] ?? 0,
        'stream_url'        => $backend . '/api/plugin/chat/stream',
    ];
}

/**
 * Sign in via Google ID token — backend verifies it, creates the account
 * (50 free credits if new), and returns a session token we store locally.
 *
 * @param string $google_token  The credential returned by the Google Sign-In button.
 * @return array|WP_Error
 */
function wam_plugin_signin( string $google_token ) {
    $backend = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );

    if ( ! wam_is_safe_backend_url( $backend ) ) {
        return new WP_Error( 'wam_insecure_url', 'Backend URL must use HTTPS for non-local hosts.' );
    }

    $response = wp_remote_post( $backend . '/api/plugin/signin', [
        'timeout' => 15,
        'headers' => [ 'Content-Type' => 'application/json' ],
        'body'    => wp_json_encode( [ 'google_token' => $google_token ] ),
    ] );

    if ( is_wp_error( $response ) ) {
        return $response;
    }

    $code = wp_remote_retrieve_response_code( $response );
    $data = json_decode( wp_remote_retrieve_body( $response ), true );

    if ( $code === 401 ) {
        return new WP_Error( 'wam_google_invalid', $data['detail'] ?? 'Google sign-in failed.' );
    }
    if ( $code !== 200 ) {
        return new WP_Error( 'wam_signin_failed', $data['detail'] ?? 'Sign-in failed (HTTP ' . $code . ').' );
    }

    update_option( 'wam_merchant_email',    $data['email'] );
    update_option( 'wam_merchant_name',     $data['name'] ?? '' );
    update_option( 'wam_session_token',     wam_encrypt_token( $data['session_token'] ) );
    update_option( 'wam_credits_remaining', (int) $data['credits_remaining'] );

    return $data;
}
