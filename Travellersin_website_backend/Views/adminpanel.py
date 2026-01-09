from rest_framework.decorators import api_view
from rest_framework.response import Response
from Travellersin_website_backend.models import Admin, Booking, Query, EventBooking
from Travellersin_website_backend.serializers import AdminSerializer, BookingSerializer, EventBookingSerializer
from .whatsapp import send_booking_confirmation

@api_view(["GET", "POST"])
def admin_list_create(request):
    """
    GET  -> List all active admins
    POST -> Create new admin
    """

    if request.method == "GET":
        admins = Admin.objects.filter(is_active=True)
        serializer = AdminSerializer(admins, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        serializer = AdminSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET", "PATCH"])
def admin_detail_update(request, admin_id):
    """
    GET   -> Get admin by admin_id
    PATCH -> Update admin details
    """
    try:
        admin = Admin.objects.get(admin_id=admin_id, is_active=True)
    except Admin.DoesNotExist:
        return Response(
            {"error": "Admin not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        serializer = AdminSerializer(admin)
        return Response(serializer.data)

    if request.method == "PATCH":
        serializer = AdminSerializer(
            admin,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

@api_view(["PATCH"])
def admin_soft_delete(request, admin_id):
    """
    PATCH -> Soft delete admin
    """
    try:
        admin = Admin.objects.get(admin_id=admin_id)
    except Admin.DoesNotExist:
        return Response(
            {"error": "Admin not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    admin.is_active = False
    admin.save()

    return Response(
        {"message": "Admin deactivated successfully"},
        status=status.HTTP_200_OK
    )

@api_view(["GET"])
def admin_dashboard(request):
    return Response({
        "total_bookings": Booking.objects.count(),
        "live_rooms": Rooms.objects.count(),
        "pending_queries": Query.objects.filter(status="open").count(),
        "active_events": EventBooking.objects.filter(status="pending").count()
    })

@api_view(["PATCH"])
def update_booking_status(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    # 1. Update Booking Status (Confirmed, Cancelled, etc.)
    status_val = request.data.get("booking_status", booking.booking_status)
    booking.booking_status = status_val
    
    if status_val == "cancelled":
        booking.cancellation_reason = request.data.get("cancellation_reason", "Cancelled by Admin")
    # 2. Handle Payment Details
    payment_details = booking.payment_details or {}
    # If it's an empty dict, initialize defaults
    if not payment_details:
        payment_details = {"amount": 0, "amount_paid": 0, "status": "pending", "method": "cash"}
    else:
        # Make a copy to ensure Django detects the change
        payment_details = dict(payment_details)

    # Update amount_paid if provided
    new_payment_amount = request.data.get("amount_paid")
    if new_payment_amount is not None:
        try:
            amount_to_add = float(new_payment_amount)
            current_paid = float(payment_details.get("amount_paid", 0))
            total_amount = float(payment_details.get("amount", 0))
            
            updated_paid = current_paid + amount_to_add
            payment_details["amount_paid"] = updated_paid
            
            # Auto-calculate status
            if updated_paid >= total_amount:
                payment_details["status"] = "paid"
            elif updated_paid > 0:
                payment_details["status"] = "partially_paid"
            else:
                payment_details["status"] = "pending"
                
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount_paid format"}, status=400)

    # Explicitly override status if provided
    manual_status = request.data.get("payment_status")
    if manual_status:
        payment_details["status"] = manual_status
    
    # Re-assign to the model field
    booking.payment_details = payment_details
    booking.save()

    # Trigger WhatsApp if confirmed
    if status_val == "confirmed":
        send_booking_confirmation(booking)

    return Response({"message": "Booking updated successfully", "booking": BookingSerializer(booking).data})

@api_view(["POST"])
def approve_cancellation(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        if booking.booking_status != "cancellation_requested":
            return Response({"error": "No cancellation request found for this booking"}, status=400)
        
        booking.booking_status = "cancelled"
        booking.save()
        return Response({"message": "Cancellation approved", "booking": BookingSerializer(booking).data})
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

@api_view(["POST"])
def reject_cancellation(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        if booking.booking_status != "cancellation_requested":
            return Response({"error": "No cancellation request found for this booking"}, status=400)
        
        # Default back to 'confirmed' if rejected
        booking.booking_status = "confirmed"
        booking.save()
        return Response({"message": "Cancellation request rejected", "booking": BookingSerializer(booking).data})
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)
@api_view(['PATCH'])
def update_event_booking_status(request, booking_id):
    try:
        booking = EventBooking.objects.get(booking_id=booking_id)
        new_status = request.data.get('status')
        if new_status:
            booking.status = new_status
            booking.save()
            return Response({"success": True, "status": booking.status})
        return Response({"error": "Status is required"}, status=status.HTTP_400_BAD_REQUEST)
    except EventBooking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
