from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from Travellersin_website_backend.models import Rooms, Booking
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from Travellersin_website_backend.serializers import RoomSerializer



@api_view(["GET", "POST"])
def rooms_list_create(request):
    if request.method == "GET":
        rooms = Rooms.objects.all()
        serializer = RoomSerializer(rooms, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        serializer = RoomSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH", "DELETE"])
def room_detail_update(request, room_number):
    try:
        room = Rooms.objects.get(room_number=room_number)
    except Rooms.DoesNotExist:
        return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(RoomSerializer(room).data)

    if request.method == "PATCH":
        serializer = RoomSerializer(room, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        room.delete()
        return Response({"message": "Room deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        
@api_view(["GET"])
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
            # We use delimiters for exact matching in comma-separated string
            search_pattern = f",{room_no},"
            overlapping = Booking.objects.filter(
                room_numbers__icontains=search_pattern,
                check_in__lt=check_out,
                check_out__gt=check_in,
                booking_status__in=["confirmed", "pending"]
            )
            if overlapping.exists():
                is_available = False
                conflicts.append(room_no)

        return Response({
            "is_available": is_available,
            "conflicts": conflicts
        })
    except Exception as e:
        return Response({"error": str(e)}, status=400)
@api_view(["GET"])
def get_room_bookings(request, room_number):
    try:
        # Get all confirmed or pending bookings for this room
        search_pattern = f",{room_number},"
        bookings = Booking.objects.filter(
            room_numbers__icontains=search_pattern,
            booking_status__in=["confirmed", "pending"]
        )
        
        booked_dates = []
        for b in bookings:
            booked_dates.append({
                "start": b.check_in,
                "end": b.check_out
            })
            
        return Response(booked_dates)
    except Exception as e:
        return Response({"error": str(e)}, status=400)
