"""CLI replacement for the console steps B-E in the README.

Creates IAM roles, the matplotlib layer, the three lambdas, the S3 trigger,
and the API Gateway REST API, then wires the driver lambda's env vars.

Prereq: run create_resources.py first (bucket + table must exist) and build
the matplotlib layer zip:
    mkdir -p layer_build/python
    python3 -m pip install matplotlib -t layer_build/python \
        --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all:
    cd layer_build && zip -r -q ../matplotlib-layer.zip python && cd ..
"""

import io
import json
import os
import time
import zipfile

import boto3
from botocore.exceptions import ClientError

import config

HERE = os.path.dirname(os.path.abspath(__file__))
LAYER_ZIP = os.path.join(HERE, 'matplotlib-layer.zip')

TRUST_POLICY = json.dumps({
    'Version': '2012-10-17',
    'Statement': [{
        'Effect': 'Allow',
        'Principal': {'Service': 'lambda.amazonaws.com'},
        'Action': 'sts:AssumeRole',
    }],
})

BASIC_EXEC_POLICY_ARN = 'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'


def zip_lambda(src_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(src_path, arcname='lambda_function.py')
    return buf.getvalue()


def ensure_role(iam, role_name, inline_policy):
    try:
        resp = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=TRUST_POLICY,
        )
        role_arn = resp['Role']['Arn']
        print('Created role:', role_name)
    except ClientError as err:
        if err.response['Error']['Code'] != 'EntityAlreadyExists':
            raise
        role_arn = iam.get_role(RoleName=role_name)['Role']['Arn']
        print('Role already exists:', role_name)

    iam.attach_role_policy(RoleName=role_name, PolicyArn=BASIC_EXEC_POLICY_ARN)
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=role_name + '-inline',
        PolicyDocument=json.dumps(inline_policy),
    )
    return role_arn


def ensure_function(lam, name, role_arn, code_path, env=None, layers=None,
                     timeout=30, memory=128):
    code = {'ZipFile': zip_lambda(code_path)}
    kwargs = dict(
        FunctionName=name,
        Runtime='python3.12',
        Role=role_arn,
        Handler='lambda_function.lambda_handler',
        Code=code,
        Timeout=timeout,
        MemorySize=memory,
    )
    if env is not None:
        kwargs['Environment'] = {'Variables': env}
    if layers is not None:
        kwargs['Layers'] = layers

    for attempt in range(6):
        try:
            resp = lam.create_function(**kwargs)
            print('Created function:', name)
            return resp['FunctionArn']
        except ClientError as err:
            code_name = err.response['Error']['Code']
            if code_name == 'ResourceConflictException':
                lam.update_function_code(FunctionName=name, ZipFile=code['ZipFile'])
                update_kwargs = dict(
                    FunctionName=name, Timeout=timeout, MemorySize=memory,
                    Role=role_arn, Handler='lambda_function.lambda_handler',
                )
                if env is not None:
                    update_kwargs['Environment'] = {'Variables': env}
                if layers is not None:
                    update_kwargs['Layers'] = layers
                lam.get_waiter('function_updated').wait(FunctionName=name)
                lam.update_function_configuration(**update_kwargs)
                print('Updated function:', name)
                return lam.get_function(FunctionName=name)['Configuration']['FunctionArn']
            if code_name == 'InvalidParameterValueException' and attempt < 5:
                # IAM role not yet propagated.
                time.sleep(5)
                continue
            raise
    raise RuntimeError('Could not create function ' + name)


def ensure_layer(lam, force=False):
    versions = lam.list_layer_versions(LayerName=config.LAYER_NAME).get('LayerVersions', [])
    if versions and not force:
        arn = versions[0]['LayerVersionArn']
        print('Layer already exists:', arn)
        return arn

    with open(LAYER_ZIP, 'rb') as f:
        content = f.read()
    resp = lam.publish_layer_version(
        LayerName=config.LAYER_NAME,
        Content={'ZipFile': content},
        CompatibleRuntimes=['python3.12'],
        CompatibleArchitectures=['x86_64'],
    )
    print('Published layer:', resp['LayerVersionArn'])
    return resp['LayerVersionArn']


def setup_s3_trigger(lam, s3, bucket, account_id, function_arn):
    try:
        lam.add_permission(
            FunctionName=config.SIZE_TRACKING_FUNCTION,
            StatementId='AllowS3Invoke',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn='arn:aws:s3:::' + bucket,
            SourceAccount=account_id,
        )
    except ClientError as err:
        if err.response['Error']['Code'] != 'ResourceConflictException':
            raise

    time.sleep(5)
    s3.put_bucket_notification_configuration(
        Bucket=bucket,
        NotificationConfiguration={
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': function_arn,
                'Events': ['s3:ObjectCreated:*', 's3:ObjectRemoved:*'],
            }],
        },
    )
    print('S3 trigger configured on bucket:', bucket)


def ensure_rest_api(apigw):
    apis = apigw.get_rest_apis(limit=500).get('items', [])
    for api in apis:
        if api['name'] == config.API_NAME:
            print('API already exists:', api['id'])
            return api['id']
    api = apigw.create_rest_api(name=config.API_NAME)
    print('Created REST API:', api['id'])
    return api['id']


def ensure_resource(apigw, api_id):
    resources = apigw.get_resources(restApiId=api_id, limit=500)['items']
    root_id = next(r['id'] for r in resources if r['path'] == '/')
    for r in resources:
        if r.get('pathPart') == config.API_RESOURCE_PATH:
            return r['id']
    resource = apigw.create_resource(
        restApiId=api_id, parentId=root_id, pathPart=config.API_RESOURCE_PATH)
    return resource['id']


def setup_api_gateway(apigw, lam, region, account_id, function_arn):
    api_id = ensure_rest_api(apigw)
    resource_id = ensure_resource(apigw, api_id)

    try:
        apigw.put_method(
            restApiId=api_id, resourceId=resource_id,
            httpMethod='GET', authorizationType='NONE')
    except ClientError as err:
        if err.response['Error']['Code'] != 'ConflictException':
            raise

    integration_uri = (
        'arn:aws:apigateway:{}:lambda:path/2015-03-31/functions/{}/invocations'
    ).format(region, function_arn)
    apigw.put_integration(
        restApiId=api_id, resourceId=resource_id, httpMethod='GET',
        type='AWS_PROXY', integrationHttpMethod='POST', uri=integration_uri)

    try:
        lam.add_permission(
            FunctionName=config.PLOTTING_FUNCTION,
            StatementId='AllowAPIGatewayInvoke',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn='arn:aws:execute-api:{}:{}:{}/*/GET/{}'.format(
                region, account_id, api_id, config.API_RESOURCE_PATH),
        )
    except ClientError as err:
        if err.response['Error']['Code'] != 'ResourceConflictException':
            raise

    apigw.create_deployment(restApiId=api_id, stageName=config.API_STAGE)
    url = 'https://{}.execute-api.{}.amazonaws.com/{}/{}'.format(
        api_id, region, config.API_STAGE, config.API_RESOURCE_PATH)
    print('API deployed:', url)
    return url


def main():
    session = boto3.Session(profile_name=config.ADMIN_PROFILE, region_name=config.REGION)
    account_id = session.client('sts').get_caller_identity()['Account']
    bucket = config.bucket_name(account_id)
    region = config.REGION

    bucket_arn = 'arn:aws:s3:::' + bucket
    table_arn = 'arn:aws:dynamodb:{}:{}:table/{}'.format(region, account_id, config.TABLE_NAME)

    iam = session.client('iam')
    lam = session.client('lambda')
    s3 = session.client('s3')
    apigw = session.client('apigateway')

    # --- IAM roles ---
    size_tracking_role = ensure_role(iam, config.SIZE_TRACKING_ROLE, {
        'Version': '2012-10-17',
        'Statement': [
            {'Effect': 'Allow', 'Action': ['s3:ListBucket', 's3:GetObject'],
             'Resource': [bucket_arn, bucket_arn + '/*']},
            {'Effect': 'Allow', 'Action': 'dynamodb:PutItem', 'Resource': table_arn},
        ],
    })
    plotting_role = ensure_role(iam, config.PLOTTING_ROLE, {
        'Version': '2012-10-17',
        'Statement': [
            {'Effect': 'Allow', 'Action': 'dynamodb:Query',
             'Resource': [table_arn, table_arn + '/index/' + config.GSI_NAME]},
            {'Effect': 'Allow', 'Action': 's3:PutObject', 'Resource': bucket_arn + '/*'},
        ],
    })
    driver_role = ensure_role(iam, config.DRIVER_ROLE, {
        'Version': '2012-10-17',
        'Statement': [
            {'Effect': 'Allow', 'Action': ['s3:PutObject', 's3:DeleteObject'],
             'Resource': bucket_arn + '/*'},
        ],
    })

    print('Waiting for IAM role propagation...')
    time.sleep(10)

    # --- matplotlib layer ---
    layer_arn = ensure_layer(lam)

    # --- size-tracking lambda + S3 trigger ---
    size_tracking_arn = ensure_function(
        lam, config.SIZE_TRACKING_FUNCTION, size_tracking_role,
        os.path.join(HERE, 'size_tracking_lambda.py'))
    setup_s3_trigger(lam, s3, bucket, account_id, size_tracking_arn)

    # --- plotting lambda + API Gateway ---
    plotting_arn = ensure_function(
        lam, config.PLOTTING_FUNCTION, plotting_role,
        os.path.join(HERE, 'plotting_lambda.py'),
        env={'BUCKET_NAME': bucket}, layers=[layer_arn], memory=256)
    plot_api_url = setup_api_gateway(apigw, lam, region, account_id, plotting_arn)

    # --- driver lambda ---
    ensure_function(
        lam, config.DRIVER_FUNCTION, driver_role,
        os.path.join(HERE, 'driver_lambda.py'),
        env={'BUCKET_NAME': bucket, 'PLOT_API_URL': plot_api_url})

    print('\nDone.')
    print('Bucket:', bucket)
    print('Plot API URL:', plot_api_url)
    print('Invoke the driver lambda to run the demo:')
    print('  aws lambda invoke --profile {} --function-name {} /tmp/out.json'
          .format(config.ADMIN_PROFILE, config.DRIVER_FUNCTION))


if __name__ == '__main__':
    main()
