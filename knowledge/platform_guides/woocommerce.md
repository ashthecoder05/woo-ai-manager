# Blockonomics on WooCommerce

## Requirements
- WordPress 5.0+
- WooCommerce 4.0+
- PHP 7.4+
- SSL certificate (HTTPS)
- A Bitcoin wallet with xpub exported

## Installation
1. In WordPress admin: **Plugins → Add New → Search "Blockonomics Bitcoin"**
2. Install and activate the plugin
3. Go to **WooCommerce → Settings → Payments → Blockonomics**
4. Enter your **API Key** from https://www.blockonomics.co/merchants
5. Click **Test Setup** — all checks should pass
6. Save settings

## xpub Setup
1. In Blockonomics dashboard → **Wallets** → Add wallet
2. Export xpub from your wallet (Electrum: Wallet → Information → Master Public Key)
3. Paste xpub and set your callback URL to: `https://yoursite.com/?wc-api=WC_Blockonomics`

## Testing
- Place a test order and select Bitcoin at checkout
- A payment page with a QR code and address will appear
- Confirm the address is fresh (not reused from a previous order)

## Common Issues
- **"Test Setup Failed"**: API key wrong or xpub not saved in Blockonomics dashboard
- **Webhook not received**: Check that WooCommerce permalinks are set to "Post name" (Settings → Permalinks)
- **Gap limit error**: Increase gap limit in Blockonomics dashboard to 100

## Code Snippet — Manual Payment Status Check (PHP)
```php
$order_id = 123;
$order = wc_get_order($order_id);
$btc_address = $order->get_meta('blockonomics_bitcoin_address');
// Use the Blockonomics API to check balance on this address
```
