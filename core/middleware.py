import jwt
from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.utils.deprecation import MiddlewareMixin

class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to authenticate users using JWT tokens passed either in the
    'Authorization' header as a Bearer token or in a 'gigsure_token' cookie.
    """
    def process_request(self, request):
        token = None

        # 1. Check Authorization Header
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        # 2. Check Cookie Fallback
        if not token:
            token = request.COOKIES.get('gigsure_token')

        if token:
            try:
                # Decode the JWT token using Django's SECRET_KEY
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user_id = payload.get('user_id')
                if user_id:
                    user = User.objects.get(id=user_id)
                    request.user = user
                    # Store session variables for template role-gating compatibility
                    request.session['role'] = payload.get('role', 'beneficiary')
                    request.session['company'] = payload.get('company', '')
                    return None
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
                # Token expired, invalid, or user does not exist.
                # Force anonymous user representation for stateless enforcement.
                request.user = AnonymousUser()
        
        # If no JWT token is provided, do not override request.user,
        # allowing local session auth to act as a fallback in dev.
        return None
