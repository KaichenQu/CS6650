"""Configuration constants and derived names for the assignment."""

ADMIN_PROFILE = 'admin'

USER_NAME = 'assignment1_user'
DEV_ROLE = 'Dev'
USER_ROLE = 'User'

# Managed policies attached to each role.
DEV_POLICY_ARN = 'arn:aws:iam::aws:policy/AmazonS3FullAccess'
USER_POLICY_ARN = 'arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess'

ASSUME_POLICY_NAME = 'allow_assume_roles'

# If you change this away from us-east-1, create_bucket adds a LocationConstraint.
REGION = 'us-east-1'

IMAGE_FILE = 'recording1.jpg'
OBJECT_PREFIX = 'assignment'


def dev_role_arn(account_id):
    return 'arn:aws:iam::{}:role/{}'.format(account_id, DEV_ROLE)


def user_role_arn(account_id):
    return 'arn:aws:iam::{}:role/{}'.format(account_id, USER_ROLE)


def bucket_name(account_id):
    # Bucket names are globally unique; the account id keeps it unique.
    return 'cs6620-assignment1-{}'.format(account_id)
