import json
import time
import queue
import threading
from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ..permissions import PublicReadOnlyOrHasRolePermission
from ..models import Booking

# Active SSE listener client queues
_subscribers = []
_subscribers_lock = threading.Lock()

def add_subscriber(q):
    with _subscribers_lock:
        _subscribers.append(q)

def remove_subscriber(q):
    with _subscribers_lock:
        if q in _subscribers:
            _subscribers.remove(q)

from django.core.serializers.json import DjangoJSONEncoder

def serialize_date(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)

def get_online_pending_bookings_data():
    online_bookings = [
        b for b in Booking.objects.all()
        if (
            str(getattr(b, "booking_source", "")).lower().strip() in ["online", "website"]
            or str(getattr(b, "created_type", "")).lower().strip() == "customer"
        )
        and str(getattr(b, "booking_status", "") or getattr(b, "status", "")).lower().replace("_", " ").strip() == "pending"
    ]
    data = []
    for b in online_bookings:
        amt = getattr(b, "amount", None)
        if amt is None and isinstance(getattr(b, "payment_details", None), dict):
            amt = b.payment_details.get("amount")
        data.append({
            "booking_id": str(b.booking_id or getattr(b, "id", "")),
            "id": str(b.booking_id or getattr(b, "id", "")),
            "guest_name": b.guest_name or "",
            "guest_phone": b.guest_phone or "",
            "check_in": serialize_date(b.check_in),
            "amount": amt,
            "booking_source": b.booking_source or "online",
            "booking_status": b.booking_status or "pending",
        })
    return data

# Alias for backwards compatibility
get_online_confirmed_bookings_data = get_online_pending_bookings_data

def broadcast_booking_notification():
    """
    Push updated online pending bookings list to all active SSE client streams in real-time
    """
    try:
        data = get_online_pending_bookings_data()
        payload = json.dumps(data, cls=DjangoJSONEncoder, default=str)
        event_str = f"event: bookings_update\ndata: {payload}\n\n"
        with _subscribers_lock:
            active_count = len(_subscribers)
            print(f"📡 [SSE] Broadcasting online pending bookings ({len(data)} items) to {active_count} active subscriber(s)...")
            for q in list(_subscribers):
                try:
                    q.put_nowait(event_str)
                except Exception as q_err:
                    print(f"Error pushing to subscriber queue: {q_err}")
    except Exception as e:
        print(f"SSE Broadcast Error: {e}")

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def notification_stream(request):
    """
    SSE stream endpoint. Establishes single persistent connection, emits initial data immediately,
    and pushes live updates whenever online bookings are created or updated.
    """
    q = queue.Queue(maxsize=100)
    add_subscriber(q)
    print(f"🔌 [SSE] Client connected to notifications stream. Total active: {len(_subscribers)}")

    def event_generator():
        try:
            # 1. Immediately emit current active online confirmed bookings
            initial_data = get_online_confirmed_bookings_data()
            yield f"event: bookings_update\ndata: {json.dumps(initial_data, cls=DjangoJSONEncoder, default=str)}\n\n"

            # 2. Stream live updates as they occur with 15s keepalive ping
            while True:
                try:
                    msg = q.get(timeout=15)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            print("🔌 [SSE] Client disconnected from notifications stream.")
        finally:
            remove_subscriber(q)

    response = StreamingHttpResponse(event_generator(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    response["Access-Control-Allow-Origin"] = "*"
    return response

@api_view(["GET"])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def admin_notifications(request):
    """
    Standard REST endpoint for fetching online confirmed bookings
    """
    return Response(get_online_confirmed_bookings_data())
