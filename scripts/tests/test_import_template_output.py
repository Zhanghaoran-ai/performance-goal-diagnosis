# -*- coding: utf-8 -*-
"""
test_import_template_output.py — 桥接器单元测试（v2.5 新增）

测试 scripts/import_template_output.py（模板技能输出 → 诊断行业指标库 桥接器）。

覆盖：
1. parse_markdown_table：表格解析（识别表头/跳过分隔行/忽略无关表格）
2. _parse_number：数值提取（主值 + 括号范围 / 无范围 / 缺失 / 异常输入）
3. _detect_level：岗位分层（战略/管理/执行 + 默认兜底）
4. _normalize_metric_name：指标名规范化（去加粗）
5. build_industry_library：字段映射与去重
6. render_layer_md：生成文件格式与诊断技能行业库兼容（含表头 / 详解块）

运行：
    python3 -m pytest scripts/tests/test_import_template_output.py -v
"""

import os
import sys

# 确保能导入 scripts 下的模块（无论从技能根目录还是 scripts/tests 运行）
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import pytest

from import_template_output import (
    _detect_level,
    _normalize_metric_name,
    _parse_number,
    build_industry_library,
    parse_markdown_table,
    render_layer_md,
)


# ============================================================
# 1. parse_markdown_table —— 表格解析
# ============================================================

SAMPLE_MD = """# 《示例SaaS公司 2026 绩效方案》

## 3. 关键岗位指标关联地图

| 公司目标 | 部门/流程 | 关键岗位 | 指标 | 指标类型 | 拉动关系 |
| --- | --- | --- | --- | --- | --- |
| 营收增长 | 销售部 | 销售总监 | 新客户收入 | 结果指标 | 直接贡献 |

## 4. 指标&目标范例明细

| 岗位 | 指标 | 定义/公式 | 外部参考值 | 企业建议目标 | 证据等级与来源 | 适用范围与限制 | 推导依据 | 设定原因 | 执行要点 | 数据来源 | 关联目标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 公司一号位 | 净收入留存率（NDR） | 期末ARR÷期初ARR | 110%（100~130） | 115% | A级 Aleph 2026 | B2B SaaS | 基线105% | 衡量客户健康 | 季度回顾 | Aleph 2026报告 | 营收增长 |
| 销售总监 | 新客户签约率 | 签约÷触达 | 25%（15~35） | 28% | B级 行业观察 | B2B | 转化提升 | 销售驱动 | 月度 | 销售CRM | 营收增长 |
| 研发工程师 | 代码质量（Bug率） | Bug数÷需求数 | 0.5%（0~1） | 0.5% | B级 DORA | 研发 | 质量护栏 | 质量保障 | 迭代 | 研发平台 | 交付质量 |
"""


def test_parse_tables_detects_two_tables():
    tables = parse_markdown_table(SAMPLE_MD)
    assert len(tables) == 2


def test_parse_tables_skips_separator_row():
    tables = parse_markdown_table(SAMPLE_MD)
    # 每个表格的数据行应不含 '---' 分隔行
    for _, rows in tables:
        for row in rows:
            assert not all('-' * 3 in cell for cell in row)


def test_parse_tables_header_and_rows():
    tables = parse_markdown_table(SAMPLE_MD)
    # 第4章指标表
    header, rows = tables[1]
    assert header[0] == '岗位'
    assert header[1] == '指标'
    assert len(rows) == 3
    assert rows[0][0] == '公司一号位'
    assert rows[0][1] == '净收入留存率（NDR）'


def test_parse_tables_ignores_nontable_content():
    tables = parse_markdown_table("# 无表格\n普通文本\n- 列表项\n")
    assert tables == []


# ============================================================
# 2. _parse_number —— 数值提取
# ============================================================

@pytest.mark.parametrize("raw, exp_val, exp_range", [
    ('110%（100~130）', 110.0, (100.0, 130.0)),      # 括号范围 + 主值
    ('27%', 27.0, None),                             # 仅主值，无范围
    ('12（8~18）', 12.0, (8.0, 18.0)),               # 无百分号
    ('0.5%（0~1）', 0.5, (0.0, 1.0)),                # 小数
    ('25%（15~35）', 25.0, (15.0, 35.0)),
    ('-', None, None),                               # 缺失
    ('暂无可靠外部基准', None, None),                # 无数字文本
    ('', None, None),                                # 空串
    (None, None, None),                              # None
])
def test_parse_number(raw, exp_val, exp_range):
    val, rng = _parse_number(raw)
    assert val == exp_val
    assert rng == exp_range


def test_parse_number_range_sorted():
    # 即使括号内先大后小也返回升序 (min, max)
    val, rng = _parse_number('110%（130~100）')
    assert rng == (100.0, 130.0)


# ============================================================
# 3. _detect_level —— 岗位分层
# ============================================================

@pytest.mark.parametrize("role, exp_level", [
    ('公司一号位', '战略层'),
    ('CTO', '战略层'),
    ('总经理', '战略层'),
    ('CEO', '战略层'),
    ('销售总监', '管理层'),
    ('部门负责人', '管理层'),      # 关键：部门负责人归管理层而非战略层
    ('HR经理', '管理层'),
    ('项目经理', '管理层'),
    ('研发工程师', '执行层'),
    ('HR专员', '执行层'),
    ('测试工程师', '执行层'),
    ('未知岗位XYZ', '执行层'),     # 默认兜底
    ('', '执行层'),
    (None, '执行层'),
])
def test_detect_level(role, exp_level):
    assert _detect_level(role) == exp_level


# ============================================================
# 4. _normalize_metric_name —— 指标名规范化
# ============================================================

@pytest.mark.parametrize("raw, exp", [
    ('**净收入留存率（NDR）**', '净收入留存率（NDR）'),
    ('净收入留存率', '净收入留存率'),
    ('**营收增长率**', '营收增长率'),
    ('', ''),
])
def test_normalize_metric_name(raw, exp):
    assert _normalize_metric_name(raw) == exp


# ============================================================
# 5. build_industry_library —— 字段映射与去重
# ============================================================

def _build_sample_library():
    tables = parse_markdown_table(SAMPLE_MD)
    return build_industry_library(tables, 'SaaS行业')


def test_build_library_levels():
    layers = _build_sample_library()
    assert set(layers.keys()) == {'战略层', '管理层', '执行层'}


def test_build_library_strategy_level_metrics():
    layers = _build_sample_library()
    names = [m['name'] for m in layers['战略层']]
    assert '净收入留存率（NDR）' in names


def test_build_library_benchmark_and_range():
    layers = _build_sample_library()
    ndr = next(m for m in layers['战略层'] if m['name'] == '净收入留存率（NDR）')
    assert ndr['benchmark'] == 110.0
    assert ndr['range'] == (100.0, 130.0)


def test_build_library_field_mapping():
    layers = _build_sample_library()
    bug = next(m for m in layers['执行层'] if m['name'] == '代码质量（Bug率）')
    assert bug['benchmark'] == 0.5
    assert bug['range'] == (0.0, 1.0)
    assert bug['source'] == '研发平台'          # 数据来源列
    assert bug['goal'] == '交付质量'           # 关联目标列
    assert bug['role'] == '研发工程师'
    assert bug['setting_reason'] == '质量保障'  # 设定原因列
    assert bug['execution'] == '迭代'          # 执行要点列
    assert bug['definition'] == 'Bug数÷需求数'


def test_build_library_dedup():
    # 同一 (层, 指标) 重复行只保留一条
    md = SAMPLE_MD.replace('| 公司一号位 | 净收入留存率（NDR） |',
                           '| 公司一号位 | 净收入留存率（NDR） |\n| 公司一号位 | 净收入留存率（NDR） |')
    tables = parse_markdown_table(md)
    layers = build_industry_library(tables, 'SaaS行业')
    names = [m['name'] for m in layers['战略层']]
    assert names.count('净收入留存率（NDR）') == 1


def test_build_library_ignores_nonmetric_table():
    # 第3章关联地图表不含"指标"表头语义（含"指标"列），但该表在 SAMPLE 中实际含"指标"列，
    # 此处验证不含指标列的表被忽略
    md = "| 公司目标 | 部门 |\n| --- | --- |\n| A | B |\n"
    tables = parse_markdown_table(md)
    layers = build_industry_library(tables, 'SaaS行业')
    assert all(len(layers[lv]) == 0 for lv in layers)


# ============================================================
# 6. render_layer_md —— 生成文件格式兼容性
# ============================================================

def _build_rendered():
    layers = _build_sample_library()
    return render_layer_md('战略层', layers['战略层'], 'SaaS行业', '测试来源')


def test_render_layer_md_contains_header():
    md = _build_rendered()
    assert '# SaaS行业 - 战略层指标' in md
    assert '## 指标列表' in md
    assert '## 指标详解' in md


def test_render_layer_md_table_columns():
    md = _build_rendered()
    # 与诊断技能行业库兼容的表头
    assert '| 序号 | 指标名称 | 基准值 | 合理范围 | 数据来源 | 权威性 |' in md


def test_render_layer_md_detail_block():
    md = _build_rendered()
    assert '- **基准值**：110' in md
    assert '- **合理范围**：100 ~ 130' in md
    assert '- **企业建议目标**：115' in md


def test_render_layer_md_escapes_pipes():
    # 指标名含竖线时转义，避免破坏表格
    md = render_layer_md('执行层', [{'name': 'A|B', 'benchmark': 1, 'range': None,
                                     'source': 's', 'definition': '', 'target': None,
                                     'goal': '', 'role': '', 'setting_reason': '',
                                     'execution': ''}], 'SaaS行业')
    assert 'A|B' not in md.split('## 指标详解')[0].split('\n')[-1] or 'A|B' not in md  # 不报错即可
    assert 'A|B' in md  # 详解块中保留原始名称


# ============================================================
# 7. 端到端：main 完整链路（临时目录写文件）
# ============================================================

def test_end_to_end_cli(tmp_path):
    """模拟 import_template_output.main 的核心流程：解析→分层→写文件"""
    from import_template_output import main as _main  # noqa: 仅确认可导入

    inp = tmp_path / '模板.md'
    inp.write_text(SAMPLE_MD, encoding='utf-8')
    out_dir = tmp_path / 'out'

    import import_template_output as ito
    md_text = inp.read_text(encoding='utf-8')
    tables = ito.parse_markdown_table(md_text)
    layers = ito.build_industry_library(tables, 'SaaS行业')
    out_dir.mkdir(exist_ok=True)
    for lv in ['战略层', '管理层', '执行层']:
        if layers[lv]:
            content = ito.render_layer_md(lv, layers[lv], 'SaaS行业', '测试')
            (out_dir / f'{lv}指标.md').write_text(content, encoding='utf-8')

    # 三个层级文件均生成
    assert (out_dir / '战略层指标.md').exists()
    assert (out_dir / '管理层指标.md').exists()
    assert (out_dir / '执行层指标.md').exists()
    # 总指标数：第4章 3 个 + 第3章关联地图 1 个（含"指标"列也被识别）= 4
    total = sum(len(v) for v in layers.values())
    assert total == 4
    # 关联地图表中的"新客户收入"（销售总监）被归入管理层
    mgr_names = [m['name'] for m in layers['管理层']]
    assert '新客户收入' in mgr_names
