"""
Custom JWT token views for cookie-based authentication
"""
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthThrottle(AnonRateThrottle):
    """Rate limit for auth endpoints"""
    scope = 'auth'


def set_jwt_cookies(response, access_token, refresh_token=None):
    """
    Helper to set JWT cookies in response
    """
    access_cookie = settings.SIMPLE_JWT.get('AUTH_COOKIE')
    access_expiration = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME').total_seconds()
    cookie_secure = settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', True)
    cookie_httponly = settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True)
    cookie_samesite = settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
    cookie_domain = settings.SIMPLE_JWT.get('AUTH_COOKIE_DOMAIN')
    cookie_path = settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/')
    
    # Set access token
    response.set_cookie(
        access_cookie,
        access_token,
        max_age=access_expiration,
        secure=cookie_secure,
        httponly=cookie_httponly,
        samesite=cookie_samesite,
        domain=cookie_domain,
        path=cookie_path
    )
    
    # Set refresh token if provided
    if refresh_token:
        refresh_cookie = settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH')
        refresh_expiration = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME').total_seconds()
        
        response.set_cookie(
            refresh_cookie,
            refresh_token,
            max_age=refresh_expiration,
            secure=cookie_secure,
            httponly=cookie_httponly,
            samesite=cookie_samesite,
            domain=cookie_domain,
            path=cookie_path
        )
    
    return response


class CookieTokenObtainPairView(TokenObtainPairView):
    """
    Custom view for obtaining JWT pair and setting in cookies
    instead of returning in response body
    """
    throttle_classes = [AuthThrottle]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        data = serializer.validated_data
        response = Response(
            {"detail": "Login successful", "user": request.user.username}, 
            status=status.HTTP_200_OK
        )
        
        # Set cookies
        return set_jwt_cookies(
            response=response,
            access_token=data["access"],
            refresh_token=data["refresh"]
        )


class CookieTokenRefreshView(TokenRefreshView):
    """
    Custom view for refreshing tokens from cookie
    """
    throttle_classes = [AuthThrottle]
    
    def extract_refresh_token(self):
        refresh_token = self.request.COOKIES.get(
            settings.SIMPLE_JWT.get('AUTH_COOKIE_REFRESH')
        )
        return {"refresh": refresh_token}
    
    def post(self, request, *args, **kwargs):
        # Get token from cookie, not request body
        refresh_token_data = self.extract_refresh_token()
        
        if not refresh_token_data.get('refresh'):
            return Response(
                {"detail": "No valid refresh token found in cookies"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = TokenRefreshSerializer(data=refresh_token_data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response(
                {"detail": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        data = serializer.validated_data
        response = Response(
            {"detail": "Token refreshed successfully"},
            status=status.HTTP_200_OK
        )
        
        # Set only access token cookie (keep existing refresh token)
        return set_jwt_cookies(
            response=response,
            access_token=data["access"]
        )
