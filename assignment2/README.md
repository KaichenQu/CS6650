# Assignment 2 — Lambda S3 Bucket-Size Tracker

Microservice app that records S3 bucket size on every change and plots the
last-10-seconds size curve plus an all-time high line.

## Files

| File | Role |
|------|------|
| `config.py` | Constants shared by the local scripts |
| `create_resources.py` | **Part 1** — local script: creates the bucket + DynamoDB table |
| `cleanup.py` | Local script: deletes the bucket + table (for demo cleanup) |
| `size_tracking_lambda.py` | **Part 2** — totals bucket size on S3 events, writes to DynamoDB |
| `plotting_lambda.py` | **Part 3** — plots size history, stores `plot` in the bucket, exposes REST API |
| `driver_lambda.py` | **Part 4** — runs object operations, then calls the plotting API |

## Resources

- **Bucket**: `cs6620-assignment2-<account_id>` (printed by the Part 1 script)
- **Table**: `S3-object-size-history`
- **Region**: `us-east-1`

### Table design

Generic — holds size history for any bucket, not just this one.

- Partition key `BucketName` (S), sort key `Timestamp` (N, epoch ms)
- Attributes `TotalSize` (N), `ObjectCount` (N), `GSIPK` (S, constant `"ALL"`)
- GSI `SizeIndex`: partition key `GSIPK`, sort key `TotalSize` (KEYS_ONLY)

Both lambda reads use **Query, never Scan**:
- Last 10s of one bucket → main table query on `BucketName` + `Timestamp BETWEEN`.
- All-time max across any bucket → `SizeIndex` query, descending, `Limit=1`.

---

## Part 1 — create resources (local)

```bash
aws configure --profile admin      # needs S3 + DynamoDB permissions (once)
uv run python assignment2/create_resources.py
```

Note the printed bucket name — you'll use it as `BUCKET_NAME` below. The bucket
and table now exist and are empty.

---

## CLI setup (replaces Console setup B-E below)

`deploy_lambdas.py` creates everything in steps B-E via boto3: IAM roles, the
matplotlib layer, the three lambdas, the S3 trigger, and the API Gateway REST
API, then wires the driver lambda's env vars. It is idempotent — rerunning it
updates existing resources instead of failing.

Build the matplotlib layer zip once (not committed — see `.gitignore`):

```bash
mkdir -p assignment2/layer_build/python
python3 -m pip install matplotlib pillow -t assignment2/layer_build/python \
    --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all:
find assignment2/layer_build/python -name tests -type d -exec rm -rf {} +
find assignment2/layer_build/python -name __pycache__ -type d -exec rm -rf {} +
find assignment2/layer_build/python -name "*.pyi" -delete
rm -rf assignment2/layer_build/python/{PIL,pillow.libs,pillow-*.dist-info,mpl_toolkits,matplotlib/mpl-data/sample_data}
cd assignment2/layer_build && zip -r -q ../matplotlib-layer.zip python -x "*.dist-info/RECORD" && cd ../..
```

> Note: matplotlib's Agg/PNG backend needs Pillow at import time — keep it in
> the layer even though the stripped build above removes other extras.

Then deploy:

```bash
uv run python assignment2/deploy_lambdas.py
```

This prints the `PLOT_API_URL` and the invoke command for the demo:

```bash
aws lambda invoke --profile admin --function-name cs6620-a2-driver /tmp/out.json
```

Skip to [Demo](#demo) below. The "Console setup" section is the manual
equivalent if you'd rather click through the AWS console.

---

## Console setup

### A. matplotlib layer (for the plotting lambda)

Pick one:

**Quick — public Klayers ARN** (us-east-1, Python 3.12). Browse
<https://api.klayers.cloud/api/v2/p3.12/layers/latest/us-east-1/html/matplotlib.html>
for the current ARN, then attach it to the plotting lambda.

**DIY (most reliable, ARNs change):**
```bash
mkdir -p python
pip install matplotlib -t python/ --python-version 3.12 --only-binary=:all:
zip -r matplotlib-layer.zip python
```
Lambda → Layers → Create layer → upload `matplotlib-layer.zip`, compatible
runtime Python 3.12.

### B. size-tracking lambda (Part 2)

1. Create function → author from scratch → Python 3.12. Paste `size_tracking_lambda.py`.
2. Handler: `lambda_function.lambda_handler` (or rename file accordingly).
3. **Permissions** — add to its execution role:
   ```json
   { "Effect": "Allow",
     "Action": ["s3:ListBucket", "s3:GetObject"],
     "Resource": ["arn:aws:s3:::cs6620-assignment2-<account_id>",
                  "arn:aws:s3:::cs6620-assignment2-<account_id>/*"] }
   ```
   ```json
   { "Effect": "Allow",
     "Action": "dynamodb:PutItem",
     "Resource": "arn:aws:dynamodb:us-east-1:<account_id>:table/S3-object-size-history" }
   ```
4. **Trigger**: bucket → S3 trigger on event types
   *All object create events* and *All object removal events*.
5. Increase timeout to ~30s if the bucket is large.

### C. plotting lambda (Part 3)

1. Create function → Python 3.12. Paste `plotting_lambda.py`. Attach the matplotlib layer.
2. Timeout ~30s, memory ≥256 MB (matplotlib is heavy).
3. **Env var**: `BUCKET_NAME = cs6620-assignment2-<account_id>`.
4. **Permissions**:
   ```json
   { "Effect": "Allow",
     "Action": "dynamodb:Query",
     "Resource": ["arn:aws:dynamodb:us-east-1:<account_id>:table/S3-object-size-history",
                  "arn:aws:dynamodb:us-east-1:<account_id>:table/S3-object-size-history/index/SizeIndex"] }
   ```
   ```json
   { "Effect": "Allow", "Action": "s3:PutObject",
     "Resource": "arn:aws:s3:::cs6620-assignment2-<account_id>/*" }
   ```

### D. REST API (API Gateway)

1. API Gateway → Create **REST API** → resource + **GET** method → Lambda
   **proxy integration** → plotting lambda.
2. Deploy to a stage (e.g. `prod`). Copy the **Invoke URL** — that's `PLOT_API_URL`.

### E. driver lambda (Part 4)

1. Create function → Python 3.12. Paste `driver_lambda.py`.
2. Timeout ~30s (it sleeps ~8s).
3. **Env vars**: `BUCKET_NAME` and `PLOT_API_URL` (the invoke URL from step D).
4. **Permissions**:
   ```json
   { "Effect": "Allow",
     "Action": ["s3:PutObject", "s3:DeleteObject"],
     "Resource": "arn:aws:s3:::cs6620-assignment2-<account_id>/*" }
   ```

---

## Demo

1. Run Part 1 script → TAs confirm bucket + table exist and are empty.
2. (Setup steps B–E above, done by you.)
3. Manually invoke the driver lambda (console → Test).
4. TAs check the DynamoDB table (4 rows: sizes ≈ 18, 27, 0, 2) and download the
   `plot` object from the bucket (4-point curve + red "Historical high" line ≈ 27).
5. Cleanup: `uv run python assignment2/cleanup.py` (deletes the bucket + table).
   To also remove the lambdas, IAM roles, layer, and API Gateway created by
   `deploy_lambdas.py`, run `uv run python assignment2/teardown_lambdas.py`.

## Notes

- The 2-second sleeps keep all 4 points inside the plotting lambda's 10-second window.
- Object contents are the exact strings from the spec; byte sizes come out
  18/27/0/2, matching the spec's 19/28/0/2 shape (rise → drop → rise).
- The plotting lambda writes a `plot` object into the same bucket, which the
  size-tracking lambda will count on subsequent triggers. For a clean curve,
  run the driver against a fresh bucket (cleanup → create_resources → invoke).
