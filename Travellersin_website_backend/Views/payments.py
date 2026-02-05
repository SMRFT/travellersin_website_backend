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
    Record Payment Transaction (Simplified Flow)
    Skipping Signature Verification as per request.
    """
    razorpay_payment_id = request.data.get("razorpay_payment_id")
    # razorpay_order_id = request.data.get("razorpay_order_id") # Not used in this flow
    # razorpay_signature = request.data.get("razorpay_signature") # Not used in this flow
    razorpay_payment_id = request.data.get("razorpay_payment_id")
    booking_id = request.data.get("booking_id")

    print(f"DEBUG Verify Payment Data: {request.data}")

    if not razorpay_payment_id or not booking_id:
         return Response({"error": "Missing payment_id or booking_id"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Custom Transaction ID Generation (REF_TIMESTAMP_RANDOM)
        import time
        import uuid
        t_str = str(int(time.time() * 1000))
        r_str = uuid.uuid4().hex[:8].upper()
        generated_transaction_id = f"REF_{t_str}_{r_str}"
        billing_id = f"BILL_{t_str}_{r_str}"

        # Update booking status
        try:
            booking = Booking.objects.get(booking_id=booking_id)

            # Calculate Amounts
            try:
                current_total = float(booking.payment_details.get("amount", 0))
                previously_paid = float(booking.payment_details.get("amount_paid", 0))
            except:
                current_total = 0
                previously_paid = 0
            
            transaction_amount = current_total - previously_paid 
            if transaction_amount < 0: transaction_amount = 0 

            new_amount_paid = previously_paid + transaction_amount
            payment_status = "paid" if new_amount_paid >= current_total else "partially_paid"

            # Update Billing Numbers List
            billing_numbers = booking.payment_details.get("billing_numbers", [])
            billing_numbers.append(billing_id)

            # Update Payment Details JSON structure
            booking.payment_details.update({
                 "amount_paid": new_amount_paid,
                 "status": payment_status,
                 "method": "razorpay",
                 "billing_numbers": billing_numbers,
                 "latest_billing_no": billing_id,
                 "transaction_id": generated_transaction_id
            })
            
            booking.booking_status = "confirmed"
            booking.save()
            
            # Create Billing Record
            from ..models import Billing
            
            Billing.objects.create(
                booking=booking,
                billing_no=billing_id, 
                amount_paid=transaction_amount,
                total_amount=current_total,
                payment_type="razorpay",
                status="success",
                
                # New Fields
                transaction_id=generated_transaction_id,
                payment_gateway_ref_id=razorpay_payment_id,
                
                razorpay_payment_id=razorpay_payment_id
            )
            
            # Send WhatsApp Confirmation
            send_booking_confirmation(booking)
            
            return Response({"message": "Payment recorded and booking confirmed", "booking": BookingSerializer(booking).data}, status=status.HTTP_200_OK)
            
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": "Payment recording failed"}, status=status.HTTP_400_BAD_REQUEST)

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
        
        # Create Billing Record for Cash
        from ..models import Billing
        import time
        import uuid
        t_str = str(int(time.time() * 1000))
        r_str = uuid.uuid4().hex[:8].upper()
        billing_id = f"REF_{t_str}_{r_str}"

        Billing.objects.create(
            booking=booking,
            billing_no=billing_id,
            amount_paid=0, # Paid 0 initially for Pay at Hotel
            total_amount=booking.payment_details.get("amount", 0),
            payment_type="cash"
        )
        
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
