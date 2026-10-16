"""Render settings. Local development continues to use core.settings."""
from .settings import *
import dj_database_url

DEBUG = False
if not os.getenv('DATABASE_URL'):
    raise ImproperlyConfigured('Set DATABASE_URL to the hosted PostgreSQL connection string.')
if not os.getenv('CLOUDINARY_URL'):
    raise ImproperlyConfigured('Set CLOUDINARY_URL for persistent uploaded-file storage.')
DATABASES = {'default': dj_database_url.config(conn_max_age=0, conn_health_checks=True, ssl_require=True)}
if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Hosted deployment requires PostgreSQL.')
render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)
CORS_ALLOWED_ORIGINS = [value.strip() for value in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if value.strip()]
CORS_ALLOW_ALL_ORIGINS = False
CSRF_TRUSTED_ORIGINS = [value.strip() for value in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if value.strip()]
if render_host:
    CSRF_TRUSTED_ORIGINS.append('https://' + render_host)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
MIDDLEWARE = [*MIDDLEWARE]
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
INSTALLED_APPS = [*INSTALLED_APPS, 'cloudinary_storage']
STORAGES = {
    'default': {'BACKEND': 'core.hosted_storage.HostedMediaStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
CLOUDINARY_STORAGE = {'SECURE': True, 'MEDIA_TAG': 'd2c-marketplace-testing'}
