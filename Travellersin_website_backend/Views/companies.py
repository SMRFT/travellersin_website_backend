from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from ..models import Company
from ..serializers import CompanySerializer
from ..utils import get_model_first, get_auth_user
from pyauth.auth import HasRolePermission

def generate_company_id():
    existing_companies = list(Company.objects.filter(company_id__startswith="COM-"))
    max_num = 0
    for c in existing_companies:
        try:
            num_part = str(c.company_id).replace("COM-", "").strip()
            if num_part.isdigit():
                val = int(num_part)
                if val > max_num:
                    max_num = val
        except (ValueError, IndexError):
            pass
    next_num = max_num + 1
    return f"COM-{next_num:05d}"

def sync_or_create_company(company_id=None, company_name=None, contact_person=None, company_address=None, city=None, state=None, pincode=None, phone=None, gst_no=None, created_by="user", lastmodified_by="user"):
    if not company_name and not company_id:
        return None

    company = None
    if company_id:
        company = get_model_first(Company.objects.filter(company_id=str(company_id).strip()))
    if not company and company_name:
        clean_name = str(company_name).strip()
        if clean_name:
            company = get_model_first(Company.objects.filter(company_name__iexact=clean_name))
    if not company and gst_no and str(gst_no).strip():
        company = get_model_first(Company.objects.filter(gst_no=str(gst_no).strip()))

    if not company:
        company_id_new = generate_company_id()
        company = Company(
            company_id=company_id_new,
            company_name=str(company_name).strip() if company_name else f"Company_{company_id_new}",
            contact_person=contact_person or "",
            company_address=company_address or "",
            city=city or "",
            state=state or "",
            pincode=pincode or "",
            phone=phone or "",
            gst_no=gst_no or "",
            created_by=str(created_by) if created_by else "user"
        )
        company.save()
    else:
        changed = False
        if company_name and (not company.company_name or company.company_name.startswith("Company_")):
            company.company_name = str(company_name).strip()
            changed = True
        if contact_person and not company.contact_person:
            company.contact_person = contact_person
            changed = True
        if company_address and not company.company_address:
            company.company_address = company_address
            changed = True
        if city and not company.city:
            company.city = city
            changed = True
        if state and not company.state:
            company.state = state
            changed = True
        if pincode and not company.pincode:
            company.pincode = pincode
            changed = True
        if phone and not company.phone:
            company.phone = phone
            changed = True
        if gst_no and not company.gst_no:
            company.gst_no = gst_no
            changed = True
        if changed:
            company.lastmodified_by = str(lastmodified_by) if lastmodified_by else "user"
            company.lastmodified_date = timezone.now()
            company.save()

    return company

@api_view(["GET", "POST"])
@permission_classes([HasRolePermission])
def companies_list_create(request):
    """
    GET /companies/ - List all companies (alphabetical / latest)
    POST /companies/ - Create a new company
    """
    if request.method == "GET":
        search_query = request.query_params.get("search", "").strip()
        companies_qs = Company.objects.all()
        if search_query:
            companies_qs = companies_qs.filter(company_name__icontains=search_query)
        
        companies_list = list(companies_qs)
        try:
            companies_list.sort(key=lambda c: getattr(c, "company_name", "") or "")
        except Exception:
            pass
        return Response(CompanySerializer(companies_list, many=True).data)

    if request.method == "POST":
        auth_user_id = get_auth_user(request)
        data = request.data
        name = data.get("company_name", "").strip()
        if not name:
            return Response({"error": "Company Name is required"}, status=status.HTTP_400_BAD_REQUEST)

        company = sync_or_create_company(
            company_id=data.get("company_id"),
            company_name=name,
            contact_person=data.get("contact_person") or data.get("company_person"),
            company_address=data.get("company_address") or data.get("address"),
            city=data.get("city") or data.get("company_city"),
            state=data.get("state") or data.get("company_state"),
            pincode=data.get("pincode") or data.get("company_pincode"),
            phone=data.get("phone") or data.get("company_phone"),
            gst_no=data.get("gst_no") or data.get("company_gst"),
            created_by=str(auth_user_id),
            lastmodified_by=str(auth_user_id)
        )
        return Response(CompanySerializer(company).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([HasRolePermission])
def company_detail_update(request, company_id):
    """
    GET, PATCH, DELETE /companies/<company_id>/
    """
    try:
        company = Company.objects.get(company_id=company_id)
    except Company.DoesNotExist:
        return Response({"error": "Company not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CompanySerializer(company).data)

    if request.method == "PATCH":
        from django.utils import timezone
        auth_user_id = get_auth_user(request)
        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        company.delete()
        return Response({"message": f"Company {company_id} deleted successfully"}, status=status.HTTP_200_OK)
