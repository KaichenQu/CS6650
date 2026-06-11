"""Delete all assignment1 AWS resources so main.py can run clean."""

import boto3
from botocore.exceptions import ClientError
import config
import s3_ops


def delete_bucket_if_exists(s3, bucket):
    try:
        s3_ops.delete_bucket(s3, bucket)
        print('Deleted bucket:', bucket)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucket':
            print('Bucket not found, skipping')
        else:
            raise


def delete_user_if_exists(iam, user_name, policy_name):
    try:
        iam.delete_user_policy(UserName=user_name, PolicyName=policy_name)
    except iam.exceptions.NoSuchEntityException:
        pass
    try:
        for key in iam.list_access_keys(UserName=user_name)['AccessKeyMetadata']:
            iam.delete_access_key(UserName=user_name, AccessKeyId=key['AccessKeyId'])
        iam.delete_user(UserName=user_name)
        print('Deleted user:', user_name)
    except iam.exceptions.NoSuchEntityException:
        print('User not found, skipping')


def delete_role_if_exists(iam, role_name, policy_arn):
    try:
        iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    except iam.exceptions.NoSuchEntityException:
        pass
    try:
        iam.delete_role(RoleName=role_name)
        print('Deleted role:', role_name)
    except iam.exceptions.NoSuchEntityException:
        print('Role not found, skipping:', role_name)


def main():
    admin = boto3.Session(profile_name=config.ADMIN_PROFILE)
    iam = admin.client('iam')
    s3 = admin.client('s3')
    account_id = admin.client('sts').get_caller_identity()['Account']

    delete_bucket_if_exists(s3, config.bucket_name(account_id))
    delete_user_if_exists(iam, config.USER_NAME, config.ASSUME_POLICY_NAME)
    delete_role_if_exists(iam, config.DEV_ROLE, config.DEV_POLICY_ARN)
    delete_role_if_exists(iam, config.USER_ROLE, config.USER_POLICY_ARN)
    print('Cleanup done.')


if __name__ == '__main__':
    main()
