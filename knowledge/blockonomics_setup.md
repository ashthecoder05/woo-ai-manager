# Blockonomics Setup — Official Documentation

## Account Setup (First Steps)
1. Have a Bitcoin wallet ready before starting (Electrum is recommended for beginners)
2. Register at blockonomics.co
3. Go to Dashboard > Wallets > Add a BTC wallet (you need your wallet's xPub key)
4. Go to Dashboard > Stores > create a store, paste your Callback URL, enable Bitcoin
5. Get your API Key from Dashboard > Stores — this is your "Blockonomics password"
6. Run "Test Setup" — green checkmarks = everything is working

**xPub key**: A special code from your wallet that lets Blockonomics generate payment addresses without being able to spend your money. Think of it like giving someone your address book but not your house keys.

**Callback URL**: The address Blockonomics sends a message to when a payment arrives. Like giving someone your phone number so they can call you when a package is delivered.

---

## WooCommerce (WordPress) Integration

### Easy way (recommended):
1. WordPress Dashboard > Plugins > Add New > search "WordPress Bitcoin Payments - Blockonomics" > Install & Activate
2. Follow the setup banner — enter your API Key, name your store
3. Run "Test Setup" in WooCommerce > Settings > Payments > Blockonomics

### Manual way:
1. Copy API Key from Blockonomics Dashboard > Stores
2. Paste into WooCommerce > Settings > Payments > Blockonomics Bitcoin
3. Add your wallet in Blockonomics Dashboard > Wallets (need wallet name, xPub key, sample address)
4. Copy the Callback URL from WordPress and paste it into your Blockonomics store settings
5. Run "Test Setup"

**Common issues:**
- Orders not updating: your web host is blocking Blockonomics notifications — ask host to whitelist Blockonomics IPs
- No JavaScript checkout: enable "No JavaScript checkout page" in Advanced settings (needed for Tor browser users)

---

## PrestaShop Integration

1. Create Blockonomics account, add a Bitcoin wallet (need xPub key)
2. Download the plugin ZIP from GitHub — do NOT extract it
3. Upload the ZIP via PrestaShop admin > Modules
4. Copy API Key from Blockonomics Dashboard > Stores, paste into plugin settings
5. Test: add item to cart, check out, copy the Bitcoin address shown, test it in Blockonomics Logs

**Common issues:**
| Problem | Fix |
|---|---|
| Bitcoin icon missing at checkout | Enable Blockonomics in Carrier restrictions |
| Orders not marked paid | Web host blocking payment notifications |
| Customer overpaid/underpaid | Exchange fees reduced the amount — use "Underpayment Slack" setting |

---

## WHMCS Integration

1. Add BTC wallet in Blockonomics Dashboard
2. Download plugin from WHMCS Marketplace
3. Upload the `modules` folder via FTP to `/modules/gateways/blockonomics/` (set permissions to 755)
4. Activate via WHMCS: Add-ons > Apps and Integrations > search Blockonomics
5. Paste API Key from Blockonomics Dashboard > Stores
6. Run "Test Setup" — checkmarks per currency confirm success

**Common issues:**
- "Test Setup" stuck: check file permissions are set to 755 and the JSON file is publicly accessible
- Unpaid orders: DDoS protection blocking Blockonomics — whitelist their callback IPs

---

## Invoice Ninja Integration

1. Invoice Ninja: Settings > Payment Settings > Add Payment Gateway > click "Setup" on Blockonomics
2. Enter API Key from Blockonomics Dashboard > Stores
3. Settings tab: enable "Crypto"
4. Add wallet (wallet name, xPub key, sample receiving address)
5. Create a store in Blockonomics > copy the Invoice Ninja webhook URL > paste as Callback URL > enable Bitcoin > link wallet
6. Run Health Check

---

## Telegram Bot Integration

1. Create Blockonomics account, add Bitcoin wallet
2. Install the "Greed" Telegram bot (from GitHub)
3. Get a bot token from BotFather in Telegram using `/newbot`
4. In config.toml: add your API Key and a secret (any random string you make up)
5. Create a store in Blockonomics Dashboard, set Callback URL to include your secret
6. Start the bot: `python -OO core.py`
7. Test with `/start` in Telegram

---

## Common Rules Across ALL Integrations

- API Key always comes from: Blockonomics Dashboard > Stores
- The most common reason payments don't update: your web host is blocking Blockonomics notifications
- Always run "Test Setup" after configuring — green checkmark = working
- For USDT payments: need MetaMask wallet, use Sepolia testnet for testing
- Electrum wallet is the easiest for beginners who need an xPub key
