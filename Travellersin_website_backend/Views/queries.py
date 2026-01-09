from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from Travellersin_website_backend.models import Query
from Travellersin_website_backend.serializers import QuerySerializer

@api_view(["GET", "POST"])
def queries_list_create(request):
    if request.method == "GET":
        queries = Query.objects.all().order_by("-created_at")
        return Response(QuerySerializer(queries, many=True).data)

    if request.method == "POST":
        serializer = QuerySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH", "DELETE"])
def query_detail_update(request, pk):
    try:
        query = Query.objects.get(pk=pk)
    except Query.DoesNotExist:
        return Response({"error": "Query not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(QuerySerializer(query).data)

    if request.method == "PATCH":
        serializer = QuerySerializer(query, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        query.delete()
        return Response({"message": "Query deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
