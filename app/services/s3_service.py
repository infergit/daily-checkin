import os
import uuid
import boto3
import redis
import time
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from flask import current_app
import logging

# Add imports for CloudFront signed URLs (if using private content)
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from botocore.signers import CloudFrontSigner
    CLOUDFRONT_SIGNING_AVAILABLE = True
except ImportError:
    CLOUDFRONT_SIGNING_AVAILABLE = False

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
        
        # CloudFront configuration
        self.use_cloudfront = current_app.config.get('USE_CLOUDFRONT', False)
        self.cloudfront_domain = current_app.config.get('CLOUDFRONT_DOMAIN', '')
        self.cloudfront_key_pair_id = current_app.config.get('CLOUDFRONT_KEY_PAIR_ID', '')
        self.cloudfront_private_key_path = current_app.config.get('CLOUDFRONT_PRIVATE_KEY_PATH', '')
        
        # Default URL expiration (30 days in seconds)
        self.default_expires = 30 * 24 * 60 * 60  # 30 days
        
        # Initialize Redis client for URL caching
        self._init_redis_client()
        
        if self.use_cloudfront:
            current_app.logger.info(f"CloudFront distribution configured: {self.cloudfront_domain}")
    
    def _init_redis_client(self):
        """Initialize Redis client for URL caching"""
        try:
            redis_host = current_app.config.get('REDIS_HOST')
            redis_port = int(current_app.config.get('REDIS_PORT', 6379))
            redis_password = current_app.config.get('REDIS_PASSWORD')
            redis_ssl = current_app.config.get('REDIS_SSL', False)  # Changed to take boolean directly
            redis_db = int(current_app.config.get('REDIS_DB', 0))
            
            # If REDIS_URL is provided, use it instead of individual settings
            redis_url = current_app.config.get('REDIS_URL')
            
            if redis_url:
                self.redis_client = redis.from_url(
                    redis_url,
                    socket_timeout=0.8,  # 800ms timeout instead of default
                    socket_connect_timeout=0.8  # 800ms connection timeout
                )
                current_app.logger.info(f"Initialized Redis client using URL with 800ms timeout")
            elif redis_host:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password if redis_password else None,
                    ssl=redis_ssl,
                    db=redis_db,
                    socket_timeout=0.8,  # 800ms timeout instead of 5s
                    socket_connect_timeout=0.8  # 800ms connection timeout instead of 5s
                )
                current_app.logger.info(f"Initialized Redis client using host: {redis_host}, port: {redis_port}, timeout: 800ms")
            else:
                current_app.logger.warning("Redis configuration not found. URL caching disabled.")
                self.redis_client = None
                
            # Test Redis connection
            if self.redis_client:
                self.redis_client.ping()
                current_app.logger.info("Successfully connected to Redis")
        except Exception as e:
            current_app.logger.error(f"Failed to initialize Redis client: {e}")
            self.redis_client = None
    
    def _get_cached_url(self, cache_key):
        """
        Get a URL from Redis cache if available
        
        Args:
            cache_key: Redis cache key for the URL
            
        Returns:
            cached_url or None if not found
        """
        if not self.redis_client:
            return None
            
        try:
            cached_url = self.redis_client.get(cache_key)
            if cached_url:
                current_app.logger.debug(f"Cache hit for {cache_key}")
                return cached_url.decode('utf-8')
            current_app.logger.debug(f"Cache miss for {cache_key}")
            return None
        except Exception as e:
            current_app.logger.error(f"Error retrieving from Redis: {e}")
            return None
    
    def _cache_url(self, cache_key, url, expires):
        """
        Store URL in Redis cache with expiration
        
        Args:
            cache_key: Redis cache key
            url: The URL to cache
            expires: Validity period in seconds
        """
        if not self.redis_client or not url:
            return
            
        try:
            # Set TTL slightly shorter than actual URL expiry (90%)
            ttl = int(expires * 0.9)
            self.redis_client.setex(cache_key, ttl, url)
            current_app.logger.debug(f"Cached URL for {cache_key} with TTL {ttl}s")
        except Exception as e:
            current_app.logger.error(f"Error storing in Redis: {e}")
    
    def _invalidate_cache(self, s3_key):
        """
        Invalidate cache entries for a specific S3 key
        
        Args:
            s3_key: S3 object key to invalidate
        """
        if not self.redis_client:
            return
            
        try:
            # Remove both S3 and CloudFront URL cache entries
            s3_cache_key = f"s3_url:{s3_key}"
            cf_cache_key = f"cf_url:{s3_key}"
            thumb_cache_key = f"s3_url:thumbnails/{s3_key}"
            cf_thumb_cache_key = f"cf_url:thumbnails/{s3_key}"
            
            self.redis_client.delete(s3_cache_key, cf_cache_key, thumb_cache_key, cf_thumb_cache_key)
            current_app.logger.debug(f"Invalidated cache for {s3_key}")
        except Exception as e:
            current_app.logger.error(f"Error invalidating Redis cache: {e}")
    
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
    
    def get_cloudfront_url(self, s3_key, expires=None):
        """Get a CloudFront URL for a file
        
        Args:
            s3_key: File path in S3
            expires: URL validity period (seconds), default 30 days
            
        Returns:
            url: CloudFront URL
        """
        if expires is None:
            expires = self.default_expires
            
        if not self.use_cloudfront or not self.cloudfront_domain:
            # Fall back to S3 if CloudFront is not configured
            return self.get_file_url(s3_key, expires)
        
        # Create cache key
        cache_key = f"cf_url:{s3_key}"
        
        # Check cache first
        cached_url = self._get_cached_url(cache_key)
        if cached_url:
            return cached_url
        
        # If using CloudFront with private content, sign the URL
        if self.cloudfront_key_pair_id and self.cloudfront_private_key_path and CLOUDFRONT_SIGNING_AVAILABLE:
            try:
                # Check if the private key file exists
                if not os.path.exists(self.cloudfront_private_key_path):
                    current_app.logger.error(f"CloudFront private key not found at: {self.cloudfront_private_key_path}")
                    # Fall back to S3 presigned URL
                    url = self.s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.bucket_name, 'Key': s3_key},
                        ExpiresIn=expires
                    )
                    self._cache_url(cache_key, url, expires)
                    return url
                
                # Read the private key
                with open(self.cloudfront_private_key_path, 'rb') as key_file:
                    private_key = serialization.load_pem_private_key(
                        key_file.read(),
                        password=None,
                        backend=default_backend()
                    )
                
                # Create a signer
                def rsa_signer(message):
                    return private_key.sign(
                        message,
                        padding.PKCS1v15(),
                        hashes.SHA1()
                    )
                
                # Ensure s3_key doesn't start with a slash
                if s3_key.startswith('/'):
                    s3_key = s3_key[1:]
                    
                # Calculate expiration time
                expire_date = datetime.utcnow() + timedelta(seconds=expires)
                
                # Create CloudFront signer
                cloudfront_signer = CloudFrontSigner(self.cloudfront_key_pair_id, rsa_signer)
                
                # Generate the signed URL
                signed_url = cloudfront_signer.generate_presigned_url(
                    f"https://{self.cloudfront_domain}/{s3_key}",
                    date_less_than=expire_date
                )
                
                # Cache the URL
                self._cache_url(cache_key, signed_url, expires)
                
                current_app.logger.debug(f"Generated signed CloudFront URL for {s3_key}")
                return signed_url
                
            except Exception as e:
                current_app.logger.error(f"Error generating signed CloudFront URL: {e}")
                # Fall back to S3 presigned URL
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': s3_key},
                    ExpiresIn=expires
                )
                self._cache_url(cache_key, url, expires)
                return url
        
        # Regular CloudFront URL (fallback)
        url = f"https://{self.cloudfront_domain}/{s3_key}"
        self._cache_url(cache_key, url, expires)
        return url
    
    def _get_signed_cloudfront_url(self, s3_key, expires=3600):
        """Generate a signed CloudFront URL for private content
        
        Only used if CloudFront is configured with a key pair ID and private key
        """
        if not CLOUDFRONT_SIGNING_AVAILABLE:
            current_app.logger.warning("CloudFront signing packages not installed.")
            return f"https://{self.cloudfront_domain}/{s3_key}"
            
        key_path = self.cloudfront_private_key_path
        if not os.path.exists(key_path):
            current_app.logger.error(f"CloudFront private key not found at: {key_path}")
            return f"https://{self.cloudfront_domain}/{s3_key}"
        
        try:
            with open(key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
                
            expire_date = datetime.utcnow() + timedelta(seconds=expires)
            cloudfront_signer = CloudFrontSigner(self.cloudfront_key_pair_id, self._rsa_signer(private_key))
            
            # Generate the signed URL
            signed_url = cloudfront_signer.generate_presigned_url(
                f"https://{self.cloudfront_domain}/{s3_key}",
                date_less_than=expire_date
            )
            return signed_url
        except Exception as e:
            current_app.logger.error(f"Error creating signed CloudFront URL: {e}")
            return f"https://{self.cloudfront_domain}/{s3_key}"
    
    def _rsa_signer(self, private_key):
        """Return a signer function for CloudFront signed URLs"""
        def sign_with_key(message):
            return private_key.sign(
                message,
                padding.PKCS1v15(),
                hashes.SHA1()
            )
        return sign_with_key
    
    def get_file_url(self, s3_key, expires=None):
        """Get temporary access URL for a file
        
        Args:
            s3_key: File path in S3
            expires: URL validity period (seconds), default 30 days
            
        Returns:
            presigned_url: Signed temporary access URL
        """
        if expires is None:
            expires = self.default_expires
            
        # If CloudFront is enabled, use it instead of direct S3 URLs
        if self.use_cloudfront and self.cloudfront_domain:
            return self.get_cloudfront_url(s3_key, expires)
        
        # Create cache key
        cache_key = f"s3_url:{s3_key}"
        
        # Check cache first
        cached_url = self._get_cached_url(cache_key)
        if cached_url:
            return cached_url
            
        try:
            # Log the key we're trying to access for debugging
            current_app.logger.debug(f"Cache miss - Generating presigned URL for bucket:{self.bucket_name}, key:{s3_key}")
            
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expires
            )
            
            # Cache the URL
            self._cache_url(cache_key, presigned_url, expires)
            
            return presigned_url
            
        except ClientError as e:
            current_app.logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def generate_presigned_url(self, s3_key, expires=3600):
        """Alias for get_file_url method to maintain compatibility with templates"""
        return self.get_file_url(s3_key, expires)
    
    def get_thumbnail_url(self, original_key, expires=None):
        """Get thumbnail URL for an image
        
        Args:
            original_key: Original image key
            expires: URL validity period (seconds), default 30 days
            
        Returns:
            presigned_url: Signed thumbnail URL
        """
        if expires is None:
            expires = self.default_expires
            
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
        # If CloudFront is enabled, use it instead of direct S3 URLs
        if self.use_cloudfront and self.cloudfront_domain:
            return f"https://{self.cloudfront_domain}/{s3_key}"
            
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
            
            # Invalidate cache entries for this file
            self._invalidate_cache(s3_key)
            
            return True
            
        except ClientError as e:
            current_app.logger.error(f"Error deleting file from S3: {e}")