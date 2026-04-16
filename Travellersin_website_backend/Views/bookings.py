from rest_framework.decorators import api_view
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from Travellersin_website_backend.models import Booking
from Travellersin_website_backend.serializers import BookingSerializer

@api_view(["GET", "POST"])
def bookings_list_create(request):
    if request.method == "GET":
        customer_id = request.query_params.get("customer_id")
        if customer_id:
            bookings = Booking.objects.filter(customer_id=customer_id).order_by("-created_at")
        else:
            bookings = Booking.objects.all().order_by("-created_at")
            
        # Date Filter
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if start_date_str and end_date_str:
            try:
                from datetime import datetime
                # Parse YYYY-MM-DD
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                
                # Make end_date include the whole day (23:59:59)
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                
                bookings = bookings.filter(created_at__range=[start_dt, end_dt])
            except Exception as e:
                print(f"Date filter error: {e}")
                
        return Response(BookingSerializer(bookings, many=True).data)

    if request.method == "POST":
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            booking = serializer.save()
            
            # If initial payment was recorded, create a Billing record
            payment_details = booking.payment_details or {}
            amount_paid = float(payment_details.get("amount_paid", 0))
            
            if amount_paid > 0:
                from django.utils import timezone
                import time
                import uuid
                from ..models import Billing
                
                t_str = str(int(time.time() * 1000))
                r_str = uuid.uuid4().hex[:8].upper()
                billing_no = f"REF_{t_str}_{r_str}"
                
                p_type = payment_details.get("payment_type") or payment_details.get("method") or "cash"
                t_id = payment_details.get("transaction_id") or payment_details.get("latest_transaction_id")
                
                try:
                    Billing.objects.create(
                        billing_no=billing_no,
                        booking=booking,
                        amount_paid=amount_paid,
                        total_amount=float(payment_details.get("amount", 0)),
                        payment_type=p_type,
                        transaction_id=t_id
                    )
                    
                    # Update billing_numbers in booking
                    if "billing_numbers" not in payment_details:
                        payment_details["billing_numbers"] = []
                    payment_details["billing_numbers"].append(billing_no)
                    payment_details["latest_billing_no"] = billing_no
                    booking.payment_details = payment_details
                    booking.save()
                except Exception as e:
                    print(f"Error creating initial billing record: {e}")
            
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH"])
def booking_detail_update(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    if request.method == "GET":
        return Response(BookingSerializer(booking).data)

    if request.method == "PATCH":
        serializer = BookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
@api_view(["GET"])
def track_booking(request):
    booking_id = request.query_params.get("booking_id")
    phone = request.query_params.get("phone")

    if not booking_id or not phone:
        return Response({"error": "Both Booking ID and Phone number are required"}, status=400)

    try:
        # Search by booking_id and guest_phone
        booking = Booking.objects.get(booking_id=booking_id, guest_phone=phone)
        return Response(BookingSerializer(booking).data)
    except Booking.DoesNotExist:
        return Response({"error": "No booking found with these details"}, status=404)
@api_view(["POST"])
def cancel_booking(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    # Policy: Within 24 hours of booking creation
    if timezone.now() > booking.created_at + timedelta(hours=24):
        return Response({"error": "Cancellation window (24h from booking) has expired"}, status=400)

    reason = request.data.get("reason", "Cancelled by guest")
    booking.booking_status = "cancellation_requested"
    booking.cancellation_reason = reason
    booking.save()
    return Response({"message": "Cancellation request submitted for admin approval", "booking": BookingSerializer(booking).data})
