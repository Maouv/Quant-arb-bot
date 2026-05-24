# Secret Management

## Prinsip
- Secret **tidak** disimpan di dalam project directory
- Secret **tidak** di-load otomatis via `.bashrc`
- Load eksplisit per-run — lebih aman dan terkontrol

## Lokasi
```
~/.secrets/quant-arb-bot/.env
```

## Format File
```env
# PRODUCTION
BINANCE_REST_URL=https://fapi.binance.com
BINANCE_API_KEY=your-live-api-key
BINANCE_API_SECRET=your-live-api-secret

# TESTNET
BINANCE_TESTNET_URL=https://testnet.binancefuture.com
BINANCE_TESTNET_KEY=your-testnet-key
BINANCE_TESTNET_SECRET=your-testnet-secret
```

## Setup
```bash
mkdir -p ~/.secrets/quant-arb-bot
cp .env.example ~/.secrets/quant-arb-bot/.env
# isi nilai asli, lalu:
chmod 600 ~/.secrets/quant-arb-bot/.env
```

## Load di Python
```python
from dotenv import load_dotenv
import os

load_dotenv(os.path.expanduser("~/.secrets/quant-arb-bot/.env"))
```

## Load via Shell
```bash
set -a; source ~/.secrets/quant-arb-bot/.env; set +a
python main.py
```
