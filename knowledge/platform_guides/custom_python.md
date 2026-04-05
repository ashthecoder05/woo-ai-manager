# Blockonomics on Custom Python (Flask / FastAPI / Django)

## Requirements
- Python 3.8+
- `httpx` or `requests` library
- Public HTTPS endpoint for webhooks (use ngrok for local dev)
- Blockonomics API key

## Installation
```bash
pip install httpx python-dotenv
```

## Generate a Payment Address
```python
import httpx

API_KEY = "your_api_key"

def new_btc_address() -> str:
    resp = httpx.post(
        "https://www.blockonomics.co/api/new_address",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"reset": 0},
    )
    resp.raise_for_status()
    return resp.json()["address"]
```

## Convert Order Amount to BTC
```python
def get_btc_price_usd() -> float:
    resp = httpx.get("https://www.blockonomics.co/api/price?currency=USD")
    return resp.json()["price"]

def usd_to_satoshis(usd_amount: float) -> int:
    price = get_btc_price_usd()
    btc = usd_amount / price
    return int(btc * 1e8)
```

## FastAPI Webhook Handler
```python
from fastapi import APIRouter, Query

router = APIRouter()
WEBHOOK_SECRET = "your_webhook_secret"

@router.get("/webhook/blockonomics")
def blockonomics_webhook(
    secret: str = Query(...),
    addr: str = Query(...),
    value: int = Query(...),
    txid: str = Query(...),
    status: int = Query(...),
):
    if secret != WEBHOOK_SECRET:
        return {"error": "invalid secret"}, 403

    # status: 0=unconfirmed, 1=partial, 2=confirmed
    if status >= 2:
        # fulfill_order(addr, value)
        pass

    return {"ok": True}
```

## Django Webhook Handler
```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def blockonomics_webhook(request):
    secret = request.GET.get("secret")
    if secret != settings.BLOCKONOMICS_SECRET:
        return JsonResponse({"error": "forbidden"}, status=403)

    addr = request.GET.get("addr")
    value = int(request.GET.get("value", 0))
    status = int(request.GET.get("status", -1))

    if status >= 2:
        # process confirmed payment
        pass

    return JsonResponse({"ok": True})
```

## Local Development with ngrok
```bash
ngrok http 8000
# Copy the https URL, e.g. https://abc123.ngrok.io
# Set your Blockonomics callback to: https://abc123.ngrok.io/webhook/blockonomics?secret=YOUR_SECRET
```
