"""Configuration constants for the local scripts (Part 1 and cleanup).

The lambda handlers are uploaded standalone and cannot import this module, so
they keep their own copies of the table/index/attribute names. Keep the two in
sync if you change anything here.
"""

# If you change this away from us-east-1, create_bucket adds a LocationConstraint.
REGION = 'us-east-1'

ADMIN_PROFILE = 'admin'

TABLE_NAME = 'S3-object-size-history'
GSI_NAME = 'SizeIndex'

# Attribute names (shared design with the lambda handlers).
ATTR_BUCKET = 'BucketName'
ATTR_TIMESTAMP = 'Timestamp'
ATTR_SIZE = 'TotalSize'
ATTR_COUNT = 'ObjectCount'
ATTR_GSIPK = 'GSIPK'
GSIPK_VALUE = 'ALL'

PLOT_KEY = 'plot'


def bucket_name(account_id):
    # Bucket names are globally unique; the account id keeps it unique.
    return 'cs6620-assignment2-{}'.format(account_id)
