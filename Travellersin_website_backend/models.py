from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import uuid
from .fields import SafeJSONField
from .utils import get_model_first


class AuditModel(models.Model):
    created_by = models.CharField(max_length=100, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    @property
    def created_at(self):
        return self.created_date

    @created_at.setter
    def created_at(self, value):
        self.created_date = value

    @property
    def lastmodified_at(self):
        return self.lastmodified_date

    @lastmodified_at.setter
    def lastmodified_at(self, value):
        self.lastmodified_date = value

    @property
    def updated_at(self):
        return self.lastmodified_date

    @updated_at.setter
    def updated_at(self, value):
        self.lastmodified_date = value

    def save(self, *args, **kwargs):
        if self.pk:
            self.lastmodified_date = timezone.now()
        super().save(*args, **kwargs)


class Rooms(AuditModel):
    room_number = models.CharField(max_length=10, primary_key=True)
    room_type = models.CharField(max_length=50)
    size = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    bed_details = SafeJSONField(default=dict)  
    amenities = SafeJSONField(default=list)
    about = models.TextField(blank=True)
    images = SafeJSONField(default=list)
    offers = SafeJSONField(default=dict, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default="active")  # "active" or "maintenance"

    def save(self, *args, **kwargs):
        # Sync is_active and status
        if not self.is_active or self.status in ["maintenance", "inactive"]:
            self.is_active = False
            self.status = "maintenance"
        else:
            self.is_active = True
            self.status = "active"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Room {self.room_number} - {self.room_type}"


class Event(AuditModel):
    event_name = models.CharField(max_length=100)
    size = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    amenities = SafeJSONField(default=list)
    about = models.TextField()
    images = SafeJSONField(default=list)
    offers = SafeJSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return self.event_name


class Query(AuditModel):
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

    def save(self, *args, **kwargs):
        if not self.query_id:
            self.query_id = f"QRY-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.query_id} - {self.name} - {self.subject}"


class Company(AuditModel):
    company_id = models.CharField(
        max_length=30,
        unique=True,
        primary_key=True,
        editable=False
    )
    company_name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    company_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    gst_no = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.company_id:
            from .Views.companies import generate_company_id
            self.company_id = generate_company_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_id} - {self.company_name}"


class Customer(AuditModel):
    customer_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    id_proof_type = models.CharField(max_length=50, blank=True, null=True)
    id_proof_number = models.CharField(max_length=50, blank=True, null=True)
    id_proof_file = models.CharField(max_length=200, blank=True, null=True)

    password = models.CharField(max_length=255, blank=True, null=True)  # hashed password

    def save(self, *args, **kwargs):
        if not self.customer_id:
            from .Views.customers import generate_customer_id
            self.customer_id = generate_customer_id()

        # Hash password only if provided and not already hashed
        if self.password:
            if not self.password.startswith("pbkdf2_"):
                self.password = make_password(self.password)
        else:
            self.password = None

        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.customer_id} - {self.name}"

    @property
    def is_authenticated(self):
        return True


class Booking(AuditModel):
    booking_id = models.CharField(max_length=30, primary_key=True)

    # Primary reference to Customer model
    customer_id = models.CharField(max_length=100, blank=True, null=True)

    # Primary reference to Company model
    company_id = models.CharField(max_length=50, blank=True, null=True)

    room_details = SafeJSONField(default=list)  # [{"roomNo": "101", "isActive": true, "isCleaned": null}]
    number_of_guests = models.PositiveIntegerField(default=1)

    check_in = models.DateTimeField()
    check_out = models.DateTimeField()

    guest_check_in = models.DateTimeField(null=True, blank=True)
    guest_check_out = models.DateTimeField(null=True, blank=True)

    payment_details = SafeJSONField(default=dict)
    tax_details = SafeJSONField(default=dict, blank=True, null=True)

    extra_addons = SafeJSONField(default=list)

    booking_status = models.CharField(
        max_length=20,
        default="pending"
    )
    
    booking_source = models.CharField(
        max_length=20,
        default="online" # "online" or "walk_in"
    )
    
    cancellation_reason = models.TextField(blank=True, null=True)

    discount_amount = models.FloatField(default=0.0)
    discount_remarks = models.TextField(blank=True, null=True)

    bill_type = models.CharField(max_length=20, default="Rack", blank=True, null=True)
    round_off = models.FloatField(default=0.0)
    created_type = models.CharField(max_length=20, blank=True, null=True)

    # Customer delegation properties for seamless access
    @property
    def customer(self):
        if hasattr(self, '_cached_customer'):
            return self._cached_customer
        if self.customer_id:
            c = get_model_first(Customer.objects.filter(customer_id=self.customer_id))
            self._cached_customer = c
            return c
        return None

    # Company delegation properties
    @property
    def company(self):
        if hasattr(self, '_cached_company'):
            return self._cached_company
        if self.company_id:
            comp = get_model_first(Company.objects.filter(company_id=self.company_id))
            self._cached_company = comp
            return comp
        return None

    @property
    def company_details(self):
        comp = self.company
        if comp:
            return {
                "company_id": comp.company_id,
                "company_name": comp.company_name,
                "contact_person": comp.contact_person or "",
                "company_address": comp.company_address or "",
                "city": comp.city or "",
                "state": comp.state or "",
                "pincode": comp.pincode or "",
                "phone": comp.phone or "",
                "gst_no": comp.gst_no or ""
            }
        return {}

    @property
    def guest_name(self):
        c = self.customer
        return c.name if c else ""

    @property
    def guest_phone(self):
        c = self.customer
        return c.phone if c else ""

    @property
    def guest_email(self):
        c = self.customer
        return c.email if c else ""

    @property
    def guest_address(self):
        c = self.customer
        return c.address if c else ""

    @property
    def id_proof_type(self):
        c = self.customer
        return c.id_proof_type if c else ""

    @property
    def id_proof_number(self):
        c = self.customer
        return c.id_proof_number if c else ""

    @property
    def id_proof_file(self):
        c = self.customer
        return c.id_proof_file if c else ""

    @property
    def room_numbers(self):
        if self.room_details and isinstance(self.room_details, list):
            rn_list = []
            for item in self.room_details:
                if isinstance(item, dict) and item.get('roomNo'):
                    rn_list.append(str(item.get('roomNo')).strip())
                elif isinstance(item, (str, int)):
                    rn_list.append(str(item).strip())
            return ",".join(rn_list)
        return ""

    @property
    def food_details(self):
        # Extract food items dynamically from extra_addons
        res = {}
        if self.extra_addons and isinstance(self.extra_addons, list):
            for item in self.extra_addons:
                if isinstance(item, dict) and (item.get("category") == "food" or "food" in str(item.get("id", "")).lower() or item.get("id") in ["breakfast", "lunch", "dinner", "snacks", "tea_coffee", "food_custom"]):
                    item_id = item.get("id") or item.get("name", "food").lower().replace(" ", "_")
                    res[item_id] = {
                        "count": item.get("count", 1),
                        "rate": item.get("rate", item.get("price", 0)),
                        "items": item.get("remarks", ""),
                        "price": item.get("price", 0)
                    }
        return res

    @property
    def amount_paid(self):
        if hasattr(self, '_cached_bills'):
            return sum(float(b.amount_paid or 0) for b in self._cached_bills)
        try:
            return sum(float(b.amount_paid or 0) for b in self.bills.all())
        except Exception:
            return 0.0

    def save(self, *args, **kwargs):
        if not self.booking_id:
            from .Views.bookings import generate_booking_id
            self.booking_id = generate_booking_id()

        # Ensure all JSON fields are never None
        if self.tax_details is None:
            self.tax_details = {}
        if self.payment_details is None:
            self.payment_details = {}
        if self.extra_addons is None:
            self.extra_addons = []
        if self.room_details is None:
            self.room_details = []

        # Ensure room_details is a list of room objects
        import json
        if isinstance(self.room_details, str):
            try:
                self.room_details = json.loads(self.room_details)
            except Exception:
                self.room_details = []

        if isinstance(self.room_details, list):
            normalized_rd = []
            for item in self.room_details:
                if isinstance(item, dict) and item.get('roomNo'):
                    normalized_rd.append({
                        "roomNo": str(item.get('roomNo')).strip(),
                        "isActive": item.get('isActive', True),
                        "isCleaned": item.get('isCleaned', None)
                    })
                elif isinstance(item, (str, int)):
                    normalized_rd.append({
                        "roomNo": str(item).strip(),
                        "isActive": True,
                        "isCleaned": None
                    })
            self.room_details = normalized_rd

        # Enforce Payment Status Consistency & Strip Unwanted Fields
        if self.payment_details:
            try:
                if isinstance(self.payment_details, str):
                    self.payment_details = json.loads(self.payment_details)
                
                if isinstance(self.payment_details, dict):
                    p_details = dict(self.payment_details)
                    unwanted_keys = [
                        'method', 'paid', 'amount_paid', 'latest_billing_no',
                        'transaction_id', 'latest_transaction_id', 'payment_type', 'date'
                    ]
                    for k in unwanted_keys:
                        p_details.pop(k, None)
                    
                    total = float(p_details.get('amount', 0))
                    discount = float(self.discount_amount or 0)
                    net_payable = max(0.0, total - discount)
                    
                    paid = 0.0
                    try:
                        paid = sum(float(b.amount_paid or 0) for b in self.bills.all())
                    except Exception:
                        pass

                    if p_details.get('status') not in ['refunded', 'refund_pending']:
                        if paid >= net_payable and net_payable > 0:
                            p_details['status'] = 'paid'
                        elif paid > 0:
                            p_details['status'] = 'partially_paid'
                        elif not p_details.get('status'):
                            p_details['status'] = 'pending'
                    
                    self.payment_details = p_details
            except (ValueError, TypeError, ImportError):
                pass

        # Populate created_type role if not set
        if not self.created_type:
            from Travellersin_website_backend.middleware import get_current_user
            user = get_current_user()
            if user and getattr(user, 'is_authenticated', False):
                if isinstance(user, Admin):
                    self.created_type = "Admin"
                elif isinstance(user, Customer):
                    self.created_type = "customer"
            else:
                self.created_type = "customer"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_id} - {self.guest_name} ({self.booking_status})"


class Admin(AuditModel):
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

    def save(self, *args, **kwargs):
        if not self.admin_id:
            self.admin_id = f"ADMIN-{uuid.uuid4().hex[:8].upper()}"

        # Hash password only once
        if not self.password.startswith("pbkdf2_"):
            self.password = make_password(self.password)

        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.admin_id} - {self.name}"

    @property
    def is_authenticated(self):
        return True


class CommunicationLog(AuditModel):
    booking_id = models.CharField(max_length=50, blank=True, null=True)
    guest_name = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=20) # e.g., "WhatsApp", "Email"
    recipient = models.CharField(max_length=100)
    status = models.CharField(max_length=20) # e.g., "Success", "Failed"
    details = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.type} to {self.recipient} - {self.status}"


class EventBooking(AuditModel):
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

    def __str__(self):
        return f"{self.booking_id} - {self.name} - {self.event_type}"


class Billing(AuditModel):
    billing_no = models.CharField(max_length=50, primary_key=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='bills')
    
    amount_paid = models.FloatField()
    payment_type = models.CharField(max_length=20, default='cash')

    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    payment_gateway_ref_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, default="success")

    # Razorpay Fields
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.billing_no:
            from .Views.payments import generate_billing_no
            self.billing_no = generate_billing_no(self.created_date or timezone.now())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.billing_no} - {self.booking.booking_id}"


class GalleryCategory(AuditModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Gallery(AuditModel):
    image_id = models.CharField(max_length=100) # GridFS file ID
    
    # Linked to Category Model
    category = models.ForeignKey(GalleryCategory, on_delete=models.CASCADE, related_name='images')
    
    order = models.IntegerField(default=1) # "which 1, 2"
    title = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.category.name} - {self.title or self.image_id}"
