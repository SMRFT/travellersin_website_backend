from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from Travellersin_website_backend.models import Rooms, Booking
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from Travellersin_website_backend.serializers import RoomSerializer
from ..permissions import PublicReadOnlyOrHasRolePermission, PublicOrHasRolePermission
from ..utils import get_auth_user


@api_view(["GET", "POST"])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def rooms_list_create(request):
    if request.method == "GET":
        rooms = Rooms.objects.all()
        serializer = RoomSerializer(rooms, many=True, context={'request': request})
        return Response(serializer.data)

    if request.method == "POST":
        auth_user_id = get_auth_user(request)
        serializer = RoomSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(created_by=str(auth_user_id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def room_detail_update(request, room_number):
    try:
        room = Rooms.objects.get(room_number=room_number)
    except Rooms.DoesNotExist:
        return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(RoomSerializer(room, context={'request': request}).data)

    if request.method == "PATCH":
        auth_user_id = get_auth_user(request)
        serializer = RoomSerializer(room, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        room.delete()
        return Response({"message": "Room deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        
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

@api_view(["GET"])
@permission_classes([PublicOrHasRolePermission])
def check_room_availability(request):
    room_numbers = request.query_params.get("room_numbers")  # Comma separated "101,102"
    check_in_str = request.query_params.get("check_in")
    check_out_str = request.query_params.get("check_out")

    if not all([room_numbers, check_in_str, check_out_str]):
        return Response({"error": "Missing parameters"}, status=400)

    try:
        check_in = parse_dt(check_in_str)
        check_out = parse_dt(check_out_str)
        
        if not check_in or not check_out:
            return Response({"error": "Invalid date format"}, status=400)

        rooms_list = [r.strip() for r in room_numbers.split(",")]
        
        now_dt = timezone.now()
        from datetime import timedelta
        is_immediate = (check_in <= now_dt)
        recent_threshold = now_dt - timedelta(days=2)
        all_recent_bookings = list(Booking.objects.all().order_by('-created_date')[:100])

        is_available = True
        conflicts = []

        for room_no in rooms_list:
            try:
                room_obj = Rooms.objects.get(room_number=room_no)
                if getattr(room_obj, 'status', 'active') in ["maintenance", "inactive"] or getattr(room_obj, 'is_active', True) is False:
                    conflicts.append(room_no)
                    continue
            except Rooms.DoesNotExist:
                conflicts.append(room_no)
                continue

            matched_booking = None
            for b in all_recent_bookings:
                b_st = str(b.booking_status or '').lower().replace('_', ' ').strip()
                if b_st in ['checked out', 'cancelled', 'canceled']:
                    continue
                if b_st not in ['confirmed', 'checked in', 'pending', 'booked', 'pending confirmation']:
                    continue

                has_room = False
                r_details = b.room_details or []
                if isinstance(r_details, str):
                    try:
                        import json
                        r_details = json.loads(r_details)
                    except Exception:
                        r_details = []

                for item in r_details:
                    if isinstance(item, dict) and str(item.get('roomNo')).strip() == str(room_no).strip() and item.get('isActive', True):
                        has_room = True
                        break
                    elif str(item).strip() == str(room_no).strip():
                        has_room = True
                        break
                if not has_room and b.room_numbers:
                    booked_rn = [r.strip() for r in str(b.room_numbers).strip(',').split(',') if r.strip()]
                    if str(room_no).strip() in booked_rn:
                        has_room = True

                if not has_room:
                    continue

                is_overlapping = (b.check_in < check_out and b.check_out > check_in)
                if b.check_out <= now_dt:
                    is_inhouse = (b_st in ['checked in', 'occupied'] or (b.guest_check_in is not None and b.guest_check_out is None))
                    if not is_inhouse:
                        continue

                is_inhouse_overstay = (
                    is_immediate and
                    b.guest_check_in is not None and
                    b.guest_check_out is None and
                    recent_threshold <= b.check_in <= now_dt and
                    b.check_out <= now_dt
                )

                if is_overlapping or is_inhouse_overstay:
                    matched_booking = b
                    break

            if matched_booking:
                conflicts.append(room_no)

        is_available = len([r for r in rooms_list if r not in conflicts]) > 0

        return Response({
            "is_available": is_available,
            "conflicts": conflicts
        })
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(["GET"])
@permission_classes([PublicOrHasRolePermission])
def get_room_bookings(request, room_number):
    try:
        r_num_str = str(room_number).strip()
        bookings = Booking.objects.filter(
            booking_status__in=["confirmed", "pending", "checked_in", "checked in", "Confirmed", "Pending", "Checked In"]
        )
        
        booked_dates = []
        for b in bookings:
            r_details = b.room_details or []
            if isinstance(r_details, str):
                try:
                    import json
                    r_details = json.loads(r_details)
                except Exception:
                    r_details = []
            
            matched = False
            for item in r_details:
                if isinstance(item, dict) and str(item.get('roomNo')).strip() == r_num_str:
                    if item.get('isActive', True) is not False:
                        matched = True
                        break
                elif str(item).strip() == r_num_str:
                    matched = True
                    break
            
            if not matched and b.room_numbers:
                booked_rn = [r.strip() for r in str(b.room_numbers).strip(",").split(",") if r.strip()]
                if r_num_str in booked_rn:
                    matched = True

            if matched:
                booked_dates.append({
                    "start": b.check_in,
                    "end": b.check_out
                })
        return Response({"booked_dates": booked_dates})
    except Exception as e:
        return Response({"error": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([PublicOrHasRolePermission])
def get_menu_items(request):
    """
    GET -> Fetch active menu items for Food & Dining selection
    """
    try:
        from ..models import MenuItems
        from ..serializers import MenuItemSerializer
        items = MenuItems.objects.filter(is_active=True).order_by("item_id")
        serializer = MenuItemSerializer(items, many=True)
        return Response(serializer.data)
    except Exception as e:
        # Fallback to direct pymongo query if needed
        try:
            import os
            import dotenv
            from pymongo import MongoClient
            dotenv.load_dotenv()
            mongo_uri = os.getenv('GLOBAL_DB_HOST', 'mongodb://localhost:27017/')
            db_name = os.getenv('TIWEB_DB_NAME', 'TravellersIN_Website')
            client = MongoClient(mongo_uri)
            db = client[db_name]
            docs = list(db['Travellersin_website_backend_menuitems'].find({"is_active": True}))
            result = []
            for d in docs:
                result.append({
                    "item_id": d.get("item_id"),
                    "item_name": d.get("item_name"),
                    "rate": float(str(d.get("rate", 0))),
                    "is_active": d.get("is_active", True)
                })
            return Response(result)
        except Exception as e2:
            return Response({"error": str(e2)}, status=400)

