import os
import django
import sys

# Setup Django
sys.path.append(r'c:\Users\Manib\Desktop\Sample Project smrft\TravellerIN_Wesite\travellersin_website_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travellerin_backend.settings')
django.setup()

from Travellersin_website_backend.models import Booking

def normalize_rooms():
    bookings = Booking.objects.all()
    count = 0
    for b in bookings:
        original = b.room_numbers or ""
        # Parse and re-format
        rooms = [r.strip() for r in original.strip(",").split(",") if r.strip()]
        if not rooms:
            normalized = ""
        else:
            normalized = "," + ",".join(rooms) + ","
            
        if original != normalized:
            print(f"Normalizing {b.booking_id}: '{original}' -> '{normalized}'")
            b.room_numbers = normalized
            b.save()
            count += 1
            
    print(f"\nSuccessfully normalized {count} bookings.")

if __name__ == "__main__":
    normalize_rooms()
