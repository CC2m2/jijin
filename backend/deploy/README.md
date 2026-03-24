# Server Deploy (systemd + nginx)

This directory provides a practical baseline for running backend API as a resident server service.

## Files

- `.env.example`: Runtime environment variables template.
- `jijin-backend.service.example`: systemd unit template.
- `install-systemd.sh`: Helper script to install and restart systemd service.
- `nginx-jijin-api.conf.example`: nginx reverse-proxy template for `/api/*`.

## Deployment Layout

- Backend root: `/opt/jijin/backend`
- venv: `/opt/jijin/backend/.venv`
- env file: `/opt/jijin/backend/.env`
- systemd unit: `/etc/systemd/system/jijin-backend.service`
- nginx site conf: `/etc/nginx/sites-available/jijin-api.conf`

## Step 1: Prepare Backend Runtime

1. Sync project code to server path:

```bash
sudo mkdir -p /opt/jijin
sudo chown -R "$USER":"$USER" /opt/jijin
cd /opt/jijin
# clone or rsync repository here
```

1. Create python env and install deps:

```bash
cd /opt/jijin/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## Step 2: Configure Environment Variables

1. Copy template and edit token:

```bash
cd /opt/jijin/backend
cp deploy/.env.example .env
vi .env
```

1. Required values:

- `API_V1_PREFIX=/api/v1`
- `FUND_DATA_TIMEOUT_SECONDS=6`
- `OPENCLAW_TOKEN=<strong-random-token>`

## Step 3: Install systemd Service

1. Install using helper script:

```bash
cd /opt/jijin/backend
chmod +x deploy/install-systemd.sh
./deploy/install-systemd.sh
```

1. Manual equivalent (if needed):

```bash
sudo cp /opt/jijin/backend/deploy/jijin-backend.service.example /etc/systemd/system/jijin-backend.service
sudo systemctl daemon-reload
sudo systemctl enable jijin-backend
sudo systemctl restart jijin-backend
```

## Step 4: Configure nginx Reverse Proxy

1. Install nginx (if missing):

```bash
sudo apt-get update
sudo apt-get install -y nginx
```

1. Install nginx site config:

```bash
sudo cp /opt/jijin/backend/deploy/nginx-jijin-api.conf.example /etc/nginx/sites-available/jijin-api.conf
sudo ln -sf /etc/nginx/sites-available/jijin-api.conf /etc/nginx/sites-enabled/jijin-api.conf
sudo nginx -t
sudo systemctl restart nginx
```

1. Optional: remove default site to avoid conflicts:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## Step 5: Verify Service

1. Verify local backend:

```bash
sudo systemctl status jijin-backend --no-pager
curl http://127.0.0.1:8000/api/v1/openclaw/health
```

1. Verify nginx proxy:

```bash
curl http://127.0.0.1/api/v1/openclaw/health
```

1. Verify token-protected tool endpoint:

```bash
curl -X POST http://127.0.0.1/api/v1/openclaw/tools/portfolio_valuation \
  -H "Content-Type: application/json" \
  -H "X-OpenClaw-Token: <your-token>" \
  -d '{"refresh":false}'
```

## Operations

1. Restart backend:

```bash
sudo systemctl restart jijin-backend
```

1. View backend logs:

```bash
sudo journalctl -u jijin-backend -n 200 --no-pager
```

1. Follow backend logs:

```bash
sudo journalctl -u jijin-backend -f
```

## Troubleshooting

1. If service fails to start:

- Check `WorkingDirectory` and `ExecStart` path in `jijin-backend.service`.
- Confirm `.env` exists and contains `OPENCLAW_TOKEN`.
- Confirm venv python exists at `/opt/jijin/backend/.venv/bin/python`.

1. If API returns 401:

- Verify request header `X-OpenClaw-Token` exactly matches `.env` token.
- Restart service after updating `.env`.

1. If upstream data timeouts occur frequently:

- Increase `FUND_DATA_TIMEOUT_SECONDS` (for example from `6` to `10`).
- Check server outbound network and DNS.

## Security Notes

- Keep backend bound to `127.0.0.1`.
- Expose only nginx externally.
- Do not log or commit token values.
