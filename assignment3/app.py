#!/usr/bin/env python3
"""CDK app entry point.

Wires three stacks together by passing resource references (not hardcoded
names) as props:

  DataStack       -> DynamoDB table + GSI
  IngestionStack  -> S3 bucket + size-tracking lambda + S3 trigger (needs table)
  ApiStack        -> plotting lambda + REST API + driver lambda
                     (needs bucket, table, GSI name)
"""

import os

import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.data_stack import DataStack
from stacks.ingestion_stack import IngestionStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
    region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-1'),
)

data = DataStack(app, 'Cs6620A3DataStack', env=env)

ingestion = IngestionStack(
    app, 'Cs6620A3IngestionStack',
    table=data.table,
    env=env,
)

ApiStack(
    app, 'Cs6620A3ApiStack',
    bucket=ingestion.bucket,
    table=data.table,
    gsi_name=data.gsi_name,
    env=env,
)

app.synth()
