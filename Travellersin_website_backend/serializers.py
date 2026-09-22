from rest_framework import serializers
from .models import Rooms, Event, Query, Booking, Customer, Company, Admin, EventBooking, Billing, Gallery, GalleryCategory, MenuItems
from django.db.models import Sum, Q
from django.utils import timezone


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItems
        fields = ["item_id", "item_name", "rate", "is_active"]


class CompanySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "company_id",
            "company_name",
            "contact_person",
            "company_address",
            "city",
            "state",
            "pincode",
            "phone",
            "gst_no",
            "created_by",
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
            "created_at",
            "lastmodified_at"
        ]
        read_only_fields = [
            "company_id",
            "created_by",
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
            "created_at",
            "lastmodified_at"
        ]

    def get_id(self, obj):
        return str(obj.company_id)


class RoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    
    class Meta:
        model = Rooms
        fields = "__all__"
        read_only_fields = ["created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at", "lastmodified_at", "updated_at"]

    def get_id(self, obj):
        return str(obj.room_number)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        import json
        import ast
        from collections import OrderedDict

        def clean_value(val):
            if val is None:
                return None
            if isinstance(val, (dict, OrderedDict)):
                return dict(val)
            if isinstance(val, list):
                return [clean_value(x) for x in val]
            if isinstance(val, str):
                s = val.strip()
                if not s:
                    return None
                if s.startswith("OrderedDict(") and s.endswith(")"):
                    s = s[12:-1]
                try:
                    return json.loads(s)
                except Exception:
                    try:
                        res = ast.literal_eval(s)
                        if isinstance(res, (dict, list, OrderedDict)):
                            return clean_value(res)
                    except Exception:
                        return val
            return val

        for field in ['bed_details', 'amenities', 'images', 'offers']:
            val = getattr(instance, field, None) or ret.get(field)
            cleaned = clean_value(val)
            if field in ['amenities', 'images']:
                ret[field] = cleaned if isinstance(cleaned, list) else ([cleaned] if cleaned else [])
            else:
                ret[field] = cleaned if isinstance(cleaned, dict) else (cleaned or {})

        request = self.context.get('request')
        
        # Format images to absolute loadable URLs
        if 'images' in ret and isinstance(ret['images'], list):
            formatted_images = []
            for img in ret['images']:
                if not img:
                    continue
                img_str = str(img).strip()
                # Clean local dev hostnames
                if '127.0.0.1:1919' in img_str or 'localhost:1919' in img_str or 'localhost:3000' in img_str or 'localhost:3001' in img_str:
                    import re
                    m = re.search(r'media/gridfs/([^/]+)', img_str)
                    if m:
                        img_str = m.group(1)
                    else:
                        import re
                        img_str = re.sub(r'^https?://[^/]+', '', img_str)

                if (img_str.startswith('http://') or img_str.startswith('https://')) and not ('127.0.0.1' in img_str or 'localhost' in img_str):
                    formatted_images.append(img_str)
                elif img_str.startswith('data:'):
                    formatted_images.append(img_str)
                else:
                    if 'media/gridfs/' in img_str:
                        file_id = img_str.split('media/gridfs/')[-1].strip('/')
                        path = f"/_b_a_c_k_e_n_d/travellerinwebsite/media/gridfs/{file_id}/"
                    elif not '/' in img_str:
                        path = f"/_b_a_c_k_e_n_d/travellerinwebsite/media/gridfs/{img_str}/"
                    else:
                        path = img_str if img_str.startswith('/') else f"/{img_str}"
                        if not path.startswith('/_b_a_c_k_e_n_d/travellerinwebsite/'):
                            path = f"/_b_a_c_k_e_n_d/travellerinwebsite{path}"

                    if request:
                        uri = request.build_absolute_uri(path)
                        if 'test.shinova.in' in uri or 'shinova.in' in uri:
                            uri = uri.replace('http://', 'https://')
                        formatted_images.append(uri)
                    else:
                        formatted_images.append(path)
            ret['images'] = formatted_images
            
        return ret

    def to_internal_value(self, data):
        # Normalize mutable dict from request data
        if hasattr(data, "dict"):
            data_dict = data.dict()
        else:
            data_dict = dict(data)

        # Map common frontend alias fields to model fields
        if "price_per_night" in data_dict and "price" not in data_dict:
            data_dict["price"] = data_dict.pop("price_per_night")
        if "description" in data_dict and "about" not in data_dict:
            data_dict["about"] = data_dict.pop("description")
        if "capacity" in data_dict and "size" not in data_dict:
            data_dict["size"] = str(data_dict.pop("capacity"))
        if "is_active" in data_dict and "status" not in data_dict:
            is_act = data_dict.pop("is_active")
            data_dict["status"] = "active" if is_act else "inactive"

        return super().to_internal_value(data_dict)

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
        read_only_fields = ["query_id", "created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at"]
    def get_id(self, obj):
        return str(obj.pk)

class BookingSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    customer_id = serializers.CharField(max_length=100, required=False, allow_null=True)
    company_id = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    
    # Guest and Company details accepted on write, resolved from Customer/Company on read
    guest_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    guest_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    guest_email = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    guest_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    company_details = serializers.JSONField(required=False, allow_null=True, default=dict)
    id_proof_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    id_proof_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    id_proof_file = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    room_numbers = serializers.JSONField(required=False, allow_null=True)
    room_details = serializers.JSONField(required=False, default=list)
    tax_details = serializers.JSONField(required=False, allow_null=True, default=dict)
    discount_amount = serializers.FloatField(required=False, default=0.0)
    discount_remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bills = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ["booking_id", "created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at", "lastmodified_at", "created_type"]

    def get_id(self, obj):
        return str(obj.pk)

    def get_bills(self, obj):
        try:
            bills_map = self.context.get('bills_map') if self.context else None
            if bills_map is not None:
                bills_list = bills_map.get(str(obj.booking_id), [])
            else:
                bills_list = list(obj.bills.all())
                bills_list.sort(key=lambda b: getattr(b, 'created_date', None) or '', reverse=True)
            return [{
                "billing_no": b.billing_no,
                "amount_paid": b.amount_paid,
                "payment_type": b.payment_type,
                "card_type": getattr(b, 'card_type', None),
                "status": b.status,
                "transaction_id": b.transaction_id,
                "date": b.created_date
            } for b in bills_list]
        except Exception:
            return []

    def to_internal_value(self, data):
        if hasattr(data, "dict"):
            data_dict = data.dict()
        else:
            data_dict = dict(data)
        
        # Strip trailing 'Z' or '+00:00' from check_in / check_out so they are parsed in local hotel time (IST)
        for field in ['check_in', 'check_out']:
            if field in data_dict and isinstance(data_dict[field], str):
                val = data_dict[field].strip()
                if val.endswith('Z') or val.endswith('z'):
                    data_dict[field] = val[:-1]
                elif val.endswith('+00:00'):
                    data_dict[field] = val[:-6]
        return super().to_internal_value(data_dict)

    def create(self, validated_data):
        from .Views.bookings import generate_booking_id
        from .Views.customers import sync_or_create_customer
        from .Views.companies import sync_or_create_company
        
        # Extract guest & customer details to sync into Customer model
        g_name = validated_data.pop('guest_name', None)
        g_phone = validated_data.pop('guest_phone', None)
        g_email = validated_data.pop('guest_email', None)
        g_address = validated_data.pop('guest_address', None)
        c_details = validated_data.pop('company_details', None)
        id_type = validated_data.pop('id_proof_type', None)
        id_num = validated_data.pop('id_proof_number', None)
        id_file = validated_data.pop('id_proof_file', None)
        cust_id = validated_data.get('customer_id', None)
        comp_id = validated_data.get('company_id', None)

        validated_data.pop('food_details', None)
        validated_data.pop('rent_details', None)
        
        r_nums = validated_data.pop('room_numbers', None)
        if r_nums and not validated_data.get('room_details'):
            if isinstance(r_nums, str):
                rn_list = [r.strip() for r in r_nums.split(',') if r.strip()]
            elif isinstance(r_nums, list):
                rn_list = [str(r).strip() for r in r_nums if str(r).strip()]
            else:
                rn_list = []
            validated_data['room_details'] = [{"roomNo": r, "isActive": True, "isCleaned": None} for r in rn_list]

        cust = sync_or_create_customer(
            name=g_name,
            phone=g_phone,
            email=g_email,
            address=g_address,
            id_proof_type=id_type,
            id_proof_number=id_num,
            id_proof_file=id_file,
            customer_id=cust_id
        )

        if cust:
            validated_data['customer_id'] = cust.customer_id

        # Sync or create company
        if c_details or comp_id:
            if isinstance(c_details, dict) and (c_details.get('company_name') or comp_id or c_details.get('company_id')):
                comp = sync_or_create_company(
                    company_id=comp_id or c_details.get('company_id'),
                    company_name=c_details.get('company_name'),
                    contact_person=c_details.get('contact_person') or c_details.get('company_person'),
                    company_address=c_details.get('company_address') or c_details.get('address'),
                    city=c_details.get('city') or c_details.get('company_city'),
                    state=c_details.get('state') or c_details.get('company_state'),
                    pincode=c_details.get('pincode') or c_details.get('company_pincode'),
                    phone=c_details.get('phone') or c_details.get('company_phone'),
                    gst_no=c_details.get('gst_no') or c_details.get('company_gst'),
                )
                if comp:
                    validated_data['company_id'] = comp.company_id
            elif comp_id:
                validated_data['company_id'] = comp_id

        if 'booking_id' not in validated_data or not validated_data['booking_id']:
            validated_data['booking_id'] = generate_booking_id()

        # Ensure tax_details and bill_type are properly populated
        tax_details = validated_data.get('tax_details')
        if not tax_details or not isinstance(tax_details, dict):
            b_type = validated_data.get('bill_type') or ("Net Rate" if validated_data.get('booking_source') == 'online' else "Rack")
            validated_data['bill_type'] = b_type
            raw_pd = validated_data.get('payment_details') or {}
            subtotal = float(raw_pd.get('amount') or 0.0)
            if b_type == "Net Rate":
                taxable = round(subtotal / 1.05, 2) if subtotal > 0 else 0.0
                ttax = round(subtotal - taxable, 2)
                cgst = round(ttax / 2, 2)
                sgst = round(ttax / 2, 2)
                validated_data['tax_details'] = {
                    "bill_type": "Net Rate",
                    "subtotal": subtotal,
                    "taxable_amount": taxable,
                    "cgst_rate": 2.5,
                    "cgst_amount": cgst,
                    "sgst_rate": 2.5,
                    "sgst_amount": sgst,
                    "total_tax": ttax,
                    "round_off": 0.0,
                    "gross_total": subtotal
                }
            else:
                cgst = round(subtotal * 0.025, 2)
                sgst = round(subtotal * 0.025, 2)
                ttax = round(cgst + sgst, 2)
                validated_data['tax_details'] = {
                    "bill_type": "Rack",
                    "subtotal": subtotal,
                    "taxable_amount": subtotal,
                    "cgst_rate": 2.5,
                    "cgst_amount": cgst,
                    "sgst_rate": 2.5,
                    "sgst_amount": sgst,
                    "total_tax": ttax,
                    "round_off": 0.0,
                    "gross_total": round(subtotal + ttax, 2)
                }

        # Auto set actual guest check in/out timestamps if applicable
        st = str(validated_data.get('booking_status', '')).lower().replace('_', ' ').strip()
        if st in ['checked in', 'checked_in'] and not validated_data.get('guest_check_in'):
            validated_data['guest_check_in'] = timezone.now()
        elif st in ['checked out', 'checked_out'] and not validated_data.get('guest_check_out'):
            validated_data['guest_check_out'] = timezone.now()

        return super().create(validated_data)

    def update(self, instance, validated_data):
        from .Views.customers import sync_or_create_customer
        from .Views.companies import sync_or_create_company
        
        g_name = validated_data.pop('guest_name', None)
        g_phone = validated_data.pop('guest_phone', None)
        g_email = validated_data.pop('guest_email', None)
        g_address = validated_data.pop('guest_address', None)
        c_details = validated_data.pop('company_details', None)
        id_type = validated_data.pop('id_proof_type', None)
        id_num = validated_data.pop('id_proof_number', None)
        id_file = validated_data.pop('id_proof_file', None)
        cust_id = validated_data.get('customer_id', instance.customer_id)
        comp_id = validated_data.get('company_id', instance.company_id)

        validated_data.pop('food_details', None)
        validated_data.pop('rent_details', None)

        r_nums = validated_data.pop('room_numbers', None)
        if r_nums and not validated_data.get('room_details'):
            if isinstance(r_nums, str):
                rn_list = [r.strip() for r in r_nums.split(',') if r.strip()]
            elif isinstance(r_nums, list):
                rn_list = [str(r).strip() for r in r_nums if str(r).strip()]
            else:
                rn_list = []
            validated_data['room_details'] = [{"roomNo": r, "isActive": True, "isCleaned": None} for r in rn_list]

        if any([g_name, g_phone, g_email, g_address, id_type, id_num, id_file]):
            cust = sync_or_create_customer(
                name=g_name,
                phone=g_phone,
                email=g_email,
                address=g_address,
                id_proof_type=id_type,
                id_proof_number=id_num,
                id_proof_file=id_file,
                customer_id=cust_id
            )
            if cust:
                validated_data['customer_id'] = cust.customer_id

        # Sync or create company
        if c_details is not None or comp_id != instance.company_id:
            if isinstance(c_details, dict) and (c_details.get('company_name') or comp_id or c_details.get('company_id')):
                comp = sync_or_create_company(
                    company_id=comp_id or c_details.get('company_id'),
                    company_name=c_details.get('company_name'),
                    contact_person=c_details.get('contact_person') or c_details.get('company_person'),
                    company_address=c_details.get('company_address') or c_details.get('address'),
                    city=c_details.get('city') or c_details.get('company_city'),
                    state=c_details.get('state') or c_details.get('company_state'),
                    pincode=c_details.get('pincode') or c_details.get('company_pincode'),
                    phone=c_details.get('phone') or c_details.get('company_phone'),
                    gst_no=c_details.get('gst_no') or c_details.get('company_gst'),
                )
                if comp:
                    validated_data['company_id'] = comp.company_id
            elif comp_id:
                validated_data['company_id'] = comp_id

        # Auto set actual guest check in/out timestamps on status change
        st = str(validated_data.get('booking_status', '')).lower().replace('_', ' ').strip()
        if st in ['checked in', 'checked_in'] and not getattr(instance, 'guest_check_in', None) and not validated_data.get('guest_check_in'):
            validated_data['guest_check_in'] = timezone.now()
        elif st in ['checked out', 'checked_out'] and not getattr(instance, 'guest_check_out', None) and not validated_data.get('guest_check_out'):
            validated_data['guest_check_out'] = timezone.now()

        return super().update(instance, validated_data)

    def validate(self, data):
        """
        Prevent double booking for all rooms in selection, handling partial updates.
        """
        instance = self.instance
        import json
        
        # Get room_details or room_numbers from payload / instance
        raw_room_details = data.get("room_details", getattr(instance, "room_details", None) if instance else None)
        raw_room_numbers = data.get("room_numbers", getattr(instance, "room_numbers", None) if instance else None)
        check_in = data.get("check_in", instance.check_in if instance else None)
        check_out = data.get("check_out", instance.check_out if instance else None)

        if isinstance(raw_room_details, str):
            try:
                raw_room_details = json.loads(raw_room_details)
            except Exception:
                raw_room_details = []

        clean_room_objs = []
        if raw_room_details and isinstance(raw_room_details, list):
            for item in raw_room_details:
                if isinstance(item, dict) and item.get("roomNo"):
                    clean_room_objs.append({
                        "roomNo": str(item.get("roomNo")).strip(),
                        "isActive": bool(item.get("isActive", True)),
                        "isCleaned": item.get("isCleaned", None)
                    })
                elif item is not None:
                    clean_room_objs.append({
                        "roomNo": str(item).strip(),
                        "isActive": True,
                        "isCleaned": None
                    })
        elif raw_room_numbers:
            if isinstance(raw_room_numbers, str):
                rn_list = [r.strip() for r in raw_room_numbers.strip(",").split(",") if r.strip()]
            elif isinstance(raw_room_numbers, list):
                rn_list = [str(r.get("roomNo") if isinstance(r, dict) else r).strip() for r in raw_room_numbers if r]
            else:
                rn_list = []
            clean_room_objs = [{"roomNo": r, "isActive": True, "isCleaned": None} for r in rn_list]

        if not clean_room_objs:
            raise serializers.ValidationError({"room_details": "At least one room must be selected"})
        
        if not check_in or not check_out:
            raise serializers.ValidationError("Check-in and check-out dates are required")

        if timezone.is_naive(check_in):
            check_in = timezone.make_aware(check_in)
        if timezone.is_naive(check_out):
            check_out = timezone.make_aware(check_out)

        if check_in >= check_out:
            raise serializers.ValidationError("Check-out must be after check-in")

        now_dt = timezone.now()
        from datetime import timedelta
        is_immediate = (check_in <= now_dt)
        recent_threshold = now_dt - timedelta(days=2)

        ACTIVE_STATUSES = [
            "confirmed", "Confirmed",
            "checked_in", "checked in", "Checked In", "Checked_In",
            "pending", "Pending", "pending_confirmation", "pending confirmation",
            "booked", "Booked"
        ]

        # Fetch recent and upcoming active bookings
        potential_overlaps = list(Booking.objects.filter(
            booking_status__in=ACTIVE_STATUSES
        ))
        if instance:
            potential_overlaps = [b for b in potential_overlaps if b.pk != instance.pk]

        for b in potential_overlaps:
            b_st = str(b.booking_status or '').lower().replace('_', ' ').strip()
            if b_st in ["checked out", "cancelled", "canceled"]:
                continue
            if b_st not in ["confirmed", "checked in", "pending", "booked", "pending confirmation"]:
                continue

            b_check_in = b.check_in
            b_check_out = b.check_out
            if not b_check_in or not b_check_out:
                continue
            if timezone.is_naive(b_check_in):
                b_check_in = timezone.make_aware(b_check_in)
            if timezone.is_naive(b_check_out):
                b_check_out = timezone.make_aware(b_check_out)

            # Check if this booking actually overlaps with the requested date range [check_in, check_out]
            is_date_overlap = (b_check_in < check_out and b_check_out > check_in)

            # If the booking's scheduled checkout has already passed:
            if b_check_out <= now_dt:
                # It only occupies the room if the guest actually checked in and has NOT checked out yet
                is_inhouse = (b_st in ['checked in', 'occupied'] or (b.guest_check_in is not None and b.guest_check_out is None))
                if not is_inhouse:
                    continue

            # If it's an immediate booking right now and the room has an active in-house guest who hasn't checked out:
            is_inhouse_overstay = (
                is_immediate and
                b.guest_check_in is not None and
                b.guest_check_out is None and
                recent_threshold <= b_check_in <= now_dt and
                b_check_out <= now_dt
            )

            if not (is_date_overlap or is_inhouse_overstay):
                continue

            # Parse room details of the conflicting booking
            b_r_details = b.room_details or []
            if isinstance(b_r_details, str):
                try:
                    import json
                    b_r_details = json.loads(b_r_details)
                except Exception:
                    b_r_details = []

            for active_r in clean_room_objs:
                room_no = str(active_r["roomNo"]).strip()
                if active_r.get("isActive", True):
                    # Check room_details list
                    for b_r in b_r_details:
                        b_r_no = str(b_r.get("roomNo") if isinstance(b_r, dict) else b_r).strip()
                        b_is_active = b_r.get("isActive", True) if isinstance(b_r, dict) else True
                        if b_r_no == room_no and b_is_active:
                            raise serializers.ValidationError(f"Room {room_no} already booked for this date range (Conflict: {b.booking_id})")
                    # Check room_numbers field fallback
                    if b.room_numbers:
                        booked_rn = [r.strip() for r in str(b.room_numbers).strip(',').split(',') if r.strip()]
                        if room_no in booked_rn:
                            raise serializers.ValidationError(f"Room {room_no} already booked for this date range (Conflict: {b.booking_id})")

        # Assign normalized room_details
        data["room_details"] = clean_room_objs

        return data

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        import json
        import ast
        from collections import OrderedDict
        from .models import Customer

        def clean_value(val):
            if val is None:
                return None
            if isinstance(val, (dict, OrderedDict)):
                return dict(val)
            if isinstance(val, list):
                return [clean_value(x) for x in val]
            if isinstance(val, str):
                s = val.strip()
                if not s:
                    return None
                if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                    try:
                        return json.loads(s)
                    except Exception:
                        try:
                            res = ast.literal_eval(s)
                            if isinstance(res, (dict, list, OrderedDict)):
                                return clean_value(res)
                        except Exception:
                            return val
                elif s.startswith("OrderedDict(") and s.endswith(")"):
                    try:
                        res = ast.literal_eval(s)
                        if isinstance(res, (dict, list, OrderedDict)):
                            return clean_value(res)
                    except Exception:
                        return val
                return val
            return val

        # Ensure room_details is list of objects
        inst_st = str(instance.booking_status or '').lower().replace('_', ' ').strip()
        is_checked_out = (inst_st == "checked out")
        r_details = clean_value(getattr(instance, 'room_details', None)) or clean_value(ret.get('room_details'))
        if (not r_details or not isinstance(r_details, list)) and instance.room_numbers:
            rn = instance.room_numbers or ""
            clean_list = [r.strip() for r in rn.strip(",").split(",") if r.strip()]
            r_details = [{"roomNo": r, "isActive": (not is_checked_out), "isCleaned": (True if is_checked_out else None)} for r in clean_list]

        ret['room_details'] = r_details or []
        ret['room_numbers'] = [item.get('roomNo') for item in ret['room_details'] if isinstance(item, dict) and item.get('roomNo')]
        
        cust_map = self.context.get('cust_map') if self.context else None
        comp_map = self.context.get('comp_map') if self.context else None
        bills_map = self.context.get('bills_map') if self.context else None

        # Dynamically attach customer details from Customer model (O(1) with context)
        if cust_map is not None:
            customer = cust_map.get(str(instance.customer_id)) if instance.customer_id else None
        else:
            customer = instance.customer

        if customer:
            ret['guest_name'] = customer.name or ""
            ret['guest_phone'] = customer.phone or ""
            ret['guest_email'] = customer.email or ""
            ret['guest_address'] = customer.address or ""
            ret['id_proof_type'] = customer.id_proof_type or ""
            ret['id_proof_number'] = customer.id_proof_number or ""
            ret['id_proof_file'] = customer.id_proof_file or ""
            ret['customer_id'] = customer.customer_id
        else:
            ret['guest_name'] = ret.get('guest_name') or ""
            ret['guest_phone'] = ret.get('guest_phone') or ""
            ret['guest_email'] = ret.get('guest_email') or ""
            ret['guest_address'] = ret.get('guest_address') or ""
            ret['id_proof_type'] = ret.get('id_proof_type') or ""
            ret['id_proof_number'] = ret.get('id_proof_number') or ""
            ret['id_proof_file'] = ret.get('id_proof_file') or ""

        # Dynamically attach company details from Company model (O(1) with context)
        ret['company_id'] = instance.company_id or ""
        if comp_map is not None:
            comp = comp_map.get(str(instance.company_id)) if instance.company_id else None
            if comp:
                ret['company_details'] = {
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
            else:
                ret['company_details'] = {}
        else:
            ret['company_details'] = instance.company_details or {}

        # Clean tax_details, extra_addons
        ret['tax_details'] = clean_value(getattr(instance, 'tax_details', None)) or {}
        ret['extra_addons'] = clean_value(getattr(instance, 'extra_addons', None)) or []
        ret['food_details'] = instance.food_details if hasattr(instance, 'food_details') else {}
        
        # Remove rent_details
        ret.pop('rent_details', None)

        # Clean and expose payment_details
        raw_pd = clean_value(getattr(instance, 'payment_details', None)) or {}
        if isinstance(raw_pd, dict):
            ret['payment_details'] = dict(raw_pd)
        else:
            ret['payment_details'] = {}

        # Amount paid resolution (O(1) with context)
        if bills_map is not None:
            b_list = bills_map.get(str(instance.booking_id), [])
            ret['amount_paid'] = sum(float(b.amount_paid or 0) for b in b_list)
        else:
            ret['amount_paid'] = instance.amount_paid

        ret['bill_type'] = instance.bill_type or (ret.get('tax_details') or {}).get('bill_type') or "Rack"
        ret['round_off'] = getattr(instance, 'round_off', 0.0) if getattr(instance, 'round_off', None) is not None else ((ret.get('tax_details') or {}).get('round_off') or 0.0)

        return ret


class CustomerSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = Customer
        fields = [
            "id",
            "customer_id",
            "name",
            "phone",
            "email",
            "address",
            "id_proof_type",
            "id_proof_number",
            "id_proof_file",
            "password",
            "created_by",
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
            "created_at"
        ]
        read_only_fields = [
            "customer_id",
            "created_by",
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
            "created_at"
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": False}
        }

    def get_id(self, obj):
        return str(obj.pk)

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        customer = Customer(**validated_data)
        if password:
            customer.password = password
        customer.save()
        return customer

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        import json
        from collections import OrderedDict

        def clean_json(val):
            if val is None:
                return {}
            if isinstance(val, (dict, OrderedDict)):
                return dict(val)
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return {}
            return val

        ret['company_details'] = clean_json(getattr(instance, 'company_details', None) or ret.get('company_details'))
        return ret

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
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
            "created_at",
            "lastmodified_at"
        ]
        read_only_fields = [
            "admin_id",
            "created_by",
            "created_date",
            "lastmodified_by",
            "lastmodified_date",
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
        read_only_fields = ["booking_id", "created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at"]

    def get_id(self, obj):
        return str(obj.pk)

    def create(self, validated_data):
        import uuid
        if 'booking_id' not in validated_data or not validated_data['booking_id']:
            validated_data['booking_id'] = f"EVT-{uuid.uuid4().hex[:8].upper()}"
        return super().create(validated_data)

class BillingSerializer(serializers.ModelSerializer):
    booking_id = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    total_booking_paid = serializers.SerializerMethodField()
    guest_name = serializers.SerializerMethodField()
    guest_phone = serializers.SerializerMethodField()
    guest_email = serializers.SerializerMethodField()
    room_numbers = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    company_gst = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    tax_details = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    discount_remarks = serializers.SerializerMethodField()
    check_in = serializers.SerializerMethodField()
    check_out = serializers.SerializerMethodField()
    guest_check_in = serializers.SerializerMethodField()
    guest_check_out = serializers.SerializerMethodField()
    booking_status = serializers.SerializerMethodField()
    booking_source = serializers.SerializerMethodField()
    round_off = serializers.SerializerMethodField()

    class Meta:
        model = Billing
        fields = "__all__"
        read_only_fields = ["billing_no", "created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at"]

    def get_booking_id(self, obj):
        try:
            if obj.booking:
                return obj.booking.booking_id or str(obj.booking.pk)
            return getattr(obj, 'booking_id', None)
        except Exception:
            return None

    def get_total_amount(self, obj):
        try:
            return float(obj.booking.total_amount or obj.booking.payment_details.get("amount", 0) or 0)
        except Exception:
            return 0

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

    def get_company_name(self, obj):
        try:
            comp = obj.booking.company_details or {}
            return comp.get("company_name", "") or ""
        except Exception:
            return ""

    def get_company_gst(self, obj):
        try:
            comp = obj.booking.company_details or {}
            return comp.get("gst_no", "") or comp.get("company_gst", "") or ""
        except Exception:
            return ""

    def get_state(self, obj):
        try:
            comp = obj.booking.company_details or {}
            return comp.get("state", "Tamil Nadu") or "Tamil Nadu"
        except Exception:
            return "Tamil Nadu"

    def get_tax_details(self, obj):
        try:
            if obj.booking and obj.booking.tax_details:
                td = obj.booking.tax_details
                if isinstance(td, str):
                    import json
                    td = json.loads(td)
                if isinstance(td, dict) and td:
                    return td
            if obj.booking:
                total = float(getattr(obj.booking, 'total_amount', 0) or (obj.booking.payment_details or {}).get('amount', 0) or obj.amount_paid or 0)
                if total > 0:
                    taxable = round(total / 1.05, 2)
                    ttax = round(total - taxable, 2)
                    cgst = round(ttax / 2, 2)
                    sgst = round(ttax - cgst, 2)
                    return {
                        "bill_type": getattr(obj.booking, 'bill_type', 'Rack') or 'Rack',
                        "subtotal": total,
                        "taxable_amount": taxable,
                        "cgst_rate": 2.5,
                        "cgst_amount": cgst,
                        "sgst_rate": 2.5,
                        "sgst_amount": sgst,
                        "total_tax": ttax,
                        "round_off": float(getattr(obj.booking, 'round_off', 0) or 0),
                        "gross_total": total
                    }
            return {}
        except Exception:
            return {}

    def get_discount_amount(self, obj):
        try:
            return float(obj.booking.discount_amount or 0)
        except Exception:
            return 0

    def get_discount_remarks(self, obj):
        try:
            return obj.booking.discount_remarks or ""
        except Exception:
            return ""

    def get_guest_check_in(self, obj):
        try:
            return obj.booking.guest_check_in or obj.booking.check_in
        except Exception:
            return None

    def get_guest_check_out(self, obj):
        try:
            return obj.booking.guest_check_out or obj.booking.check_out
        except Exception:
            return None

    def get_check_in(self, obj):
        try:
            return obj.booking.guest_check_in or obj.booking.check_in
        except Exception:
            return None

    def get_check_out(self, obj):
        try:
            return obj.booking.guest_check_out or obj.booking.check_out
        except Exception:
            return None

    def get_booking_status(self, obj):
        try:
            return obj.booking.booking_status or "confirmed"
        except Exception:
            return "confirmed"

    def get_booking_source(self, obj):
        try:
            return obj.booking.booking_source or "walk_in"
        except Exception:
            return "walk_in"

    def get_round_off(self, obj):
        try:
            return float(obj.booking.round_off or (obj.booking.tax_details or {}).get("round_off", 0) or 0)
        except Exception:
            return 0.0

class GalleryCategorySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    class Meta:
        model = GalleryCategory
        fields = "__all__"
        read_only_fields = ["created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at"]
    
    def get_id(self, obj):
        return str(obj.pk)

class GallerySerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Gallery
        fields = "__all__"
        read_only_fields = ["created_by", "created_date", "lastmodified_by", "lastmodified_date", "created_at"]

    def get_id(self, obj):
        return str(obj.pk)

    def get_image_url(self, obj):
        if not obj.image_id:
            return ""
        img_str = str(obj.image_id).strip()
        if '127.0.0.1:1919' in img_str or 'localhost:1919' in img_str or 'localhost:3000' in img_str or 'localhost:3001' in img_str:
            import re
            m = re.search(r'media/gridfs/([^/]+)', img_str)
            if m:
                img_str = m.group(1)
            else:
                import re
                img_str = re.sub(r'^https?://[^/]+', '', img_str)

        if (img_str.startswith('http://') or img_str.startswith('https://')) and not ('127.0.0.1' in img_str or 'localhost' in img_str):
            return img_str
        elif img_str.startswith('data:'):
            return img_str

        if 'media/gridfs/' in img_str:
            file_id = img_str.split('media/gridfs/')[-1].strip('/')
            path = f"/_b_a_c_k_e_n_d/travellerinwebsite/media/gridfs/{file_id}/"
        elif not '/' in img_str:
            path = f"/_b_a_c_k_e_n_d/travellerinwebsite/media/gridfs/{img_str}/"
        else:
            path = img_str if img_str.startswith('/') else f"/{img_str}"
            if not path.startswith('/_b_a_c_k_e_n_d/travellerinwebsite/'):
                path = f"/_b_a_c_k_e_n_d/travellerinwebsite{path}"

        request = self.context.get('request')
        if request:
            uri = request.build_absolute_uri(path)
            if 'test.shinova.in' in uri or 'shinova.in' in uri:
                uri = uri.replace('http://', 'https://')
            return uri
        return path


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import MenuItems
        model = MenuItems
        fields = ["item_id", "item_name", "rate", "is_active"]
