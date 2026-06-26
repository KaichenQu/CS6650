# Assignment 3 — CDK deployment of the Assignment 2 resources

Same scenario as Assignment 2, but every resource is now defined in AWS CDK
(Python) and deployed via CloudFormation. No resource has a hardcoded physical
name — CloudFormation auto-generates them and the lambdas receive the generated
names through environment variables.

## Stacks

The work is split into three cohesive stacks:

| Stack                    | Resources                                                  |
| ------------------------ | ---------------------------------------------------------- |
| `Cs6620A3DataStack`      | DynamoDB table + `SizeIndex` GSI                           |
| `Cs6620A3IngestionStack` | S3 `TestBucket`, size-tracking lambda, S3 → lambda trigger |
| `Cs6620A3ApiStack`       | matplotlib layer, plotting lambda, REST API, driver lambda |

The bucket and the size-tracking lambda are deliberately in the same stack: an
S3 event-notification resource lives in the bucket's stack but references the
lambda, so splitting them would create a circular cross-stack dependency. The
driver lambda is in the API stack so it can read the REST API URL from the same
stack.

## Layout

```text
app.py                 CDK entry point — instantiates stacks and passes references
cdk.json               CDK config (app command + feature flags)
requirements.txt       aws-cdk-lib, constructs
stacks/                one file per stack
lambdas/               the three lambda handlers (resource names read from env)
layers/                prebuilt matplotlib layer zip
```

## Deploy

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# one-time per account/region:
cdk bootstrap

cdk deploy --all
```

## Demo

Invoke the driver lambda (its name is auto-generated; find it in the Lambda
console or with the AWS CLI), then check the DynamoDB table contents and the
`plot` object written to the bucket.

## Tear down

```bash
cdk destroy --all
```
