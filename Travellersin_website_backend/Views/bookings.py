from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from datetime import timedelta
from rest_framework.response import Response
from Travellersin_website_backend.models import Booking
from Travellersin_website_backend.serializers import BookingSerializer
from ..permissions import PublicCreateOrHasRolePermission, PublicReadOnlyOrHasRolePermission
from ..utils import get_auth_user

def generate_booking_id():
    existing_bookings = list(Booking.objects.filter(booking_id__startswith="BK-"))
    max_num = 0
    for b in existing_bookings:
        try:
            num_part = str(b.booking_id).replace("BK-", "").strip()
            if num_part.isdigit():
                val = int(num_part)
                if val > max_num:
                    max_num = val
        except (ValueError, IndexError):
            pass
    next_num = max_num + 1
    return f"BK-{next_num:05d}"

def build_booking_serializer_context(bookings_list):
    from Travellersin_website_backend.models import Customer, Company, Billing
    
    cust_ids = list({str(b.customer_id) for b in bookings_list if getattr(b, 'customer_id', None)})
    comp_ids = list({str(b.company_id) for b in bookings_list if getattr(b, 'company_id', None)})
    booking_ids = list({str(b.booking_id) for b in bookings_list if getattr(b, 'booking_id', None)})
    
    cust_map = {}
    if cust_ids:
        for c in Customer.objects.filter(customer_id__in=cust_ids):
            cust_map[str(c.customer_id)] = c
            
    comp_map = {}
    if comp_ids:
        for comp in Company.objects.filter(company_id__in=comp_ids):
            comp_map[str(comp.company_id)] = comp
            
    bills_map = {}
    if booking_ids:
        for bill in Billing.objects.filter(booking_id__in=booking_ids):
            b_id = str(bill.booking_id)
            if b_id not in bills_map:
                bills_map[b_id] = []
            bills_map[b_id].append(bill)
            
    for b in bookings_list:
        b_cust_id = getattr(b, 'customer_id', None)
        b._cached_customer = cust_map.get(str(b_cust_id)) if b_cust_id else None
        
        b_comp_id = getattr(b, 'company_id', None)
        b._cached_company = comp_map.get(str(b_comp_id)) if b_comp_id else None
        
        b_book_id = getattr(b, 'booking_id', None)
        b._cached_bills = bills_map.get(str(b_book_id), [])
            
    return {
        "cust_map": cust_map,
        "comp_map": comp_map,
        "bills_map": bills_map
    }

@api_view(["GET", "POST"])
@permission_classes([PublicCreateOrHasRolePermission])
def bookings_list_create(request):
    if request.method == "GET":
        customer_id = request.query_params.get("customer_id")
        booking_type = request.query_params.get("booking_type") or request.query_params.get("type")
        status_param = request.query_params.get("status")
        
        if customer_id:
            bookings_qs = Booking.objects.filter(customer_id=customer_id)
        else:
            bookings_qs = Booking.objects.all()

        # Separate endpoints / queries by booking_type
        if booking_type == "active":
            # Active & Upcoming: pending, confirmed, checked in, cancellation requested
            bookings_qs = bookings_qs.filter(booking_status__in=[
                "pending", "confirmed", "checked in", "checked_in", "cancellation requested", "cancellation_requested",
                "booked", "active", "Pending", "Confirmed", "Checked In", "Checked_In", "Checked_in", "Cancellation Requested"
            ])
        elif booking_type in ["past", "history"]:
            # Past / Completed & Cancelled: checked out, cancelled
            bookings_qs = bookings_qs.filter(booking_status__in=[
                "checked out", "checked_out", "cancelled", "canceled", "Checked Out", "Checked_Out", "Cancelled", "Canceled"
            ])

        if status_param and status_param != "all":
            clean_p = str(status_param).replace("_", " ").strip()
            raw_p = str(status_param).replace(" ", "_").strip()
            bookings_qs = bookings_qs.filter(booking_status__in=[clean_p, raw_p, clean_p.lower(), raw_p.lower(), clean_p.title()])
            
        # Date Filter (supports start_date & end_date or from_date & to_date)
        start_date_str = request.query_params.get('start_date') or request.query_params.get('from_date')
        end_date_str = request.query_params.get('end_date') or request.query_params.get('to_date')
        
        if start_date_str or end_date_str:
            try:
                from datetime import datetime
                if start_date_str and end_date_str:
                    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                    if booking_type in ["past", "history"]:
                        bookings_qs = bookings_qs.filter(check_out__range=[start_dt, end_dt])
                    else:
                        bookings_qs = bookings_qs.filter(created_at__range=[start_dt, end_dt])
                elif start_date_str:
                    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                    if booking_type in ["past", "history"]:
                        bookings_qs = bookings_qs.filter(check_out__gte=start_dt)
                    else:
                        bookings_qs = bookings_qs.filter(created_at__gte=start_dt)
                elif end_date_str:
                    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                    if booking_type in ["past", "history"]:
                        bookings_qs = bookings_qs.filter(check_out__lte=end_dt)
                    else:
                        bookings_qs = bookings_qs.filter(created_at__lte=end_dt)
            except Exception as e:
                print(f"Date filter error: {e}")
                
        bookings_list = list(bookings_qs)
        def get_booking_sort_key(b):
            c_date = getattr(b, 'created_date', None) or getattr(b, 'created_at', None)
            if c_date is not None:
                if hasattr(c_date, 'isoformat'):
                    return c_date.isoformat()
                return str(c_date)
            return str(getattr(b, 'booking_id', ''))

        try:
            bookings_list.sort(key=get_booking_sort_key, reverse=True)
        except Exception as e:
            print(f"Sorting error: {e}")

        context = build_booking_serializer_context(bookings_list)
        return Response(BookingSerializer(bookings_list, many=True, context=context).data)

    if request.method == "POST":
        auth_user_id = get_auth_user(request)
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            booking = serializer.save(created_by=str(auth_user_id))
            
            # If initial payment was recorded, create a Billing record
            raw_pd = request.data.get("payment_details") or {}
            amount_paid = float(request.data.get("amount_paid") or raw_pd.get("amount_paid", raw_pd.get("paid", 0)))
            
            if amount_paid > 0:
                from ..models import Billing
                from .payments import generate_billing_no
                
                billing_no = generate_billing_no()
                p_type = request.data.get("payment_type") or raw_pd.get("payment_type") or raw_pd.get("method") or "cash"
                t_id = request.data.get("transaction_id") or raw_pd.get("transaction_id")
                
                try:
                    Billing.objects.create(
                        billing_no=billing_no,
                        booking=booking,
                        amount_paid=amount_paid,
                        payment_type=p_type,
                        transaction_id=t_id,
                        created_by=str(auth_user_id)
                    )
                    
                    # Update billing_numbers in booking
                    b_nums = booking.payment_details.get("billing_numbers", [])
                    if not isinstance(b_nums, list):
                        b_nums = []
                    if billing_no not in b_nums:
                        b_nums.append(billing_no)
                    
                    booking.payment_details = {
                        "amount": float(booking.payment_details.get("amount", 0)),
                        "status": "paid" if amount_paid >= float(booking.payment_details.get("amount", 0)) else "partially_paid",
                        "billing_numbers": b_nums
                    }
                    booking.lastmodified_by = str(auth_user_id)
                    booking.lastmodified_date = timezone.now()
                    booking.save()
                except Exception as e:
                    print(f"Error creating initial billing record: {e}")
            
            return Response(BookingSerializer(booking).data, status=201)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH"])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def booking_detail_update(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=404)

    if request.method == "GET":
        return Response(BookingSerializer(booking).data)

    if request.method == "PATCH":
        auth_user_id = get_auth_user(request)
        serializer = BookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
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

    auth_user_id = get_auth_user(request)
    reason = request.data.get("reason", "Cancelled by guest")
    booking.booking_status = "cancellation_requested"
    booking.cancellation_reason = reason
    booking.lastmodified_by = str(auth_user_id)
    booking.lastmodified_date = timezone.now()
    booking.save()
    return Response({"message": "Cancellation request submitted for admin approval", "booking": BookingSerializer(booking).data})
