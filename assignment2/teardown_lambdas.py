"""Tears down everything deploy_lambdas.py created: the three lambdas, their
IAM roles, the matplotlib layer, and the API Gateway REST API.

Does not touch the bucket or DynamoDB table — use cleanup.py for those.
"""

import boto3
from botocore.exceptions import ClientError

import config

BASIC_EXEC_POLICY_ARN = 'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'


def delete_function(lam, name):
    try:
        lam.delete_function(FunctionName=name)
        print('Deleted function:', name)
    except ClientError as err:
        if err.response['Error']['Code'] != 'ResourceNotFoundException':
            raise
        print('Function not found:', name)


def delete_role(iam, role_name):
    try:
        iam.detach_role_policy(RoleName=role_name, PolicyArn=BASIC_EXEC_POLICY_ARN)
    except ClientError as err:
        if err.response['Error']['Code'] != 'NoSuchEntity':
            raise

    try:
        iam.delete_role_policy(RoleName=role_name, PolicyName=role_name + '-inline')
    except ClientError as err:
        if err.response['Error']['Code'] != 'NoSuchEntity':
            raise

    try:
        iam.delete_role(RoleName=role_name)
        print('Deleted role:', role_name)
    except ClientError as err:
        if err.response['Error']['Code'] != 'NoSuchEntity':
            raise
        print('Role not found:', role_name)


def delete_layer(lam):
    versions = lam.list_layer_versions(LayerName=config.LAYER_NAME).get('LayerVersions', [])
    for v in versions:
        lam.delete_layer_version(LayerName=config.LAYER_NAME, VersionNumber=v['Version'])
        print('Deleted layer version:', config.LAYER_NAME, v['Version'])
    if not versions:
        print('Layer not found:', config.LAYER_NAME)


def delete_rest_api(apigw):
    apis = apigw.get_rest_apis(limit=500).get('items', [])
    for api in apis:
        if api['name'] == config.API_NAME:
            apigw.delete_rest_api(restApiId=api['id'])
            print('Deleted REST API:', api['id'])
            return
    print('REST API not found:', config.API_NAME)


def main():
    session = boto3.Session(profile_name=config.ADMIN_PROFILE, region_name=config.REGION)

    lam = session.client('lambda')
    iam = session.client('iam')
    apigw = session.client('apigateway')

    delete_function(lam, config.SIZE_TRACKING_FUNCTION)
    delete_function(lam, config.PLOTTING_FUNCTION)
    delete_function(lam, config.DRIVER_FUNCTION)

    delete_role(iam, config.SIZE_TRACKING_ROLE)
    delete_role(iam, config.PLOTTING_ROLE)
    delete_role(iam, config.DRIVER_ROLE)

    delete_layer(lam)
    delete_rest_api(apigw)

    print('\nDone.')


if __name__ == '__main__':
    main()
