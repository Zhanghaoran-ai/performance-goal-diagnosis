# -*- coding: utf-8 -*-
"""独立指标拆解树契约测试（v2.6）。"""

import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from indicator_tree import build_indicator_tree, build_indicator_tree_html
from standard_report import StandardReportGenerator


class StubAnalyzer:
    """以指标名组合返回可预测关系分，隔离建树规则与语义词典。"""

    def classify_metric_type(self, _text):
        return '测试类型'

    def assess_relationship(self, parent, child, **_kwargs):
        key = (parent, child)
        scores = {
            ('营收增长率', '续约率'): (0.82, 'strong', 'correct', []),
            ('营收增长率', '拜访次数'): (0.18, 'none', 'unknown', []),
            ('客户满意度', '客户满意度'): (0.35, 'weak', 'unknown', ['fake_split']),
        }
        overall, level, direction, flags = scores.get(key, (0.1, 'none', 'unknown', []))
        return {
            'overall': overall,
            'level': level,
            'flags': flags,
            'needs_review': bool(flags) or level in ('weak', 'none'),
            'layers': {
                'lexical': {'score': overall, 'detail': 'stub'},
                'semantic': {'score': overall, 'detail': 'stub'},
                'causal': {'score': 1.0 if direction == 'correct' else 0.5,
                           'direction': direction, 'detail': 'stub'},
                'numeric': {'score': 0.5, 'ratio': None, 'match': None, 'detail': 'stub'},
            },
        }


@pytest.fixture
def explicit_data():
    return {
        'users': [
            {'user_id': 'U1', 'name': '甲', 'department': '客户成功'},
            {'user_id': 'U2', 'name': '乙', 'department': '客户成功', 'manager_id': 'U1'},
        ],
        'goals': [
            {
                'goal_id': 'G1', 'title': '公司增长', 'level': 'L2',
                'owner_id': 'U1', 'owner_name': '甲', 'department': '客户成功',
                'parent_goal_ids': [],
                'indicators': [
                    {'indicator_id': 'I-PARENT', 'name': '营收增长率', 'value': 30, 'unit': '%'},
                ],
            },
            {
                'goal_id': 'G2', 'title': '客户续约', 'level': 'L3',
                'owner_id': 'U2', 'owner_name': '乙', 'department': '客户成功',
                'parent_goal_ids': ['G1'],
                'indicators': [
                    {'indicator_id': 'I-CHILD', 'parent_indicator_ids': ['I-PARENT'],
                     'name': '续约率', 'value': 92, 'unit': '%'},
                ],
            },
        ],
    }


@pytest.fixture
def inferred_and_gap_data():
    return {
        'users': [],
        'goals': [
            {
                'goal_id': 'G1', 'title': '公司增长', 'level': 'L2',
                'owner_id': 'U1', 'owner_name': '甲', 'department': '销售',
                'parent_goal_ids': [],
                'indicators': [{'name': '营收增长率', 'value': 30, 'unit': '%'}],
            },
            {
                'goal_id': 'G2', 'title': '客户经营', 'level': 'L3',
                'owner_id': 'U2', 'owner_name': '乙', 'department': '销售',
                'parent_goal_ids': ['G1'],
                'indicators': [
                    {'name': '续约率', 'value': 92, 'unit': '%'},
                    {'name': '拜访次数', 'value': 100, 'unit': '次'},
                ],
            },
            {
                'goal_id': 'G3', 'title': '孤立执行', 'level': 'L4',
                'owner_id': 'U3', 'owner_name': '丙', 'department': '销售',
                'parent_goal_ids': [],
                'indicators': [{'name': '客户满意度', 'value': 90, 'unit': '%'}],
            },
        ],
    }


def test_indicator_is_independent_node_not_goal_summary(explicit_data):
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    assert tree['summary']['total_nodes'] == 2
    assert {node['name'] for node in tree['nodes']} == {'营收增长率', '续约率'}
    assert all('indicator_id' in node for node in tree['nodes'])
    assert all('goal_id' in node for node in tree['nodes'])


def test_explicit_parent_reference_creates_solid_edge(explicit_data):
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    assert tree['summary']['explicit_edges'] == 1
    assert tree['summary']['inferred_edges'] == 0
    edge = tree['edges'][0]
    assert edge['parent_indicator_id'] == 'I-PARENT'
    assert edge['child_indicator_id'] == 'I-CHILD'
    assert edge['source'] == 'explicit'
    assert edge['line_style'] == 'solid'
    assert edge['needs_review'] is False


def test_semantic_inference_is_dashed_and_not_claimed_as_explicit(inferred_and_gap_data):
    tree = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    edge = next(e for e in tree['edges'] if e['child_indicator_id'].endswith('I001'))
    assert edge['source'] == 'semantic_inference'
    assert edge['line_style'] == 'dashed'
    assert edge['needs_review'] is True
    assert '父目标关系限定候选' in edge['scope_evidence']


def test_insufficient_evidence_becomes_data_gap(inferred_and_gap_data):
    tree = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    gap_nodes = [n for n in tree['nodes'] if n['relation_state'] == 'data_gap']
    assert any(n['name'] == '拜访次数' for n in gap_nodes)
    assert any('证据不足' in n['gap_reason'] for n in gap_nodes)
    assert not any(
        e['child_indicator_id'] == next(n['indicator_id'] for n in gap_nodes if n['name'] == '拜访次数')
        for e in tree['edges']
    )


def test_non_top_level_without_parent_goal_is_gap(inferred_and_gap_data):
    tree = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    node = next(n for n in tree['nodes'] if n['name'] == '客户满意度')
    assert node['relation_state'] == 'data_gap'
    assert '缺少父目标' in node['gap_reason']


def test_upstream_and_downstream_are_attached(explicit_data):
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    parent = next(n for n in tree['nodes'] if n['indicator_id'] == 'I-PARENT')
    child = next(n for n in tree['nodes'] if n['indicator_id'] == 'I-CHILD')
    assert len(parent['downstream_edge_ids']) == 1
    assert len(child['upstream_edge_ids']) == 1


def test_dangling_explicit_reference_is_reported_not_fabricated(explicit_data):
    explicit_data['goals'][1]['indicators'][0]['parent_indicator_ids'] = ['NOT-FOUND']
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    assert tree['summary']['dangling_reference_count'] == 1
    assert tree['summary']['explicit_edges'] == 0
    assert tree['dangling_references'][0]['reference'] == 'NOT-FOUND'


def test_html_contains_contract_and_relation_diagnostics(explicit_data):
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    page = build_indicator_tree_html(tree)
    assert 'data-component="indicator-decomposition-tree"' in page
    assert '独立指标节点' in page
    assert '实线 · 显式' in page
    assert '虚线 · 推断' in page
    assert '向上关联诊断' in page
    assert '向下承接诊断' in page
    assert 'data-node-id="I-PARENT"' in page


def test_html_marks_no_explicit_relationship_as_data_quality_warning(inferred_and_gap_data):
    tree = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    page = build_indicator_tree_html(tree)
    assert '当前输入没有指标级显式父子关系' in page
    assert '算法候选' in page
    assert '未连接指标（数据缺口）' in page


def test_standard_report_has_separate_indicator_tree_page(explicit_data):
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    result = {
        'summary': {'health_score': 100, 'health_level': '优秀', 'total_goals': 2,
                    'total_users': 2, 'total_issues': 0, 'high_count': 0,
                    'medium_count': 0, 'low_count': 0, 'by_dimension': {}},
        'issues': [], 'suggestions': [], 'indicator_tree': tree,
    }
    page = StandardReportGenerator(result, explicit_data).generate_html()
    assert 'page-indicator-tree' in page
    assert '指标拆解树与上下关联诊断' in page
    assert 'page-goal-tree' in page
    assert '目标拆解树' in page
    assert 'data-component="indicator-decomposition-tree"' in page
    assert '指标树（默认）' in page
    assert '切换到目标树' in page


def test_user_confirmed_decision_is_distinct_from_explicit(inferred_and_gap_data):
    first = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    inferred = next(e for e in first['edges'] if e['source'] == 'semantic_inference')
    data = dict(inferred_and_gap_data)
    data['indicator_relation_decisions'] = [{
        'child_indicator_id': inferred['child_indicator_id'],
        'parent_indicator_id': inferred['parent_indicator_id'],
        'action': 'confirm',
        'note': '业务负责人确认',
    }]
    tree = build_indicator_tree(data, analyzer=StubAnalyzer())
    edge = next(e for e in tree['edges'] if e['child_indicator_id'] == inferred['child_indicator_id'])
    assert edge['source'] == 'user_confirmed'
    assert edge['line_style'] == 'solid'
    assert edge['needs_review'] is False
    assert tree['summary']['user_confirmed_edges'] == 1
    assert tree['summary']['explicit_edges'] == 0


def test_reject_decision_blocks_reinference(inferred_and_gap_data):
    first = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    inferred = next(e for e in first['edges'] if e['source'] == 'semantic_inference')
    data = dict(inferred_and_gap_data)
    data['indicator_relation_decisions'] = [{
        'child_indicator_id': inferred['child_indicator_id'], 'action': 'reject',
    }]
    tree = build_indicator_tree(data, analyzer=StubAnalyzer())
    node = next(n for n in tree['nodes'] if n['indicator_id'] == inferred['child_indicator_id'])
    assert node['relation_state'] == 'user_rejected'
    assert not any(e['child_indicator_id'] == inferred['child_indicator_id'] for e in tree['edges'])
    assert any(g.get('decision_action') == 'reject' for g in tree['data_gaps'])


def test_explicit_relationship_cannot_be_overridden_by_decision(explicit_data):
    explicit_data['indicator_relation_decisions'] = [{
        'child_indicator_id': 'I-CHILD', 'action': 'reject',
    }]
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    assert tree['summary']['explicit_edges'] == 1
    assert tree['decision_results'][0]['applied'] is False
    assert '显式关系' in tree['decision_results'][0]['reason']


def test_html_contains_decision_controls_and_export(inferred_and_gap_data):
    tree = build_indicator_tree(inferred_and_gap_data, analyzer=StubAnalyzer())
    page = build_indicator_tree_html(tree)
    assert '确认保留' in page
    assert '拒绝关系' in page
    assert '待核实' in page
    assert '改选上级指标' in page
    assert '导出关系确认 JSON' in page
    assert 'indicator-relation-decisions.json' in page
    assert 'it-mobile-open' in page
    assert 'closeIndicatorDetail' in page


def test_markdown_contains_indicator_tree_relation_source(explicit_data):
    tree = build_indicator_tree(explicit_data, analyzer=StubAnalyzer())
    result = {
        'summary': {'health_score': 100, 'health_level': '优秀', 'total_goals': 2,
                    'total_users': 2, 'total_issues': 0, 'high_count': 0,
                    'medium_count': 0, 'low_count': 0, 'by_dimension': {}},
        'issues': [], 'suggestions': [], 'indicator_tree': tree,
    }
    markdown = StandardReportGenerator(result, explicit_data).generate_markdown()
    assert '页面2：指标拆解树与上下关联诊断' in markdown
    assert '显式关系（实线）' in markdown
    assert '| 显式 | 营收增长率 | 续约率 |' in markdown
    assert '页面3：目标拆解树' in markdown
    assert '页面4：诊断结果' in markdown
    assert '页面5：优化建议' in markdown
    assert '页面6：人员视图' in markdown
