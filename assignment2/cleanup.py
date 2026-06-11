"""Clean up assignment 2 resources before a demo.

Empties and deletes TestBucket and deletes the S3-object-size-history table.
The matplotlib lambda layer is left untouched (the assignment lets you keep it).
"""

import boto3
from botocore.exceptions import ClientError

import config


def delete_bucket(s3, bucket):
    try:
        objects = s3.list_objects_v2(Bucket=bucket).get('Contents', [])
        if objects:
            s3.delete_objects(
                Bucket=bucket,
                Delete={'Objects': [{'Key': o['Key']} for o in objects]})
        s3.delete_bucket(Bucket=bucket)
        print('Deleted bucket:', bucket)
    except ClientError as err:
        if err.response['Error']['Code'] in ('NoSuchBucket', '404'):
            print('Bucket not found:', bucket)
        else:
            raise


def delete_table(dynamodb):
    try:
        dynamodb.delete_table(TableName=config.TABLE_NAME)
        dynamodb.get_waiter('table_not_exists').wait(TableName=config.TABLE_NAME)
        print('Deleted table:', config.TABLE_NAME)
    except dynamodb.exceptions.ResourceNotFoundException:
        print('Table not found:', config.TABLE_NAME)


def main():
    session = boto3.Session(profile_name=config.ADMIN_PROFILE, region_name=config.REGION)
    account_id = session.client('sts').get_caller_identity()['Account']
    bucket = config.bucket_name(account_id)

    delete_bucket(session.client('s3'), bucket)
    delete_table(session.client('dynamodb'))


if __name__ == '__main__':
    main()
