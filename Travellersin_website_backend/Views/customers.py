from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from ..models import Customer
from ..serializers import CustomerSerializer
from ..utils import get_model_first, get_auth_user
from pyauth.auth import HasRolePermission

def generate_customer_id():
    existing_customers = list(Customer.objects.filter(customer_id__startswith="CUST-"))
    max_num = 0
    for c in existing_customers:
        try:
            num_part = str(c.customer_id).replace("CUST-", "").strip()
            if num_part.isdigit():
                val = int(num_part)
                if val > max_num:
                    max_num = val
        except (ValueError, IndexError):
            pass
    next_num = max_num + 1
    return f"CUST-{next_num:05d}"

def sync_or_create_customer(name=None, phone=None, email=None, address=None, company_details=None, id_proof_type=None, id_proof_number=None, id_proof_file=None, customer_id=None, created_by="user", lastmodified_by="user"):
    if not phone and not customer_id and not name:
        return None
    
    customer = None
    if customer_id:
        customer = get_model_first(Customer.objects.filter(customer_id=customer_id))
    if not customer and phone:
        customer = get_model_first(Customer.objects.filter(phone=str(phone).strip()))
        
    if not customer:
        customer_id_new = generate_customer_id()
        customer = Customer(
            customer_id=customer_id_new,
            name=name or "Guest",
            phone=str(phone).strip() if phone else f"GUEST_{customer_id_new}",
            email=email or "",
            address=address or "",
            id_proof_type=id_proof_type or "",
            id_proof_number=id_proof_number or "",
            id_proof_file=id_proof_file or "",
            password=None,
            created_by=str(created_by) if created_by else "user"
        )
        customer.save()
    else:
        changed = False
        if name and (not customer.name or customer.name == "Guest"):
            customer.name = name
            changed = True
        if email and not customer.email:
            customer.email = email
            changed = True
        if address and not customer.address:
            customer.address = address
            changed = True
        if id_proof_type and not customer.id_proof_type:
            customer.id_proof_type = id_proof_type
            changed = True
        if id_proof_number and not customer.id_proof_number:
            customer.id_proof_number = id_proof_number
            changed = True
        if id_proof_file and not customer.id_proof_file:
            customer.id_proof_file = id_proof_file
            changed = True
        if changed:
            customer.lastmodified_by = str(lastmodified_by) if lastmodified_by else "user"
            customer.lastmodified_date = timezone.now()
            customer.save()
            
    return customer

@api_view(["GET", "POST"])
@permission_classes([HasRolePermission])
def customers_list_create(request):
    """
    GET /customers/ - List all customers with optional search
    POST /customers/ - Create or update a customer record
    """
    if request.method == "GET":
        search_query = request.query_params.get("search", "").strip()
        customers_qs = Customer.objects.all()
        if search_query:
            from django.db.models import Q
            customers_qs = customers_qs.filter(
                Q(name__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(customer_id__icontains=search_query)
            )
        
        customers_list = list(customers_qs)
        try:
            customers_list.sort(key=lambda c: getattr(c, "name", "") or "")
        except Exception:
            pass
        return Response(CustomerSerializer(customers_list, many=True).data)

    if request.method == "POST":
        auth_user_id = get_auth_user(request)
        data = request.data
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        
        if not name and not phone:
            return Response({"error": "Name or Phone Number is required"}, status=status.HTTP_400_BAD_REQUEST)

        customer = sync_or_create_customer(
            name=name,
            phone=phone,
            email=data.get("email"),
            address=data.get("address"),
            id_proof_type=data.get("id_proof_type"),
            id_proof_number=data.get("id_proof_number"),
            id_proof_file=data.get("id_proof_file"),
            customer_id=data.get("customer_id"),
            created_by=str(auth_user_id),
            lastmodified_by=str(auth_user_id)
        )
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([HasRolePermission])
def customer_detail_update(request, customer_id):
    """
    GET, PATCH, DELETE /customers/<customer_id>/
    """
    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CustomerSerializer(customer).data)

    if request.method == "PATCH":
        from django.utils import timezone
        auth_user_id = get_auth_user(request)
        serializer = CustomerSerializer(customer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        customer.delete()
        return Response({"message": "Customer deleted successfully"})
