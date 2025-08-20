# backend/femseek_api/asgi.py
import os
import django
from django.core.asgi import get_asgi_application

# Set the settings module before anything else
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'femseek_api.settings')

# This is the crucial line that fixes the AppRegistryNotReady error
django.setup()

# Now it's safe to import other parts of the application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import translator.routing

# get_asgi_application() should be called after setup
http_application = get_asgi_application()

application = ProtocolTypeRouter({
    "http": http_application,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            translator.routing.websocket_urlpatterns
        )
    ),
})
