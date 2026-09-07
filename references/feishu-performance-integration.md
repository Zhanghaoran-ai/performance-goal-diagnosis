# 飞书绩效接口接入指南（v2.7）

## 能力边界

统一入口可以：

1. 在没有现成应用时，使用 `integrations/feishu-app-creator/` 创建或增量授权企业自建应用；
2. 使用用户提供的真实绩效接口配置，获取人员、目标和指标明细；
3. 将不同接口响应映射为 `users / goals / indicators` 标准结构后进入诊断；
4. 从 HTML 导出的人工关系决策 JSON 回读确认、拒绝、改选和待核实结果。

应用创建器**不等于绩效数据接口**。绩效 API 路径、scope key、鉴权方式、分页字段和响应字段必须来自租户实际开放能力或用户提供的接口文档/样例，技能不会猜测。

## 最小输入清单

接入前请提供：

- 接口基础地址；
- 人员接口和绩效目标/指标接口的路径、方法；
- 鉴权方式：已有 Bearer Token 环境变量，或 App ID/App Secret 环境变量；
- 必需的只读权限 scope key（以真实接口文档为准）；
- 分页参数、成功码字段和数据数组路径；
- 一份脱敏响应样例，或完整字段映射；
- 绩效周期、部门等查询变量。

## 凭证安全

- 配置 JSON 中禁止出现明文 token、App Secret 或 Authorization 值；
- 凭证从环境变量读取；
- 应用创建器要求 `--out`，凭证只写入该文件，权限为 `0600`，不会输出到终端；
- 凭证文件不得放入技能目录、报告目录、测试快照或 ZIP；
- 报告和标准化数据只包含业务数据与来源摘要，不包含请求头和访问令牌。

## 创建或授权自建应用（可选）

先依据用户提供的真实接口文档确认只读权限，再创建配置文件。禁止把通用权限表中不存在的“绩效权限”猜进配置。

```bash
node integrations/feishu-app-creator/scripts/create-app.mjs \
  --config /absolute/path/app-config.json \
  --out /absolute/private/path/feishu-app-credential.json \
  --timeout 600
```

终端会输出一次性授权 URL。用户在飞书中确认后，凭证写入 `--out` 文件。将凭证以环境变量提供给诊断入口：

```bash
export FEISHU_APP_ID='从私密凭证文件读取'
export FEISHU_APP_SECRET='从私密凭证文件读取'
```

## 配置驱动采集

复制 `examples/feishu-performance-api-config.example.json`，替换占位接口和映射，随后执行：

```bash
python3 scripts/diagnose.py \
  --feishu-performance-config /absolute/path/performance-api.json \
  --api-var department_id=od_xxx \
  --api-var cycle_id=cycle_xxx \
  --format html \
  --output diagnosis.html
```

### 支持的鉴权类型

- `none`：仅用于不需要凭证的内部代理或本地 mock；
- `bearer_env`：从 `auth.token_env` 指定的环境变量读取 Token；
- `tenant_access_token`：从 App ID/App Secret 环境变量获取 tenant access token。

### 绩效采集模式

- `performance.mode=list`：一个接口返回全量目标/指标；
- `performance.mode=per_user`：先获取人员，再逐人调用绩效接口，路径或参数可使用 `{user_id}` 等人员字段变量。

### 响应映射模式

- `goal_with_indicators`：每条绩效记录是一个目标，指标在 `mappings.indicators_path` 数组中；
- `indicator_rows`：每条记录是一条指标明细，适配器按 `goal_id` 聚合。

## 弱语义关系人工闭环

HTML 指标树的每条语义推断上级关系提供四种动作：

- 确认保留；
- 拒绝关系；
- 改选上级指标；
- 标记待核实。

选择完成后点击“导出关系确认 JSON”。下次诊断回读：

```bash
python3 scripts/diagnose.py \
  --input standardized-data.json \
  --relation-decisions indicator-relation-decisions.json \
  --format html \
  --output diagnosis-reviewed.html
```

处理规则：

- 输入显式指标关系优先级最高，人工决策不能覆盖；
- 人工确认/改选作为 `user_confirmed` 单独标记，不伪装成原始显式关系；
- 拒绝和待核实会阻止算法再次自动连线，并转为可追溯的数据缺口；
- 没有回读导出文件时，浏览器本地状态只用于本次查看，不会改变诊断源数据。
