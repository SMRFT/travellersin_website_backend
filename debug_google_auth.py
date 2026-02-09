from google.auth.transport import requests as google_requests
import requests
import sys

print("Python executable:", sys.executable)
try:
    print("Imported successfully")
    session = requests.Session()
    session.verify = False
    print("Session created")
    
    # Check if google_requests has Request
    if not hasattr(google_requests, 'Request'):
        print("google_requests has no Request attribute")
    else:
        print("google_requests.Request exists")
        
    transport = google_requests.Request(session=session)
    print(f"Transport created: {transport}")
    print(f"Transport type: {type(transport)}")
    print(f"Is callable: {callable(transport)}")
    
    # Try calling it
    try:
        # Just a dummy call, doesn't need to succeed, just verify it's callable
        # We expect this might fail with connection error but NOT "not callable"
        print("Attempting to call transport...")
        transport(url="https://www.googleapis.com", method="GET")
    except Exception as e:
        print(f"Call raised exception (expected): {e}")

except Exception as e:
    print(f"Fatal Error: {e}")
    import traceback
    traceback.print_exc()
