import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import uuid
from datetime import datetime

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file
load_dotenv()

def test_s3_connection():
    """Test AWS S3 connectivity and basic operations"""
    print("Testing AWS S3 connection...")
    
    # Load credentials from environment
    aws_access_key = os.environ.get('AWS_ACCESS_KEY')
    aws_secret_key = os.environ.get('AWS_SECRET_KEY')
    region = os.environ.get('AWS_REGION')
    bucket_name = os.environ.get('S3_BUCKET_NAME')
    
    if not all([aws_access_key, aws_secret_key, region, bucket_name]):
        print("ERROR: Missing required AWS credentials in .env file")
        return False
    
    try:
        # Create S3 client
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region
        )
        
        # Test bucket existence
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"✅ Successfully connected to bucket: {bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                print(f"❌ Bucket {bucket_name} does not exist")
            elif error_code == '403':
                print(f"❌ Access forbidden to bucket {bucket_name} - check permissions")
            else:
                print(f"❌ Error accessing bucket: {e}")
            return False
        
        # Generate a unique test file name
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        test_key = f"test/{timestamp}_{unique_id}_test.txt"
        test_content = f"This is a test file generated at {datetime.now().isoformat()}"
        
        # Create and upload test file
        print(f"Uploading test file as {test_key}...")
        s3.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print("✅ Upload successful")
        
        # Generate a presigned URL
        try:
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': test_key},
                ExpiresIn=3600
            )
            print(f"✅ Generated presigned URL: {url}")
        except ClientError as e:
            print(f"❌ Error generating URL: {e}")
        
        # Download the file
        try:
            response = s3.get_object(Bucket=bucket_name, Key=test_key)
            downloaded_content = response['Body'].read().decode('utf-8')
            if downloaded_content == test_content:
                print("✅ Downloaded file matches the uploaded content")
            else:
                print("❌ Downloaded file content doesn't match")
        except ClientError as e:
            print(f"❌ Error downloading file: {e}")
        
        # Delete the test file
        try:
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print("✅ Successfully deleted test file")
        except ClientError as e:
            print(f"❌ Error deleting test file: {e}")
        
        print("S3 connection test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == '__main__':
    success = test_s3_connection()
    if success:
        print("\n🎉 All S3 tests passed successfully!")
    else:
        print("\n❌ S3 tests failed. Please check your configuration.")
        sys.exit(1)