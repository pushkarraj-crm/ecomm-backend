# Free testing deployment

Create the Render web service from render.yaml, using the Free plan. Connect a free Neon PostgreSQL project and free Cloudinary account. Required private environment variables are DATABASE_URL (Neon SSL connection URI), CLOUDINARY_URL, and a fresh SECRET_KEY of at least 50 characters. Never commit real credentials. Render supplies RENDER_EXTERNAL_HOSTNAME and PORT.

Only the hosted service uses DJANGO_SETTINGS_MODULE=core.settings_hosted. Existing local settings, Docker deployment and SQLite data are unchanged. WhiteNoise serves collected static files. Cloudinary persists product images; KYC documents use authenticated raw uploads with short-lived signed download links rather than public image delivery. A single Gunicorn process is used so the process-local test cache/throttles remain consistent without an additional paid Redis service.

Set NEXT_PUBLIC_API_BASE_URL and VITE_API_BASE_URL in their respective Vercel projects to the public Render URL plus /api, then redeploy both. The two production frontend origins are allowlisted. Add specific future domains to CORS_ALLOWED_ORIGINS and, for browser-session Django admin use, CSRF_TRUSTED_ORIGINS.

The Render start command applies migrations before starting Gunicorn. Free services do not provide a separate paid pre-deploy job. The remote database starts empty; local SQLite records and uploaded files are not transferred automatically. Seed only demo records for testing, never upload private local customer/KYC data without an explicit migration request.

Razorpay and email are optional integrations requiring their own provider settings. Keep payments in provider test mode during testing. Render free instances can sleep after inactivity; the first request may need a retry while the service wakes.
