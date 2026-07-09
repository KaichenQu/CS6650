# Assignment 3 Demo 脚本

区域固定 **us-east-1**,账号 **864981726031**。所有链接直接可点。

---

## 第 0 步(demo 前先做,别当着老师现场等):部署

```bash
cd /Users/kelsonqu/Desktop/CS6620/assignment3
source .venv/bin/activate          # 没有就先建:python3 -m venv .venv && pip install -r requirements.txt
export AWS_PROFILE=admin AWS_DEFAULT_REGION=us-east-1
npx aws-cdk@2 deploy --all --require-approval never
```

三个栈都 `CREATE_COMPLETE` 后再开始 demo。上次实测约 3–4 分钟。

> **建议**:demo 前 10 分钟部署好,别现场跑 deploy(要等,还可能撞 Docker / 网络)。

---

## 第 1 步:展示 CloudFormation ——「我是用 CDK/CloudFormation 建的,不是手点的」

🔗 https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks?filteringStatus=active&filteringText=Cs6620A3

**Show 什么:**
- 列表里三个栈:`Cs6620A3DataStack`、`Cs6620A3IngestionStack`、`Cs6620A3ApiStack`,状态都是绿色 `CREATE_COMPLETE`。
- 说一句:拆成三个栈(数据 / 采集 / API),不是一个巨型单栈。
- 点开任意一个 → **Resources** 标签,展示里面的资源都是 CloudFormation 自动建的;点 **Template** 标签能看到 CDK 合成出来的模板。
- 强调:没有硬编码资源名,名字都是 CloudFormation 自动生成、再通过环境变量传给 lambda。

---

## 第 2 步:证明「三个 lambda」

🔗 https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions

**Show 什么(搜 `Cs6620A3` 过滤):**
- `Cs6620A3IngestionStack-SizeTrackingFunction...`
- `Cs6620A3ApiStack-PlottingFunction...`
- `Cs6620A3ApiStack-DriverFunction...`

> ⚠️ **注意会多出 2 个**:`...BucketNotificationsHandler...` 和 `...S3AutoDeleteObjects...`。
> 这俩是 CDK 框架自动加的辅助 lambda(一个负责配 S3 事件通知,一个负责在 destroy 时清空桶),不是业务 lambda。老师若问就这么解释。**业务 lambda 就是上面那 3 个。**

---

## 第 3 步:S3 桶 + 事件触发关系

🔗 https://us-east-1.console.aws.amazon.com/s3/buckets?region=us-east-1

**Show 什么(搜 `cs6620a3ingestionstack-testbuc`):**
- 点进桶 → **Properties** 标签 → 拉到 **Event notifications**,展示有一条指向 `SizeTrackingFunction` 的通知(`s3:ObjectCreated:*` / `s3:ObjectRemoved:*`)。
- 这就是「桶 → size-tracking lambda 的触发关系」。

---

## 第 4 步:DynamoDB 表 + 二级索引

🔗 https://us-east-1.console.aws.amazon.com/dynamodbv2/home?region=us-east-1#tables

**Show 什么(搜 `Cs6620A3DataStack`):**
- 点进表 → **Indexes** 标签,展示 GSI `SizeIndex`(这就是要求的 secondary index)。
- 先别看数据,数据等第 6 步 driver 跑完再回来看。

---

## 第 5 步:REST API

🔗 https://us-east-1.console.aws.amazon.com/apigateway/main/apis?region=us-east-1

**Show 什么:**
- 有一个 `PlotApi`(REST API,不是 HTTP API)。
- 点进去 → **Stages** → `prod`,能看到 Invoke URL,就是 plotting lambda 的入口。

---

## 第 6 步:调用 driver lambda(核心动作)

回到 Lambda 控制台点开 `...DriverFunction...` → **Test**。

或者命令行(更稳,推荐):

```bash
aws lambda invoke --function-name \
  $(aws lambda list-functions --query "Functions[?contains(FunctionName,'DriverFunction')].FunctionName" --output text) \
  --payload '{}' /tmp/out.json && cat /tmp/out.json
```

**Show 什么:** 返回 `plotted_points` 和 `historical_high`(上次是 2 和 27)。说明 driver 往桶里写了几个文件、触发 size-tracking 记录、再调 API 出图。

---

## 第 7 步:回 DynamoDB 看数据

回到第 4 步的表 → **Explore table items**。

**Show 什么:** 几条 size 快照记录(`BucketName` / `Timestamp` / `TotalSize` / `ObjectCount`),证明 S3 事件真的触发了 lambda 写库。

---

## 第 8 步:看生成的 plot 图

回到第 3 步那个桶,里面有个 plot 对象 → 点 **Open**。

**Show 什么:** 一张柱状图 PNG(桶大小随时间变化),端到端跑通的最终产物。

---

## 收尾:destroy(demo 完当场清,省钱)

```bash
cd /Users/kelsonqu/Desktop/CS6620/assignment3 && ./destroy.sh
```
