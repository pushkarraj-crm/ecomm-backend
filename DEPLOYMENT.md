# Backend deployment

The included Docker Compose stack runs PostgreSQL, password-protected Redis,
two Django/Gunicorn instances, and an Nginx load balancer. Both app instances
share the database, cache/rate-limit store, static files, and uploaded files.

## Configure secrets

Keep `.env` private and out of source control. Set a unique `SECRET_KEY`,
`POSTGRES_PASSWORD`, and `REDIS_PASSWORD`, plus production `ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS`, Razorpay, and email values before deployment. The
project `.env` is excluded from both Git and the Docker build context.
For refund status updates, set `RAZORPAY_WEBHOOK_SECRET` and configure the
Razorpay webhook URL as `https://<your-domain>/api/orders/razorpay/webhook/`.
Subscribe to `refund.created`, `refund.processed`, and `refund.failed`.

## Start the stack

```powershell
docker compose up --build -d
```

Compose waits for PostgreSQL and Redis health checks, applies migrations and
collects static files once, then starts both API instances and Nginx. The API
is available at `http://localhost:8080` by default; `/health/` is the basic
process health endpoint. Change `HTTP_PORT` to select another host port.
The PostgreSQL volume starts as a separate database; records in the local
`db.sqlite3` file are not copied into it automatically.

Nginx balances API traffic with least-connections routing and serves static
files and product images. KYC uploads are deliberately not exposed by Nginx.
The Compose Nginx listener uses HTTP on the configured host port. Put it behind
a TLS ingress or add TLS certificates to Nginx before exposing it publicly.
Set `TRUST_PROXY_SSL=True` only when the trusted proxy overwrites
`X-Forwarded-Proto`; adjust `TRUSTED_PROXY_COUNT` for the actual proxy chain.

For a DigitalOcean regional Load Balancer in front of this stack, use
`HTTP_PORT=80`, `TRUSTED_PROXY_COUNT=2`, and `TRUST_PROXY_SSL=True`. Configure
HTTPS port 443 on the Load Balancer to forward HTTP to port 80, use `/health/`
for its health check, and restrict Droplet port 80 to traffic from that Load
Balancer. The second trusted proxy is the Compose Nginx hop.

For local development without Docker, leave `REDIS_URL` blank; Django uses a
process-local cache. That fallback does not share cache or rate-limit state
between server processes, so use Redis in multi-instance deployments.

Product listing stays backward compatible when called without query
parameters. Use `GET /api/products/?page=1&page_size=24` to retrieve a bounded
page. Product catalog data is cached for `PRODUCT_CACHE_TTL_SECONDS`.
