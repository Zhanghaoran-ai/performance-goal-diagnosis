# Performance Goal Diagnosis

绩效目标与指标拆解诊断工具。它把人员、目标与指标数据标准化为可审计的诊断模型，生成独立指标树和目标树，并识别未向上对齐、承接缺口、假拆解、因果倒置、数值不闭合、指标遗漏与层级不合理等问题。

当前版本：**v2.7**

## v2.7 主要能力

- **独立指标拆解树**：每个指标作为独立节点，展示向上关联、向下承接及逐边诊断。
- **关系来源可追溯**：严格区分输入显式关系、语义推断、用户确认和数据缺口。
- **人工修正闭环**：支持确认、拒绝、改选上级、待核实、导出决策 JSON，并在后续诊断中回读。
- **四层语义判断**：结合词面、语义、因果方向和数值链路判断关系质量。
- **飞书绩效 API 适配**：通过用户提供的真实接口配置完成环境变量鉴权、分页、字段映射及人员/目标/指标标准化。
- **行业模板桥接**：可把行业绩效模板 Markdown 转换为行业指标库并用于对标诊断。
- **六页 HTML 报告**：概览、指标拆解树、目标拆解树、诊断结果、优化建议、人员视图。
- **移动端适配**：窄屏使用底部关系详情面板，核心操作可直接点击。

## 真实性边界

- 只有输入明确提供的指标父子关系才标记为 `explicit`。
- 缺少显式关系时，只在已有父目标/对齐目标约束的候选范围内进行语义推断。
- 人事汇报关系不自动等同于指标拆解关系。
- 同一目标内的多个指标不天然互为父子。
- 证据不足时保留独立节点并标记为数据缺口，不强制连线。
- 人工确认或改选标记为 `user_confirmed`，不会伪装成原始输入事实。

## 环境要求

- Python 3.8+
- 可选：`jieba`，用于增强中文分词；未安装时会降级到基础分词。
- 测试：`pytest`
- 可选飞书自建应用创建：Node.js 18+

## 快速开始

### 1. 使用标准 JSON

```bash
python3 scripts/diagnose.py \
  --input examples/end-to-end-demo/sample_input.json \
  --format html \
  --output diagnosis.html
```

支持的输出格式：`json`、`text`、`markdown`、`html`。

### 2. 使用行业指标库

```bash
python3 scripts/diagnose.py \
  --input examples/end-to-end-demo/sample_input.json \
  --industry "SaaS行业" \
  --industry-metrics examples/industry-metrics \
  --format html \
  --output diagnosis.html
```

### 3. 从行业绩效模板导入

```bash
python3 scripts/diagnose.py \
  --input /absolute/path/goals.json \
  --import-template /absolute/path/industry-template.md \
  --industry "SaaS行业" \
  --format html \
  --output diagnosis.html
```

### 4. 接入飞书绩效 HTTP API

复制并修改配置示例：

```bash
cp examples/feishu-performance-api-config.example.json performance-api.json
```

接口地址、只读权限、鉴权方式、分页和字段映射必须来自真实接口文档或脱敏响应样例，不要猜测接口路径或权限 key。凭证只从环境变量读取：

```bash
export FEISHU_APP_ID="your-app-id"
export FEISHU_APP_SECRET="your-app-secret"

python3 scripts/diagnose.py \
  --feishu-performance-config performance-api.json \
  --api-var department_id=your-department-id \
  --api-var cycle_id=your-cycle-id \
  --format html \
  --output diagnosis.html
```

应用创建只负责准备应用和凭证，不代表绩效接口或权限已经开放。详细说明见 [飞书绩效接入说明](references/feishu-performance-integration.md)。

### 5. 回读人工关系决策

在 HTML 指标树中完成确认、拒绝、改选或待核实后，导出 `indicator-relation-decisions.json`：

```bash
python3 scripts/diagnose.py \
  --input /absolute/path/goals.json \
  --relation-decisions /absolute/path/indicator-relation-decisions.json \
  --format html \
  --output reviewed-diagnosis.html
```

输入显式关系优先级最高，人工决策不会覆盖显式关系。

## 输入结构概要

```json
{
  "users": [
    {
      "user_id": "user_001",
      "name": "示例负责人",
      "department": "客户成功中心",
      "level": "L2"
    }
  ],
  "goals": [
    {
      "goal_id": "goal_001",
      "title": "提升客户续约表现",
      "owner_id": "user_001",
      "level": "L2",
      "parent_goal_ids": [],
      "indicators": [
        {
          "indicator_id": "metric_001",
          "name": "净收入留存率",
          "value": 110,
          "unit": "%",
          "parent_indicator_ids": []
        }
      ]
    }
  ]
}
```

完整示例见 `examples/end-to-end-demo/`，输入字段和关系规则见 `SKILL.md`。

## 测试

```bash
python3 -m pytest -q -p no:cacheprovider scripts/tests
```

当前版本包含 112 项测试，覆盖：

- 四层语义关系判断与边界条件
- 指标树来源和人工决策优先级
- 关系确认、拒绝、改选、待核实及导出契约
- 飞书绩效适配器鉴权、分页、字段映射和敏感信息保护
- 行业模板导入与标准化
- 移动端关系详情交互契约

## 目录结构

```text
performance-goal-diagnosis/
├── SKILL.md
├── README.md
├── LICENSE
├── scripts/
│   ├── diagnose.py
│   ├── diagnose_goals.py
│   ├── indicator_tree.py
│   ├── semantic_utils.py
│   ├── feishu_performance_adapter.py
│   ├── import_template_output.py
│   ├── standard_report.py
│   ├── tree_view.py
│   └── tests/
├── references/
│   ├── indicator-relationship-checklist.md
│   ├── standard-output-framework.md
│   └── feishu-performance-integration.md
├── integrations/
│   └── feishu-app-creator/
└── examples/
    ├── feishu-performance-api-config.example.json
    ├── end-to-end-demo/
    └── industry-metrics/
```

## 安全说明

- 不要把 App Secret、访问令牌或 Authorization 值写入配置、报告、日志、测试快照或提交记录。
- 对人员和绩效数据遵循最小权限原则，优先使用只读权限。
- 公开问题或示例前应移除真实姓名、企业邮箱、员工标识和业务敏感信息。
- API 适配器不内置未经确认的绩效接口路径或权限项。

## License

[MIT License](LICENSE)
