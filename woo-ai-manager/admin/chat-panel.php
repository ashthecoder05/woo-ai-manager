<?php
/**
 * chat-panel.php — The main WP Admin chat UI.
 */

defined( 'ABSPATH' ) || exit;

function wam_render_chat_panel() {
    if ( ! current_user_can( 'manage_woocommerce' ) ) {
        return;
    }
    ?>
    <div class="wrap" id="wam-chat-wrap">
        <h1>AI Store Manager</h1>

        <?php
        $email    = get_option( 'wam_merchant_email', '' );
        $token    = get_option( 'wam_session_token', '' );
        $credits  = (int) get_option( 'wam_credits_remaining', 0 );
        $has_key  = $email && $token;
        ?>
        <?php if ( ! $has_key ) : ?>
            <div class="notice notice-warning">
                <p>
                    To get started, <a href="<?php echo esc_url( admin_url( 'admin.php?page=wam-settings' ) ); ?>">connect your account</a> in Settings — it only takes your email, no API key needed.
                </p>
            </div>
        <?php else : ?>
            <p style="margin-bottom:8px;color:#666;font-size:12px;">
                Signed in as <strong><?php echo esc_html( $email ); ?></strong>
                &nbsp;|&nbsp;
                <span id="wam-credits"><?php echo $credits; ?> queries left</span>
                &nbsp;|&nbsp;
                <a href="<?php echo esc_url( admin_url( 'admin.php?page=wam-settings' ) ); ?>">Settings</a>
            </p>
        <?php endif; ?>

        <div id="wam-chat-container">

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
                    <?php echo $has_key ? '' : 'disabled'; ?>
                ></textarea>
                <button id="wam-send" <?php echo $has_key ? '' : 'disabled'; ?>>Send</button>
            </div>

        </div><!-- #wam-chat-container -->
    </div>
    <?php
}
