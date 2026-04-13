<?php
/**
 * Plugin Name: Woo AI Manager
 * Plugin URI:  https://github.com/your-repo/woo-ai-manager
 * Description: AI store manager that lives inside your WP Admin — knows your orders, customers, and revenue, and tells you what to do next.
 * Version:     0.1.0
 * Author:      Your Name
 * License:     GPL-2.0-or-later
 * Text Domain: woo-ai-manager
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * WC requires at least: 7.0
 */

defined( 'ABSPATH' ) || exit;

define( 'WAM_VERSION',  '0.1.0' );
define( 'WAM_DIR',      plugin_dir_path( __FILE__ ) );
define( 'WAM_URL',      plugin_dir_url( __FILE__ ) );
define( 'WAM_BASENAME', plugin_basename( __FILE__ ) );

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

    // AJAX handlers for the chat panel
    add_action( 'wp_ajax_wam_chat', 'wam_ajax_chat' );
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
        'ajaxUrl' => admin_url( 'admin-ajax.php' ),
        'nonce'   => wp_create_nonce( 'wam_chat' ),
        'version' => WAM_VERSION,
    ] );
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

    $reply = wam_chat( $message, $store_context );

    if ( is_wp_error( $reply ) ) {
        wp_send_json_error( [ 'message' => $reply->get_error_message() ], 500 );
    }

    wp_send_json_success( [ 'reply' => $reply ] );
}
