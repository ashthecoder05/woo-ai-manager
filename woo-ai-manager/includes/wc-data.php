<?php
/**
 * wc-data.php — Pull live WooCommerce store data for AI context.
 *
 * Keeps queries small and focused so we never blow the context window.
 * The AI only receives data that is relevant to the current query.
 */

defined( 'ABSPATH' ) || exit;

/**
 * Build a compact store context snapshot for the AI.
 * Returns a plain-English + structured string.
 */
function wam_get_store_context(): string {
    $today     = wam_revenue_period( 'today' );
    $week      = wam_revenue_period( '7days' );
    $month     = wam_revenue_period( '30days' );
    $recent    = wam_recent_orders( 5 );
    $low_stock = wam_low_stock_products( 5 );
    $top       = wam_top_products( 5 );

    $lines = [];
    $lines[] = '## Live Store Snapshot';
    $lines[] = sprintf( 'Today\'s revenue: $%.2f (%d orders)', $today['revenue'], $today['count'] );
    $lines[] = sprintf( 'Last 7 days:     $%.2f (%d orders)', $week['revenue'], $week['count'] );
    $lines[] = sprintf( 'Last 30 days:    $%.2f (%d orders)', $month['revenue'], $month['count'] );

    if ( ! empty( $recent ) ) {
        $lines[] = "\n## Recent Orders";
        foreach ( $recent as $o ) {
            $lines[] = sprintf(
                '- #%s | %s | $%s | %s | %s',
                $o['id'], $o['customer'], $o['total'], $o['status'], $o['date']
            );
        }
    }

    if ( ! empty( $top ) ) {
        $lines[] = "\n## Top Products (last 30 days)";
        foreach ( $top as $p ) {
            $lines[] = sprintf( '- %s — %d sold — $%.2f revenue', $p['name'], $p['qty'], $p['revenue'] );
        }
    }

    if ( ! empty( $low_stock ) ) {
        $lines[] = "\n## Low / Out-of-Stock Products";
        foreach ( $low_stock as $p ) {
            $lines[] = sprintf( '- %s (ID %d): %d in stock', $p['name'], $p['id'], $p['stock'] );
        }
    }

    return implode( "\n", $lines );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function wam_revenue_period( string $period ): array {
    global $wpdb;

    $now = current_time( 'mysql' );
    if ( $period === 'today' ) {
        $since = current_time( 'Y-m-d' ) . ' 00:00:00';
    } elseif ( $period === '7days' ) {
        $since = date( 'Y-m-d 00:00:00', strtotime( '-7 days', current_time( 'timestamp' ) ) );
    } else {
        $since = date( 'Y-m-d 00:00:00', strtotime( '-30 days', current_time( 'timestamp' ) ) );
    }

    // Use the HPOS orders table if available, fall back to posts
    if ( wam_hpos_enabled() ) {
        $row = $wpdb->get_row( $wpdb->prepare(
            "SELECT COUNT(*) as cnt, SUM(total_amount) as rev
               FROM {$wpdb->prefix}wc_orders
              WHERE status IN ('wc-completed','wc-processing')
                AND date_created_gmt >= %s",
            $since
        ) );
    } else {
        $row = $wpdb->get_row( $wpdb->prepare(
            "SELECT COUNT(*) as cnt, SUM(pm.meta_value) as rev
               FROM {$wpdb->posts} p
               JOIN {$wpdb->postmeta} pm ON pm.post_id = p.ID AND pm.meta_key = '_order_total'
              WHERE p.post_type = 'shop_order'
                AND p.post_status IN ('wc-completed','wc-processing')
                AND p.post_date >= %s",
            $since
        ) );
    }

    return [
        'revenue' => round( (float) ( $row->rev ?? 0 ), 2 ),
        'count'   => (int) ( $row->cnt ?? 0 ),
    ];
}

function wam_recent_orders( int $limit = 5 ): array {
    $args = [
        'limit'   => $limit,
        'orderby' => 'date',
        'order'   => 'DESC',
        'status'  => [ 'completed', 'processing', 'on-hold', 'pending' ],
    ];
    $orders = wc_get_orders( $args );
    $result = [];
    foreach ( $orders as $order ) {
        $result[] = [
            'id'       => $order->get_id(),
            'customer' => trim( $order->get_billing_first_name() . ' ' . $order->get_billing_last_name() ) ?: $order->get_billing_email(),
            'total'    => $order->get_total(),
            'status'   => $order->get_status(),
            'date'     => $order->get_date_created() ? $order->get_date_created()->date( 'M j' ) : '—',
        ];
    }
    return $result;
}

function wam_low_stock_products( int $limit = 5 ): array {
    $threshold = (int) get_option( 'woocommerce_notify_low_stock_amount', 2 );
    $args = [
        'post_type'      => 'product',
        'posts_per_page' => $limit,
        'meta_query'     => [
            'relation' => 'AND',
            [
                'key'     => '_manage_stock',
                'value'   => 'yes',
            ],
            [
                'key'     => '_stock',
                'value'   => $threshold,
                'compare' => '<=',
                'type'    => 'NUMERIC',
            ],
        ],
    ];
    $query    = new WP_Query( $args );
    $result   = [];
    foreach ( $query->posts as $post ) {
        $product  = wc_get_product( $post->ID );
        $result[] = [
            'id'    => $post->ID,
            'name'  => $post->post_title,
            'stock' => (int) $product->get_stock_quantity(),
        ];
    }
    return $result;
}

function wam_top_products( int $limit = 5 ): array {
    global $wpdb;
    $since = date( 'Y-m-d', strtotime( '-30 days' ) );

    $rows = $wpdb->get_results( $wpdb->prepare(
        "SELECT oi.order_item_name AS name,
                SUM(oim_qty.meta_value) AS qty,
                SUM(oim_total.meta_value) AS revenue
           FROM {$wpdb->prefix}woocommerce_order_items oi
           JOIN {$wpdb->prefix}woocommerce_order_itemmeta oim_qty
             ON oim_qty.order_item_id = oi.order_item_id AND oim_qty.meta_key = '_qty'
           JOIN {$wpdb->prefix}woocommerce_order_itemmeta oim_total
             ON oim_total.order_item_id = oi.order_item_id AND oim_total.meta_key = '_line_total'
           JOIN {$wpdb->posts} p ON p.ID = oi.order_id
              AND p.post_type = 'shop_order'
              AND p.post_status IN ('wc-completed','wc-processing')
              AND p.post_date >= %s
          WHERE oi.order_item_type = 'line_item'
          GROUP BY oi.order_item_name
          ORDER BY qty DESC
          LIMIT %d",
        $since, $limit
    ) );

    $result = [];
    foreach ( $rows as $r ) {
        $result[] = [
            'name'    => $r->name,
            'qty'     => (int) $r->qty,
            'revenue' => round( (float) $r->revenue, 2 ),
        ];
    }
    return $result;
}

function wam_hpos_enabled(): bool {
    return class_exists( '\Automattic\WooCommerce\Utilities\OrderUtil' )
        && \Automattic\WooCommerce\Utilities\OrderUtil::custom_orders_table_usage_is_enabled();
}
