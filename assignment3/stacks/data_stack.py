"""DataStack: the DynamoDB size-history table and its secondary index.

The table holds size history for any bucket:
  - PK BucketName / SK Timestamp lets us query a single bucket's recent history.
  - A GSI (SizeIndex) on a constant partition key (GSIPK) with TotalSize as the
    sort key lets us query the all-time maximum size across every bucket with a
    Query (never a Scan).

No physical table name is set, so CloudFormation auto-generates it. The table
name is handed to the lambdas via env vars by the stacks that consume it.
"""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class DataStack(Stack):
    # The GSI index name must be specified (DynamoDB does not auto-generate it);
    # it is exposed as a property so consumers pass it to lambdas by reference
    # instead of hardcoding the string.
    GSI_NAME = 'SizeIndex'

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.table = dynamodb.Table(
            self, 'SizeHistoryTable',
            partition_key=dynamodb.Attribute(
                name='BucketName', type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(
                name='Timestamp', type=dynamodb.AttributeType.NUMBER),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.table.add_global_secondary_index(
            index_name=self.GSI_NAME,
            partition_key=dynamodb.Attribute(
                name='GSIPK', type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(
                name='TotalSize', type=dynamodb.AttributeType.NUMBER),
            projection_type=dynamodb.ProjectionType.KEYS_ONLY,
        )

        self.gsi_name = self.GSI_NAME
