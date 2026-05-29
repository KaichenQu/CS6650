"""S3 operations: bucket lifecycle, objects and size reporting."""


def create_bucket(s3, bucket, region):
    if region == 'us-east-1':
        s3.create_bucket(Bucket=bucket)
    else:
        s3.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={'LocationConstraint': region})


def put_objects(s3, bucket, image_file):
    s3.put_object(Bucket=bucket, Key='assignment1.txt', Body=b'Empty Assignment 1')
    s3.put_object(Bucket=bucket, Key='assignment2.txt', Body=b'Empty Assignment 2')
    s3.upload_file(image_file, bucket, image_file)


def total_size_with_prefix(s3, bucket, prefix):
    """Sum the sizes of all objects whose key starts with prefix."""
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return sum(obj['Size'] for obj in resp.get('Contents', []))


def delete_bucket(s3, bucket):
    """Empty the bucket (required) then delete it."""
    objects = s3.list_objects_v2(Bucket=bucket).get('Contents', [])
    if objects:
        s3.delete_objects(
            Bucket=bucket,
            Delete={'Objects': [{'Key': obj['Key']} for obj in objects]})
    s3.delete_bucket(Bucket=bucket)
