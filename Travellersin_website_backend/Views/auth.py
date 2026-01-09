from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from ..models import Customer, Admin
from ..serializers import CustomerSerializer, AdminSerializer

def get_tokens_for_user(user, user_type):
    refresh = RefreshToken.for_user(user)
    # Custom claims to identify user type and ID
    refresh['user_type'] = user_type
    # Numeric PK for system compatibility
    refresh['user_id'] = user.id
    # String ID for display/profile
    refresh['custom_id'] = getattr(user, f"{user_type}_id")
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_signup(request):
    """
    Register a new customer
    """
    serializer = CustomerSerializer(data=request.data)
    if serializer.is_valid():
        customer = serializer.save()
        tokens = get_tokens_for_user(customer, "customer")
        return Response({
            "user": CustomerSerializer(customer).data,
            "tokens": tokens
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_login(request):
    """
    Authenticate a customer using phone and password
    """
    phone = request.data.get("phone")
    password = request.data.get("password")

    if not phone or not password:
        return Response({"error": "Phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        customer = Customer.objects.get(phone=phone)
        if customer.check_password(password):
            tokens = get_tokens_for_user(customer, "customer")
            return Response({
                "user": CustomerSerializer(customer).data,
                "tokens": tokens
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    except Customer.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    Authenticate an admin using phone and password
    """
    phone = request.data.get("phone")
    password = request.data.get("password")

    if not phone or not password:
        return Response({"error": "Phone and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Djongo SQL parsing fix: Filter by phone first then check is_active in python
        # or use a raw-compatible filter.
        admin = Admin.objects.filter(phone=phone).first()
        if admin and admin.is_active:
            if admin.check_password(password):
                tokens = get_tokens_for_user(admin, "admin")
                return Response({
                    "user": AdminSerializer(admin).data,
                    "tokens": tokens
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid credentials or account inactive"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # If admin not found or inactive, we reach here
        return Response({"error": "Admin not found or inactive"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_user_profile(request):
    """
    Get current logged in user profile based on JWT token content
    """
    user_id = request.auth.get('custom_id')
    user_type = request.auth.get('user_type')

    if user_type == 'customer':
        try:
            user = Customer.objects.get(customer_id=user_id)
            return Response(CustomerSerializer(user).data)
        except Customer.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
    elif user_type == 'admin':
        try:
            user = Admin.objects.get(admin_id=user_id)
            return Response(AdminSerializer(user).data)
        except Admin.DoesNotExist:
            return Response({"error": "Admin not found"}, status=404)
    
    return Response({"error": "Invalid user type"}, status=400)
