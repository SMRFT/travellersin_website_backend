from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from ..models import EventBooking
from ..serializers import EventBookingSerializer

@api_view(['GET', 'POST'])
def event_bookings_list_create(request):
    if request.method == 'GET':
        bookings = EventBooking.objects.all().order_by('-created_at')
        serializer = EventBookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = EventBookingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def track_event_booking(request):
    booking_id = request.data.get('booking_id')
    phone = request.data.get('phone')
    
    if not booking_id or not phone:
        return Response({"error": "Booking ID and Phone Number are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        booking = EventBooking.objects.get(booking_id=booking_id, phone=phone)
        serializer = EventBookingSerializer(booking)
        return Response(serializer.data)
    except EventBooking.DoesNotExist:
        return Response({"error": "Event booking not found"}, status=status.HTTP_404_NOT_FOUND)
