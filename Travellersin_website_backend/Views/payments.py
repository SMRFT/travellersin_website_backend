import os
import razorpay
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from ..models import Booking
from ..serializers import BookingSerializer
from .whatsapp import send_booking_confirmation

# Initialize Razorpay Client
client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))

@api_view(['POST'])
@permission_classes([AllowAny]) # Change to IsAuthenticated if you want to restrict
def create_razorpay_order(request):
    """
    Create a Razorpay Order
    """
    amount = request.data.get("amount")
    currency = "INR"

    if not amount:
        return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Razorpay expects amount in paise (1 INR = 100 paise)
    data = {
        "amount": int(float(amount) * 100),
        "currency": currency,
        "payment_capture": 1 # Auto capture payment
    }

    try:
        order = client.order.create(data=data)
        return Response(order, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_payment(request):
    """
    Verify Razorpay Payment Signature and link to Booking
    """
    razorpay_order_id = request.data.get("razorpay_order_id")
    razorpay_payment_id = request.data.get("razorpay_payment_id")
    razorpay_signature = request.data.get("razorpay_signature")
    booking_id = request.data.get("booking_id")

    # Verify signature
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        client.utility.verify_payment_signature(params_dict)
        
        # Update booking status
        try:
            booking = Booking.objects.get(booking_id=booking_id)
            booking.razorpay_payment_id = razorpay_payment_id
            booking.razorpay_signature = razorpay_signature
            booking.razorpay_order_id = razorpay_order_id
            booking.booking_status = "confirmed"
            booking.payment_details["method"] = "razorpay"
            booking.payment_details["status"] = "paid"
            booking.save()
            
            # Send WhatsApp Confirmation
            send_booking_confirmation(booking)
            
            return Response({"message": "Payment verified and booking confirmed", "booking": BookingSerializer(booking).data}, status=status.HTTP_200_OK)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({"error": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_cash_booking(request):
    """
    Confirm a booking with Cash (Pay at Hotel) method
    """
    booking_id = request.data.get("booking_id")

    try:
        booking = Booking.objects.get(booking_id=booking_id)
        booking.booking_status = "confirmed" # or "pending_approval" based on requirements
        booking.payment_details["method"] = "cash"
        booking.payment_details["status"] = "unpaid" # to be paid at hotel
        booking.save()
        
        # Send WhatsApp Confirmation
        send_booking_confirmation(booking)
        
        return Response({"message": "Booking confirmed with Cash payment", "booking": BookingSerializer(booking).data}, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_booking_payment(request, booking_id):
    """
    Initiate Razorpay order for an existing booking (e.g., from Track Stay or Profile)
    """
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        amount = booking.payment_details.get("amount")

        if not amount:
            return Response({"error": "Booking amount not found"}, status=status.HTTP_400_BAD_REQUEST)

        # Create Razorpay Order
        data = {
            "amount": int(float(amount) * 100),
            "currency": "INR",
            "payment_capture": 1
        }
        
        order = client.order.create(data=data)
        return Response({
            "order": order,
            "booking": BookingSerializer(booking).data
        }, status=status.HTTP_200_OK)

    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
