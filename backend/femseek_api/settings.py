# backend/femseek_api/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url # Add this import
import base64 # Added for Google Cloud credentials
import json # Added for Google Cloud credentials

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# --- Application definition (no changes here) ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'corsheaders',
    'users',
    'translator',
]

# --- Middleware (no changes here) ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Add Whitenoise for static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware', # Ensure this is placed high
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsfRMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'femseek_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'femseek_api.wsgi.application'
ASGI_APPLICATION = 'femseek_api.asgi.application'


# --- Database ---
# Use dj-database-url for PostgreSQL on Render
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'), # Render provides this env var
        conn_max_age=600
    )
}

# Password validation (no changes)
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization (no changes)
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# Render requires configuring static files properly for deployment
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles' # Collect static files here
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage' # Use Whitenoise storage

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels settings for In-Memory Layer (No Redis)
# !!! WARNING: This is NOT suitable for multi-process/multi-server deployments
# !!! Render often scales to multiple instances, which will break WebSocket communication
# !!! unless you manually ensure only one instance is running for WebSockets.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    },
}

# CORS Headers settings
CORS_ALLOW_ALL_ORIGINS = True # Be more restrictive in production by specifying origins
# CORS_ALLOWED_ORIGINS = [
#     "https://your-frontend-vercel-url.vercel.app", # Add your Vercel frontend URL here
#     "http://localhost:3000", # For local development
# ]

# Make sure your Google Cloud credentials environment variable is set
# This is read automatically by the Google Cloud libraries
# Handle Google Cloud Credentials
# For Render deployment, decode the base64-encoded JSON key
google_credentials_base64 = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64')
if google_credentials_base64:
    try:
        decoded_credentials = base64.b64decode(google_credentials_base64).decode('utf-8')
        credentials_path = BASE_DIR / 'google-credentials.json'
        with open(credentials_path, 'w') as f:
            f.write(decoded_credentials)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)
        print("Google Cloud credentials loaded from environment variable.")
    except Exception as e:
        print(f"Error decoding Google Cloud credentials: {e}")
        # Fallback or raise error if critical
else:
    # For local development or if using a direct file path
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is set in your local .env or system
    if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print("Google Cloud credentials path found in environment variable.")
    else:
        print("Warning: GOOGLE_APPLICATION_CREDENTIALS not found. Google Cloud APIs might fail.")

# Make Paystack secret key available
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
