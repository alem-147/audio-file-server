"""S3-compatible object storage client for audio files.

Talks to MinIO locally and to AWS S3 in production without code changes,
since both implement the same S3 API.
"""

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from server.config import Settings


def create_s3_client(settings: Settings) -> BaseClient:
    """Build a boto3 S3 client from application settings."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def ensure_bucket_exists(client: BaseClient, bucket_name: str) -> None:
    """Create the bucket if it does not already exist.

    Idempotent: safe to call on every app startup. This is a local-dev
    convenience only, not the intended path in production, where bucket
    provisioning should be handled by infra-as-code and the app's runtime
    credentials should not have CreateBucket permission (see
    docs/design/infra.md).
    """
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code not in ("404", "NoSuchBucket"):
            raise
        client.create_bucket(Bucket=bucket_name)
