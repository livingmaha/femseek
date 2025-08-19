from django.urls import path
from .consumers import TranslateConsumer

websocket_urlpatterns = [
    path("ws/translate/", TranslateConsumer.as_asgi()),
]
