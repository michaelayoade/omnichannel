"""
Custom authentication classes for JWT cookie-based authentication
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.conf import settings
from rest_framework.authentication import CSRFCheck


class JWTCookieAuthentication(JWTAuthentication):
    """
    Custom authentication class that extends JWTAuthentication
    to read JWT tokens from cookies instead of Authorization header.
    """
    
    def authenticate(self, request):
        # Try to authenticate by cookie
        cookie_name = settings.SIMPLE_JWT.get('AUTH_COOKIE')
        raw_token = request.COOKIES.get(cookie_name)
        
        # Fall back to Authorization header if no cookie
        if not raw_token:
            return super().authenticate(request)
            
        validated_token = self.get_validated_token(raw_token)
        
        # Enforce CSRF check for cookie-based auth on unsafe methods
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            self.enforce_csrf(request)
            
        return self.get_user(validated_token), validated_token
        
    def enforce_csrf(self, request):
        """
        Enforce CSRF validation for cookie-based auth
        """
        check = CSRFCheck(request)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise AuthenticationFailed('CSRF Failed: %s' % reason)
