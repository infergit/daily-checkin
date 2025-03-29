import os
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from flask import current_app
import logging

class S3Service:
    """
    S3 Storage Service
    Handles image upload, retrieval, and deletion operations
    """
    
    def __init__(self):
        """Initialize S3 client"""
        # Ensure we log the region we're using
        region = current_app.config['AWS_REGION']
        current_app.logger.info(f"Initializing S3 client with region: {region}")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY'],
            aws_secret_access_key=current_app.config['AWS_SECRET_KEY'],
            region_name=region
        )
        self.bucket_name = current_app.config['S3_BUCKET_NAME']
    
    def generate_s3_key(self, user_id, project_id, filename):
        """Generate unique S3 storage path
        
        Format: checkins/{user_id}/{project_id}/{timestamp}_{uuid}_{filename}
        """
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        extension = os.path.splitext(filename)[1].lower()
        
        # Ensure filename is safe
        safe_filename = f"{timestamp}_{unique_id}{extension}"
        
        return f"checkins/{user_id}/{project_id}/{safe_filename}"
    
    def upload_file(self, file_data, s3_key, content_type):
        """Upload file to S3
        
        Args:
            file_data: File content
            s3_key: S3 storage path
            content_type: File MIME type
            
        Returns:
            s3_key: File path in S3
            file_size: File size
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType=content_type
            )
            
            file_size = len(file_data)
            return s3_key, file_size
            
        except ClientError as e:
            current_app.logger.error(f"Error uploading to S3: {e}")
            raise
    
    def get_file_url(self, s3_key, expires=3600):
        """Get temporary access URL for a file
        
        Args:
            s3_key: File path in S3
            expires: URL validity period (seconds), default 1 hour
            
        Returns:
            presigned_url: Signed temporary access URL
        """
        try:
            # Log the key we're trying to access for debugging
            current_app.logger.debug(f"Generating presigned URL for bucket:{self.bucket_name}, key:{s3_key}")
            
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expires
            )
            return presigned_url
            
        except ClientError as e:
            current_app.logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def generate_presigned_url(self, s3_key, expires=3600):
        """Alias for get_file_url method to maintain compatibility with templates"""
        return self.get_file_url(s3_key, expires)
    
    def get_thumbnail_url(self, original_key, expires=3600):
        """Get thumbnail URL for an image
        
        Args:
            original_key: Original image key
            expires: URL validity period (seconds)
            
        Returns:
            presigned_url: Signed thumbnail URL
        """
        # Make sure we don't have multiple 'thumbnails/' prefixes
        if original_key.startswith('thumbnails/'):
            thumbnail_key = original_key
        else:
            thumbnail_key = f"thumbnails/{original_key}"
        
        # For debugging
        current_app.logger.debug(f"Getting thumbnail URL for original key: {original_key}, thumbnail key: {thumbnail_key}")
            
        return self.get_file_url(thumbnail_key, expires)
    
    def get_direct_url(self, s3_key):
        """Get a direct (non-presigned) URL to the S3 object
        
        Use this as a fallback if presigned URLs aren't working
        Note: Object must be publicly accessible for this to work
        """
        region = current_app.config['AWS_REGION']
        return f"https://{self.bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
    
    def delete_file(self, s3_key):
        """Delete file from S3
        
        Args:
            s3_key: File path in S3
            
        Returns:
            bool: Whether deletion was successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
            
        except ClientError as e:
            current_app.logger.error(f"Error deleting file from S3: {e}")
            return False