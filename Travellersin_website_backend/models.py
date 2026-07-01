from django.db import models
from django.contrib.auth.hashers import make_password, check_password
# Create your models here.
import uuid

class Rooms(models.Model):
    room_number = models.CharField(max_length=10, primary_key=True)
    room_type = models.CharField(max_length=50)
    size = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    bed_details = models.JSONField(default=dict)  
    # example: {"size": "King", "type": "Single"}

    amenities = models.JSONField(default=list)
    # example: ["AC", "WiFi", "TV"]

    about = models.TextField(blank=True)

    images = models.JSONField(default=list)
    # store GridFS file IDs as strings

    offers = models.JSONField(default=dict, blank=True, null=True)
    # example: {"discount_percent": 10, "description": "Weekday offer"}

    status = models.CharField(max_length=20, default="active")  # "active" or "inactive"

    created_by = models.CharField(max_length=50, blank=True, null=True)
    lastmodified_by = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Populate Audit Fields
        from Travellersin_website_backend.middleware import get_current_user
        user = get_current_user()
        phone_num = getattr(user, 'phone', None) if user else None

        is_new = self._state.adding or not Rooms.objects.filter(pk=self.pk).exists()
        if is_new:
            if phone_num and not self.created_by:
                self.created_by = phone_num
        
        if phone_num:
            self.lastmodified_by = phone_num

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Room {self.room_number}"

class Event(models.Model):
    event_name = models.CharField(max_length=100)
    size = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    amenities = models.JSONField(default=list)
    about = models.TextField()

    images = models.JSONField(default=list)
    # GridFS file IDs

    offers = models.JSONField(default=dict, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_name

class Query(models.Model):
    STATUS_CHOICES = (
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    )

    query_id = models.CharField(max_length=20, primary_key=True, editable=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15)
    subject = models.CharField(max_length=150)
    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.query_id:
            self.query_id = f"QRY-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.query_id} - {self.name} - {self.subject}"

class Booking(models.Model):
    booking_id = models.CharField(max_length=30, primary_key=True)

    customer_id = models.CharField(max_length=100, blank=True, null=True)
    guest_name = models.CharField(max_length=100, blank=True, null=True)
    guest_phone = models.CharField(max_length=15, blank=True, null=True)
    guest_email = models.EmailField(blank=True, null=True)

    room_numbers = models.CharField(max_length=200, default="")  # Comma-separated: "101,102"
    number_of_guests = models.PositiveIntegerField()

    check_in = models.DateTimeField()
    check_out = models.DateTimeField()

    payment_details = models.JSONField(default=dict)

    id_proof_type = models.CharField(max_length=50, blank=True, null=True)
    id_proof_number = models.CharField(max_length=50, blank=True, null=True)
    id_proof_file = models.CharField(max_length=100, blank=True, null=True)

    extra_addons = models.JSONField(default=list)

    booking_status = models.CharField(
        max_length=20,
        default="pending"
    )
    
    booking_source = models.CharField(
        max_length=20,
        default="online" # "online" or "manual"
    )
    
    cancellation_reason = models.TextField(blank=True, null=True)

    discount_amount = models.FloatField(default=0.0)
    guest_address = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    lastmodified_at = models.DateTimeField(auto_now=True)

    created_by = models.CharField(max_length=50, blank=True, null=True)
    lastmodified_by = models.CharField(max_length=50, blank=True, null=True)
    created_type = models.CharField(max_length=20, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Enforce Payment Status Consistency
        if self.payment_details:
            try:
                # Ensure we are working with a dict
                if isinstance(self.payment_details, str):
                    import json
                    self.payment_details = json.loads(self.payment_details)
                
                p_details = self.payment_details
                total = float(p_details.get('amount', 0))
                paid = float(p_details.get('amount_paid', 0))
                discount = float(self.discount_amount or 0)
                
                net_payable = total - discount
                # Avoid negative net payable
                if net_payable < 0: net_payable = 0
                
                # Determine status
                new_status = 'pending'
                if paid >= net_payable:
                    new_status = 'paid'
                elif paid > 0:
                    new_status = 'partially_paid'
                
                # Update status in payment_details
                p_details['status'] = new_status
                self.payment_details = p_details
            except (ValueError, TypeError, ImportError):
                # If JSON parsing fails or types are wrong, skip validation to avoid breaking save
                pass

        # Populate Audit Fields (created_by, lastmodified_by, created_type)
        from Travellersin_website_backend.middleware import get_current_user
        from Travellersin_website_backend.models import Admin, Customer

        user = get_current_user()
        role = "customer"  # Default to customer role
        phone_num = None

        if user and user.is_authenticated:
            if isinstance(user, Admin):
                role = "Admin"
                phone_num = getattr(user, 'phone', None)
            elif isinstance(user, Customer):
                role = "customer"
                phone_num = getattr(user, 'phone', None)

        is_new = self._state.adding or not Booking.objects.filter(pk=self.pk).exists()
        if is_new:
            if role and not self.created_type:
                self.created_type = role
            if phone_num and not self.created_by:
                self.created_by = phone_num
        
        if phone_num:
            self.lastmodified_by = phone_num
        
        super().save(*args, **kwargs)


class Customer(models.Model):
    customer_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)  # NOT mandatory

    password = models.CharField(max_length=255)  # hashed password

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = f"CUST-{uuid.uuid4().hex[:8].upper()}"

        # 🔐 Hash password only if it is not already hashed
        if not self.password.startswith("pbkdf2_"):
            self.password = make_password(self.password)

        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.customer_id} - {self.name}"

    @property
    def is_authenticated(self):
        return True


class Admin(models.Model):
    admin_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)  # optional
    password = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)

    created_by = models.CharField(max_length=50, blank=True, null=True)
    lastmodified_by = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    lastmodified_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.admin_id:
            self.admin_id = f"ADMIN-{uuid.uuid4().hex[:8].upper()}"

        # 🔐 Hash password only once
        if not self.password.startswith("pbkdf2_"):
            self.password = make_password(self.password)

        # Populate Audit Fields
        from Travellersin_website_backend.middleware import get_current_user
        user = get_current_user()
        phone_num = getattr(user, 'phone', None) if user else None

        is_new = self._state.adding or not Admin.objects.filter(pk=self.pk).exists()
        if is_new:
            if phone_num and not self.created_by:
                self.created_by = phone_num
        
        if phone_num:
            self.lastmodified_by = phone_num

        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.admin_id} - {self.name}"

    @property
    def is_authenticated(self):
        return True

class CommunicationLog(models.Model):
    booking_id = models.CharField(max_length=50, blank=True, null=True)
    guest_name = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=20) # e.g., "WhatsApp", "Email"
    recipient = models.CharField(max_length=100)
    status = models.CharField(max_length=20) # e.g., "Success", "Failed"
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} to {self.recipient} - {self.status}"

class EventBooking(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
    )

    booking_id = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    
    event_type = models.CharField(max_length=100)
    event_date = models.DateTimeField()
    number_of_guests = models.PositiveIntegerField()
    message = models.TextField(blank=True, null=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking_id} - {self.name} - {self.event_type}"

class Billing(models.Model):
    billing_no = models.CharField(max_length=50, primary_key=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='bills')
    
    amount_paid = models.FloatField()
    total_amount = models.FloatField()
    payment_type = models.CharField(max_length=20, default='cash')

    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    payment_gateway_ref_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, default="success")

    # Razorpay Fields
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.billing_no} - {self.booking.booking_id}"

class GalleryCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Gallery(models.Model):
    image_id = models.CharField(max_length=100) # GridFS file ID
    
    # Linked to Category Model
    category = models.ForeignKey(GalleryCategory, on_delete=models.CASCADE, related_name='images')
    
    order = models.IntegerField(default=1) # "which 1, 2"
    title = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category.name} - {self.title or self.image_id}"
