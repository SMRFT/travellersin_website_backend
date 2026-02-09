import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "travellerin_backend.settings")
django.setup()

from Travellersin_website_backend.models import Customer

try:
    print(f"Checking for duplicates of CUST-CBF3DD42...")
    customers = Customer.objects.filter(customer_id='CUST-CBF3DD42')
    print(f"Found {customers.count()} records.")
    for c in customers:
        print(f" - Name: {c.name}, PK: {c.pk}, ID: {c.id}")

    if customers.count() > 1:
        print("DUPLICATES FOUND! Attempting cleanup (keeping last one)...")
        # Keep the latest one? Or the first one?
        # Usually keep the one with data? They probably have same data if updated.
        # Let's keep the one that was fetched first? Or last?
        # Djongo might not have undefined order.
        
        # We will delete all except one.
        to_keep = customers.first() 
        # But wait, if they all have PK=None, how do we delete specific ones?
        # Djongo might rely on _id.
        # If we can't delete by PK, we might be in trouble.
        
        print("Cannot safely delete without PK. Manual DB intervention might be needed or delete ALL and recreate.")
        
except Exception as e:
    print(f"Error: {e}")

