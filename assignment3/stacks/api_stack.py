"""ApiStack: the plotting lambda, its REST API, and the driver lambda.

The plotting lambda is fronted by an API Gateway REST API. The driver lambda
lives here too so it can read the API's URL from the same stack (env var
PLOT_API_URL) without creating a cross-stack cycle.

No physical function or API name is set; CloudFormation auto-generates them.
Bucket/table/GSI identifiers reach the lambdas through env vars.
"""

import os

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from constructs import Construct

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAMBDA_ASSET = os.path.join(PROJECT_ROOT, 'lambdas')
LAYER_ASSET = os.path.join(PROJECT_ROOT, 'layers', 'matplotlib-layer.zip')


class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *,
                 bucket: s3.IBucket, table: dynamodb.ITable, gsi_name: str,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        matplotlib_layer = _lambda.LayerVersion(
            self, 'MatplotlibLayer',
            code=_lambda.Code.from_asset(LAYER_ASSET),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.X86_64],
        )

        plotting_fn = _lambda.Function(
            self, 'PlottingFunction',
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            handler='plotting_lambda.lambda_handler',
            code=_lambda.Code.from_asset(LAMBDA_ASSET),
            timeout=Duration.seconds(30),
            memory_size=256,
            layers=[matplotlib_layer],
            environment={
                'BUCKET_NAME': bucket.bucket_name,
                'TABLE_NAME': table.table_name,
                'GSI_NAME': gsi_name,
            },
        )
        table.grant_read_data(plotting_fn)
        bucket.grant_put(plotting_fn)

        api = apigw.LambdaRestApi(
            self, 'PlotApi',
            handler=plotting_fn,
            proxy=True,
        )

        driver_fn = _lambda.Function(
            self, 'DriverFunction',
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler='driver_lambda.lambda_handler',
            code=_lambda.Code.from_asset(LAMBDA_ASSET),
            timeout=Duration.seconds(60),
            environment={
                'BUCKET_NAME': bucket.bucket_name,
                'PLOT_API_URL': api.url,
            },
        )
        bucket.grant_read_write(driver_fn)
