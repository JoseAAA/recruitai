"""
MinIO S3-compatible Storage Adapter for RecruitAI.
Handles file upload, download, and URL generation for CVs and Job Profiles.
"""
import io
import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Bucket names
BUCKET_CVS = "recruitai-cvs"
BUCKET_JOB_PROFILES = "recruitai-job-profiles"


class StorageService:
    """S3-compatible storage service using MinIO."""

    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "recruitai")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "recruitai_secret")

        self.client = boto3.client(
            "s3",
            endpoint_url=f"http://{self.endpoint}",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="us-east-1",
        )

        # Ensure buckets exist on startup
        self._ensure_buckets()

    def _ensure_buckets(self):
        """Create buckets if they don't exist."""
        for bucket in [BUCKET_CVS, BUCKET_JOB_PROFILES]:
            try:
                self.client.head_bucket(Bucket=bucket)
            except ClientError:
                try:
                    self.client.create_bucket(Bucket=bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")
                except Exception as e:
                    logger.warning(f"Could not create bucket {bucket}: {e}")

    def upload_file(
        self,
        bucket: str,
        object_key: str,
        file_bytes: bytes,
        content_type: str = "application/octet-stream",
        filename: Optional[str] = None,
    ) -> str:
        """
        Upload a file to MinIO.

        Returns the object key for later retrieval.
        """
        metadata = {}
        if filename:
            metadata["original-filename"] = filename

        self.client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=io.BytesIO(file_bytes),
            ContentLength=len(file_bytes),
            ContentType=content_type,
            Metadata=metadata,
        )
        logger.info(f"Uploaded {object_key} to {bucket} ({len(file_bytes)} bytes)")
        return object_key

    def download_file(self, bucket: str, object_key: str) -> tuple[bytes, str, str]:
        """
        Download a file from MinIO.

        Returns (file_bytes, content_type, original_filename).
        """
        response = self.client.get_object(Bucket=bucket, Key=object_key)
        file_bytes = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")

        # Try to get original filename from metadata
        metadata = response.get("Metadata", {})
        original_filename = metadata.get("original-filename", object_key.split("/")[-1])

        return file_bytes, content_type, original_filename

    def file_exists(self, bucket: str, object_key: str) -> bool:
        """Check if a file exists in MinIO."""
        try:
            self.client.head_object(Bucket=bucket, Key=object_key)
            return True
        except ClientError:
            return False

    def delete_file(self, bucket: str, object_key: str) -> None:
        """Delete a file from MinIO."""
        try:
            self.client.delete_object(Bucket=bucket, Key=object_key)
            logger.info(f"Deleted {object_key} from {bucket}")
        except Exception as e:
            logger.warning(f"Could not delete {object_key} from {bucket}: {e}")

    def upload_cv(self, candidate_id: str, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Upload a CV file. Returns the object key."""
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "pdf"
        object_key = f"{candidate_id}/cv.{ext}"
        return self.upload_file(BUCKET_CVS, object_key, file_bytes, content_type, filename)

    def upload_job_profile(self, job_id: str, file_bytes: bytes, filename: str, content_type: str) -> str:
        """Upload a job profile document. Returns the object key."""
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "pdf"
        object_key = f"{job_id}/{filename}"
        return self.upload_file(BUCKET_JOB_PROFILES, object_key, file_bytes, content_type, filename)

    def download_cv(self, candidate_id: str) -> tuple[bytes, str, str]:
        """Download a candidate's CV. Tries common extensions."""
        for ext in ["pdf", "docx", "doc"]:
            key = f"{candidate_id}/cv.{ext}"
            if self.file_exists(BUCKET_CVS, key):
                return self.download_file(BUCKET_CVS, key)
        raise FileNotFoundError(f"No CV found for candidate {candidate_id}")

    def delete_cv(self, candidate_id: str) -> None:
        """Delete a candidate's CV. Tries common extensions."""
        for ext in ["pdf", "docx", "doc"]:
            key = f"{candidate_id}/cv.{ext}"
            self.delete_file(BUCKET_CVS, key)
