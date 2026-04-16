from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from Travellersin_website_backend.models import Admin, Booking, Query, EventBooking, Rooms, Billing
from Travellersin_website_backend.serializers import AdminSerializer, BookingSerializer, EventBookingSerializer, BillingSerializer
from .whatsapp import send_booking_confirmation, send_event_confirmation

@api_view(["GET", "POST"])
def admin_list_create(request):
    """
    GET  -> List all active admins
    POST -> Create new admin
    """

    if request.method == "GET":
        # Djongo fix: Filter in Python to avoid SQLDecodeError on boolean fields
        admins = [a for a in Admin.objects.all() if a.is_active]
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
        admin = Admin.objects.get(admin_id=admin_id)
        if not admin.is_active:
            raise Admin.DoesNotExist
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
        
        # DEBUG LOGging - Useful for the user to see in terminal
        print(f"Update Booking Request Body: {request.data}")

        # 1. Update Basic Fields
        status_val = request.data.get("booking_status", booking.booking_status)
        booking.booking_status = status_val
        if status_val == "cancelled":
            booking.cancellation_reason = request.data.get("cancellation_reason", "Cancelled by Admin")
        
        check_in = request.data.get("check_in")
        check_out = request.data.get("check_out")
        if check_in: booking.check_in = check_in
        if check_out: booking.check_out = check_out

        # 2. Handle Payment Details
        p_details = dict(booking.payment_details or {"amount": 0, "amount_paid": 0, "status": "pending", "method": "cash"})
        
        new_paid = request.data.get("amount_paid")
        
        # Extract payment fields - explicit None check so empty string != None
        _pt = request.data.get("payment_type") or request.data.get("method")
        p_type = _pt if _pt else None

        _tid = request.data.get("transaction_id")
        t_id = _tid if (_tid is not None and _tid != '') else None
            
        manual_p_status = request.data.get("payment_status")
        
        print(f"DEBUG EXTRACT: p_type={p_type!r}, t_id={t_id!r}, raw={request.data.get('transaction_id')!r}")

        if new_paid is not None:
            try:
                amt_to_add = float(new_paid)
                current_paid = float(p_details.get("amount_paid", 0))
                current_total = float(p_details.get("amount", 0))
                
                # Always increment from current DB value
                new_total_paid = current_paid + amt_to_add
                p_details["amount_paid"] = new_total_paid
                
                # Auto-calculate status (if not manually overridden)
                if not manual_p_status:
                    net_payable = current_total - float(booking.discount_amount or 0)
                    if float(p_details["amount_paid"]) >= net_payable:
                        p_details["status"] = "paid"
                    elif float(p_details["amount_paid"]) > 0:
                        p_details["status"] = "partially_paid"
                    else:
                        p_details["status"] = "pending"
                else:
                    p_details["status"] = manual_p_status

                # Record current method/transaction
                if p_type: 
                    p_details["method"] = p_type
                    p_details["payment_type"] = p_type
                if t_id is not None: 
                    p_details["transaction_id"] = t_id
                    p_details["latest_transaction_id"] = t_id

                # Create Billing Entry for this specific transaction
                import uuid
                import time
                from ..models import Billing
                t_str = str(int(time.time() * 1000))
                r_str = uuid.uuid4().hex[:8].upper()
                bill_no = f"REF_{t_str}_{r_str}"
                
                try:
                    print(f"CREATING BILLING: bill_no={bill_no}, amt={amt_to_add}, total={current_total}, ptype={p_type or p_details.get('method','cash')}, t_id={t_id!r}")
                    Billing.objects.create(
                        billing_no=bill_no,
                        booking=booking,
                        amount_paid=amt_to_add,
                        total_amount=current_total,
                        payment_type=p_type or p_details.get("method", "cash"),
                        transaction_id=t_id if t_id else None
                    )
                    
                    if "billing_numbers" not in p_details:
                        p_details["billing_numbers"] = []
                    if bill_no not in p_details["billing_numbers"]:
                        p_details["billing_numbers"].append(bill_no)
                    p_details["latest_billing_no"] = bill_no
                except Exception as b_err:
                    print(f"Billing record creation failed: {b_err}")

            except (ValueError, TypeError) as e:
                print(f"Amount calculation failed: {e}")

        # Apply finally
        booking.payment_details = p_details
        booking.save()

        # 3. WhatsApp Integration
        if booking.booking_status == "confirmed":
            send_booking_confirmation(booking)

        return Response({
            "message": "Booking updated successfully", 
            "booking": BookingSerializer(booking).data
        })

    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)
    except Exception as general_err:
        import traceback
        traceback.print_exc()
        return Response({"error": str(general_err)}, status=500)

import razorpay
import os

# Initialize Razorpay Client (Ensure keys are loaded from settings/env)
client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))

@api_view(["POST"])
def approve_cancellation(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        if booking.booking_status != "cancellation_requested":
            return Response({"error": "No cancellation request found for this booking"}, status=400)
        
        # Calculate Refund
        payment_details = booking.payment_details or {}
        amount_paid = float(payment_details.get("amount_paid", 0))
        refund_amount = 0
        fine_amount = 0
        
        if amount_paid > 0:
            # 15% Cancellation Fine
            fine_amount = amount_paid * 0.15
            refund_amount = amount_paid - fine_amount
            
            # Initiate Razorpay Refund if applicable
            rzp_payment_id = booking.razorpay_payment_id
            refund_id = None
            refund_status = "pending"
            
            if rzp_payment_id and payment_details.get("method") == "razorpay":
                try:
                    # Razorpay expects amount in paise
                    refund_data = {
                        "amount": int(refund_amount * 100),
                        "speed": "normal",
                        "notes": {
                            "booking_id": booking_id,
                            "reason": "Cancellation Refund (15% Fine Deducted)"
                        }
                    }
                    refund = client.payment.refund(rzp_payment_id, refund_data)
                    refund_id = refund.get("id")
                    refund_status = refund.get("status")
                    
                except Exception as e:
                    print(f"Razorpay Refund Failed: {e}")
                    refund_status = "failed"
            
            # Update Payment Details with Refund Info
            payment_details["refund_amount"] = refund_amount
            payment_details["cancellation_fine"] = fine_amount
            payment_details["refund_id"] = refund_id
            payment_details["refund_status"] = refund_status
            payment_details["status"] = "refunded" if refund_status == "processed" else "refund_pending"
            
            booking.payment_details = payment_details

        booking.booking_status = "cancelled"
        booking.save()
        
        return Response({
            "message": f"Cancellation approved. Refund initiated: ₹{refund_amount} (Fine: ₹{fine_amount})", 
            "booking": BookingSerializer(booking).data
        })
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
            old_status = booking.status
            booking.status = new_status
            booking.save()
            
            # If status changed to confirmed, send WhatsApp
            if new_status == 'confirmed' and old_status != 'confirmed':
                try:
                    send_event_confirmation(booking)
                except Exception as e:
                    print(f"WhatsApp notification failed: {e}")
                    
            return Response({"success": True, "status": booking.status})
        return Response({"error": "Status is required"}, status=status.HTTP_400_BAD_REQUEST)
    except EventBooking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["GET"])
def admin_room_availability(request):
    """
    GET -> Get availability for all rooms for a specific date
    """
    date_str = request.query_params.get("date")
    if not date_str:
        return Response({"error": "Date parameter is required"}, status=400)

    try:
        from django.utils.dateparse import parse_datetime
        from django.utils.timezone import make_aware, is_aware
        import datetime

        target_time = parse_datetime(date_str)
        if not target_time:
            # Fallback to date if it's just a date
            from django.utils.dateparse import parse_date
            d = parse_date(date_str)
            if d:
                target_time = datetime.datetime.combine(d, datetime.time.min)
            else:
                return Response({"error": "Invalid datetime format. Use ISO format or YYYY-MM-DD"}, status=400)

        # Ensure timezone awareness if settings specify
        if not is_aware(target_time):
            target_time = make_aware(target_time)
        
        rooms = Rooms.objects.all()
        # Active bookings for this precise moment (overlap check)
        # check_in <= target_time < check_out
        active_bookings = Booking.objects.filter(
            check_in__lte=target_time,
            check_out__gt=target_time,
            booking_status__in=["confirmed", "pending"]
        )

        availability_data = []

        for room in rooms:
            # Find if this room is in any active booking
            room_booking = None
            for b in active_bookings:
                # Room numbers are comma separated: "101,102"
                booked_rooms = [r.strip() for r in b.room_numbers.split(",") if r.strip()]
                if room.room_number in booked_rooms:
                    room_booking = b
                    break
            
            status_val = "available"
            booking_details = None
            
            if room_booking:
                status_val = room_booking.booking_status
                booking_details = {
                    "booking_id": room_booking.booking_id,
                    "guest_name": room_booking.guest_name,
                    "check_in": room_booking.check_in,
                    "check_out": room_booking.check_out,
                }
            
            availability_data.append({
                "room_number": room.room_number,
                "room_type": room.room_type,
                "status": status_val,
                "booking_details": booking_details
            })

        return Response(availability_data)

    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(["GET"])
def billing_history(request):
    """
    GET -> List bills. Supports filtering by ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """
    try:
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        bills = Billing.objects.all().order_by('-created_date')

        if start_date_str and end_date_str:
            # Parse dates
            from django.utils.dateparse import parse_date
            import datetime
            from django.utils import timezone

            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)

            if start_date and end_date:
                # Combine with min/max time
                # Make them timezone aware if strictly required, but simple approach:
                # Create naive datetime and make aware if USE_TZ=True
                min_time = datetime.time.min
                max_time = datetime.time.max
                
                start_dt = datetime.datetime.combine(start_date, min_time)
                end_dt = datetime.datetime.combine(end_date, max_time)
                
        if start_date_str and end_date_str:
            # Parse dates
            from django.utils.dateparse import parse_date
            import datetime
            from django.utils import timezone

            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)

            if start_date and end_date:
                # Combine with min/max time
                # Make them timezone aware if strictly required, but simple approach:
                # Create naive datetime and make aware if USE_TZ=True
                min_time = datetime.time.min
                max_time = datetime.time.max
                
                start_dt = datetime.datetime.combine(start_date, min_time)
                end_dt = datetime.datetime.combine(end_date, max_time)
                
                # Make aware
                start_dt = timezone.make_aware(start_dt)
                end_dt = timezone.make_aware(end_dt)
                
                bills = bills.filter(created_date__range=[start_dt, end_dt])

        serializer = BillingSerializer(bills, many=True)
        return Response(serializer.data)
    except Exception as e:
        print(f"Billing Filter Error: {e}") # Log it
        return Response({"error": str(e)}, status=500)
