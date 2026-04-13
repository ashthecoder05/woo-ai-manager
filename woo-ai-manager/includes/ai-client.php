<?php
/**
 * ai-client.php — Calls the Woo AI Manager backend.
 *
 * The plugin never touches OpenAI directly. It sends the merchant's
 * session token + store context to the backend, which handles the
 * Azure OpenAI call and credit deduction server-side.
 */

defined( 'ABSPATH' ) || exit;

// Default backend URL — change this one value for production
define( 'WAM_DEFAULT_BACKEND', 'http://localhost:8000' );

/**
 * Send a chat message to the backend and return the reply.
 *
 * @param string $user_message  The merchant's question.
 * @param string $store_context Live store data (injected into system prompt on the backend).
 * @return array{reply: string, credits_remaining: int}|WP_Error
 */
function wam_chat( string $user_message, string $store_context = '' ) {
    $email   = get_option( 'wam_merchant_email', '' );
    $token   = get_option( 'wam_session_token', '' );
    $backend = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );

    if ( ! $email || ! $token ) {
        return new WP_Error(
            'wam_not_connected',
            'Not connected. Go to AI Manager → Settings and sign in with your email.'
        );
    }

    $response = wp_remote_post( $backend . '/api/plugin/chat', [
        'timeout'     => 30,
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
 * Sign in with email — creates an account on the backend (50 free credits)
 * and stores the session token locally.
 *
 * @return array|WP_Error
 */
function wam_plugin_signin( string $email ) {
    $backend = rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' );

    $response = wp_remote_post( $backend . '/api/plugin/signin', [
        'timeout' => 15,
        'headers' => [ 'Content-Type' => 'application/json' ],
        'body'    => wp_json_encode( [ 'email' => $email ] ),
    ] );

    if ( is_wp_error( $response ) ) {
        return $response;
    }

    $code = wp_remote_retrieve_response_code( $response );
    $data = json_decode( wp_remote_retrieve_body( $response ), true );

    if ( $code !== 200 ) {
        return new WP_Error( 'wam_signin_failed', $data['detail'] ?? 'Sign-in failed.' );
    }

    update_option( 'wam_merchant_email',   $data['email'] );
    update_option( 'wam_session_token',    $data['session_token'] );
    update_option( 'wam_credits_remaining', (int) $data['credits_remaining'] );

    return $data;
}
