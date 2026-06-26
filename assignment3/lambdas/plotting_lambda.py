"""Plotting lambda.

When called (synchronously via its REST API), it:
  - queries the last 10 seconds of TestBucket's size history,
  - queries the all-time maximum size across ANY bucket (via the GSI),
  - plots the recent size curve plus a "Historical high" horizontal line,
  - stores the PNG as the object `plot` in TestBucket.

All reads use Query, never Scan.

The bucket name, table name and GSI name all come from env vars (BUCKET_NAME,
TABLE_NAME, GSI_NAME) injected by CDK, so no resource name is hardcoded.

Runtime: Python 3.12 + a matplotlib layer.
"""

import io
import os
import time

import boto3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TABLE_NAME = os.environ['TABLE_NAME']
GSI_NAME = os.environ['GSI_NAME']

ATTR_BUCKET = 'BucketName'
ATTR_TIMESTAMP = 'Timestamp'
ATTR_SIZE = 'TotalSize'
ATTR_GSIPK = 'GSIPK'
GSIPK_VALUE = 'ALL'
PLOT_KEY = 'plot'
WINDOW_MS = 10 * 1000

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')


def recent_points(bucket, now_ms):
    """Query the last 10 seconds for one bucket; return sorted (ts, size) lists."""
    resp = dynamodb.query(
        TableName=TABLE_NAME,
        KeyConditionExpression='{} = :b AND #ts BETWEEN :start AND :now'.format(ATTR_BUCKET),
        ExpressionAttributeNames={'#ts': ATTR_TIMESTAMP},
        ExpressionAttributeValues={
            ':b': {'S': bucket},
            ':start': {'N': str(now_ms - WINDOW_MS)},
            ':now': {'N': str(now_ms)},
        },
        ScanIndexForward=True,
    )
    timestamps = [int(item[ATTR_TIMESTAMP]['N']) for item in resp['Items']]
    sizes = [int(item[ATTR_SIZE]['N']) for item in resp['Items']]
    return timestamps, sizes


def historical_high():
    """Query the GSI for the max TotalSize ever recorded for any bucket."""
    resp = dynamodb.query(
        TableName=TABLE_NAME,
        IndexName=GSI_NAME,
        KeyConditionExpression='{} = :all'.format(ATTR_GSIPK),
        ExpressionAttributeValues={':all': {'S': GSIPK_VALUE}},
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp['Items']
    return int(items[0][ATTR_SIZE]['N']) if items else 0


def build_plot(timestamps, sizes, high):
    fig, ax = plt.subplots()
    if timestamps:
        t0 = timestamps[0]
        xs = [(t - t0) / 1000.0 for t in timestamps]
        ax.plot(xs, sizes, marker='o', label='TestBucket size')
    ax.axhline(y=high, color='red', linestyle='--', label='Historical high')
    ax.set_xlabel('Time (seconds within last 10s window)')
    ax.set_ylabel('Total size (bytes)')
    ax.set_title('TestBucket size over last 10 seconds')
    ax.legend()

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf


def lambda_handler(event, context):
    bucket = os.environ['BUCKET_NAME']
    now_ms = int(time.time() * 1000)

    timestamps, sizes = recent_points(bucket, now_ms)
    high = historical_high()
    buf = build_plot(timestamps, sizes, high)

    s3.put_object(Bucket=bucket, Key=PLOT_KEY, Body=buf.getvalue(),
                  ContentType='image/png')

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': '{{"plotted_points": {}, "historical_high": {}, "plot_key": "{}"}}'.format(
            len(sizes), high, PLOT_KEY),
    }
