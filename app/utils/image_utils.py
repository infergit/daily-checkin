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

def process_image(image_data, max_width=1200, quality=85, format='JPEG'):
    """
    Process an image for storage with optimized memory usage
    """
    try:
        # Use a context manager with BytesIO to ensure proper cleanup
        with BytesIO(image_data) as input_stream:
            # Open image but don't fully decode it yet
            img = Image.open(input_stream)
            
            # Record format before any processing
            original_format = img.format
            is_heif = original_format in ['HEIF', 'HEIC']
            
            # Get original dimensions first - this doesn't fully load the image
            original_width, original_height = img.size
            
            # Calculate new dimensions if needed - before loading full image
            if original_width > max_width:
                ratio = max_width / original_width
                new_height = int(original_height * ratio)
                new_dimensions = (max_width, new_height)
                resize_needed = True
            else:
                new_dimensions = (original_width, original_height)
                resize_needed = False
            
            # Now fully load the image and process it
            img.load()
            
            # Handle EXIF rotation - simpler handling to reduce memory usage
            if not is_heif and hasattr(img, '_getexif') and img._getexif():
                orientation_key = next((k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None)
                if orientation_key and orientation_key in img._getexif():
                    orientation = img._getexif()[orientation_key]
                    if orientation in [3, 6, 8]:
                        if orientation == 3:
                            img = img.rotate(180, expand=True)
                        elif orientation == 6:
                            img = img.rotate(270, expand=True)
                        elif orientation == 8:
                            img = img.rotate(90, expand=True)
            
            # Handle format conversion and resize in one step when possible
            if format == 'JPEG' and img.mode == 'RGBA':
                # If RGBA and saving as JPEG, convert to RGB
                if resize_needed:
                    img = img.resize(new_dimensions, Image.LANCZOS).convert('RGB')
                else:
                    img = img.convert('RGB')
            elif resize_needed:
                img = img.resize(new_dimensions, Image.LANCZOS)
            
            # Save processed image directly to bytes
            output = BytesIO()
            
            # Set appropriate content type
            content_types = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'WEBP': 'image/webp'
            }
            content_type = content_types.get(format, 'image/jpeg')
            
            # Use lower quality (85 instead of 100) for better compression
            if format == 'JPEG':
                img.save(output, format=format, quality=quality, optimize=True)
            elif format == 'PNG':
                img.save(output, format=format, optimize=True)
            elif format == 'WEBP':
                img.save(output, format=format, quality=quality)
            else:
                img.save(output, format='JPEG', quality=quality, optimize=True)
            
            # Get final dimensions
            width, height = img.size
            
            # Get processed data and explicitly close images
            output.seek(0)
            processed_data = output.getvalue()
            
            # Explicitly close and delete objects to free memory
            img.close()
            del img
            output.close()
            
            return processed_data, content_type, width, height
    
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
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
        # Skip EXIF processing for HEIF images
        if isinstance(img, Image.Image) and hasattr(img, 'format') and img.format in ['HEIF', 'HEIC']:
            logger.info("Skipping EXIF orientation for HEIF/HEIC image")
            return img
            
        # Extract EXIF data (only for JPEG and similar formats)
        if hasattr(img, '_getexif'):
            exif = img._getexif()
            
            if exif:
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
    if size is None:
        size = current_app.config.get('THUMBNAIL_SIZE', (300, 300))
    
    try:
        # First, downsize the image to a more manageable size before creating thumbnail
        with BytesIO(image_data) as input_stream:
            # Open image but don't decode fully
            with Image.open(input_stream) as img:
                original_format = img.format
                original_size = img.size
                
                # Directly create thumbnail - more memory efficient
                img.thumbnail(size, Image.LANCZOS)
                
                # Save as JPEG with reasonable quality
                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                
                thumbnail_data = output.getvalue()
                output.close()
                return thumbnail_data
                
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