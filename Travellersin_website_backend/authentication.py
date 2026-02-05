from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from .models import Admin, Customer

class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_type = validated_token.get('user_type')
            user_id = validated_token.get('user_id')

            if user_type == 'admin':
                user = Admin.objects.get(id=user_id)
            elif user_type == 'customer':
                user = Customer.objects.get(id=user_id)
            else:
                # Fallback or strict failure
                # If no user_type is present, maybe it's a legacy token or unrelated?
                raise AuthenticationFailed('Token missing user_type claim', code='user_not_found')

            if not user.is_active if hasattr(user, 'is_active') else True:
                 raise AuthenticationFailed('User is inactive', code='user_inactive')

            return user

        except (Admin.DoesNotExist, Customer.DoesNotExist):
            raise AuthenticationFailed('User not found', code='user_not_found')
        except Exception as e:
            raise AuthenticationFailed(str(e), code='authentication_failed')
