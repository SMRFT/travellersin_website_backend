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
        
@api_view(["GET"])
@permission_classes([PublicOrHasRolePermission])
def check_room_availability(request):
    room_numbers = request.query_params.get("room_numbers")  # Comma separated "101,102"
    check_in_str = request.query_params.get("check_in")
    check_out_str = request.query_params.get("check_out")

    if not all([room_numbers, check_in_str, check_out_str]):
        return Response({"error": "Missing parameters"}, status=400)

    try:
        check_in = parse_datetime(check_in_str)
        check_out = parse_datetime(check_out_str)
        
        if not check_in or not check_out:
            return Response({"error": "Invalid date format"}, status=400)

        rooms_list = [r.strip() for r in room_numbers.split(",")]
        
        is_available = True
        conflicts = []

        for room_no in rooms_list:
            try:
                room_obj = Rooms.objects.get(room_number=room_no)
                if getattr(room_obj, 'status', 'active') == "maintenance" or getattr(room_obj, 'is_active', True) is False:
                    is_available = False
                    conflicts.append(room_no)
                    continue
            except Rooms.DoesNotExist:
                is_available = False
                conflicts.append(room_no)
                continue

            # Check overlap against bookings using both room_details and room_numbers
            candidate_bookings = Booking.objects.filter(
                check_in__lt=check_out,
                check_out__gt=check_in,
                booking_status__in=["confirmed", "pending", "checked_in", "checked in", "Confirmed", "Pending", "Checked In"]
            )
            
            is_room_conflict = False
            for b in candidate_bookings:
                r_details = b.room_details or []
                if isinstance(r_details, str):
                    try:
                        import json
                        r_details = json.loads(r_details)
                    except Exception:
                        r_details = []
                
                matched = False
                for item in r_details:
                    if isinstance(item, dict) and str(item.get('roomNo')).strip() == str(room_no).strip():
                        if item.get('isActive', True) is not False:
                            matched = True
                            break
                    elif str(item).strip() == str(room_no).strip():
                        matched = True
                        break
                
                if not matched and b.room_numbers:
                    booked_rn = [r.strip() for r in str(b.room_numbers).strip(",").split(",") if r.strip()]
                    if str(room_no).strip() in booked_rn:
                        matched = True

                if matched:
                    is_room_conflict = True
                    break

            if is_room_conflict:
                is_available = False
                conflicts.append(room_no)

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

