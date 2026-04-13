<?php
/**
 * dashboard-widget.php — Quick insight card on the WP dashboard home.
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
    $today = wam_revenue_period( 'today' );
    $week  = wam_revenue_period( '7days' );
    $low   = wam_low_stock_products( 3 );
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
                <strong>Low stock:</strong>
                <ul>
                    <?php foreach ( $low as $p ) : ?>
                        <li>
                            <a href="<?php echo esc_url( get_edit_post_link( $p['id'] ) ); ?>">
                                <?php echo esc_html( $p['name'] ); ?>
                            </a>
                            — <?php echo (int) $p['stock']; ?> left
                        </li>
                    <?php endforeach; ?>
                </ul>
            </div>
        <?php endif; ?>

        <p class="wam-widget-cta">
            <a href="<?php echo esc_url( admin_url( 'admin.php?page=wam-chat' ) ); ?>" class="button button-primary">
                Open AI Manager
            </a>
        </p>
    </div>
    <?php
}
