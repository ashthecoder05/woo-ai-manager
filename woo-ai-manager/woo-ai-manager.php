<?php
/**
 * Plugin Name: Woo AI Manager
 * Plugin URI:  PLACEHOLDER_PLUGIN_URL
 * Description: AI store manager that lives inside your WP Admin — knows your orders, customers, and revenue, and tells you what to do next.
 * Version:     0.1.0
 * Author:      Aishwarya Adyanthaya
 * Author URI:  PLACEHOLDER_AUTHOR_URL
 * License:     GPL-2.0-or-later
 * Text Domain: woo-ai-manager
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * WC requires at least: 7.0
 */

defined( 'ABSPATH' ) || exit;

define( 'WAM_VERSION',     '0.1.0' );
define( 'WAM_DIR',         plugin_dir_path( __FILE__ ) );
define( 'WAM_URL',         plugin_dir_url( __FILE__ ) );
define( 'WAM_BASENAME',    plugin_basename( __FILE__ ) );
define( 'WAM_UPGRADE_URL', 'PLACEHOLDER_UPGRADE_URL' );

// ── Core includes ─────────────────────────────────────────────────────────────
require_once WAM_DIR . 'includes/wc-data.php';
require_once WAM_DIR . 'includes/ai-client.php';
require_once WAM_DIR . 'admin/settings-page.php';
require_once WAM_DIR . 'admin/chat-panel.php';
require_once WAM_DIR . 'admin/dashboard-widget.php';

// ── Boot ──────────────────────────────────────────────────────────────────────
add_action( 'plugins_loaded', 'wam_init' );

function wam_init() {
    if ( ! class_exists( 'WooCommerce' ) ) {
        add_action( 'admin_notices', function () {
            echo '<div class="notice notice-error"><p><strong>Woo AI Manager</strong> requires WooCommerce to be active.</p></div>';
        } );
        return;
    }

    // Register admin menus
    add_action( 'admin_menu', 'wam_register_menus' );

    // Enqueue assets
    add_action( 'admin_enqueue_scripts', 'wam_enqueue_assets' );

    // Dashboard widget
    add_action( 'wp_dashboard_setup', 'wam_register_dashboard_widget' );

    // AJAX handlers
    add_action( 'wp_ajax_wam_chat',           'wam_ajax_chat' );
    add_action( 'wp_ajax_wam_google_signin',  'wam_ajax_google_signin' );
    add_action( 'wp_ajax_wam_register_store', 'wam_ajax_register_store' );
}

// ── Menus ─────────────────────────────────────────────────────────────────────
function wam_register_menus() {
    // Top-level menu: "AI Manager"
    add_menu_page(
        'AI Store Manager',
        'AI Manager',
        'manage_woocommerce',
        'wam-chat',
        'wam_render_chat_panel',
        'dashicons-superhero-alt',
        56
    );

    // Settings sub-page
    add_submenu_page(
        'wam-chat',
        'AI Manager Settings',
        'Settings',
        'manage_options',
        'wam-settings',
        'wam_render_settings_page'
    );
}

// ── Assets ────────────────────────────────────────────────────────────────────
function wam_enqueue_assets( $hook ) {
    // Only load on our own pages
    if ( strpos( $hook, 'wam-' ) === false && $hook !== 'index.php' ) {
        return;
    }

    wp_enqueue_style(
        'wam-admin',
        WAM_URL . 'admin/wam-admin.css',
        [],
        WAM_VERSION
    );

    wp_enqueue_script(
        'wam-chat',
        WAM_URL . 'admin/wam-chat.js',
        [],
        WAM_VERSION,
        true  // footer
    );

    // Pass data to JS
    wp_localize_script( 'wam-chat', 'wamData', [
        'ajaxUrl'        => admin_url( 'admin-ajax.php' ),
        'adminUrl'       => admin_url(),
        'nonce'          => wp_create_nonce( 'wam_chat' ),
        'upgradeUrl'     => WAM_UPGRADE_URL,
        'version'        => WAM_VERSION,
        // Direct-to-backend mode (used when WC credentials are registered)
        'backendUrl'     => rtrim( get_option( 'wam_backend_url', WAM_DEFAULT_BACKEND ), '/' ),
        'merchantEmail'  => get_option( 'wam_merchant_email', '' ),
        'sessionToken'   => get_option( 'wam_session_token', '' ),
        'storeConnected' => (bool) get_option( 'wam_store_connected', false ),
    ] );
}

// ── AJAX: Google sign-in ──────────────────────────────────────────────────────
function wam_ajax_google_signin() {
    check_ajax_referer( 'wam_google_signin', 'nonce' );

    if ( ! current_user_can( 'manage_options' ) ) {
        wp_send_json_error( [ 'message' => 'Unauthorised.' ], 403 );
    }

    $google_token = isset( $_POST['google_token'] ) ? sanitize_text_field( wp_unslash( $_POST['google_token'] ) ) : '';
    if ( ! $google_token ) {
        wp_send_json_error( [ 'message' => 'Missing Google token.' ], 400 );
    }

    $result = wam_plugin_signin( $google_token );

    if ( is_wp_error( $result ) ) {
        wp_send_json_error( [ 'message' => $result->get_error_message() ], 401 );
    }

    wp_send_json_success( $result );
}

// ── AJAX: register store ──────────────────────────────────────────────────────
function wam_ajax_register_store() {
    check_ajax_referer( 'wam_register_store', 'nonce' );

    if ( ! current_user_can( 'manage_options' ) ) {
        wp_send_json_error( [ 'message' => 'Unauthorised.' ], 403 );
    }

    $consumer_key    = isset( $_POST['consumer_key'] )    ? sanitize_text_field( wp_unslash( $_POST['consumer_key'] ) )    : '';
    $consumer_secret = isset( $_POST['consumer_secret'] ) ? sanitize_text_field( wp_unslash( $_POST['consumer_secret'] ) ) : '';

    if ( ! $consumer_key || ! $consumer_secret ) {
        wp_send_json_error( [ 'message' => 'Both Consumer Key and Consumer Secret are required.' ], 400 );
    }

    $result = wam_register_store( $consumer_key, $consumer_secret );

    if ( is_wp_error( $result ) ) {
        wp_send_json_error( [ 'message' => $result->get_error_message() ], 400 );
    }

    wp_send_json_success( $result );
}

// ── AJAX: chat ────────────────────────────────────────────────────────────────
function wam_ajax_chat() {
    check_ajax_referer( 'wam_chat', 'nonce' );

    if ( ! current_user_can( 'manage_woocommerce' ) ) {
        wp_send_json_error( [ 'message' => 'Unauthorised.' ], 403 );
    }

    $message = isset( $_POST['message'] ) ? sanitize_text_field( wp_unslash( $_POST['message'] ) ) : '';
    if ( ! $message ) {
        wp_send_json_error( [ 'message' => 'Empty message.' ], 400 );
    }

    // Fetch live store context to give the AI real data
    $store_context = wam_get_store_context();

    $result = wam_chat( $message, $store_context );

    if ( is_wp_error( $result ) ) {
        $code = $result->get_error_code() === 'wam_no_credits' ? 402 : 500;
        wp_send_json_error( [ 'message' => $result->get_error_message() ], $code );
    }

    wp_send_json_success( [
        'reply'             => $result['reply'],
        'credits_remaining' => $result['credits_remaining'],
    ] );
}
