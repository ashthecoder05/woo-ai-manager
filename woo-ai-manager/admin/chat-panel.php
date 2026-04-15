<?php
/**
 * chat-panel.php — Main WP Admin chat UI.
 *
 * @package Woo_AI_Manager
 * @version 0.1.0
 */

defined( 'ABSPATH' ) || exit;

function wam_render_chat_panel() {
    if ( ! current_user_can( 'manage_woocommerce' ) ) {
        return;
    }

    $email        = get_option( 'wam_merchant_email', '' );
    $name         = get_option( 'wam_merchant_name', '' );
    $token        = get_option( 'wam_session_token', '' );
    $credits      = (int) get_option( 'wam_credits_remaining', 0 );
    $is_connected = $email && $token;
    $can_chat     = $is_connected && $credits > 0;
    $settings_url = admin_url( 'admin.php?page=wam-settings' );
    ?>
    <div class="wrap" id="wam-chat-wrap">
        <h1>AI Store Manager</h1>

        <?php if ( ! $is_connected ) : ?>

            <!-- ── Not connected ──────────────────────────────────────── -->
            <div class="wam-setup-card">
                <div class="wam-setup-icon">🤖</div>
                <h2>Set up your AI store manager</h2>
                <p>Sign in with Google to get <strong>50 free AI queries</strong>. Takes 30 seconds — no API key, no credit card.</p>
                <a href="<?php echo esc_url( $settings_url ); ?>" class="button button-primary button-large">
                    Go to Settings to get started →
                </a>
            </div>

        <?php elseif ( $credits === 0 ) : ?>

            <!-- ── Out of credits ─────────────────────────────────────── -->
            <div class="wam-upgrade-card">
                <h2>You've used all 50 free queries</h2>
                <p>Upgrade to keep your AI store manager running — unlimited queries, priority support, and proactive alerts coming soon.</p>
                <a href="<?php echo esc_url( WAM_UPGRADE_URL ); ?>" class="button button-primary button-large" target="_blank" rel="noopener">
                    Upgrade now →
                </a>
                <p style="margin-top:12px;font-size:12px;color:#666;">
                    Signed in as <?php echo esc_html( $name ?: $email ); ?> &nbsp;·&nbsp;
                    <a href="<?php echo esc_url( $settings_url ); ?>">Settings</a>
                </p>
            </div>

        <?php else : ?>

            <!-- ── Chat UI ────────────────────────────────────────────── -->
            <div id="wam-chat-container">

                <!-- Header bar -->
                <div id="wam-chat-header">
                    <span>Ask anything about your store</span>
                    <span id="wam-credits-display" class="<?php echo $credits <= 10 ? 'wam-credits-low' : ''; ?>">
                        <?php echo $credits; ?> queries left
                    </span>
                </div>

                <!-- Quick-action buttons -->
                <div id="wam-quick-actions">
                    <button class="wam-quick-btn" data-msg="Summarise this week's sales for me.">This week's summary</button>
                    <button class="wam-quick-btn" data-msg="Which orders are stuck or need attention right now?">Stuck orders</button>
                    <button class="wam-quick-btn" data-msg="What are my top selling products this month?">Top products</button>
                    <button class="wam-quick-btn" data-msg="Do I have any low stock products I should reorder?">Low stock alerts</button>
                </div>

                <!-- Message history -->
                <div id="wam-messages" role="log" aria-live="polite"></div>

                <!-- Input area -->
                <div id="wam-input-area">
                    <textarea
                        id="wam-input"
                        rows="2"
                        placeholder="Ask anything about your store… (Enter to send, Shift+Enter for new line)"
                    ></textarea>
                    <button id="wam-send">Send</button>
                </div>

            </div><!-- #wam-chat-container -->

            <p style="margin-top:8px;font-size:12px;color:#888;">
                Signed in as <?php echo esc_html( $name ?: $email ); ?> &nbsp;·&nbsp;
                <a href="<?php echo esc_url( $settings_url ); ?>">Settings</a>
            </p>

        <?php endif; ?>
    </div>
    <?php
}
