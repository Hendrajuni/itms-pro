from io import BytesIO
from django.core.files import File
from PIL import Image

def compress_image(image, max_size=1024, quality=70):
    """
    Compresses an image file.
    :param image: The original image file (InMemoryUploadedFile or FieldFile)
    :param max_size: Max dimension (width/height)
    :param quality: JPEG Quality (1-100)
    :return: Compressed image file
    """
    if not image:
        return None

    im = Image.open(image)
    
    # Convert to RGB if RGBA (e.g. png) to save as JPEG
    if im.mode in ('RGBA', 'P'):
        im = im.convert('RGB')
        
    # Resize if needed
    width, height = im.size
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(max_size * height / width)
        else:
            new_height = max_size
            new_width = int(max_size * width / height)
        im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
    # Save to BytesIO
    im_io = BytesIO()
    im.save(im_io, format='JPEG', quality=quality)
    
    # Create a new Django File object
    new_image = File(im_io, name=image.name.rsplit('.', 1)[0] + '.jpg')
    return new_image
