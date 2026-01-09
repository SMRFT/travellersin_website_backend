from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Customer, Admin

class MultiModelJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        """
        Custom logic to fetch user from either Customer or Admin tables
        based on the user_type claim in the token.
        """
        user_id = validated_token.get('user_id')
        user_type = validated_token.get('user_type')

        if not user_id or not user_type:
            return None

        if user_type == 'customer':
            try:
                return Customer.objects.get(id=user_id)
            except Customer.DoesNotExist:
                return None
        elif user_type == 'admin':
            try:
                return Admin.objects.get(id=user_id)
            except Admin.DoesNotExist:
                return None
        
        return None
