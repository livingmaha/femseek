# settings.py (additions)

INSTALLED_APPS = [
    # ... existing apps
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'corsheaders',
    'users',
    'translator',
]

MIDDLEWARE = [
    # ...
    'corsheaders.middleware.CorsMiddleware', # Should be placed high up
    'django.middleware.common.CommonMiddleware',
    # ...
]

# Allow requests from your Vercel frontend
CORS_ALLOWED_ORIGINS = [
    "https://your-vercel-frontend-url.com",
    "http://localhost:8080", # For local development
]

# Set Channels as the ASGI application
ASGI_APPLICATION = 'femseek_api.asgi.application'

# Configure the channel layer (using Redis for production is recommended)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer" # For development
        # For production, use Redis:
        # "BACKEND": "channels_redis.core.RedisChannelLayer",
        # "CONFIG": {
        #     "hosts": [("your-redis-host", 6379)],
        # },
    },
}

# --- Store these in environment variables ---
GOOGLE_APPLICATION_CREDENTIALS = "path/to/your/gcp-service-account.json"
PAYSTACK_SECRET_KEY = "YOUR_PAYSTACK_SECRET_KEY"
