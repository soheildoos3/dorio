# Dario Warranty React

Standalone public warranty/activation page. QR labels should point to:

`http://127.0.0.1:5174/warranty/<SERIAL>`

## Development

```bash
cp .env.example .env
npm install
npm run dev
```

The backend must allow the warranty app origin in `CORS_ORIGINS`. For LAN/mobile scanning, replace `127.0.0.1` with the server LAN IP or your production domain in both `.env` files and in the panel's Warranty settings.
