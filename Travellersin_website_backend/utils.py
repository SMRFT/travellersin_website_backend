def get_model_first(qs):
    try:
        for item in qs:
            return item
    except Exception:
        pass
    return None

def get_auth_user(request):
    """
    Extracts the auth-user-id from request data, headers, or PyAuth JWT token.
    Falls back to 'user' for unauthenticated public website actions.
    """
    val = None
    if hasattr(request, 'data') and isinstance(request.data, dict):
        val = request.data.get('auth-user-id')
    
    if not val:
        val = request.headers.get('auth-user-id') or request.META.get('HTTP_AUTH_USER_ID')
        
    if not val:
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
        if auth_header and str(auth_header).strip():
            try:
                import jwt
                token = str(auth_header).replace('Bearer ', '').strip()
                payload = jwt.decode(token, options={"verify_signature": False})
                val = payload.get('aud') or payload.get('user_id') or payload.get('employee_id') or payload.get('username')
            except Exception:
                pass
                
    return str(val) if val else "user"
