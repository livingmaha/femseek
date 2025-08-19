# views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User
from .serializers import UserSerializer

class UserSignupView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Handle case where user already exists but re-submits
        if 'email' in serializer.errors and 'already exists' in str(serializer.errors['email']):
            user = User.objects.get(email=request.data['email'])
            return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# serializers.py
from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['name', 'email', 'usage_purpose']

# urls.py
from django.urls import path
from .views import UserSignupView

urlpatterns = [
    path('signup/', UserSignupView.as_view(), name='signup'),
]
