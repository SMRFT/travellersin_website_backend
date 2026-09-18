PAGE_MAPPING = {
    # Dashboard:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/dashboard/?(\?.*)?$': 'TIN-P-DASH',

    # Rooms:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/rooms/?(\?.*)?$': 'TIN-API-RM',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/rooms/check-availability/?(\?.*)?$': 'TIN-API-RM',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/rooms/(?:[^/]+)/bookings/?(\?.*)?$': 'TIN-API-RM',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/rooms/(?:[^/]+)/?(\?.*)?$': 'TIN-API-RM',

    # Room Availability Calendar:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/room-availability/?(\?.*)?$': 'TIN-P-RA',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/room-availability/update-status/?(\?.*)?$': 'TIN-P-RA',

    # Bookings:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/bookings/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/bookings/track/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/bookings/(?:[^/]+)/cancel/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/bookings/(?:[^/]+)/?(\?.*)?$': 'TIN-API-BK',

    # Customers:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/customers/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/customers/(?:[^/]+)/?(\?.*)?$': 'TIN-API-BK',

    # Companies:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/companies/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/companies/(?:[^/]+)/?(\?.*)?$': 'TIN-API-BK',

    # Admin Booking Actions & Cancellations:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/booking/(?:[^/]+)/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/booking/(?:[^/]+)/approve-cancellation/?(\?.*)?$': 'TIN-API-BK',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/booking/(?:[^/]+)/reject-cancellation/?(\?.*)?$': 'TIN-API-BK',

    # Events:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/events/?(\?.*)?$': 'TIN-API-EV',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/events/bookings/?(\?.*)?$': 'TIN-API-EV',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/events/status/?(\?.*)?$': 'TIN-API-EV',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/events/(?:[^/]+)/?(\?.*)?$': 'TIN-API-EV',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/event-booking/(?:[^/]+)/?(\?.*)?$': 'TIN-API-EV',

    # Queries & Support:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/queries/?(\?.*)?$': 'TIN-API-QR',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/queries/(?:[^/]+)/?(\?.*)?$': 'TIN-API-QR',

    # Gallery:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/gallery/?(\?.*)?$': 'TIN-API-GA',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/gallery/(?:[^/]+)/?(\?.*)?$': 'TIN-API-GA',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/gallery-categories/?(\?.*)?$': 'TIN-API-GA',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/gallery-categories/(?:[^/]+)/?(\?.*)?$': 'TIN-API-GA',

    # Accounts & Billing History:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/billing-history/?(\?.*)?$': 'TIN-P-ACC',

    # Admin Management:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/?(\?.*)?$': 'TIN-API-ADM',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/(?:[^/]+)/?(\?.*)?$': 'TIN-API-ADM',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/admin/(?:[^/]+)/delete/?(\?.*)?$': 'TIN-API-ADM',

    # Media:
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/upload/room-image/?(\?.*)?$': 'TIN-API-RM',
    r'^/_b_a_c_k_e_n_d/travellerinwebsite/media/gridfs/(?:[^/]+)/?(\?.*)?$': 'TIN-API-RM',
}

PAGE_ACTION_MAPPING = {
    'xxx': {
        'DELETE': 'RWD',
    },
}

GEN_ACTION_MAPPING = {
    'POST': 'RW',
    'PUT': 'RW',
    'DELETE': 'RW',
    'PATCH': 'RW',
    'GET': 'R',
}
