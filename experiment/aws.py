import boto3
from botocore.exceptions import NoCredentialsError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Utility function for uploading files to S3
def upload_to_s3(file_path, s3_path):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    try:
        s3_client.upload_file(file_path, settings.AWS_STORAGE_BUCKET_NAME, s3_path)
        s3_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{s3_path}"
        logger.info(f"Uploaded {file_path} to {s3_url}")
        return s3_url
    except FileNotFoundError:
        logger.error(f"File {file_path} was not found.")
    except NoCredentialsError:
        logger.error("AWS credentials not available.")
    except Exception as e:
        logger.error(f"Failed to upload {file_path} to S3: {str(e)}")
    return None