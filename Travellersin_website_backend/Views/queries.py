from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from Travellersin_website_backend.models import Query
from Travellersin_website_backend.serializers import QuerySerializer
from ..permissions import PublicCreateOrHasRolePermission, AdminOrHasRolePermission as HasRolePermission
from ..utils import get_auth_user

@api_view(["GET", "POST"])
@permission_classes([PublicCreateOrHasRolePermission])
def queries_list_create(request):
    if request.method == "GET":
        queries_qs = Query.objects.all()
        
        # Date Filter
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if start_date_str and end_date_str:
            try:
                from datetime import datetime
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                
                queries_qs = queries_qs.filter(created_at__range=[start_dt, end_dt])
            except Exception as e:
                print(f"Date filter error: {e}")
                
        queries_list = list(queries_qs)
        try:
            queries_list.sort(key=lambda q: getattr(q, 'created_at', None) or '', reverse=True)
        except Exception:
            pass

        return Response(QuerySerializer(queries_list, many=True).data)

    if request.method == "POST":
        auth_user_id = get_auth_user(request)
        serializer = QuerySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=str(auth_user_id))
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([HasRolePermission])
def query_detail_update(request, pk):
    try:
        query = Query.objects.get(pk=pk)
    except Query.DoesNotExist:
        return Response({"error": "Query not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(QuerySerializer(query).data)

    if request.method == "PATCH":
        auth_user_id = get_auth_user(request)
        serializer = QuerySerializer(query, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        query.delete()
        return Response({"message": "Query deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
