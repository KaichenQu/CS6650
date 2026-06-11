"""Part 1: create TestBucket and the S3-object-size-history table.

Runs on your laptop, not as a lambda.

Prereq: an admin profile with S3 and DynamoDB permissions:
    aws configure --profile admin

The table is designed to hold size history for any bucket, not just this one:
  - PK BucketName / SK Timestamp lets us query a single bucket's recent history.
  - A GSI (SizeIndex) on a constant partition key with TotalSize as the sort key
    lets us query the all-time maximum size across every bucket without a scan.
"""

import boto3
from botocore.exceptions import ClientError

import config


def create_bucket(s3, bucket, region):
    try:
        if region == 'us-east-1':
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={'LocationConstraint': region})
        print('Created bucket:', bucket)
    except ClientError as err:
        code = err.response['Error']['Code']
        if code in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
            print('Bucket already exists:', bucket)
        else:
            raise


def create_table(dynamodb):
    try:
        dynamodb.create_table(
            TableName=config.TABLE_NAME,
            BillingMode='PAY_PER_REQUEST',
            AttributeDefinitions=[
                {'AttributeName': config.ATTR_BUCKET, 'AttributeType': 'S'},
                {'AttributeName': config.ATTR_TIMESTAMP, 'AttributeType': 'N'},
                {'AttributeName': config.ATTR_GSIPK, 'AttributeType': 'S'},
                {'AttributeName': config.ATTR_SIZE, 'AttributeType': 'N'},
            ],
            KeySchema=[
                {'AttributeName': config.ATTR_BUCKET, 'KeyType': 'HASH'},
                {'AttributeName': config.ATTR_TIMESTAMP, 'KeyType': 'RANGE'},
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': config.GSI_NAME,
                'KeySchema': [
                    {'AttributeName': config.ATTR_GSIPK, 'KeyType': 'HASH'},
                    {'AttributeName': config.ATTR_SIZE, 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'KEYS_ONLY'},
            }],
        )
        print('Creating table:', config.TABLE_NAME)
        dynamodb.get_waiter('table_exists').wait(TableName=config.TABLE_NAME)
        print('Table is active:', config.TABLE_NAME)
    except dynamodb.exceptions.ResourceInUseException:
        print('Table already exists:', config.TABLE_NAME)


def main():
    session = boto3.Session(profile_name=config.ADMIN_PROFILE, region_name=config.REGION)
    account_id = session.client('sts').get_caller_identity()['Account']
    bucket = config.bucket_name(account_id)
    print('Account ID:', account_id)

    create_bucket(session.client('s3'), bucket, config.REGION)
    create_table(session.client('dynamodb'))

    print('\nDone. Bucket and table exist and are empty.')
    print('Bucket name (use as BUCKET_NAME env var in the lambdas):', bucket)


if __name__ == '__main__':
    main()
