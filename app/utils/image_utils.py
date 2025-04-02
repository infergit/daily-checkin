# app/utils/image_utils.py
from PIL import Image, ExifTags
from io import BytesIO
import os
from flask import current_app
import logging

# Replace pyheif with pillow_heif
try:
    import pillow_heif
    pillow_heif.register_heif_opener()  # Register with Pillow
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False
    logging.warning("pillow-heif not installed. HEIC/HEIF images will not be supported.")

logger = logging.getLogger(__name__)

def process_image(image_data, max_width=1200, quality=100, format='JPEG'):
    """
    Process an image for storage:
    1. Resize large images while maintaining aspect ratio
    2. Optionally convert format
    3. Handle EXIF rotation
    4. Strip EXIF metadata for privacy
    5. Preserve maximum original image quality
    
    Args:
        image_data (bytes): Raw image data
        max_width (int): Maximum width to resize to
        quality (int): JPEG/WebP quality (1-100)
        format (str): Target format ('JPEG', 'PNG', 'WEBP')
        
    Returns:
        tuple: (processed_image_data, new_content_type, width, height)
    """
    try:
        # With pillow_heif registered, we can directly open HEIC files with PIL
        img = Image.open(BytesIO(image_data))
        
        # Handle EXIF rotation but don't keep the EXIF data
        img = correct_image_orientation(img)
        
        # Create a new image with same pixel data but no EXIF metadata
        if format == 'JPEG' and img.mode == 'RGBA':
            # Convert RGBA to RGB if saving as JPEG
            clean_img = Image.new('RGB', img.size)
        else:
            clean_img = Image.new(img.mode, img.size)
        
        # Copy the pixel data (without metadata)
        clean_img.paste(img)
        
        # Use our clean image from now on
        img = clean_img
        
        # Get original dimensions
        original_width, original_height = img.size
        
        # Resize if width exceeds max_width
        if original_width > max_width:
            ratio = max_width / original_width
            new_height = int(original_height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        # Save the processed image to bytes
        output = BytesIO()
        
        # Save with appropriate format and settings, but no EXIF data
        # Maximum quality (100) to preserve all original quality
        if format == 'JPEG':
            img.save(output, format=format, quality=quality, optimize=True, exif=bytes())
            content_type = 'image/jpeg'
        elif format == 'PNG':
            img.save(output, format=format, optimize=True)
            content_type = 'image/png'
        elif format == 'WEBP':
            img.save(output, format=format, quality=quality)
            content_type = 'image/webp'
        else:
            # Default to JPEG
            img.save(output, format='JPEG', quality=quality, optimize=True, exif=bytes())
            content_type = 'image/jpeg'
        
        # Get current dimensions after processing
        width, height = img.size
        
        # Get the processed image data
        processed_data = output.getvalue()
        
        return processed_data, content_type, width, height
    
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        # Return original data on error
        return image_data, None, None, None

def correct_image_orientation(img):
    """
    Correct image orientation based on EXIF data
    
    Args:
        img: PIL Image object
        
    Returns:
        PIL Image object with correct orientation
    """
    try:
        # Extract EXIF data
        exif = img._getexif()
        
        if (exif):
            # Find orientation tag
            orientation_key = None
            for key, value in ExifTags.TAGS.items():
                if value == 'Orientation':
                    orientation_key = key
                    break
            
            if orientation_key and orientation_key in exif:
                orientation = exif[orientation_key]
                
                # Rotate based on orientation value
                if orientation == 2:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    img = img.rotate(180)
                elif orientation == 4:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                elif orientation == 5:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(90)
                elif orientation == 6:
                    img = img.rotate(270)
                elif orientation == 7:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(270)
                elif orientation == 8:
                    img = img.rotate(90)
    
    except (AttributeError, KeyError, IndexError) as e:
        # Some images don't have EXIF data or have corrupt data
        logger.warning(f"Error processing EXIF orientation: {str(e)}")
    
    return img

def create_thumbnail(image_data, size=None):
    """
    Create a thumbnail from image data
    
    Args:
        image_data (bytes): Raw image data
        size (tuple): (width, height) for thumbnail, uses config default if None
        
    Returns:
        bytes: Thumbnail image data
    """
    if size is None:
        size = current_app.config.get('THUMBNAIL_SIZE', (300, 300))
    
    try:
        # Open the image
        img = Image.open(BytesIO(image_data))
        
        # Handle EXIF rotation
        img = correct_image_orientation(img)
        
        # Create a clean image without EXIF data
        if img.mode == 'RGBA':
            clean_img = Image.new('RGB', img.size)
        else:
            clean_img = Image.new(img.mode, img.size)
            
        # Copy the pixel data (without metadata)
        clean_img.paste(img)
        img = clean_img
        
        # Create thumbnail (maintains aspect ratio)
        img.thumbnail(size, Image.LANCZOS)
        
        # Save thumbnail to bytes
        output = BytesIO()
        
        # Save optimized JPEG with no EXIF data - higher quality for thumbnails
        img.save(output, format='JPEG', quality=95, optimize=True, exif=bytes())
        
        return output.getvalue()
    
    except Exception as e:
        logger.error(f"Error creating thumbnail: {str(e)}")
        return None

def get_image_dimensions(image_data):
    """
    Get image dimensions from image data
    
    Args:
        image_data (bytes): Raw image data
        
    Returns:
        tuple: (width, height) or None if error
    """
    try:
        img = Image.open(BytesIO(image_data))
        return img.size
    except Exception as e:
        logger.error(f"Error getting image dimensions: {str(e)}")
        return None

def is_valid_image_old(file_data, allowed_extensions=None):
    """Validate if data is a valid image"""
    if allowed_extensions is None:
        allowed_extensions = current_app.config.get(
            'ALLOWED_IMAGE_EXTENSIONS', 
            ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif']
        )
    
    # With pillow_heif, we can use PIL directly for all formats
    try:
        img = Image.open(BytesIO(file_data))
        img.verify()  # Verify it's an image
        
        # Check if format is allowed
        format_lower = img.format.lower() if img.format else ""
        if format_lower == "jpeg":
            format_lower = "jpg"
        elif format_lower == "heif":  # pillow_heif uses "heif" for both heic and heif
            return any(ext.lower() in ['heic', 'heif'] for ext in allowed_extensions)
            
        return format_lower in [ext.lower() for ext in allowed_extensions]
    except Exception as e:
        # Special case for HEIC detection if pillow-heif fails
        if HEIC_SUPPORT:
            # Try checking file signature
            try:
                first_bytes = file_data[:12]
                is_heic = (b'ftyp' in first_bytes and 
                          (b'heic' in first_bytes or b'heix' in first_bytes or 
                          b'hevc' in first_bytes or b'hevx' in first_bytes))
                
                if is_heic and any(ext.lower() in ['heic', 'heif'] for ext in allowed_extensions):
                    logger.warning(f"HEIC identified by signature but not by PIL")
                    return True
            except Exception:
                pass
                
        logger.warning(f"Image validation error: {str(e)}")
        return False

''' 临时解决iPhone相册图片上传问题 '''
def is_valid_image(image_data, allowed_extensions):
    try:
        # Try to open as image, which validates it's a real image
        img = Image.open(BytesIO(image_data))
        img.verify()  # Verify it's a valid image
        return True
    except Exception as e:
        current_app.logger.error(f"Image validation error: {str(e)}")
        return False