"""Tears down everything deploy_lambdas.py created: the three lambdas, their
IAM roles, the matplotlib layer, and the API Gateway REST API.

Matches resources by config.RESOURCE_PREFIXES rather than exact names, so it also
catches resources whose names AWS suffixed (e.g. console-created roles like
cs6620-a2-driver-role-62e9pljd). AWS service-linked roles are never touched.

Does not touch the bucket or DynamoDB table — use cleanup.py for those.
"""

import boto3
from botocore.exceptions import ClientError

import config

PREFIXES = config.RESOURCE_PREFIXES


def delete_functions(lam):
    found = False
    paginator = lam.get_paginator('list_functions')
    for page in paginator.paginate():
        for fn in page['Functions']:
            if fn['FunctionName'].startswith(PREFIXES):
                lam.delete_function(FunctionName=fn['FunctionName'])
                print('Deleted function:', fn['FunctionName'])
                found = True
    if not found:
        print('No functions found with prefix:', PREFIXES)


def delete_roles(iam):
    found = False
    paginator = iam.get_paginator('list_roles')
    for page in paginator.paginate():
        for role in page['Roles']:
            name = role['RoleName']
            # Never delete AWS service-linked roles.
            if role['Path'].startswith('/aws-service-role/'):
                continue
            if not name.startswith(PREFIXES):
                continue
            delete_role(iam, name)
            found = True
    if not found:
        print('No roles found with prefix:', PREFIXES)


def delete_role(iam, role_name):
    for policy in iam.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']:
        iam.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
    for policy_name in iam.list_role_policies(RoleName=role_name)['PolicyNames']:
        iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
    iam.delete_role(RoleName=role_name)
    print('Deleted role:', role_name)


def delete_layers(lam):
    found = False
    paginator = lam.get_paginator('list_layers')
    for page in paginator.paginate():
        for layer in page['Layers']:
            if not layer['LayerName'].startswith(PREFIXES):
                continue
            versions = lam.list_layer_versions(LayerName=layer['LayerName']).get('LayerVersions', [])
            for v in versions:
                lam.delete_layer_version(LayerName=layer['LayerName'], VersionNumber=v['Version'])
                print('Deleted layer version:', layer['LayerName'], v['Version'])
                found = True
    if not found:
        print('No layers found with prefix:', PREFIXES)


def delete_rest_apis(apigw):
    found = False
    for api in apigw.get_rest_apis(limit=500).get('items', []):
        if api['name'].startswith(PREFIXES):
            apigw.delete_rest_api(restApiId=api['id'])
            print('Deleted REST API:', api['name'], api['id'])
            found = True
    if not found:
        print('No REST APIs found with prefix:', PREFIXES)


def main():
    session = boto3.Session(profile_name=config.ADMIN_PROFILE, region_name=config.REGION)

    lam = session.client('lambda')
    iam = session.client('iam')
    apigw = session.client('apigateway')

    delete_functions(lam)
    delete_roles(iam)
    delete_layers(lam)
    delete_rest_apis(apigw)

    print('\nDone.')


if __name__ == '__main__':
    main()
