import jwt
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from .models import Admin, Customer

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            raw_token = header

        # Convert raw_token bytes to string if needed
        if isinstance(raw_token, bytes):
            raw_token_str = raw_token.decode("utf-8")
        else:
            raw_token_str = str(raw_token)

        # 1. Try PyAuth / RS256 token decode first
        try:
            unverified_payload = jwt.decode(
                raw_token_str,
                options={"verify_signature": False, "verify_exp": False}
            )

            # Check if this is a PyAuth / Centralized SSO Token (contains aud, allowed-actions, or iss)
            if "aud" in unverified_payload or "allowed-actions" in unverified_payload or unverified_payload.get("iss") == "https://lab.shinova.in/":
                user = self.get_user(unverified_payload)
                return (user, unverified_payload)
        except Exception:
            pass

        # 2. Try Standard SimpleJWT HS256 validation
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except Exception:
            # If standard SimpleJWT fails, don't block the request if endpoint is AllowAny
            return None

    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given token payload,
        supporting both standard SimpleJWT claims and PyAuth payload claims.
        """
        try:
            user_type = validated_token.get('user_type')
            user_id = validated_token.get('user_id') or validated_token.get('aud')
            allowed_actions = validated_token.get('allowed-actions', [])

            # Detect admin/staff role from pyauth allowed-actions if user_type is not explicitly specified
            if not user_type and isinstance(allowed_actions, list):
                if any(act.startswith('TIN-R') or act.startswith('TI-R') or act.startswith('STR-R') or act.startswith('ST-R') for act in allowed_actions):
                    user_type = 'admin'

            if user_type == 'admin':
                try:
                    user = Admin.objects.get(admin_id=user_id)
                except Admin.DoesNotExist:
                    # Centralized SSO/PyAuth user: create lightweight mock object
                    user = Admin(
                        admin_id=str(user_id or "ADM001"),
                        name=validated_token.get("name", "Admin User"),
                        email=validated_token.get("email", "admin@travellersinn.com"),
                        phone=validated_token.get("phone", "0000000000"),
                        is_superadmin=validated_token.get("is_superadmin", True)
                    )
            elif user_type == 'customer':
                try:
                    user = Customer.objects.get(customer_id=user_id)
                except Customer.DoesNotExist:
                    user = Customer(
                        customer_id=str(user_id or "CUST001"),
                        name=validated_token.get("name", "Customer"),
                        email=validated_token.get("email", ""),
                        phone=validated_token.get("phone", "")
                    )
            else:
                # Try finding Admin first, then Customer
                try:
                    user = Admin.objects.get(admin_id=user_id)
                except Admin.DoesNotExist:
                    try:
                        user = Customer.objects.get(customer_id=user_id)
                    except Customer.DoesNotExist:
                        user = Admin(
                            admin_id=str(user_id or "ADM001"),
                            name=validated_token.get("name", "Admin User"),
                            email=validated_token.get("email", "admin@travellersinn.com"),
                            phone="0000000000",
                            is_superadmin=True
                        )

            if hasattr(user, 'is_active') and not user.is_active:
                raise AuthenticationFailed('User is inactive', code='user_inactive')

            return user

        except Exception as e:
            raise AuthenticationFailed(str(e), code='authentication_failed')
