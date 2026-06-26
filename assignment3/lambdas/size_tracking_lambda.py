"""Size-tracking lambda.

Triggered by S3 object create/update/delete events on TestBucket. On every
trigger it totals the size of all objects currently in the bucket and writes a
snapshot (size, object count, timestamp, bucket name) to the size-history table.

The table name comes from the TABLE_NAME env var (CDK injects the
auto-generated name), so nothing about the table is hardcoded here. The bucket
name comes from the triggering event itself.

Runtime: Python 3.12. No layer needed (boto3 ships with the runtime).
"""

import os
import time

import boto3

TABLE_NAME = os.environ['TABLE_NAME']

ATTR_BUCKET = 'BucketName'
ATTR_TIMESTAMP = 'Timestamp'
ATTR_SIZE = 'TotalSize'
ATTR_COUNT = 'ObjectCount'
ATTR_GSIPK = 'GSIPK'
GSIPK_VALUE = 'ALL'

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')


def total_size(bucket):
    """Return (total_bytes, object_count) for all objects in the bucket."""
    total = 0
    count = 0
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            total += obj['Size']
            count += 1
    return total, count


def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    total, count = total_size(bucket)
    timestamp = int(time.time() * 1000)

    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            ATTR_BUCKET: {'S': bucket},
            ATTR_TIMESTAMP: {'N': str(timestamp)},
            ATTR_SIZE: {'N': str(total)},
            ATTR_COUNT: {'N': str(count)},
            ATTR_GSIPK: {'S': GSIPK_VALUE},
        },
    )

    print('bucket={} size={} count={} ts={}'.format(bucket, total, count, timestamp))
    return {'bucket': bucket, 'total_size': total, 'object_count': count}
