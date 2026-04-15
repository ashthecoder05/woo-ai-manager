=== Woo AI Manager ===
Contributors:       PLACEHOLDER_WP_USERNAME
Author:             Aishwarya Adyanthaya
Tags:               woocommerce, ai, store manager, analytics, chatbot
Requires at least:  6.0
Tested up to:       6.9
Requires PHP:       7.4
Stable tag:         0.1.0
License:            GPL-2.0-or-later
License URI:        https://www.gnu.org/licenses/gpl-2.0.html

The AI store manager that lives inside your WordPress admin — knows your orders, customers, and revenue, and tells you what to do next.

== Description ==

**Woo AI Manager** gives your WooCommerce store an AI assistant that actually knows your store data.

Ask it anything about your store:

* "Summarise this week's sales"
* "Which orders are stuck?"
* "What are my top products this month?"
* "Do I have anything running low on stock?"

It reads your live WooCommerce data — orders, revenue, products, stock — and answers in plain English. No exports, no dashboards to dig through.

= How it works =

1. Install the plugin
2. Sign in with Google (free — no API key, no credit card)
3. Get 50 free AI queries immediately
4. Open AI Manager from your WP Admin sidebar and start asking

= What you get for free =

* 50 AI queries — ask anything about your store
* Live revenue snapshot (today, 7 days, 30 days)
* Recent orders summary
* Top selling products
* Low stock alerts
* Dashboard widget with today's revenue

= Privacy =

Your store data (order totals, product names, stock levels) is sent to our servers to generate AI responses. We never store your customer names or emails beyond the current request. See our privacy policy at PLACEHOLDER_PRIVACY_URL.

== Installation ==

1. Upload the `woo-ai-manager` folder to `/wp-content/plugins/`
2. Activate the plugin through the **Plugins** menu in WordPress
3. Go to **AI Manager → Settings** and sign in with Google
4. Start asking questions from **AI Manager** in your sidebar

WooCommerce must be installed and active.

== Frequently Asked Questions ==

= Do I need an OpenAI or API key? =

No. You sign in with Google and use our managed AI service. Your first 50 queries are free with no credit card required.

= What store data does the AI see? =

Revenue totals, recent orders (customer name, total, status), top products, and low-stock items. It does not see customer emails, addresses, or payment details.

= What happens when I use all 50 free queries? =

You can upgrade to a paid plan at PLACEHOLDER_UPGRADE_URL to continue.

= Is my data secure? =

Yes. Communication between the plugin and our backend uses HTTPS. Your OpenAI key is never required — we handle all AI calls server-side.

= Does this work with WooCommerce HPOS? =

Yes — the plugin automatically detects whether your store uses High-Performance Order Storage (HPOS) or the legacy post-based order system.

== Screenshots ==

1. The AI Manager chat panel — ask questions about your store in plain English
2. The Settings page — sign in with Google, view remaining free queries
3. The dashboard widget — today's revenue and low stock alerts at a glance

== Changelog ==

= 0.1.0 =
* Initial release
* Google SSO sign-in with 50 free queries
* Live store context: revenue, orders, top products, low stock
* WP Admin chat panel with quick-action buttons
* Dashboard widget

== Upgrade Notice ==

= 0.1.0 =
Initial release.
