"""Assignment 1 orchestration.

Prereqs:
  - Configure an admin profile:  aws configure --profile admin
    (needs IAM, STS and S3 permissions)
  - Put an image named recording1.jpg in this directory.
"""

import boto3

import config
import iam_ops
import s3_ops
from sts_ops import assume_role


def main():
    # Step 0. Admin session and account id.
    admin = boto3.Session(profile_name=config.ADMIN_PROFILE)
    iam = admin.client('iam')
    account_id = admin.client('sts').get_caller_identity()['Account']
    print('Account ID:', account_id)

    dev_arn = config.dev_role_arn(account_id)
    user_arn_role = config.user_role_arn(account_id)
    bucket = config.bucket_name(account_id)

    # Step 1. User and access key.
    user_arn = iam_ops.create_user(iam, config.USER_NAME)
    print('Created user:', user_arn)
    key_id, secret = iam_ops.create_access_key(iam, config.USER_NAME)

    # Step 2. Roles with a trust policy pointing at the user.
    trust_policy = iam_ops.build_trust_policy(user_arn)
    iam_ops.create_role_with_retry(iam, config.DEV_ROLE, trust_policy)
    iam_ops.create_role_with_retry(iam, config.USER_ROLE, trust_policy)
    print('Created roles Dev and User')

    # Step 3. Attach permissions and let the user assume the roles.
    iam_ops.attach_managed_policy(iam, config.DEV_ROLE, config.DEV_POLICY_ARN)
    iam_ops.attach_managed_policy(iam, config.USER_ROLE, config.USER_POLICY_ARN)
    iam_ops.allow_assume_roles(iam, config.USER_NAME, config.ASSUME_POLICY_NAME,
                               [dev_arn, user_arn_role])

    # User session used to assume the roles below.
    user_sts = boto3.Session(aws_access_key_id=key_id,
                             aws_secret_access_key=secret).client('sts')

    # Step 4. Assume Dev, create the bucket and objects.
    s3 = assume_role(user_sts, dev_arn, 'dev_session').client('s3')
    s3_ops.create_bucket(s3, bucket, config.REGION)
    print('Created bucket:', bucket)
    s3_ops.put_objects(s3, bucket, config.IMAGE_FILE)
    print('Uploaded assignment1.txt, assignment2.txt, recording1.jpg')

    # Step 5. Assume User (read only) and total the "assignment" objects.
    s3_ro = assume_role(user_sts, user_arn_role, 'user_session').client('s3')
    size = s3_ops.total_size_with_prefix(s3_ro, bucket, config.OBJECT_PREFIX)
    print('Total size of objects with prefix assignment:', size, 'bytes')

    input('Show resources in the console, then press Enter to delete the bucket...')

    # Step 6. Assume Dev again and delete the bucket.
    s3 = assume_role(user_sts, dev_arn, 'dev_session_cleanup').client('s3')
    s3_ops.delete_bucket(s3, bucket)
    print('Deleted all objects and the bucket')

    # Optional IAM cleanup.
    if input('Press y then Enter to also clean up the IAM user and roles: ').strip() == 'y':
        iam_ops.delete_user(iam, config.USER_NAME, config.ASSUME_POLICY_NAME)
        iam_ops.delete_role(iam, config.DEV_ROLE, config.DEV_POLICY_ARN)
        iam_ops.delete_role(iam, config.USER_ROLE, config.USER_POLICY_ARN)
        print('Deleted IAM user and roles')


if __name__ == '__main__':
    main()
