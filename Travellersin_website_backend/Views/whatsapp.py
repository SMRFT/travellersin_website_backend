import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from ..models import Booking, CommunicationLog, EventBooking
from django.utils import timezone

def send_booking_confirmation(booking):
    """
    WhatsApp communication is currently disabled.
    """
    return True

def send_event_confirmation(booking):
    """
    WhatsApp communication is currently disabled.
    """
    return True

@api_view(["POST"])
def send_whatsapp_test(request):
    """
    Test endpoint for manual WhatsApp sending
    """
    booking_id = request.data.get("booking_id")
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        success = send_booking_confirmation(booking)
        if success:
            return Response({"success": True, "message": "WhatsApp sent"})
        return Response({"success": False, "message": "WhatsApp failed"}, status=400)
    except Booking.DoesNotExist:
        return Response({"success": False, "error": "Booking not found"}, status=404)
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=500)