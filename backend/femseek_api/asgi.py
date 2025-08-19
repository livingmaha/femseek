# backend/femseek_api/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack # Ensure this is imported
import translator.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'femseek_api.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack( # Correctly wraps the URLRouter for authentication
        URLRouter(
            translator.routing.websocket_urlpatterns
        )
    ),
})
