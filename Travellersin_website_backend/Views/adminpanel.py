from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from Travellersin_website_backend.models import Admin, Booking, Query, EventBooking, Rooms, Billing
from Travellersin_website_backend.serializers import AdminSerializer, BookingSerializer, EventBookingSerializer, BillingSerializer
from .whatsapp import send_booking_confirmation, send_event_confirmation
from pyauth.auth import HasRolePermission
from ..utils import get_auth_user
import razorpay
import os
import time
import uuid
from django.utils import timezone
from datetime import timedelta

# Initialize Razorpay Client (Ensure keys are loaded from settings/env)
client = razorpay.Client(auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")))

@api_view(["GET", "POST"])
@permission_classes([HasRolePermission])
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
        auth_user_id = get_auth_user(request)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        data['created_by'] = str(auth_user_id)
        serializer = AdminSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET", "PATCH"])
@permission_classes([HasRolePermission])
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
        auth_user_id = get_auth_user(request)
        admin.lastmodified_by = str(auth_user_id)
        admin.lastmodified_date = timezone.now()
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
@permission_classes([HasRolePermission])
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

    auth_user_id = get_auth_user(request)
    admin.is_active = False
    admin.lastmodified_by = str(auth_user_id)
    admin.lastmodified_date = timezone.now()
    admin.save()

    return Response(
        {"message": "Admin deactivated successfully"},
        status=status.HTTP_200_OK
    )

@api_view(["GET"])
@permission_classes([HasRolePermission])
def admin_dashboard(request):
    return Response({
        "total_bookings": Booking.objects.count(),
        "live_rooms": Rooms.objects.count(),
        "pending_queries": Query.objects.filter(status="open").count(),
        "active_events": EventBooking.objects.filter(status="pending").count()
    })

@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def update_booking_status(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        
        # Directly extract auth-user-id from backend auth helper
        auth_user_id = get_auth_user(request)
        booking.lastmodified_by = str(auth_user_id)
        booking.lastmodified_date = timezone.now()
        
        # DEBUG LOGging - Useful for the user to see in terminal
        print(f"Update Booking Request Body: {request.data}")

        # 1. Update Basic Fields
        raw_status = request.data.get("booking_status") or request.data.get("status") or booking.booking_status
        status_clean = str(raw_status).replace("_", " ").strip() if raw_status else ""
        status_norm = status_clean.lower()
        
        # Verify payment before allowing checkout
        if status_norm in ["checked out", "checked_out"]:
            payment_details = booking.payment_details or {}
            tax_details = booking.tax_details or {}
            
            # 1. Total / Gross amount resolution
            gross_total = 0.0
            if isinstance(tax_details, dict) and tax_details.get("gross_total"):
                gross_total = float(tax_details.get("gross_total") or 0.0)
            elif isinstance(payment_details, dict) and payment_details.get("amount"):
                gross_total = float(payment_details.get("amount") or 0.0)
            elif getattr(booking, "total_amount", None):
                gross_total = float(booking.total_amount or 0.0)
            elif getattr(booking, "price", None):
                gross_total = float(booking.price or 0.0)
                
            disc_amt = float(booking.discount_amount or 0.0)
            round_off = float(booking.round_off or (tax_details.get("round_off") if isinstance(tax_details, dict) else 0.0) or 0.0)
            net_amt = round(gross_total - disc_amt + round_off, 2)
            
            # 2. Amount paid resolution from Billing model / booking.amount_paid
            paid_amt = float(booking.amount_paid if getattr(booking, 'amount_paid', None) is not None else payment_details.get("amount_paid", 0.0))
            
            balance_due = round(net_amt - paid_amt, 2)
            if balance_due > 0.99:
                return Response(
                    {"error": f"Cannot check out guest with outstanding balance. Pending balance: ₹{balance_due:.2f}. Please record full payment before checking out."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Record actual guest checkout datetime
            if not booking.guest_check_out:
                booking.guest_check_out = timezone.now()

            # Update room_details: isActive=False, isCleaned=False (Dirty)
            r_details = booking.room_details or []
            if not r_details and booking.room_numbers:
                rn_list = [r.strip() for r in str(booking.room_numbers).strip(",").split(",") if r.strip()]
                r_details = [{"roomNo": r, "isActive": False, "isCleaned": False} for r in rn_list]
            else:
                for item in r_details:
                    if isinstance(item, dict):
                        item['isActive'] = False
                        item['isCleaned'] = False
            booking.room_details = r_details

        elif status_norm in ["confirmed", "checked in", "checked_in"]:
            # Record actual guest checkin datetime if status is checked in
            if status_norm in ["checked in", "checked_in"] and not booking.guest_check_in:
                booking.guest_check_in = timezone.now()

            r_details = booking.room_details or []
            if r_details:
                for item in r_details:
                    if isinstance(item, dict):
                        item['isActive'] = True
                booking.room_details = r_details

        booking.booking_status = status_clean
        if status_norm in ["cancelled", "canceled"]:
            booking.cancellation_reason = request.data.get("cancellation_reason", "Cancelled by Admin")
            refund_type = request.data.get("refund_type", "auto")
            
            # --- START REFUND LOGIC ---
            payment_details = booking.payment_details or {}
            amount_paid = float(booking.amount_paid if getattr(booking, 'amount_paid', None) is not None else payment_details.get("amount_paid", 0.0))
            refund_amount = 0
            fine_amount = 0
            
            if amount_paid > 0 and payment_details.get("status") not in ["refunded", "refund_pending"]:
                if refund_type == "full":
                    fine_amount = 0
                elif refund_type == "fine":
                    fine_amount = amount_paid * 0.15
                else:
                    # 24-Hour Full Refund Policy (Auto)
                    time_since_booking = timezone.now() - booking.created_at
                    if time_since_booking <= timedelta(hours=24):
                        fine_amount = 0
                    else:
                        fine_amount = amount_paid * 0.15 # 15% Cancellation Fine
                    
                refund_amount = amount_paid - fine_amount
                
                # Initiate Razorpay Refund if applicable
                refund_id = None
                refund_status = "pending"
                
                if payment_details.get("method") == "razorpay":
                    # Fetch the Razorpay payment ID from the Billing model
                    rzp_bills = list(booking.bills.filter(payment_type="razorpay"))
                    rzp_bills.sort(key=lambda b: getattr(b, 'created_date', None) or '', reverse=True)
                    billing = rzp_bills[0] if rzp_bills else None
                    rzp_payment_id = billing.razorpay_payment_id if billing else None
                    
                    if rzp_payment_id:
                        key_id = os.getenv("RAZORPAY_KEY_ID", "")
                        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
                        
                        if key_id and key_id == key_secret and "test" in key_id.lower():
                            # Mocking for dummy test keys to prevent Authentication Failed
                            print("Using Dummy Razorpay Secret. Mocking Refund Success.")
                            refund_id = f"rfnd_mock_{int(time.time())}"
                            refund_status = "processed"
                        else:
                            try:
                                # Razorpay expects amount in paise
                                refund_data = {
                                    "amount": int(refund_amount * 100),
                                    "speed": "normal",
                                    "notes": {
                                        "booking_id": booking_id,
                                        "reason": f"Cancellation Refund ({'Full Refund' if fine_amount == 0 else '15% Fine Deducted'})"
                                    }
                                }
                                refund = client.payment.refund(rzp_payment_id, refund_data)
                                refund_id = refund.get("id")
                                refund_status = refund.get("status")
                            except Exception as e:
                                print(f"Razorpay Refund Failed: {e}")
                                refund_status = "failed"
                                payment_details["refund_error"] = str(e)
                
                # Create Refund Billing Record
                from .payments import generate_billing_no
                refund_bill_no = generate_billing_no()
                
                Billing.objects.create(
                    billing_no=refund_bill_no,
                    booking=booking,
                    amount_paid=-refund_amount, # Negative to show return
                    payment_type="razorpay_refund" if payment_details.get("method") == "razorpay" else "cash_refund",
                    status="success" if refund_status == "processed" else "pending",
                    transaction_id=refund_id,
                    payment_gateway_ref_id=rzp_payment_id if payment_details.get("method") == "razorpay" else None,
                    created_by=str(auth_user_id)
                )
                
                if "billing_numbers" not in payment_details or not isinstance(payment_details["billing_numbers"], list):
                    payment_details["billing_numbers"] = []
                if refund_bill_no not in payment_details["billing_numbers"]:
                    payment_details["billing_numbers"].append(refund_bill_no)
                payment_details["latest_billing_no"] = refund_bill_no

                # Update Payment Details with Refund Info
                payment_details["refund_amount"] = refund_amount
                payment_details["cancellation_fine"] = fine_amount
                payment_details["refund_id"] = refund_id
                payment_details["refund_status"] = refund_status
                payment_details["status"] = "refunded" if refund_status == "processed" else "refund_pending"
                
                # We will assign payment_details directly to the booking later in this function
                # But we update it in the request so it's merged into p_details
                request.data["payment_details"] = payment_details
            # --- END REFUND LOGIC ---

        
        check_in = request.data.get("check_in")
        check_out = request.data.get("check_out")
        if check_in: booking.check_in = check_in
        if check_out: booking.check_out = check_out

        # 2. Handle Payment Details & Recording
        raw_pd = request.data.get("payment_details")
        p_details = dict(booking.payment_details or {})
        if isinstance(raw_pd, dict):
            p_details.update({k: v for k, v in raw_pd.items() if k in ['amount', 'status', 'billing_numbers']})

        new_paid = request.data.get("amount_paid")
        if new_paid is None and isinstance(raw_pd, dict):
            if "amount_paid" in raw_pd and float(raw_pd.get("amount_paid", 0)) > 0:
                total_in_req = float(raw_pd["amount_paid"])
                existing_paid = sum(float(b.amount_paid or 0) for b in booking.bills.all())
                if total_in_req > existing_paid:
                    new_paid = total_in_req - existing_paid
            elif "paid" in raw_pd and float(raw_pd.get("paid", 0)) > 0:
                total_in_req = float(raw_pd["paid"])
                existing_paid = sum(float(b.amount_paid or 0) for b in booking.bills.all())
                if total_in_req > existing_paid:
                    new_paid = total_in_req - existing_paid

        _pt = request.data.get("payment_type") or request.data.get("method") or (raw_pd.get("payment_type") if isinstance(raw_pd, dict) else None) or (raw_pd.get("method") if isinstance(raw_pd, dict) else None)
        p_type = _pt if _pt else "cash"

        _tid = request.data.get("transaction_id") or (raw_pd.get("transaction_id") if isinstance(raw_pd, dict) else None)
        t_id = _tid if (_tid is not None and str(_tid).strip() != '') else None

        manual_p_status = request.data.get("payment_status") or (raw_pd.get("status") if isinstance(raw_pd, dict) else None)

        if new_paid is not None and float(new_paid) > 0:
            try:
                amt_to_add = float(new_paid)
                current_total = float(p_details.get("amount", 0) or (raw_pd.get("amount") if isinstance(raw_pd, dict) else 0) or 0)
                
                existing_paid = sum(float(b.amount_paid or 0) for b in booking.bills.all())
                new_total_paid = existing_paid + amt_to_add

                net_payable = max(0.0, current_total - float(booking.discount_amount or 0))
                if not manual_p_status:
                    if new_total_paid >= net_payable and net_payable > 0:
                        p_details["status"] = "paid"
                    elif new_total_paid > 0:
                        p_details["status"] = "partially_paid"
                    else:
                        p_details["status"] = "pending"
                else:
                    p_details["status"] = manual_p_status

                from .payments import generate_billing_no
                bill_no = generate_billing_no()

                try:
                    Billing.objects.create(
                        billing_no=bill_no,
                        booking=booking,
                        amount_paid=amt_to_add,
                        payment_type=p_type,
                        transaction_id=t_id,
                        created_by=str(auth_user_id)
                    )

                    if "billing_numbers" not in p_details or not isinstance(p_details["billing_numbers"], list):
                        p_details["billing_numbers"] = []
                    if bill_no not in p_details["billing_numbers"]:
                        p_details["billing_numbers"].append(bill_no)
                except Exception as b_err:
                    print(f"Billing record creation failed: {b_err}")

            except (ValueError, TypeError) as e:
                print(f"Amount calculation failed: {e}")

        # Strip transient fields from p_details before saving
        if isinstance(p_details, dict):
            unwanted_keys = [
                'method', 'paid', 'amount_paid', 'latest_billing_no',
                'transaction_id', 'latest_transaction_id', 'payment_type', 'date'
            ]
            for k in unwanted_keys:
                p_details.pop(k, None)

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

# Initialize Razorpay Client is done at the top of the file

@api_view(["POST"])
@permission_classes([HasRolePermission])
def approve_cancellation(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        if booking.booking_status != "cancellation_requested":
            return Response({"error": "No cancellation request found for this booking"}, status=400)
        
        auth_user_id = get_auth_user(request)
        booking.lastmodified_by = str(auth_user_id)
        booking.lastmodified_date = timezone.now()

        # Calculate Refund
        payment_details = booking.payment_details or {}
        amount_paid = float(payment_details.get("amount_paid", 0))
        refund_amount = 0
        fine_amount = 0
        
        if amount_paid > 0:
            # 24-Hour Full Refund Policy
            time_since_booking = timezone.now() - booking.created_at
            if time_since_booking <= timedelta(hours=24):
                fine_amount = 0
            else:
                fine_amount = amount_paid * 0.15 # 15% Cancellation Fine
                
            refund_amount = amount_paid - fine_amount
            
            # Initiate Razorpay Refund if applicable
            refund_id = None
            refund_status = "pending"
            
            if payment_details.get("method") == "razorpay":
                rzp_bills = list(booking.bills.filter(payment_type="razorpay"))
                rzp_bills.sort(key=lambda b: getattr(b, 'created_date', None) or '', reverse=True)
                billing = rzp_bills[0] if rzp_bills else None
                rzp_payment_id = billing.razorpay_payment_id if billing else None
                
                if rzp_payment_id:
                    key_id = os.getenv("RAZORPAY_KEY_ID", "")
                    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
                    
                    if key_id and key_id == key_secret and "test" in key_id.lower():
                        # Mocking for dummy test keys to prevent Authentication Failed
                        print("Using Dummy Razorpay Secret. Mocking Refund Success.")
                        refund_id = f"rfnd_mock_{int(time.time())}"
                        refund_status = "processed"
                    else:
                        try:
                            # Razorpay expects amount in paise
                            refund_data = {
                                "amount": int(refund_amount * 100),
                                "speed": "normal",
                                "notes": {
                                    "booking_id": booking_id,
                                    "reason": f"Cancellation Refund ({'Full Refund' if fine_amount == 0 else '15% Fine Deducted'})"
                                }
                            }
                            refund = client.payment.refund(rzp_payment_id, refund_data)
                            refund_id = refund.get("id")
                            refund_status = refund.get("status")
                            
                        except Exception as e:
                            print(f"Razorpay Refund Failed: {e}")
                            refund_status = "failed"
                            payment_details["refund_error"] = str(e)
            
            # Create Refund Billing Record
            from .payments import generate_billing_no
            refund_bill_no = generate_billing_no()
            
            Billing.objects.create(
                billing_no=refund_bill_no,
                booking=booking,
                amount_paid=-refund_amount, # Negative to show return
                payment_type="razorpay_refund" if payment_details.get("method") == "razorpay" else "cash_refund",
                status="success" if refund_status == "processed" else "pending",
                transaction_id=refund_id,
                payment_gateway_ref_id=rzp_payment_id if payment_details.get("method") == "razorpay" else None,
                created_by=str(auth_user_id)
            )
            
            if "billing_numbers" not in payment_details or not isinstance(payment_details["billing_numbers"], list):
                payment_details["billing_numbers"] = []
            if refund_bill_no not in payment_details["billing_numbers"]:
                payment_details["billing_numbers"].append(refund_bill_no)
            payment_details["latest_billing_no"] = refund_bill_no

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
@permission_classes([HasRolePermission])
def reject_cancellation(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        if booking.booking_status != "cancellation_requested":
            return Response({"error": "No cancellation request found for this booking"}, status=400)
        
        auth_user_id = get_auth_user(request)
        booking.lastmodified_by = str(auth_user_id)
        booking.lastmodified_date = timezone.now()

        # Default back to 'confirmed' if rejected
        booking.booking_status = "confirmed"
        booking.save()
        return Response({"message": "Cancellation request rejected", "booking": BookingSerializer(booking).data})
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def update_event_booking_status(request, booking_id):
    try:
        booking = EventBooking.objects.get(booking_id=booking_id)
        auth_user_id = get_auth_user(request)
        booking.lastmodified_by = str(auth_user_id)
        booking.lastmodified_date = timezone.now()
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
@permission_classes([HasRolePermission])
def admin_room_availability(request):
    """
    GET -> Get availability for all rooms for a specific date:
    - Vacant (Green: #10B981)
    - Occupied (Blue: #3B82F6)
    - Dirty / Needs Cleaning (Orange: #F59E0B)
    - Under Maintenance (Black: #1F2937)
    """
    date_str = request.query_params.get("date") # Optional YYYY-MM-DD or ISO string
    check_in_str = request.query_params.get("check_in")
    check_out_str = request.query_params.get("check_out")
    exclude_booking_id = request.query_params.get("exclude_booking_id")
    
    def parse_dt(val_str):
        if not val_str:
            return None
        from datetime import datetime
        s = str(val_str).strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt
            except Exception:
                pass
        try:
            dt = datetime.fromisoformat(s)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except Exception:
            return None

    ci_dt = parse_dt(check_in_str)
    co_dt = parse_dt(check_out_str)
    
    if ci_dt and co_dt:
        target_start = ci_dt
        target_end = co_dt
        target_date = ci_dt.date()
    else:
        d_dt = parse_dt(date_str)
        if d_dt:
            target_date = d_dt.date()
        else:
            target_date = timezone.now().date()
        from datetime import datetime
        target_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        target_end = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))

    try:
        rooms = list(Rooms.objects.all())
        # Sort rooms naturally by room_number
        try:
            rooms.sort(key=lambda r: int(''.join(filter(str.isdigit, str(r.room_number)))) if any(c.isdigit() for c in str(r.room_number)) else str(r.room_number))
        except Exception:
            pass

        # 1. Fetch active bookings covering target date
        booking_query = (
            Q(booking_status__in=["confirmed", "Confirmed", "checked_in", "checked in", "Checked In", "Checked_In"]) &
            Q(check_in__lt=target_end) &
            Q(check_out__gt=target_start)
        )
        if exclude_booking_id:
            booking_query = booking_query & ~Q(booking_id=exclude_booking_id)

        active_bookings = list(Booking.objects.filter(booking_query))

        # 2. Fetch recent bookings to evaluate cleaning status
        all_recent_bookings = list(Booking.objects.all().order_by('-created_date')[:50])

        availability_data = []

        for room in rooms:
            r_num_str = str(room.room_number).strip()
            try:
                r_price = float(str(room.price)) if room.price is not None else 0.0
            except Exception:
                r_price = 0.0
            r_size = str(room.size or "")
            
            # Case 1: Under Maintenance (Black)
            if getattr(room, 'is_active', True) is False or getattr(room, 'status', 'active') in ["maintenance", "inactive"]:
                availability_data.append({
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "price": r_price,
                    "size": r_size,
                    "status": "maintenance",
                    "status_label": "Under Maintenance",
                    "color": "black",
                    "color_code": "#1F2937",
                    "current_booking": None
                })
                continue

            # Check if occupied by an active booking
            matched_booking = None
            for b in active_bookings:
                r_details = b.room_details or []
                for item in r_details:
                    if isinstance(item, dict):
                        if str(item.get('roomNo')).strip() == r_num_str and item.get('isActive', True):
                            matched_booking = b
                            break
                    elif str(item).strip() == r_num_str:
                        matched_booking = b
                        break
                if matched_booking:
                    break

            # Case 2: Occupied (Blue)
            if matched_booking:
                availability_data.append({
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "price": r_price,
                    "size": r_size,
                    "status": "occupied",
                    "status_label": "Occupied",
                    "color": "blue",
                    "color_code": "#3B82F6",
                    "current_booking": {
                        "booking_id": matched_booking.booking_id,
                        "guest_name": matched_booking.guest_name,
                        "guest_phone": matched_booking.guest_phone,
                        "check_in": matched_booking.check_in,
                        "check_out": matched_booking.check_out,
                        "status": matched_booking.booking_status
                    }
                })
                continue

            # Case 3: Check cleaning status from most recent booking for this room
            is_cleaned = True
            for b in all_recent_bookings:
                r_details = b.room_details or []
                found = False
                for item in r_details:
                    if isinstance(item, dict) and str(item.get('roomNo')).strip() == r_num_str:
                        if item.get('isCleaned') is False:
                            is_cleaned = False
                        found = True
                        break
                if found:
                    break

            if not is_cleaned:
                # Dirty / Needs Cleaning (Orange)
                availability_data.append({
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "price": r_price,
                    "size": r_size,
                    "status": "dirty",
                    "status_label": "Needs Cleaning",
                    "color": "orange",
                    "color_code": "#F59E0B",
                    "current_booking": None
                })
            else:
                # Case 4: Vacant / Clean (Green)
                availability_data.append({
                    "room_number": room.room_number,
                    "room_type": room.room_type,
                    "price": r_price,
                    "size": r_size,
                    "status": "vacant",
                    "status_label": "Vacant / Clean",
                    "color": "green",
                    "color_code": "#10B981",
                    "current_booking": None
                })

        return Response({
            "date": str(target_date),
            "total_rooms": len(rooms),
            "summary": {
                "vacant": len([r for r in availability_data if r["status"] == "vacant"]),
                "occupied": len([r for r in availability_data if r["status"] == "occupied"]),
                "dirty": len([r for r in availability_data if r["status"] == "dirty"]),
                "maintenance": len([r for r in availability_data if r["status"] == "maintenance"])
            },
            "rooms": availability_data
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

@api_view(["POST", "PATCH"])
@permission_classes([HasRolePermission])
def update_room_availability_status(request):
    """
    POST/PATCH -> Update room housekeeping or maintenance status:
    - 'vacant' / 'cleaned': sets room active, latest booking isCleaned=True
    - 'dirty': sets room active, latest booking isCleaned=False
    - 'maintenance': sets room is_active=False, status='maintenance'
    - 'occupied': sets room is_active=True, status='active'
    """
    room_number = request.data.get("room_number")
    new_status = (request.data.get("status") or "").lower().strip()
    auth_user_id = get_auth_user(request)

    if not room_number:
        return Response({"error": "room_number is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        room = Rooms.objects.get(room_number=room_number)
    except Rooms.DoesNotExist:
        return Response({"error": f"Room {room_number} not found"}, status=status.HTTP_404_NOT_FOUND)

    r_num_str = str(room_number).strip()
    room.lastmodified_by = str(auth_user_id)
    room.lastmodified_date = timezone.now()

    if new_status in ["maintenance", "undermaintenance", "under_maintenance", "inactive"]:
        room.is_active = False
        room.status = "maintenance"
        room.save()
    elif new_status in ["vacant", "clean", "cleaned", "available"]:
        room.is_active = True
        room.status = "active"
        room.save()
        # Mark recent booking as isCleaned = True
        all_recent = list(Booking.objects.all().order_by('-created_date')[:15])
        for b in all_recent:
            r_details = b.room_details or []
            updated = False
            for item in r_details:
                if isinstance(item, dict) and str(item.get('roomNo')).strip() == r_num_str:
                    item['isCleaned'] = True
                    updated = True
            if updated:
                b.room_details = r_details
                b.lastmodified_by = str(auth_user_id)
                b.lastmodified_date = timezone.now()
                b.save()
                break
    elif new_status in ["dirty", "uncleaned", "needs_cleaning"]:
        room.is_active = True
        room.status = "active"
        room.save()
        # Mark recent booking as isCleaned = False
        all_recent = list(Booking.objects.all().order_by('-created_date')[:15])
        for b in all_recent:
            r_details = b.room_details or []
            updated = False
            for item in r_details:
                if isinstance(item, dict) and str(item.get('roomNo')).strip() == r_num_str:
                    item['isCleaned'] = False
                    updated = True
            if updated:
                b.room_details = r_details
                b.lastmodified_by = str(auth_user_id)
                b.lastmodified_date = timezone.now()
                b.save()
                break
    elif new_status == "occupied":
        room.is_active = True
        room.status = "active"
        room.save()
    else:
        return Response({"error": f"Invalid status: {new_status}. Allowed: vacant, dirty, maintenance, occupied"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        "success": True,
        "room_number": room.room_number,
        "status": room.status,
        "is_active": room.is_active,
        "message": f"Room {room.room_number} status updated to {new_status}"
    })

@api_view(["GET"])
@permission_classes([HasRolePermission])
def billing_history(request):
    """
    GET -> List bills. Supports filtering by ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    """
    try:
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        bills_qs = Billing.objects.all()

        if start_date_str and end_date_str:
            from django.utils.dateparse import parse_date
            import datetime
            from django.utils import timezone

            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)

            if start_date and end_date:
                min_time = datetime.time.min
                max_time = datetime.time.max
                
                start_dt = datetime.datetime.combine(start_date, min_time)
                end_dt = datetime.datetime.combine(end_date, max_time)
                
                try:
                    start_dt = timezone.make_aware(start_dt)
                    end_dt = timezone.make_aware(end_dt)
                except Exception:
                    pass
                
                bills_qs = bills_qs.filter(created_date__range=[start_dt, end_dt])

        bills_list = list(bills_qs)
        try:
            bills_list.sort(key=lambda b: getattr(b, 'created_date', None) or '', reverse=True)
        except Exception:
            pass

        serializer = BillingSerializer(bills_list, many=True)
        return Response(serializer.data)
    except Exception as e:
        print(f"Billing Filter Error: {e}")
        return Response({"error": str(e)}, status=500)
