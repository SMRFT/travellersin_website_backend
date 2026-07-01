from rest_framework import serializers
from .models import Rooms, Event, Query, Booking, Customer, Admin, EventBooking, Billing, Gallery, GalleryCategory
from django.db.models import Sum

class RoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    
    class Meta:
        model = Rooms
        fields = "__all__"
        read_only_fields = ["created_by", "lastmodified_by"]

    def get_id(self, obj):
        return str(obj.room_number)

class EventSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = Event
        fields = "__all__"
    
    def get_id(self, obj):
        return str(obj.pk)

class QuerySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = Query
        fields = "__all__"
        read_only_fields = ["query_id", "created_at"]
    def get_id(self, obj):
        return str(obj.pk)

class BookingSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    customer_id = serializers.CharField(max_length=100, required=False, allow_null=True)
    # room_numbers will be handled as a string in the model but we accept list/string in serializer
    room_numbers = serializers.JSONField(required=True)
    discount_amount = serializers.FloatField(required=False, default=0.0)
    bills = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ["booking_id", "created_at", "lastmodified_at", "created_by", "lastmodified_by", "created_type"]

    def get_id(self, obj):
        return str(obj.pk)

    def get_bills(self, obj):
        # Local import to avoid circular dependency/ordering issues
        from .serializers import BillingSerializer 
        # But wait, we are IN serializers.py, so we can't import from .serializers if class isn't defined yet.
        # We need to access the model reverse relation. 
        # Since BillingSerializer is defined BELOW, we can't use it directly here unless we move it UP.
        # Strategy: Define a simple inline serializer or move BillingSerializer UP.
        # Moving BillingSerializer UP is better.
        # For now, let's use a simple manual dict construction to avoid huge diff of moving class.
        return [{
            "billing_no": b.billing_no,
            "amount_paid": b.amount_paid,
            "payment_type": b.payment_type,
            "status": b.status,
            "transaction_id": b.transaction_id,
            "date": b.created_date
        } for b in obj.bills.all().order_by('-created_date')]

    def create(self, validated_data):
        import uuid
        if 'booking_id' not in validated_data or not validated_data['booking_id']:
            validated_data['booking_id'] = f"BK-{uuid.uuid4().hex[:8].upper()}"
        
        # Note: room_numbers formatting is now handled in validate()
        return super().create(validated_data)




    def validate(self, data):
        """
        Prevent double booking for all rooms in selection, handling partial updates.
        """
        instance = self.instance
        
        # Get values from payload or fallback to existing instance values
        room_data = data.get("room_numbers", instance.room_numbers if instance else None)
        check_in = data.get("check_in", instance.check_in if instance else None)
        check_out = data.get("check_out", instance.check_out if instance else None)

        if not room_data:
            raise serializers.ValidationError({"room_numbers": "At least one room must be selected"})
        
        if not check_in or not check_out:
            raise serializers.ValidationError("Check-in and check-out dates are required")

        if check_in >= check_out:
            raise serializers.ValidationError("Check-out must be after check-in")

        # Parse room list for validation
        if isinstance(room_data, str):
            room_list = [r.strip() for r in room_data.strip(",").split(",") if r.strip()]
        elif isinstance(room_data, list):
            room_list = [str(r) for r in room_data if r is not None]
        else:
            room_list = []

        # Check availability for each room
        for room_no in room_list:
            # We search for the room_no surrounded by commas to avoid partial matches
            search_pattern = f",{room_no},"
            overlapping = Booking.objects.filter(
                room_numbers__icontains=search_pattern,
                check_in__lt=check_out,
                check_out__gt=check_in,
                booking_status__in=["confirmed", "pending"]
            )

            if instance:
                overlapping = overlapping.exclude(pk=instance.pk)

            if overlapping.exists():
                conflict = overlapping.first()
                raise serializers.ValidationError(f"Room {room_no} already booked for this date range (Conflict: {conflict.booking_id})")


        # Format room_numbers for consistent storage (Comma-separated string)
        # We update 'data' so it's used in both create and update
        if isinstance(room_data, list):
            clean_rooms = [str(r).strip() for r in room_data if r is not None]
            data['room_numbers'] = "," + ",".join(clean_rooms) + ","
        elif isinstance(room_data, str):
            cleaned = room_data.strip(',')
            if cleaned:
                data['room_numbers'] = f",{cleaned},"
            else:
                data['room_numbers'] = ""

        return data


class CustomerSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = Customer
        fields = ["id", "customer_id", "name", "phone", "email", "password"]
        extra_kwargs = {
            "password": {"write_only": True}  # 🔐 never return password
        }

    def get_id(self, obj):
        return str(obj.pk)

    def create(self, validated_data):
        password = validated_data.pop("password")
        customer = Customer(**validated_data)
        customer.password = password  # hashed in model.save()
        customer.save()
        return customer

class AdminSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = Admin
        fields = [
            "id",
            "admin_id",
            "name",
            "phone",
            "email",
            "password",
            "is_active",
            "is_superadmin",
            "created_by",
            "lastmodified_by",
            "created_at",
            "lastmodified_at"
        ]
        read_only_fields = [
            "admin_id",
            "created_by",
            "lastmodified_by",
            "created_at",
            "lastmodified_at"
        ]
        extra_kwargs = {
            "password": {"write_only": True}
        }

    def get_id(self, obj):
        return str(obj.pk)

    def create(self, validated_data):
        admin = Admin(**validated_data)
        admin.save()  # password hashed in model.save()
        return admin

class EventBookingSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = EventBooking
        fields = "__all__"
        read_only_fields = ["booking_id", "created_at"]

    def get_id(self, obj):
        return str(obj.pk)

    def create(self, validated_data):
        import uuid
        if 'booking_id' not in validated_data or not validated_data['booking_id']:
            validated_data['booking_id'] = f"EVT-{uuid.uuid4().hex[:8].upper()}"
        return super().create(validated_data)

class BillingSerializer(serializers.ModelSerializer):
    total_booking_paid = serializers.SerializerMethodField()
    guest_name = serializers.SerializerMethodField()
    guest_phone = serializers.SerializerMethodField()
    guest_email = serializers.SerializerMethodField()
    room_numbers = serializers.SerializerMethodField()

    class Meta:
        model = Billing
        fields = "__all__"

    def get_total_booking_paid(self, obj):
        try:
            # Sum of all bills linked to this booking
            return obj.booking.bills.aggregate(total=Sum('amount_paid'))['total'] or 0
        except Exception:
            return 0

    def get_guest_name(self, obj):
        try:
            return obj.booking.guest_name
        except Exception:
            return "Deleted Booking"

    def get_guest_phone(self, obj):
        try:
            return obj.booking.guest_phone
        except Exception:
            return "N/A"

    def get_guest_email(self, obj):
        try:
            return obj.booking.guest_email
        except Exception:
            return "N/A"
    
    def get_room_numbers(self, obj):
        try:
            return obj.booking.room_numbers
        except Exception:
            return "N/A"

class GalleryCategorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = GalleryCategory
        fields = "__all__"
    
    def get_id(self, obj):
        return str(obj.pk)

class GallerySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Gallery
        fields = "__all__"

    def get_id(self, obj):
        return str(obj.pk)
