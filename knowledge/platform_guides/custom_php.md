# Blockonomics on Custom PHP

## Requirements
- PHP 7.4+
- `curl` extension enabled
- Public HTTPS server
- Blockonomics API key

## Generate a Payment Address
```php
<?php
function blockonomics_new_address(string $api_key): string {
    $ch = curl_init('https://www.blockonomics.co/api/new_address');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode(['reset' => 0]),
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $api_key,
            'Content-Type: application/json',
        ],
        CURLOPT_RETURNTRANSFER => true,
    ]);
    $response = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return $response['address'];
}
```

## Get BTC Price
```php
function blockonomics_get_price(string $currency = 'USD'): float {
    $url = 'https://www.blockonomics.co/api/price?currency=' . urlencode($currency);
    $data = json_decode(file_get_contents($url), true);
    return (float) $data['price'];
}
```

## Webhook Handler (webhook.php)
```php
<?php
define('WEBHOOK_SECRET', 'your_secret_here');

$secret = $_GET['secret'] ?? '';
if ($secret !== WEBHOOK_SECRET) {
    http_response_code(403);
    echo json_encode(['error' => 'forbidden']);
    exit;
}

$addr   = $_GET['addr']   ?? '';
$value  = (int)($_GET['value']  ?? 0);
$txid   = $_GET['txid']   ?? '';
$status = (int)($_GET['status'] ?? -1);

// Log the event
file_put_contents(
    __DIR__ . '/webhook_log.txt',
    date('c') . " addr=$addr value=$value txid=$txid status=$status\n",
    FILE_APPEND
);

if ($status >= 2) {
    // Payment confirmed — fulfill order
    fulfill_order($addr, $value);
}

echo json_encode(['ok' => true]);

function fulfill_order(string $addr, int $satoshis): void {
    // Your fulfillment logic here
}
```

## .htaccess for Clean URLs (Apache)
```apache
RewriteEngine On
RewriteRule ^webhook/blockonomics$ webhook.php [L,QSA]
```
