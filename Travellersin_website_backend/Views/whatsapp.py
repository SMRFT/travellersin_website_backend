import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from ..models import Booking, CommunicationLog, EventBooking
from django.utils import timezone

def send_booking_confirmation(booking):
    """
    Utility function to send WhatsApp confirmation using Botify API
    """
    try:
        api_key = ""
        botify_url = "https://dashboard.botify.in/api/v1/external/sendtemplatemessage"
        
        phone = str(booking.guest_phone).strip()
        if not phone.startswith("91") and len(phone) == 10:
            phone = f"91{phone}"
            
        # Template variables order:
        # 1. {{Name}}
        # 2. {{booking_id}}
        # 3. {{booking_date}}
        # 4. {{check_in_time}}
        # 5. {{check_out_time}}
        # 6. {{PHONE_NUMBER}}
        
        template_params_list = [
            booking.guest_name or "Valued Guest",
            booking.booking_id,
            booking.created_at.strftime('%d-%m-%Y'),
            booking.check_in.strftime('%d-%m-%Y %I:%M %p'),
            booking.check_out.strftime('%d-%m-%Y %I:%M %p'),
            booking.guest_phone or "N/A"
        ]
        
        template_params = ",".join([str(p) for p in template_params_list])
        
        params = {
            "apikey": api_key,
            "contact": phone,
            "template": "travellersinn_welcome_customer1_template",
            "params": template_params,
        }
        
        r = requests.get(botify_url, params=params, timeout=20)
        
        try:
            response_json = r.json()
            is_success = r.status_code == 200 and response_json.get("success") is True
        except ValueError:
            response_json = {}
            is_success = False
            
        status = "Success" if is_success else "Failed"
        
        # Log communication
        CommunicationLog.objects.create(
            booking_id=booking.booking_id,
            guest_name=booking.guest_name,
            type="WhatsApp",
            recipient=phone,
            status=status,
            details=r.text
        )
        
        return is_success
    except Exception as e:
        print(f"WhatsApp Error: {str(e)}")
        try:
            CommunicationLog.objects.create(
                booking_id=booking.booking_id,
                guest_name=booking.guest_name,
                type="WhatsApp",
                recipient=str(booking.guest_phone),
                status="Failed",
                details=str(e)
            )
        except:
            pass
        return False

def send_event_confirmation(booking):
    """
    Utility function to send WhatsApp confirmation for Event Bookings using Botify API
    """
    try:
        api_key = ""
        botify_url = "https://dashboard.botify.in/api/v1/external/sendtemplatemessage"
        
        phone = str(booking.phone).strip()
        if not phone.startswith("91") and len(phone) == 10:
            phone = f"91{phone}"
            
        # Template variables order:
        # 1. {{name}}
        # 2. {{booking_id}}
        # 3. {{event_type}}
        # 4. {{event_date}}
        # 5. {{number_of_guests}}
        # 6. {{phone}}
        # 7. {{status}}
        
        template_params_list = [
            booking.name or "Valued Guest",
            booking.booking_id,
            booking.event_type,
            booking.event_date.strftime('%d-%m-%Y %I:%M %p'),
            booking.number_of_guests,
            booking.phone or "N/A",
            booking.status.upper()
        ]
        
        template_params = ",".join([str(p) for p in template_params_list])
        
        params = {
            "apikey": api_key,
            "contact": phone,
            "template": "travellersin_event",
            "params": template_params,
        }
        
        r = requests.get(botify_url, params=params, timeout=20)
        
        try:
            response_json = r.json()
            is_success = r.status_code == 200 and response_json.get("success") is True
        except ValueError:
            response_json = {}
            is_success = False
            
        status = "Success" if is_success else "Failed"
        
        # Log communication
        CommunicationLog.objects.create(
            booking_id=booking.booking_id,
            guest_name=booking.name,
            type="WhatsApp",
            recipient=phone,
            status=status,
            details=r.text
        )
        
        return is_success
    except Exception as e:
        print(f"WhatsApp Error: {str(e)}")
        try:
            CommunicationLog.objects.create(
                booking_id=booking.booking_id,
                guest_name=booking.name,
                type="WhatsApp",
                recipient=str(booking.phone),
                status="Failed",
                details=str(e)
            )
        except:
            pass
        return False

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