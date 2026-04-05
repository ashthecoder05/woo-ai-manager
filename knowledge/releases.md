# Blockonomics Plugin Releases

## WordPress / WooCommerce Plugin

### v3.9.1 (Latest)
- **Fix:** Callbacks could pick up an older order instead of the most recent one for the same address
- **Improvement:** Much better logging built in
- **How to update:** WP Dashboard → Plugins → Update available next to Blockonomics
- **If issues after update:** WooCommerce → Status → Logs → select blockonomics log file

### v3.9.0
- Added support for USDT ERC-20 payments
- Improved gap limit handling

### v3.8.5
- Fixed: Payment page not loading on some WooCommerce themes
- Fixed: Duplicate order creation on page refresh

---

## PrestaShop Plugin

### v2.1.0 (Latest)
- Added USDT support
- Fixed: Bitcoin icon missing at checkout on some themes
- Fixed: Order status not updating when DDoS protection is active

---

## WHMCS Plugin

### v2.0.2 (Latest)
- Fixed: File permission issues causing Test Setup to fail
- Improved: Error messages now show exact cause
- Requires: File permissions set to 755

---

## How the assistant should use this:
When a merchant describes an issue, check if any recent release addresses it.
If yes, proactively tell them:
1. The version number and what it fixes
2. How to update (specific steps for their platform)
3. What to do if the problem persists after updating (e.g., share logs)

Always mention the update in a friendly, helpful way — like a colleague who just spotted a fix.
