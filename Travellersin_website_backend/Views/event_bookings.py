from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from ..models import EventBooking
from ..serializers import EventBookingSerializer
from .whatsapp import send_event_confirmation
from ..permissions import PublicCreateOrHasRolePermission
from ..utils import get_auth_user

@api_view(['GET', 'POST'])
@permission_classes([PublicCreateOrHasRolePermission])
def event_bookings_list_create(request):
    if request.method == 'GET':
        bookings_qs = EventBooking.objects.all()
        
        # Date Filter
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if start_date_str and end_date_str:
            try:
                from datetime import datetime
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                
                from django.db.models import Q
                bookings_qs = bookings_qs.filter(
                    Q(created_date__range=[start_dt, end_dt]) | Q(created_at__range=[start_dt, end_dt])
                )
            except Exception as e:
                print(f"Date filter error: {e}")
                
        bookings_list = list(bookings_qs)
        try:
            bookings_list.sort(key=lambda b: getattr(b, 'created_date', None) or getattr(b, 'created_at', None) or '', reverse=True)
        except Exception:
            pass

        serializer = EventBookingSerializer(bookings_list, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        auth_user_id = get_auth_user(request)
        serializer = EventBookingSerializer(data=request.data)
        if serializer.is_valid():
            booking = serializer.save(created_by=str(auth_user_id))
            # Send WhatsApp confirmation
            try:
                send_event_confirmation(booking)
            except Exception as e:
                print(f"WhatsApp notification failed: {e}")
                
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
