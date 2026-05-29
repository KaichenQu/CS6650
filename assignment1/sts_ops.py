"""STS helper for assuming a role from a user session."""

import time

import boto3
from botocore.exceptions import ClientError


def assume_role(sts_client, role_arn, session_name, retries=12, delay=5):
    """Assume a role and return a new boto3 Session.

    Retries while the new access key and inline policy propagate (IAM is
    eventually consistent).
    """
    last_error = None
    for _ in range(retries):
        try:
            creds = sts_client.assume_role(
                RoleArn=role_arn, RoleSessionName=session_name)['Credentials']
            return boto3.Session(
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'])
        except ClientError as err:
            last_error = err
            time.sleep(delay)
    raise last_error
