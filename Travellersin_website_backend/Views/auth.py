from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password
from ..models import Customer, Admin
from ..serializers import CustomerSerializer, AdminSerializer
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests
import os
import uuid

# Helper to generate tokens
def get_tokens_for_user(user, user_type='customer'):
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['user_type'] = user_type
    
    if user_type == 'admin':
        refresh['user_id'] = user.admin_id
        refresh['is_superadmin'] = user.is_superadmin
    else:
        refresh['user_id'] = user.customer_id

    access = refresh.access_token
    access['user_type'] = user_type
    
    if user_type == 'admin':
        access['user_id'] = user.admin_id
        access['is_superadmin'] = user.is_superadmin
    else:
        access['user_id'] = user.customer_id

    return {
        'refresh': str(refresh),
        'access': str(access),
    }

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_signup(request):
    serializer = CustomerSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        tokens = get_tokens_for_user(user, 'customer')
        return Response({
            'user': serializer.data,
            'tokens': tokens,
            'message': 'Signup successful'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def customer_login(request):
    phone = request.data.get('phone')
    password = request.data.get('password')

    if not phone or not password:
        return Response({'error': 'Please provide both phone and password'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = Customer.objects.get(phone=phone)
    except Customer.DoesNotExist:
        return Response({'error': 'Invalid phone or password'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.check_password(password):
        return Response({'error': 'Invalid phone or password'}, status=status.HTTP_401_UNAUTHORIZED)

    tokens = get_tokens_for_user(user, 'customer')
    serializer = CustomerSerializer(user)
    
    return Response({
        'user': serializer.data,
        'tokens': tokens,
        'message': 'Login successful'
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    phone = request.data.get('phone')
    password = request.data.get('password')

    if not phone or not password:
        return Response({'error': 'Please provide both phone and password'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = Admin.objects.get(phone=phone)
    except Admin.DoesNotExist:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.check_password(password):
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        
    if not user.is_active:
         return Response({'error': 'Account is inactive'}, status=status.HTTP_403_FORBIDDEN)

    tokens = get_tokens_for_user(user, 'admin')
    serializer = AdminSerializer(user)
    
    return Response({
        'user': serializer.data,
        'tokens': tokens,
        'message': 'Admin login successful'
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    user = request.user
    # request.user is determined by the authentication class
    # Check type of user instance to decide serializer
    if isinstance(user, Admin):
        serializer = AdminSerializer(user)
        user_type = 'admin'
    else:
        serializer = CustomerSerializer(user)
        user_type = 'customer'

    return Response({
        'user': serializer.data,
        'user_type': user_type
    })

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    user = request.user
    
    # We only allow Customer updates for now based on requirements, 
    # but let's support Admin too if needed or just check type.
    if isinstance(user, Admin):
        serializer = AdminSerializer(user, data=request.data, partial=True)
    else:
        # Prevent phone number duplication if phone is being changed
        new_phone = request.data.get('phone')
        if new_phone and new_phone != user.phone:
            if Customer.objects.filter(phone=new_phone).exists():
                return Response({'error': 'Phone number already registered with another account.'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CustomerSerializer(user, data=request.data, partial=True)

    if serializer.is_valid():
        # 🟢 FIX for Duplication: Use update() instead of save()
        # Because object.save() is creating new records due to pk=None issue with Djongo/MongoDB
        
        updated_data = serializer.validated_data
        
        if isinstance(user, Customer):
             Customer.objects.filter(customer_id=user.customer_id).update(**updated_data)
             # Re-fetch to return updated data
             user = Customer.objects.get(customer_id=user.customer_id)
             return Response({
                'user': CustomerSerializer(user).data,
                'message': 'Profile updated successfully'
            })
        
        # Admin Updates (if any)
        if isinstance(user, Admin):
             Admin.objects.filter(admin_id=user.admin_id).update(**updated_data)
             user = Admin.objects.get(admin_id=user.admin_id)
             return Response({
                'user': AdminSerializer(user).data,
                'message': 'Profile updated successfully'
            })

        # Fallback (should not reach here)
        serializer.save()
        return Response({
            'user': serializer.data,
            'message': 'Profile updated successfully'
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- Google OAuth ---

@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth(request):
    """
    Handles Google Login AND Signup.
    Expected Payload:
    - token: Google ID Token
    - phone: (Optional) Phone number. Required only for NEW users.
    """
    token = request.data.get('token')
    phone = request.data.get('phone')
    
    if not token:
        return Response({'error': 'Google token is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Verify the token
        # You should replace 'YOUR_GOOGLE_CLIENT_ID' with the actual client ID if verifying audience
        # logic: id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
        # For now, we will trust the token if we can decode it, but strictly you must verify audience.
        CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
        
        # Bypass SSL Verification for local dev env issues (SSLError)
        session = requests.Session()
        session.verify = False 
        transport = google_requests.Request(session)
        
        id_info = id_token.verify_oauth2_token(token, transport, CLIENT_ID)
        
        email = id_info.get('email')
        name = id_info.get('name')
        
        if not email:
            return Response({'error': 'Google token does not contain email'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        try:
            user = Customer.objects.get(email=email)
            # Login existing user
            tokens = get_tokens_for_user(user, 'customer')
            serializer = CustomerSerializer(user)
            return Response({
                'user': serializer.data,
                'tokens': tokens,
                'message': 'Login successful',
                'is_new_user': False
            }, status=status.HTTP_200_OK)
            
        except Customer.DoesNotExist:
            # New User Flow
            if not phone:
                # User needs to provide phone number
                return Response({
                    'message': 'User not registered. Phone number required.',
                    'email': email,
                    'name': name,
                    'is_new_user': True
                }, status=status.HTTP_202_ACCEPTED) # 202 Accepted: Processing continues, need more info
            
            # If phone is provided, create user
            # Check if phone is already taken
            if Customer.objects.filter(phone=phone).exists():
                 return Response({'error': 'Phone number already registered with another account.'}, status=status.HTTP_400_BAD_REQUEST)

            # Create new customer
            # Generate a random password since they use Google Auth
            random_password = str(uuid.uuid4())
            user = Customer.objects.create(
                name=name,
                email=email,
                phone=phone,
                password=random_password 
            )
            # Hash password isn't strictly needed here as we used create() not create_user (common in Django User) 
            # But our Customer model hashes in save(), so we are good.
            
            tokens = get_tokens_for_user(user, 'customer')
            serializer = CustomerSerializer(user)
             
            return Response({
                'user': serializer.data,
                'tokens': tokens,
                'message': 'Signup successful',
                'is_new_user': True
            }, status=status.HTTP_201_CREATED)

    except ValueError:
        return Response({'error': 'Invalid Google Token'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
