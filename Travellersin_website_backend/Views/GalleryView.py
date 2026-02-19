from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from ..models import Gallery, GalleryCategory
from ..serializers import GallerySerializer, GalleryCategorySerializer
from .media import get_gridfs
import uuid
import os
from mimetypes import guess_type
from bson import ObjectId

@api_view(['GET', 'POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def gallery_list_create(request):
    """
    GET: List all gallery images
    POST: Create a new gallery image
    """
    if request.method == 'GET':
        cat_param = request.query_params.get('category')
        gallery = Gallery.objects.all().order_by('order')

        if cat_param:
            if cat_param.isdigit():
                 gallery = gallery.filter(category__id=cat_param)
            else:
                 gallery = gallery.filter(category__name__iexact=cat_param)
        
        serializer = GallerySerializer(gallery, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        data = request.data.copy()
        
        # Handle Image Upload if provided
        if 'image_file' in request.FILES:
            image = request.FILES['image_file']
            fs = get_gridfs()
            ext = os.path.splitext(image.name)[1]
            filename = f"gallery_{uuid.uuid4().hex}{ext}"
            file_id = fs.put(
                image.read(),
                filename=filename,
                content_type=image.content_type or guess_type(image.name)[0]
            )
            data['image_id'] = str(file_id)
        
        serializer = GallerySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PATCH', 'DELETE'])
def gallery_detail_update_delete(request, pk):
    try:
        gallery_item = Gallery.objects.get(pk=pk)
    except Gallery.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = GallerySerializer(gallery_item)
        return Response(serializer.data)

    if request.method == 'PATCH':
        serializer = GallerySerializer(gallery_item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        # Optional: Delete from GridFS too
        # fs = get_gridfs()
        # try:
        #     fs.delete(ObjectId(gallery_item.image_id))
        # except:
        #     pass
        gallery_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
def category_list_create(request):
    if request.method == 'GET':
        categories = GalleryCategory.objects.all().order_by('name')
        serializer = GalleryCategorySerializer(categories, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        serializer = GalleryCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'DELETE'])
def category_detail_delete(request, pk):
    try:
        category = GalleryCategory.objects.get(pk=pk)
    except GalleryCategory.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = GalleryCategorySerializer(category)
        return Response(serializer.data)

    if request.method == 'DELETE':
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
