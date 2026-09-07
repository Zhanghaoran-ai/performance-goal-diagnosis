# -*- coding: utf-8 -*-
"""
import_template_output.py — 模板技能输出 → 诊断行业指标库 桥接器（v2.5 新增）

实现用户工作流闭环：先应用 industry-performance-template 技能产出行业绩效模板
（Markdown 绩效方案，含第4章「指标&目标范例明细」表），再应用本技能做目标拆解诊断。

本脚本把模板技能输出的 Markdown 绩效方案自动转换为诊断技能可消费的
「行业指标库」三层格式（战略层/管理层/执行层 .md），从而支撑诊断的
「指标偏离行业基准」对标分析。

用法：
    python3 scripts/import_template_output.py \
        --input 模板技能输出的绩效方案.md \
        --output ./industry_metrics/SaaS行业 \
        --industry "SaaS行业"

    # 随后用转换出的指标库做诊断对标
    python3 scripts/diagnose.py --input goals.json \
        --industry-metrics ./industry_metrics \
        --format html -o report.html

支持两种输入表格：
1. 模板技能第4章「指标&目标范例明细」（列含：岗位、指标、定义/公式、外部参考值、
   企业建议目标、证据等级与来源、数据来源、关联目标）
2. 任意包含「指标|基准值|合理范围」列的自定义表格
"""

import argparse
import os
import re
import sys


# 岗位 → 层级映射关键词
# 注意：战略层仅限公司级（一号位/CEO等）；"部门负责人"属于部门管理，归管理层。
LEVEL_RULES = [
    # (关键词列表, 层级)
    (['CEO', 'CTO', 'COO', 'CFO', '总经理', '总裁', '创始人', 'VP', '副总裁',
      '首席', '高管', '一号位', '公司负责人', '公司总经理'], '战略层'),
    (['部门负责人', '总监', '负责人', '经理', '主管', 'Leader', 'lead', 'head', 'Head',
      '管理者'], '管理层'),
    (['专员', '工程师', '顾问', '代表', '助理', '执行', '员工', '开发',
      '测试', '运营', '设计', '客服', '销售', '出纳', '会计', '编辑'], '执行层'),
]

DEFAULT_LEVEL = '执行层'


def _esc_tsv_cell(value):
    """转义表格单元格（去竖线、去换行）"""
    return re.sub(r'[\|\n\r]', ' ', str(value or '')).strip()


def parse_markdown_table(md_text):
    """
    解析 Markdown 中的表格，返回 [(header_list, [row_list, ...]), ...]
    """
    tables = []
    lines = md_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|'):
            header_cells = [c.strip() for c in line.strip('|').split('|')]
            # 跳过分隔行 | --- | --- |
            if i + 1 < len(lines) and re.match(r'^\s*\|[\s:\-|]+\|\s*$', lines[i + 1].strip()):
                rows = []
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith('|'):
                    cells = [c.strip() for c in lines[j].strip().strip('|').split('|')]
                    rows.append(cells)
                    j += 1
                tables.append((header_cells, rows))
                i = j
                continue
        i += 1
    return tables


def _parse_number(raw):
    """
    从文本中提取数字（用于基准值/目标值）。
    如 '110%（100~130）'→(110.0,(100.0,130.0))，'27%'→(27.0,None)，'12（8~18）'→(12.0,(8,18))。
    返回 (主值, 范围(min,max) 或 None)。
    """
    if not raw:
        return None, None
    text = str(raw)
    m = re.search(r'(-?\d+(?:\.\d+)?)', text)
    if not m:
        return None, None
    val = float(m.group(1))
    # 优先提取括号内的范围，如（100~130）/（100-130）/（100,130）
    range_match = re.search(r'[（(]\s*(\d+(?:\.\d+)?)\s*[~\-至,到]\s*(\d+(?:\.\d+)?)\s*[)）]', text)
    if range_match:
        lo, hi = float(range_match.group(1)), float(range_match.group(2))
        return val, (min(lo, hi), max(lo, hi))
    # 次优：提取主值后的连续数字作为范围
    nums = re.findall(r'(-?\d+(?:\.\d+)?)', text)
    if len(nums) >= 2:
        vals = [float(n) for n in nums]
        return val, (min(vals[:2]), max(vals[:2]))
    return val, None


def _detect_level(role_text):
    """根据岗位关键词判断层级"""
    role = str(role_text or '')
    for keywords, level in LEVEL_RULES:
        for kw in keywords:
            if kw.lower() in role.lower():
                return level
    return DEFAULT_LEVEL


def _normalize_metric_name(name):
    """去指标名中的加粗/前后缀"""
    name = re.sub(r'\*\*?', '', str(name or ''))
    return name.strip()


def build_industry_library(tables, industry_name, source_meta=None):
    """
    从解析的表格构建三层行业指标库。

    返回: {'战略层': [metric_dict,...], '管理层': [...], '执行层': [...]}
    """
    layers = {'战略层': [], '管理层': [], '执行层': []}
    seen = set()  # (layer, metric) 去重

    for header, rows in tables:
        header_lower = [h.lower() for h in header]
        # 判断是否指标表（含"指标"列）
        if not any('指标' in h for h in header):
            continue

        # 定位列：精确匹配优先，回退包含匹配
        def _find_col(exact_kw, contain_kw=None):
            for idx, h in enumerate(header):
                if h.strip() == exact_kw:
                    return idx
            if contain_kw:
                for idx, h in enumerate(header):
                    if contain_kw in h:
                        return idx
            return None

        col_metric = _find_col('指标', '指标名称')
        # 岗位列：兼容"岗位"与"关键岗位"表头（关联地图表用后者）
        col_role = _find_col('岗位')
        if col_role is None:
            col_role = _find_col(None, '岗位')
        col_ref = _find_col('外部参考值', '参考值')
        col_target = _find_col('企业建议目标', '建议目标')
        col_benchmark = _find_col('基准值')
        col_range = _find_col('合理范围')
        col_source = _find_col('数据来源')          # 精确，避免误配"证据等级与来源"
        col_evidence = _find_col('证据等级与来源', '证据等级')
        col_definition = _find_col('定义/公式', '定义')
        col_goal = _find_col('关联目标', '公司目标')
        col_setting_reason = _find_col('设定原因')
        col_execution = _find_col('执行要点')

        if col_metric is None:
            continue

        for row in rows:
            # 跳过空行/表头重复
            if not row or not any(c.strip() for c in row):
                continue
            # 容错：表内竖线导致行被拆多列时，按表头长度截断处理
            metric_raw = row[col_metric] if col_metric < len(row) else ''
            metric = _normalize_metric_name(metric_raw)
            if not metric or metric in ('指标', '指标名称', '指标名'):
                continue

            role = row[col_role] if col_role is not None and col_role < len(row) else ''
            level = _detect_level(role)

            # 基准值：优先用"基准值"列，否则用"外部参考值"
            raw_bench = ''
            if col_benchmark is not None and col_benchmark < len(row):
                raw_bench = row[col_benchmark]
            elif col_ref is not None and col_ref < len(row):
                raw_bench = row[col_ref]
            bench_val, bench_range = _parse_number(raw_bench)

            # 合理范围
            if col_range is not None and col_range < len(row) and row[col_range].strip():
                _, rng = _parse_number(row[col_range])
                if rng:
                    bench_range = rng
            elif bench_range is None and bench_val is not None:
                bench_range = (round(bench_val * 0.9, 1), round(bench_val * 1.2, 1))

            # 建议目标（企业推导）
            target_val = None
            if col_target is not None and col_target < len(row):
                target_val, _ = _parse_number(row[col_target])

            # 数据来源：优先"数据来源"列，回退"证据等级与来源"
            source = ''
            if col_source is not None and col_source < len(row):
                source = row[col_source]
            elif col_evidence is not None and col_evidence < len(row):
                source = row[col_evidence]

            definition = row[col_definition] if col_definition is not None and col_definition < len(row) else ''
            goal = row[col_goal] if col_goal is not None and col_goal < len(row) else ''
            setting_reason = row[col_setting_reason] if col_setting_reason is not None and col_setting_reason < len(row) else ''
            execution = row[col_execution] if col_execution is not None and col_execution < len(row) else ''

            key = (level, metric)
            if key in seen:
                continue
            seen.add(key)

            layers[level].append({
                'name': metric,
                'benchmark': bench_val,
                'range': bench_range,
                'source': source,
                'definition': definition,
                'target': target_val,
                'goal': goal,
                'role': role,
                'setting_reason': setting_reason,
                'execution': execution,
            })

    return layers


def render_layer_md(layer_name, metrics, industry_name, source_note=''):
    """
    渲染单个层级 .md 文件（与诊断技能行业指标库格式兼容）
    """
    lines = [f"# {industry_name} - {layer_name}指标", ""]
    lines.append("> ⚠️ **数据质量声明**：本指标库由 industry-performance-template 技能输出转换而来，")
    lines.append("> 基准值仅供参考，不构成决策依据。建议结合企业自身历史数据综合判断。")
    lines.append("> ")
    lines.append(f"> 📝 **来源**：{source_note or '行业绩效模板输出'}（v2.5 桥接器转换）")
    lines.append("")
    if layer_name == '战略层':
        lines.append("> 面向公司高管/一号位，承接战略目标，对标行业基准，更新频率：月/季")
    elif layer_name == '管理层':
        lines.append("> 面向部门总监/负责人，分解战略目标，负责运营管控，更新频率：周/月")
    else:
        lines.append("> 面向岗位员工/执行者，落地执行，更新频率：日/周")
    lines.append("")
    lines.append("## 指标列表")
    lines.append("")
    lines.append("| 序号 | 指标名称 | 基准值 | 合理范围 | 数据来源 | 权威性 |")
    lines.append("|------|---------|--------|---------|---------|--------|")
    for idx, m in enumerate(metrics, 1):
        bm = f"{m['benchmark']:g}" if m['benchmark'] is not None else '-'
        rng = ''
        if m['range']:
            rng = f"{m['range'][0]:g} ~ {m['range'][1]:g}"
        else:
            rng = '按行业对标'
        src = _esc_tsv_cell(m['source']) or '行业模板输出'
        lines.append(f"| {idx} | **{_esc_tsv_cell(m['name'])}** | {bm} | {rng} | {src[:40]} | ⭐⭐⭐ |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 指标详解")
    lines.append("")
    for idx, m in enumerate(metrics, 1):
        lines.append(f"### {idx}. {m['name']}")
        lines.append("")
        lines.append(f"- **基准值**：{m['benchmark']:g}" if m['benchmark'] is not None else "- **基准值**：暂无可靠外部基准")
        if m['range']:
            lines.append(f"- **合理范围**：{m['range'][0]:g} ~ {m['range'][1]:g}")
        if m['definition']:
            lines.append(f"- **定义/公式**：{_esc_tsv_cell(m['definition'])}")
        if m['target'] is not None:
            lines.append(f"- **企业建议目标**：{m['target']:g}")
        if m['goal']:
            lines.append(f"- **关联公司目标**：{_esc_tsv_cell(m['goal'])}")
        if m['role']:
            lines.append(f"- **关联岗位**：{_esc_tsv_cell(m['role'])}")
        if m['setting_reason']:
            lines.append(f"- **设定原因**：{_esc_tsv_cell(m['setting_reason'])}")
        if m['execution']:
            lines.append(f"- **执行要点**：{_esc_tsv_cell(m['execution'])}")
        if m['source']:
            lines.append(f"- **数据来源**：{_esc_tsv_cell(m['source'])}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='把 industry-performance-template 技能输出的绩效方案 Markdown '
                    '转换为 performance-goal-diagnosis 的行业指标库（三层 .md）')
    parser.add_argument('--input', '-i', required=True,
                        help='模板技能输出的绩效方案 Markdown 文件路径')
    parser.add_argument('--output', '-o', required=True,
                        help='输出目录（将创建 <行业名>/ 子目录，内含三层指标文件）')
    parser.add_argument('--industry', '-n', default='通用行业',
                        help='行业名称（用于目录名与文件标题，默认"通用行业"）')
    parser.add_argument('--source-note', default='',
                        help='来源说明（写入文件头部，默认自动生成）')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在：{args.input}")
        sys.exit(1)

    md_text = open(args.input, encoding='utf-8').read()
    tables = parse_markdown_table(md_text)
    if not tables:
        print("❌ 未在输入文件中解析到任何表格，请确认是模板技能输出的绩效方案 Markdown")
        sys.exit(1)

    layers = build_industry_library(tables, args.industry)
    total = sum(len(v) for v in layers.values())
    if total == 0:
        print("❌ 未解析到任何指标行，请确认第4章指标表列名包含「指标」")
        sys.exit(1)

    out_dir = os.path.join(args.output, args.industry)
    os.makedirs(out_dir, exist_ok=True)
    source_note = args.source_note or f'{args.industry}行业绩效模板（成长期）'

    layer_names = {'战略层': '战略层', '管理层': '管理层', '执行层': '执行层'}
    for layer in ['战略层', '管理层', '执行层']:
        if not layers[layer]:
            continue
        content = render_layer_md(layer_names[layer], layers[layer], args.industry, source_note)
        path = os.path.join(out_dir, f"{layer}指标.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✅ {layer}：{len(layers[layer])} 个指标 → {path}")

    print(f"\n✅ 转换完成：共 {total} 个指标，写入 {out_dir}")
    print(f"   下一步：python3 scripts/diagnose.py --input goals.json \\")
    print(f"           --industry-metrics {os.path.abspath(args.output)} --format html -o report.html")


if __name__ == '__main__':
    main()
