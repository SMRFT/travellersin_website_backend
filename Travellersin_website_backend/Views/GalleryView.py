from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from ..models import Gallery, GalleryCategory
from ..serializers import GallerySerializer, GalleryCategorySerializer
from .media import get_gridfs
from ..permissions import PublicReadOnlyOrHasRolePermission
from ..utils import get_auth_user
import uuid
import os
from mimetypes import guess_type
from bson import ObjectId

@api_view(['GET', 'POST'])
@permission_classes([PublicReadOnlyOrHasRolePermission])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def gallery_list_create(request):
    """
    GET: List all gallery images
    POST: Create a new gallery image
    """
    if request.method == 'GET':
        cat_param = request.query_params.get('category')
        gallery_qs = Gallery.objects.all()

        if cat_param:
            if cat_param.isdigit():
                 gallery_qs = gallery_qs.filter(category__id=cat_param)
            else:
                 gallery_qs = gallery_qs.filter(category__name__iexact=cat_param)
        
        gallery_list = list(gallery_qs)
        try:
            gallery_list.sort(key=lambda g: getattr(g, 'order', 1))
        except Exception:
            pass

        serializer = GallerySerializer(gallery_list, many=True, context={'request': request})
        return Response(serializer.data)

    if request.method == 'POST':
        auth_user_id = get_auth_user(request)
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
        
        serializer = GallerySerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save(created_by=str(auth_user_id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def gallery_detail_update_delete(request, pk):
    try:
        gallery_item = Gallery.objects.get(pk=pk)
    except Gallery.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = GallerySerializer(gallery_item, context={'request': request})
        return Response(serializer.data)

    if request.method == 'PATCH':
        from django.utils import timezone
        auth_user_id = get_auth_user(request)
        serializer = GallerySerializer(gallery_item, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save(lastmodified_by=str(auth_user_id), lastmodified_date=timezone.now())
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        gallery_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
@permission_classes([PublicReadOnlyOrHasRolePermission])
def category_list_create(request):
    if request.method == 'GET':
        categories_list = list(GalleryCategory.objects.all())
        try:
            categories_list.sort(key=lambda c: getattr(c, 'name', ''))
        except Exception:
            pass
        serializer = GalleryCategorySerializer(categories_list, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        auth_user_id = get_auth_user(request)
        serializer = GalleryCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=str(auth_user_id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'DELETE'])
@permission_classes([PublicReadOnlyOrHasRolePermission])
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

