from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from Travellersin_website_backend.models import Event
from Travellersin_website_backend.serializers import EventSerializer

@api_view(["GET", "POST"])
def events_list_create(request):
    if request.method == "GET":
        events = Event.objects.all()
        return Response(EventSerializer(events, many=True).data)

    if request.method == "POST":
        serializer = EventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

@api_view(["GET", "PATCH", "DELETE"])
def event_detail_update(request, pk):
    try:
        event = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(EventSerializer(event).data)

    if request.method == "PATCH":
        serializer = EventSerializer(event, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "DELETE":
        event.delete()
        return Response({"message": "Event deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
