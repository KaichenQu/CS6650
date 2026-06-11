"""Part 4: driver lambda.

Performs a sequence of object operations on TestBucket (each triggers the
size-tracking lambda, producing one data point), sleeping between them so the
points are spread out, then calls the plotting lambda's REST API.

Invoke this manually from the AWS console.

Runtime: Python 3.12. No layer needed (urllib is in the stdlib).
Env vars:
  BUCKET_NAME   - the TestBucket name
  PLOT_API_URL  - the REST API URL of the plotting lambda
"""

import os
import time
import urllib.request

import boto3

s3 = boto3.client('s3')

SLEEP_SECONDS = 2


def lambda_handler(event, context):
    bucket = os.environ['BUCKET_NAME']
    api_url = os.environ['PLOT_API_URL']

    # Create assignment1.txt
    s3.put_object(Bucket=bucket, Key='assignment1.txt', Body=b'Empty Assignment 1')
    time.sleep(SLEEP_SECONDS)

    # Update assignment1.txt
    s3.put_object(Bucket=bucket, Key='assignment1.txt', Body=b'Empty Assignment 2222222222')
    time.sleep(SLEEP_SECONDS)

    # Delete assignment1.txt
    s3.delete_object(Bucket=bucket, Key='assignment1.txt')
    time.sleep(SLEEP_SECONDS)

    # Create assignment2.txt
    s3.put_object(Bucket=bucket, Key='assignment2.txt', Body=b'33')
    time.sleep(SLEEP_SECONDS)

    # Call the plotting lambda synchronously.
    with urllib.request.urlopen(api_url) as resp:
        body = resp.read().decode()
        print('plotting API response:', resp.status, body)

    return {'status': 'done', 'plotting_response': body}
