from django.urls import path
from .Views.rooms import rooms_list_create, room_detail_update, check_room_availability, get_room_bookings
from .Views.events import events_list_create, event_detail_update
from .Views.queries import queries_list_create, query_detail_update
from .Views.bookings import bookings_list_create, booking_detail_update, track_booking, cancel_booking
from .Views.adminpanel import (
    admin_dashboard, update_booking_status, admin_list_create, 
    admin_detail_update, admin_soft_delete, approve_cancellation, 
    reject_cancellation, update_event_booking_status, 
    admin_room_availability, billing_history
)
from .Views.auth import customer_signup, customer_login, admin_login, get_user_profile, google_auth, update_user_profile
from .Views.payments import create_razorpay_order, verify_payment, confirm_cash_booking, initiate_booking_payment
from .Views.media import upload_room_image, serve_gridfs_file
from .Views.whatsapp import send_whatsapp_test
from .Views.event_bookings import event_bookings_list_create, track_event_booking
from .Views.GalleryView import gallery_list_create, gallery_detail_update_delete, category_list_create, category_detail_delete

urlpatterns = [
    # Gallery - Category Management
    path("gallery/", gallery_list_create),
    path("gallery/<int:pk>/", gallery_detail_update_delete),
    path("gallery-categories/", category_list_create),
    path("gallery-categories/<int:pk>/", category_detail_delete),

    # Rooms
    path("rooms/", rooms_list_create),
    path("rooms/check-availability/", check_room_availability),
    path("rooms/<str:room_number>/bookings/", get_room_bookings),
    path("rooms/<str:room_number>/", room_detail_update),

    # Events
    path("events/", events_list_create),
    path("events/bookings/", event_bookings_list_create),
    path("events/status/", track_event_booking),
    path("events/<int:pk>/", event_detail_update),

    # Queries
    path("queries/", queries_list_create),
    path("queries/<str:pk>/", query_detail_update),

    # Bookings
    path("bookings/", bookings_list_create),
    path("bookings/track/", track_booking),
    path("bookings/<str:booking_id>/cancel/", cancel_booking),
    path("bookings/<str:booking_id>/", booking_detail_update),

    # Admin
    path("admin/dashboard/", admin_dashboard),
    path("admin/room-availability/", admin_room_availability),
    path("admin/booking/<str:booking_id>/", update_booking_status),
    path("admin/event-booking/<str:booking_id>/", update_event_booking_status),
    path("admin/booking/<str:booking_id>/approve-cancellation/", approve_cancellation),
    path("admin/booking/<str:booking_id>/reject-cancellation/", reject_cancellation),
    path("admin/billing-history/", billing_history),
    path("admin/", admin_list_create),                     # GET, POST
    path("admin/<str:admin_id>/", admin_detail_update),    # GET, PATCH
    path("admin/<str:admin_id>/delete/", admin_soft_delete),

    # Auth
    path("auth/signup/", customer_signup),
    path("auth/login/", customer_login),
    path("auth/admin/login/", admin_login),
    path("auth/profile/", get_user_profile),
    path("auth/profile/update/", update_user_profile),
    path("auth/google/", google_auth),

    # Payments
    path("payments/create-order/", create_razorpay_order),
    path("payments/booking/<str:booking_id>/initiate/", initiate_booking_payment),
    path("payments/verify/", verify_payment),
    path("payments/confirm-cash/", confirm_cash_booking),

    # Media
    path("upload/room-image/", upload_room_image),
    path("media/gridfs/<str:file_id>/", serve_gridfs_file),

    # WhatsApp
    path("whatsapp/send-test/", send_whatsapp_test),
]


