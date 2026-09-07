# 端到端示例

这是一个完整的端到端示例，展示如何使用绩效目标拆解诊断工具。

## 📁 目录结构

```
end-to-end-demo/
├── README.md                    # 本文件
├── sample_input.json            # 示例输入数据
├── sample_output.json           # 示例输出（JSON 格式）
├── sample_report.md             # 示例输出（Markdown 格式）
└── sample_report.html           # 示例输出（HTML 可视化报告）
```

## 🚀 快速开始

### 1. 查看示例输入

`sample_input.json` 包含了一个 4 人团队的示例数据：
- L1：示例负责人A（团队负责人，4 个目标）
- L2：示例经理B（小组负责人，2 个目标）
- L3：示例员工C（客户成功经理，2 个目标）
- L3：示例员工D（客户成功经理，3 个目标）

总共 11 个目标，包含完整的层级关系和对齐关系。

### 2. 运行诊断

在 Skill 根目录下运行：

```bash
# JSON 格式输出（默认）
python3 scripts/diagnose.py \
  --input examples/end-to-end-demo/sample_input.json \
  --output my_result.json

# Markdown 格式输出（可直接贴到飞书文档）
python3 scripts/diagnose.py \
  --input examples/end-to-end-demo/sample_input.json \
  --output my_report.md \
  --format markdown

# HTML 可视化报告（可直接在浏览器打开）
python3 scripts/diagnose.py \
  --input examples/end-to-end-demo/sample_input.json \
  --output my_report.html \
  --format html

# 带行业指标库
python3 scripts/diagnose.py \
  --input examples/end-to-end-demo/sample_input.json \
  --output my_result.json \
  --industry-metrics ../industry-metrics
```

### 3. 查看结果

运行成功后，你会看到类似这样的输出：

```
============================================================
🎯 绩效目标拆解诊断工具 v1.4
============================================================
📊 开始数据采集...
  方式：从文件加载（examples/end-to-end-demo/sample_input.json）
✅ 数据加载完成
   总人数：4
   有 OKR 的人数：4
   目标总数：11
   权限级别：Level 1

🔍 校验数据格式...
✅ 数据校验通过

🔬 开始多维度诊断...

  [1/7] 上下层数据不匹配... 发现 0 个问题
  [2/7] 无具体执行人... 发现 0 个问题
  [3/7] 目标重复... 发现 0 个问题
  [4/7] 责任不清... 发现 1 个问题
  [5/7] 未向上对齐... 发现 1 个问题
  [6/7] 层次不准确... 发现 0 个问题
  [7/7] 指标偏离行业基准... 发现 0 个问题

✅ 诊断完成
   健康度：85 / 100（良好）
   问题总数：2
     高严重度：1
     中严重度：1
     低严重度：0

💾 结果已保存到：my_result.json

============================================================
✅ 诊断完成！
============================================================
```

## 📊 示例结果说明

### 健康度评分
- **85 / 100（良好）**
- 目标总数：11 个
- 问题总数：2 个

### 发现的问题

1. **责任不清（高严重度）**
   - 目标：让 CSM 助手稳定进入试用
   - 问题：上级目标有 3 个 KR，但仅有 1 个子目标，可能存在责任真空

2. **未向上对齐（中严重度）**
   - 目标：扩大重点项目价值，进一步提升 people 应用深度
   - 问题：该目标有上级，但未对齐到上级的任何目标

### 优化建议
- P0：优先解决 1 个高严重度问题
- P1：逐步解决 1 个中严重度问题
- P1：建立目标对齐 review 机制

## 🎯 自己试试

### 用你自己的数据

1. 参考 `sample_input.json` 的格式，准备你的团队数据
2. 运行诊断命令
3. 查看结果，分析问题

### 数据格式要求

输入数据需要包含以下字段：

```json
{
  "meta": {
    "collect_time": "2026-08-09 15:30:00",
    "permission_level": 1,
    "total_users": 4,
    "users_with_okr": 4,
    "total_goals": 11
  },
  "goals": [
    {
      "goal_id": "G-0001",
      "title": "目标标题",
      "level": "L1",
      "owner_id": "ou_001",
      "owner_name": "张三",
      "department": "部门名",
      "parent_goal_ids": [],
      "aligned_to_goal_ids": [],
      "indicators": [],
      "progress": 0.3,
      "weight": 0.25,
      "key_results": []
    }
  ],
  "users": [
    {
      "user_id": "ou_001",
      "name": "张三",
      "position": "职位",
      "department": "部门",
      "manager_id": "",
      "level": "L1",
      "email": "zhangsan@example.com"
    }
  ]
}
```

## 💡 小技巧

1. **用缓存加速**：添加 `--use-cache` 参数，第二次运行会快很多
2. **只看高优问题**：添加 `--severity-threshold high`，只显示高严重度问题
3. **校验数据**：添加 `--validate`，只校验数据格式，不运行诊断
4. **详细输出**：添加 `-v`，查看更详细的运行日志

## 📝 下一步

- 试试用真实的团队数据运行
- 探索行业指标库功能
- 查看 `sample_report.html`，体验可视化报告
- 阅读 SKILL.md，了解更多功能
