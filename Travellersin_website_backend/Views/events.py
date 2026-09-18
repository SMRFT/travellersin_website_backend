from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from Travellersin_website_backend.models import Event
from Travellersin_website_backend.serializers import EventSerializer
from ..permissions import PublicReadOnlyOrHasRolePermission
from ..utils import get_auth_user

@api_view(["GET", "POST"])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def events_list_create(request):
    if request.method == "GET":
        events = Event.objects.all()
        return Response(EventSerializer(events, many=True).data)

    if request.method == "POST":
        auth_user_id = get_auth_user(request)
        serializer = EventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=str(auth_user_id))
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def event_detail_update(request, pk):
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(EventSerializer(event).data)

    if request.method == "PATCH":
        auth_user_id = get_auth_user(request)
        serializer = EventSerializer(event, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        event.delete()
        return Response({"message": "Event deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
