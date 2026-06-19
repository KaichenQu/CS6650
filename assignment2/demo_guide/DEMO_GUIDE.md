# Assignment 2 Demo 完整讲解 & 操作指南

> 沙箱验证已通过：7 个 Python 文件全部能编译，字节数 18 / 27 / 2，和 README 一致。
> （spec 写 19/28 是因为它假设末尾有换行符，不影响"涨→跌→涨"的形状。）

---

## 一、先看懂整体：这是个什么东西

作业要你做一个"**记录 S3 桶大小变化、并画成图**"的小系统，用**微服务**思路拆成 3 个 Lambda：

```
                    ┌──────────────────────────────────────────┐
  你在控制台         │              AWS 云里                       │
  手动点 "Test"  →  │  driver lambda(司机)                        │
                    │     │ 1.建 assignment1.txt (18字节)         │
                    │     │ 2.改它      (27字节)                   │
                    │     │ 3.删它      (0字节)                    │
                    │     │ 4.建 assignment2.txt (2字节)          │
                    │     │   每步之间 sleep 2 秒                  │
                    │     ↓                                       │
                    │   每次动 S3 桶 → 自动触发 ↓                  │
                    │  size-tracking lambda(记账员)               │
                    │     算出"现在桶里所有对象总大小"             │
                    │     写一行进 DynamoDB 表                     │
                    │                                             │
                    │  driver 最后调 REST API ↓                   │
                    │  plotting lambda(画图员)                    │
                    │     从表里查数据 → matplotlib 画图           │
                    │     把图存回 S3 桶，对象名叫 plot            │
                    └──────────────────────────────────────────┘
```

**关键角色**：
- **driver（司机）**：你手动触发的总指挥，制造数据 + 最后叫画图。
- **size-tracking（记账员）**：被 S3 自动触发，负责"算总量+记账"。
- **plotting（画图员）**：被 REST API 调用，负责"查数据+画图"。

---

## 二、概念扫盲（每个名词都讲一遍）

**1. S3（桶 Bucket）**
亚马逊的网盘。一个"桶"就是一个文件夹，里面放"对象（object）"，每个对象就是一个文件。对象有 `Key`（文件名）和 `Size`（字节数）。桶名全球唯一，所以你的桶名带了账号 ID：`cs6620-assignment2-864981726031`。

**2. DynamoDB（表 Table）**
亚马逊的 NoSQL 数据库。你的表 `S3-object-size-history` 每一行（item）记一个快照：

| 字段 | 含义 |
|---|---|
| `BucketName` | 哪个桶（**分区键 HASH**）|
| `Timestamp` | 什么时候记的，毫秒（**排序键 RANGE**）|
| `TotalSize` | 当时桶里总字节数 |
| `ObjectCount` | 当时有几个对象 |
| `GSIPK` | 固定值 `"ALL"`，给索引用的 |

**为什么用 `BucketName`+`Timestamp` 做主键？** 因为作业说"别假设只有一个桶"。用桶名做分区键，将来多个桶也能分开存；用时间戳做排序键，就能"查某个桶最近 10 秒的记录"。

**3. Query vs Scan（重点，作业明确禁止 Scan）**
- **Scan** = 把整张表从头翻到尾，慢、贵。
- **Query** = 按键精确定位，快。作业**不允许 Scan**。

你的两处读都用 Query：
- 查"最近 10 秒"：`BucketName = 桶名 AND Timestamp BETWEEN (现在-10秒) AND 现在`。
- 查"历史最大值"：这里有个难点 ↓

**4. GSI 全局二级索引（这是设计里最妙的地方）**
作业要画一条"任何桶历史上达到过的最大 size"的横线。问题：DynamoDB 的 Query 必须先指定分区键，但"所有桶里的最大值"跨了很多分区，没法直接 Query，正常只能 Scan——但 Scan 被禁止。

解决办法：建一个**额外索引 `SizeIndex`**，让**所有行的分区键都用同一个固定值 `"ALL"`（GSIPK）**，排序键用 `TotalSize`。这样所有记录都挤进同一个分区，按大小排好序。查最大值时：`GSIPK = "ALL"`，倒序（`ScanIndexForward=False`），取第 1 条（`Limit=1`）——一次 Query 拿到全表最大值，不用 Scan。`KEYS_ONLY` 表示索引里只存键，省空间。

**5. Lambda（函数）**
不用自己开服务器的"一段代码"。你上传一个 Python 文件，AWS 在事件发生时自动跑它。入口函数固定叫 `lambda_handler(event, context)`：`event` 是触发它的事件数据，`context` 是运行环境信息。

**6. Lambda Layer（层）**
Lambda 默认只自带 `boto3`（AWS SDK）这些基础库，**没有 matplotlib**。matplotlib 很大，不能直接塞进函数代码，于是单独打包成一个"层"挂上去。你的 `matplotlib-layer.zip`（37MB）就是这个。注意：matplotlib 存 PNG 需要 Pillow，所以层里也带了 Pillow。作业说 demo 时这个层**可以保留不删**。

**7. IAM Role（权限角色）**
AWS 默认**什么都不许干**。每个 Lambda 要绑一个"角色"，明确写它能干啥：
- 记账员：要能 `s3:ListBucket`（列桶内容算大小）、`dynamodb:PutItem`（写表）。
- 画图员：要能 `dynamodb:Query`（查表+查索引）、`s3:PutObject`（把图存回桶）。
- 司机：要能 `s3:PutObject`/`s3:DeleteObject`（建/删对象）。

给多了不安全，给少了会报 `AccessDenied`。

**8. S3 Trigger（事件触发器）**
在桶上配一个规则："只要有对象被建/改/删，就自动调 size-tracking lambda"。这就是记账员不用你手动点、能自动记账的原因。要选 **All object create events** + **All object removal events** 两类事件。

**9. API Gateway / REST API**
Lambda 默认只能在 AWS 内部被调。要让它"像网址一样被 HTTP 同步调用"，就用 API Gateway 包一层，给你一个 `https://xxx/prod/plot` 的网址（Invoke URL）。司机最后就是 `urllib.urlopen(这个网址)` 来叫画图员。作业要求画图 Lambda **必须暴露 REST API**。

---

## 三、每个文件干什么（对应作业 Part）

| 文件 | 对应 | 一句话 |
|---|---|---|
| `config.py` | — | 本地脚本共用的常量（表名、桶名规则等）|
| `create_resources.py` | **Part 1** | 在你电脑上跑，建好空桶+空表 |
| `size_tracking_lambda.py` | **Part 2** | 记账员：S3 事件触发→算总量→写表 |
| `plotting_lambda.py` | **Part 3** | 画图员：查表→画图→存 `plot`→给 REST API |
| `driver_lambda.py` | **Part 4** | 司机：建改删对象→调 API |
| `cleanup.py` | — | 删桶+表（demo 前清场用）|
| `deploy_lambdas.py` / `teardown_lambdas.py` | — | 用代码一键建/删全部 Lambda（**练习用，demo 不用**）|

⚠️ 注意：Lambda 文件里把表名、字段名**又抄了一份**（没 `import config`）。因为 Lambda 上传到云上是独立运行的，导入不到你本地的 config.py。所以如果你改 config.py 的字段名，**三个 Lambda 文件里也要同步改**。

---

## 四、Demo 当天怎么做（严格按 TA 的 8 步）

作业要求 demo 时**手动在控制台建**所有 Lambda（不能用你的一键脚本）。先把环境清干净，然后照做。

> ⚠️ **先确认右上角 Region = N. Virginia (us-east-1)**。所有资源都建在这个区，区选错了会"找不到"刚建的东西。下面所有链接都已锁定到 us-east-1。

**需要打开的网页（建议先各开一个标签页）**

| 用途 | 网页 | 链接 |
|---|---|---|
| 控制台首页 | AWS Console | <https://console.aws.amazon.com/> |
| 看桶 / 看 `plot` 对象 | S3 | <https://s3.console.aws.amazon.com/s3/buckets?region=us-east-1> |
| 看表里的 4 行数据 | DynamoDB → Explore items | <https://console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=S3-object-size-history> |
| 建 3 个 Lambda | Lambda | <https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions> |
| 建 REST API | API Gateway | <https://console.aws.amazon.com/apigateway/main/apis?region=us-east-1> |
| 改权限（IAM 角色）| IAM Roles | <https://console.aws.amazon.com/iam/home#/roles> |

**第 0 步（demo 前，清场）**
```bash
uv run python assignment2/cleanup.py             # 删旧桶和表
uv run python assignment2/teardown_lambdas.py    # 删旧Lambda/角色/API（层保留）
```

**第 1 步：跑 Part 1 脚本**
```bash
uv run python assignment2/create_resources.py
```
它会打印桶名，**记下这个桶名**（后面所有 Lambda 都要用）。TA 会看：桶和表存在、且是空的。✅

> 下面把每个字段填什么、每个按钮为什么点都写清楚。你的两个固定值（已填进下面所有 JSON，无需再替换）：
> **账号ID** `864981726031`、**桶名** `cs6620-assignment2-864981726031`（第 1 步脚本会打印同样的名字确认）。
> 其它固定值：Region `us-east-1`、表 `S3-object-size-history`、GSI `SizeIndex`、Runtime `Python 3.12`、Handler `lambda_function.lambda_handler`。

---

### 第 2 步：建 size-tracking lambda（记账员）

打开 Lambda 控制台 <https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions>

**2.1 建函数**
- 右上角橙色 **Create function** → 选 **Author from scratch**（从零写，不用模板）。
- **Function name**：`cs6620-a2-size-tracking`
- **Runtime**：Python 3.12 —— *为什么*：你的代码是 Python，且 boto3 在 3.12 运行时自带，不用额外装。
- **Architecture**：x86_64 默认即可 —— *为什么*：后面 matplotlib 层是按 x86_64 编译的，全账号保持一致省事。
- 展开 **Change default execution role** → 选 **Create a new role with basic Lambda permissions** —— *为什么*：先给它一个"只能写日志"的空角色，等下再往里加 S3/DynamoDB 权限。
- 点 **Create function**。

> 📷 **如果这里弹出 "Create role" 界面（带 Default policies / Additional policy 的那个）**：
> - **Role name**：保持自动生成的名字（如 `size-tracking-lambda-role-xxxxx`），不用改。
> - **Default policies** 里那条 `AWSLambdaBasicExecutionRole` **保留**（它给写日志权限）。
> - **Additional policy**：可以二选一——
>   1. **省事**：选 **No additional policy**，直接 Create，S3/DynamoDB 权限等到第 2.4 步再加。
>   2. **一步到位**：选 **Create new policy**，把 JSON 编辑框整段替换成下面 2.4 的那段权限(已是真实账号)，省得第 2.4 步再进 IAM。
> - 截图里 `"Action": []`、`"Resource": []` 是空模板，**就是要你填**——别留空，照 2.4 的 JSON 粘进去。

**2.2 贴代码**
- 进函数页，下方 **Code** 标签里默认有个 `lambda_function.py`，里面是模板代码。
- 全选删掉，把你 `size_tracking_lambda.py` 的内容**整段粘贴**进去。
- 按 **Ctrl/Cmd+S**，再点 **Deploy**（蓝色）—— *为什么*：Lambda 改完代码必须 Deploy 才真正生效，光保存不算。
- 上方 **Runtime settings → Handler** 确认是 `lambda_function.lambda_handler` —— *为什么*：这是"文件名.函数名"。控制台文件叫 `lambda_function.py`，你的入口函数叫 `lambda_handler`，对得上才不会报 "Unable to import module"。

**2.3 调超时**
- **Configuration** 标签 → 左侧 **General configuration** → **Edit** → **Timeout** 改成 `0 min 30 sec` → Save —— *为什么*：默认只有 3 秒，桶里对象多时 list+算总量可能超过 3 秒被掐断。

**2.4 加权限（关键）**

- **Configuration** → 左侧 **Permissions** → 点 **Execution role** 下面那个蓝色角色名 —— 会**新开一个 IAM 标签页**。
- 在 IAM 角色页：**Add permissions** → **Create inline policy** → 切到 **JSON** 标签 → 把下面整段粘进去（已是真实账号无需替换）：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::cs6620-assignment2-864981726031",
        "arn:aws:s3:::cs6620-assignment2-864981726031/*"
      ] },
    { "Effect": "Allow",
      "Action": "dynamodb:PutItem",
      "Resource": "arn:aws:dynamodb:us-east-1:864981726031:table/S3-object-size-history" }
  ]
}
```

- **Next** → Policy name 随便填如 `size-tracking-inline` → **Create policy**。
- *为什么是这几条*：`s3:ListBucket`+`s3:GetObject` 让它能遍历桶算总大小；`dynamodb:PutItem` 让它能往表里写一行。注意桶有**两个 ARN**：不带 `/*` 的是"桶本身"（ListBucket 用），带 `/*` 的是"桶里对象"（GetObject 用）——少一个就报 AccessDenied。

**2.5 配 S3 触发器（让它自动被调）**
- 回到 Lambda 函数页 → 上方 **Function overview** 区 → **+ Add trigger**。
- **Source** 选 **S3** → **Bucket** 选你的桶 `cs6620-assignment2-864981726031`。
- **Event types**：勾 **All object create events** 和 **All object removal events** —— *为什么*：作业要求"建/改/删对象都要记账"。create 覆盖建+改（改=覆盖写也是 create），removal 覆盖删。
- 底部勾上 **Recursive invocation 确认框**（"I acknowledge..."）→ **Add** —— *为什么*：AWS 怕你"动桶→触发 Lambda→Lambda 又动桶→无限循环"，让你确认知情。记账员只写 DynamoDB 不写桶，没有真循环。

---

### 第 3 步：建 plotting lambda（画图员）

回 Lambda 控制台 → **Create function** → Author from scratch → Python 3.12。
- **Function name**：`cs6620-a2-plotting`，同样新建 basic 角色 → Create function。

> 🔴 **Runtime 必须选 Python 3.12,不能用控制台默认的 3.14!**
> matplotlib 层里的 numpy 是按 3.12 编译的(C 扩展绑定 Python 版本)。若用 3.14,
> numpy 的 ABI 对不上,会报 `Runtime.ImportModuleError: ... Error importing numpy`,
> API Gateway 返回 **502 Bad Gateway**,driver 收到 `HTTP Error 502`。
> 建完若发现选错,Configuration → General configuration → Edit → Runtime 改回 `Python 3.12`。

**3.1 贴代码**：粘贴 `plotting_lambda.py` → Ctrl/Cmd+S → **Deploy**。

**3.2 挂 matplotlib 层（重点）**
- 函数页**最下方** **Layers** 区 → **Add a layer**。
- 选 **Custom layers** → 下拉选 `cs6620-a2-matplotlib`（你之前上传的层）→ 选最新 Version → **Add**。
- *为什么*：Lambda 运行时不自带 matplotlib，代码里 `import matplotlib` 会直接崩。层就是把这个大库挂上去的方式。
- *没有这个层怎么办*：先去 Lambda → Layers → Create layer → 上传 `assignment2/matplotlib-layer.zip`，兼容运行时选 Python 3.12、架构 x86_64。

**3.3 调内存和超时**
- Configuration → General configuration → Edit → **Memory** `256 MB`、**Timeout** `30 sec` → Save —— *为什么*：matplotlib 画图吃内存又慢，128MB/3 秒会 OOM 或超时。

**3.4 加环境变量**
- Configuration → **Environment variables** → Edit → Add → Key `BUCKET_NAME`，Value `cs6620-assignment2-864981726031` → Save。
- *为什么*：代码里 `os.environ['BUCKET_NAME']` 决定查谁、把 `plot` 存哪。没设会 KeyError。

**3.5 加权限**（同 2.4 的方式进 IAM，粘下面 JSON，已是真实账号无需替换）：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": "dynamodb:Query",
      "Resource": [
        "arn:aws:dynamodb:us-east-1:864981726031:table/S3-object-size-history",
        "arn:aws:dynamodb:us-east-1:864981726031:table/S3-object-size-history/index/SizeIndex"
      ] },
    { "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::cs6620-assignment2-864981726031/*" }
  ]
}
```

- *为什么有两个 dynamodb Resource*：一个是表本身（查最近 10 秒），一个是 `/index/SizeIndex` 索引（查历史最大值）。查索引需要单独授权，少了第二行历史高点那条线就报错。`s3:PutObject` 用来把图存成 `plot`。

---

### 第 4 步：建 REST API（让画图员能被 HTTP 调）

打开 API Gateway <https://console.aws.amazon.com/apigateway/main/apis?region=us-east-1>
- **Create API** → 找到 **REST API**（不是 HTTP API、不是 WebSocket）那张卡 → **Build** —— *为什么必须 REST API*：作业明确要求 REST API；而且下面要用的 Lambda proxy 配法是 REST 这套。
- **API name**：`cs6620-a2-plot-api` → **Create API**。

**4.1 建资源**
- 左侧 **Resources** → **Create resource**。
- **Resource name** 填 `plot` → **Create resource** —— *为什么*：这决定 URL 路径是 `/plot`。

**4.2 建 GET 方法**
- 选中刚建的 `/plot` → **Create method**。
- **Method type** 选 **GET** —— *为什么*：driver 用 `urllib.urlopen` 默认发 GET。
- **Integration type** 选 **Lambda function**。
- 打开 **Lambda proxy integration** 开关 —— *为什么*：proxy 模式下 API 网关把整个请求原样丢给 Lambda，Lambda 返回 `{statusCode, headers, body}`，正好匹配你 `plotting_lambda.py` 的返回格式。
- **Lambda function** 选 `cs6620-a2-plotting` → **Create method**。（弹出"给 API 权限调用 Lambda"的确认就允许。）

**4.3 部署**
- 右上 **Deploy API** → **Stage** 选 **New stage** → Stage name 填 `prod` → **Deploy** —— *为什么*：API 要部署到一个 stage 才有公网地址。
- 部署后在 **Stages → prod** 看到 **Invoke URL**，形如
  `https://abc123.execute-api.us-east-1.amazonaws.com/prod`

- **完整的 API 地址 = Invoke URL + `/plot`**，即
  `https://abc123.execute-api.us-east-1.amazonaws.com/prod/plot`

- 把这个完整地址记下来，就是下一步要填的 `PLOT_API_URL`。

---

### 第 5 步：建 driver lambda（司机）

回 Lambda 控制台 → Create function → Python 3.12 → **Function name** `cs6620-a2-driver` → 新建 basic 角色 → Create function。

**5.1 贴代码**：粘贴 `driver_lambda.py` → Ctrl/Cmd+S → **Deploy**。

**5.2 调超时**：Configuration → General → Timeout `30 sec` —— *为什么*：它内部要 sleep 4×2=8 秒再调 API，默认 3 秒必被掐断。

**5.3 加两个环境变量**（Configuration → Environment variables → Edit → Add）：
- `BUCKET_NAME` = `cs6620-assignment2-864981726031`
- `PLOT_API_URL` = 第 4 步那个**带 `/plot` 的完整地址**
- *为什么*：代码靠这俩知道"动哪个桶"和"最后调哪个网址画图"。

**5.4 加权限**（进 IAM 贴 JSON，已是真实账号无需替换）：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::cs6620-assignment2-864981726031/*" }
  ]
}
```

- *为什么*：司机只做建对象（PutObject）和删对象（DeleteObject），不读不写表，所以权限就这两条。

---

### 第 6 步：手动触发 driver

- 在 `cs6620-a2-driver` 函数页 → **Test** 标签 → **Create new event** → 名字随便、内容保持默认 `{}` → **Save** → **Test**。
- *为什么内容是空 `{}`*：driver 不读 `event` 里的东西，给个空对象就行。
- 点完它会跑约 8 秒（建→改→删→建，各 sleep 2 秒），最后调 API 画图。绿色成功即可，**别重复点**（点一次=一套 4 个数据点）。

---

### 第 7 步：TA 检查结果

- **DynamoDB**：<https://console.aws.amazon.com/dynamodbv2/home?region=us-east-1#item-explorer?table=S3-object-size-history>
  应有 **4 行**，`TotalSize` 约 **18 / 27 / 0 / 2**（涨→更涨→清零→小涨）。
- **S3 plot 图**：<https://s3.console.aws.amazon.com/s3/buckets?region=us-east-1> → 进桶 → 选 `plot` → **Download**。
  打开是：一条 4 点折线 + 一条红色虚线 "Historical high"(≈27)。✅

---

## 五、几个容易翻车的点

1. **为什么 sleep 2 秒**：画图员只查"最近 10 秒"。4 个点 × 间隔 2 秒 = 8 秒，刚好都落在 10 秒窗口里。间隔太大就有点会被甩出窗口。
2. **Handler 名字**：控制台默认 `lambda_function.lambda_handler`。你要么把粘贴的文件命名为 `lambda_function.py`，要么把 Handler 字段改成你的文件名。错了会报 "Unable to import module"。
3. **plot 对象会被算进去**：画图员把 `plot` 存回桶，会再次触发记账员、多记一行。所以每次 demo 都要**先 cleanup 重建一个干净的桶**再跑，曲线才干净。
4. **权限别漏**：90% 的报错是 `AccessDenied`。对照上面每个 Lambda 该有的权限逐个核对。
5. **demo 时别 debug**：作业明说 demo 出错不让现场调试，所以**提前先用 `deploy_lambdas.py` 在自己账号上整套跑通一遍**验证，再清掉，demo 当天手动重建。
