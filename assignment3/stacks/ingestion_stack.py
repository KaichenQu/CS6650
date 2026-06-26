"""IngestionStack: TestBucket, the size-tracking lambda, and their wiring.

The bucket and the lambda it triggers live in the SAME stack on purpose. An S3
event notification resource is created in the bucket's stack but references the
target lambda; if the bucket and lambda were in different stacks this would form
a circular dependency (bucket stack -> lambda stack for the notification, lambda
stack -> bucket stack for the read grant). Co-locating them avoids that.

No physical bucket or function name is set; CloudFormation auto-generates them.
The lambda learns the table name through the TABLE_NAME env var.
"""

import os

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAMBDA_ASSET = os.path.join(PROJECT_ROOT, 'lambdas')


class IngestionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *,
                 table: dynamodb.ITable, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.bucket = s3.Bucket(
            self, 'TestBucket',
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        size_tracking_fn = _lambda.Function(
            self, 'SizeTrackingFunction',
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler='size_tracking_lambda.lambda_handler',
            code=_lambda.Code.from_asset(LAMBDA_ASSET),
            timeout=Duration.seconds(30),
            environment={'TABLE_NAME': table.table_name},
        )

        # Least-privilege permissions, generated from the resource references.
        self.bucket.grant_read(size_tracking_fn)
        table.grant_write_data(size_tracking_fn)

        # The event-triggering relationship between the bucket and the lambda.
        notification = s3n.LambdaDestination(size_tracking_fn)
        self.bucket.add_event_notification(s3.EventType.OBJECT_CREATED, notification)
        self.bucket.add_event_notification(s3.EventType.OBJECT_REMOVED, notification)
