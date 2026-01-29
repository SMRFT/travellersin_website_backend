from rest_framework import serializers
from .models import Rooms, Event, Query, Booking, Customer, Admin, EventBooking, Billing
from django.db.models import Sum

class RoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    
    class Meta:
        model = Rooms
        fields = "__all__"

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
    
    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ["booking_id", "created_at", "lastmodified_at"]

    def get_id(self, obj):
        return str(obj.pk)

    def create(self, validated_data):
        import uuid
        if 'booking_id' not in validated_data or not validated_data['booking_id']:
            validated_data['booking_id'] = f"BK-{uuid.uuid4().hex[:8].upper()}"
        
        # Convert list to comma-separated string for model storage
        if isinstance(validated_data.get('room_numbers'), list):
            # Ensure all items are strings and filter out None
            clean_rooms = [str(r) for r in validated_data['room_numbers'] if r is not None]
            # Using delimiters for safer searching: ,101,102,
            validated_data['room_numbers'] = "," + ",".join(clean_rooms) + ","
            
        return super().create(validated_data)

    def validate(self, data):
        """
        Prevent double booking for all rooms in selection
        """
        room_data = data.get("room_numbers")
        check_in = data.get("check_in")
        check_out = data.get("check_out")

        if not room_data:
            raise serializers.ValidationError("At least one room must be selected")

        if isinstance(room_data, str):
            room_list = [r.strip() for r in room_data.strip(",").split(",") if r.strip()]
        elif isinstance(room_data, list):
            room_list = [str(r) for r in room_data if r is not None]
        else:
            room_list = []

        if check_in >= check_out:
            raise serializers.ValidationError("Check-out must be after check-in")

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

            # 🛠️ EXCLUDE CURRENT BOOKING (For updates)
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                raise serializers.ValidationError(f"Room {room_no} already booked for this date range")

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
            "is_superadmin"
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
        # Sum of all bills linked to this booking
        return obj.booking.bills.aggregate(total=Sum('amount_paid'))['total'] or 0

    def get_guest_name(self, obj):
        return obj.booking.guest_name

    def get_guest_phone(self, obj):
        return obj.booking.guest_phone

    def get_guest_email(self, obj):
        return obj.booking.guest_email
    
    def get_room_numbers(self, obj):
        return obj.booking.room_numbers
