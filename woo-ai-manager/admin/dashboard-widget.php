<?php
/**
 * dashboard-widget.php — Revenue snapshot + low stock on WP dashboard home.
 *
 * @package Woo_AI_Manager
 * @version 0.1.0
 */

defined( 'ABSPATH' ) || exit;

function wam_register_dashboard_widget() {
    if ( ! current_user_can( 'manage_woocommerce' ) ) {
        return;
    }
    wp_add_dashboard_widget(
        'wam_dashboard_widget',
        'AI Store Manager',
        'wam_render_dashboard_widget'
    );
}

function wam_render_dashboard_widget() {
    $today   = wam_revenue_period( 'today' );
    $week    = wam_revenue_period( '7days' );
    $low     = wam_low_stock_products( 3 );
    $credits = (int) get_option( 'wam_credits_remaining', 0 );
    $email   = get_option( 'wam_merchant_email', '' );
    $token   = get_option( 'wam_session_token', '' );
    $connected = $email && $token;
    ?>
    <div class="wam-widget">

        <div class="wam-widget-stats">
            <div class="wam-stat">
                <span class="wam-stat-label">Today</span>
                <span class="wam-stat-value">$<?php echo number_format( $today['revenue'], 2 ); ?></span>
                <span class="wam-stat-sub"><?php echo (int) $today['count']; ?> orders</span>
            </div>
            <div class="wam-stat">
                <span class="wam-stat-label">Last 7 days</span>
                <span class="wam-stat-value">$<?php echo number_format( $week['revenue'], 2 ); ?></span>
                <span class="wam-stat-sub"><?php echo (int) $week['count']; ?> orders</span>
            </div>
        </div>

        <?php if ( ! empty( $low ) ) : ?>
            <div class="wam-widget-alerts">
                <strong>⚠ Low stock:</strong>
                <ul>
                    <?php foreach ( $low as $p ) : ?>
                        <li>
                            <a href="<?php echo esc_url( get_edit_post_link( $p['id'] ) ); ?>">
                                <?php echo esc_html( $p['name'] ); ?>
                            </a>
                            — <?php echo $p['stock'] === 0 ? '<strong style="color:#cc1818;">Out of stock</strong>' : (int) $p['stock'] . ' left'; ?>
                        </li>
                    <?php endforeach; ?>
                </ul>
            </div>
        <?php endif; ?>

        <?php if ( ! $connected ) : ?>
            <p class="wam-widget-cta">
                <a href="<?php echo esc_url( admin_url( 'admin.php?page=wam-settings' ) ); ?>" class="button button-primary">
                    Set up AI Manager (free)
                </a>
            </p>
        <?php elseif ( $credits === 0 ) : ?>
            <p class="wam-widget-notice wam-widget-notice--error">
                No queries left. <a href="<?php echo esc_url( WAM_UPGRADE_URL ); ?>" target="_blank" rel="noopener"><strong>Upgrade →</strong></a>
            </p>
        <?php elseif ( $credits <= 10 ) : ?>
            <p class="wam-widget-notice wam-widget-notice--warning">
                <?php echo $credits; ?> queries left.
                <a href="<?php echo esc_url( WAM_UPGRADE_URL ); ?>" target="_blank" rel="noopener">Upgrade for unlimited →</a>
            </p>
            <p class="wam-widget-cta">
                <a href="<?php echo esc_url( admin_url( 'admin.php?page=wam-chat' ) ); ?>" class="button button-primary">Open AI Manager</a>
            </p>
        <?php else : ?>
            <p class="wam-widget-cta">
                <a href="<?php echo esc_url( admin_url( 'admin.php?page=wam-chat' ) ); ?>" class="button button-primary">Open AI Manager</a>
                <span style="font-size:11px;color:#888;margin-left:8px;"><?php echo $credits; ?> queries left</span>
            </p>
        <?php endif; ?>

    </div>
    <?php
}
