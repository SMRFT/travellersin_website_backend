from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.http import HttpResponse, Http404
from django.db import connections
import gridfs
import os
import uuid
from mimetypes import guess_type
from bson import ObjectId

def get_gridfs():
    # Use the existing djongo/pymongo connection
    connection = connections['default']
    
    # Ensure connection is established
    if connection.connection is None:
        connection.connect()
    
    db_name = connection.settings_dict['NAME']
    base = connection.connection
    
    # 1. If it's already the database (typical for Djongo)
    if hasattr(base, 'name') and base.name == db_name:
        db = base
    # 2. If it's the client, use get_database (safely check it's not a collection proxy)
    elif hasattr(base, 'get_database'):
         # In PyMongo, Database doesn't have get_database, but MongoClient does.
         # However, Database[attr] returns a Collection.
         # So we check if 'get_database' is an attribute that exists as a real method
         # standard way to check if it's a client or db in pymongo
         if base.__class__.__name__ == 'Database':
             db = base
         else:
             try:
                 db = base.get_database(db_name)
             except (TypeError, AttributeError):
                 db = base[db_name]
    # 3. Fallback
    else:
        db = base[db_name]
            
    return gridfs.GridFS(db)

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_room_image(request):
    if 'image' not in request.FILES:
        return Response({"error": "No image provided"}, status=status.HTTP_400_BAD_REQUEST)
    
    image = request.FILES['image']
    fs = get_gridfs()
    
    # Generate unique filename
    ext = os.path.splitext(image.name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    
    # Store in GridFS
    file_id = fs.put(
        image.read(),
        filename=filename,
        content_type=image.content_type or guess_type(image.name)[0]
    )
            
    # Return the URL - we'll use a specific route for GridFS files
    file_url = f"/media/gridfs/{file_id}/"
    
    return Response({
        "url": file_url,
        "filename": filename,
        "id": str(file_id)
    }, status=status.HTTP_201_CREATED)

def serve_gridfs_file(request, file_id):
    try:
        fs = get_gridfs()
        grid_out = fs.get(ObjectId(file_id))
        
        response = HttpResponse(grid_out.read(), content_type=grid_out.content_type)
        response['Content-Disposition'] = f'inline; filename="{grid_out.filename}"'
        return response
    except Exception as e:
        raise Http404("File not found")
