import threading

_thread_locals = threading.local()

class ThreadLocalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Normalize HTTP_AUTHORIZATION for PyAuth and SimpleJWT compatibility
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if auth and auth.startswith('Bearer '):
            raw_token = auth[7:].strip()
            # If the token is a PyAuth / JWT token, strip 'Bearer ' so pyauth jwt.decode does not fail
            request.META['HTTP_AUTHORIZATION'] = raw_token

        _thread_locals.request = request
        try:
            response = self.get_response(request)
        finally:
            if hasattr(_thread_locals, 'request'):
                del _thread_locals.request
        return response

def get_current_request():
    return getattr(_thread_locals, 'request', None)

def get_current_user():
    request = get_current_request()
    if request:
        return getattr(request, 'user', None)
    return None
