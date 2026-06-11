"""IAM operations: user, access key, roles, policies and cleanup."""

import json
import time


def create_user(iam, user_name):
    """Create the IAM user and return its ARN."""
    try:
        iam.create_user(UserName=user_name)
    except iam.exceptions.EntityAlreadyExistsException:
        pass
    return iam.get_user(UserName=user_name)['User']['Arn']


def create_access_key(iam, user_name):
    """Create an access key and return (access_key_id, secret_access_key)."""
    key = iam.create_access_key(UserName=user_name)['AccessKey']
    return key['AccessKeyId'], key['SecretAccessKey']


def build_trust_policy(user_arn):
    """Trust policy that lets the given user assume the role."""
    return {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": user_arn},
            "Action": "sts:AssumeRole"
        }]
    }


def create_role_with_retry(iam, role_name, trust_policy, retries=12, delay=5):
    """Create a role, retrying while the freshly created user ARN propagates.

    A just-created user is not immediately valid as a trust-policy principal,
    so CreateRole can raise MalformedPolicyDocument until IAM is consistent.
    """
    for _ in range(retries):
        try:
            iam.create_role(RoleName=role_name,
                            AssumeRolePolicyDocument=json.dumps(trust_policy))
            return
        except iam.exceptions.MalformedPolicyDocumentException:
            time.sleep(delay)
    iam.create_role(RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy))


def attach_managed_policy(iam, role_name, policy_arn):
    iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)


def allow_assume_roles(iam, user_name, policy_name, role_arns):
    """Give the user an inline policy permitting sts:AssumeRole on the roles."""
    iam.put_user_policy(
        UserName=user_name,
        PolicyName=policy_name,
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": list(role_arns)
            }]
        })
    )


def delete_user(iam, user_name, policy_name):
    """Remove inline policy and all access keys, then delete the user."""
    iam.delete_user_policy(UserName=user_name, PolicyName=policy_name)
    for key in iam.list_access_keys(UserName=user_name)['AccessKeyMetadata']:
        iam.delete_access_key(UserName=user_name, AccessKeyId=key['AccessKeyId'])
    iam.delete_user(UserName=user_name)


def delete_role(iam, role_name, policy_arn):
    """Detach the managed policy, then delete the role."""
    iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    iam.delete_role(RoleName=role_name)
