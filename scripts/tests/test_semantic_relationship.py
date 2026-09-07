# -*- coding: utf-8 -*-
"""
test_semantic_relationship.py — 四层语义关联判断单元测试（v2.5）

目标：锁定 SemanticAnalyzer.assess_relationship 的四层判断规则，防止词典、
阈值或权重调整导致假拆解、因果倒置、数值断裂等结论悄然漂移。

本测试分两类：
1. 真实中文指标用例：验证分词、同义词、因果词和反向指标的实际表现；
2. 隔离规则用例：通过 monkeypatch 固定各层输入，精确验证阈值、权重和硬压级。

运行：
    python3 -m pytest scripts/tests/test_semantic_relationship.py -v
"""

import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from semantic_utils import SemanticAnalyzer


@pytest.fixture
def analyzer():
    """每个用例使用独立分析器，避免词频或 monkeypatch 状态互相影响。"""
    return SemanticAnalyzer()


def _stub_layers(monkeypatch, analyzer, *, lexical, semantic, causal):
    """隔离四层规则：固定词面、语义和因果层原始结果。"""
    monkeypatch.setattr(analyzer, 'multi_dim_similarity', lambda *_a, **_k: lexical)
    monkeypatch.setattr(analyzer, 'word_similarity', lambda *_a, **_k: semantic)
    monkeypatch.setattr(analyzer, 'detect_causal_direction', lambda *_a, **_k: causal)


# ============================================================
# 1. 基础语义能力：真实中文指标
# ============================================================


def test_synonym_normalization(analyzer):
    assert analyzer.normalize_word('营收') == '收入'
    assert analyzer.normalize_word('用户满意度') == '客户满意度'
    assert analyzer.normalize_word('续费') == '续约'


def test_synonym_pair_has_positive_similarity(analyzer):
    score = analyzer.word_similarity('客户满意度', '用户满意度')
    assert score > 0


def test_unrelated_pair_is_less_similar_than_synonym_pair(analyzer):
    related = analyzer.word_similarity('客户满意度', '用户满意度')
    unrelated = analyzer.word_similarity('客户满意度', '招聘完成率')
    assert related > unrelated


@pytest.mark.parametrize('metric', [
    '客户流失率', '员工离职率', '产品缺陷率', '系统故障率', '客户投诉率', '单位成本',
])
def test_reverse_metric_detection(analyzer, metric):
    assert analyzer.is_negative_metric(metric) is True


@pytest.mark.parametrize('metric', [
    '营业收入', '客户满意度', '续约率', '销售完成率',
])
def test_positive_metric_not_misclassified_as_reverse(analyzer, metric):
    assert analyzer.is_negative_metric(metric) is False


# ============================================================
# 2. 因果方向：过程（下级）应驱动结果（上级）
# ============================================================


def test_causal_direction_correct(analyzer):
    assert analyzer.detect_causal_direction(
        '营业收入增长率', '销售拜访完成率'
    ) == 'correct'


def test_causal_direction_reverse(analyzer):
    assert analyzer.detect_causal_direction(
        '销售拜访完成率', '营业收入增长率'
    ) == 'reverse'


def test_causal_direction_unclear(analyzer):
    assert analyzer.detect_causal_direction(
        '客户健康度', '产品价值实现'
    ) == 'unclear'


def test_assessment_uses_string_causal_result(analyzer, monkeypatch):
    """回归保护：detect_causal_direction 当前返回字符串，综合评估必须正确消费。"""
    monkeypatch.setattr(analyzer, 'multi_dim_similarity', lambda *_a, **_k: 0.4)
    monkeypatch.setattr(analyzer, 'word_similarity', lambda *_a, **_k: 0.4)
    result = analyzer.assess_relationship('营业收入增长率', '销售拜访完成率')
    assert result['layers']['causal']['direction'] == 'correct'
    assert result['layers']['causal']['score'] == 1.0


def test_causal_reverse_is_flagged_and_capped(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.7, semantic=0.8, causal='reverse')
    result = analyzer.assess_relationship('过程完成率', '营业收入增长率')
    assert 'causal_reverse' in result['flags']
    assert result['overall'] <= 0.2
    assert result['level'] == 'none'
    assert result['needs_review'] is True


# ============================================================
# 3. 假拆解与语义重叠
# ============================================================


def test_identical_metric_is_fake_split(analyzer):
    result = analyzer.assess_relationship('客户续约率', '客户续约率')
    assert 'fake_split' in result['flags']
    assert result['overall'] <= 0.35
    assert result['level'] in ('weak', 'none')
    assert result['needs_review'] is True


def test_prefix_copy_is_fake_split(analyzer):
    result = analyzer.assess_relationship('客户续约率', '华南区客户续约率')
    assert 'fake_split' in result['flags']
    assert result['overall'] <= 0.35


def test_high_semantic_overlap_flag(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.2, semantic=0.85, causal='unclear')
    result = analyzer.assess_relationship('父指标', '子指标')
    assert 'semantic_overlap' in result['flags']
    assert result['layers']['semantic']['score'] == 1.0
    assert result['needs_review'] is True


def test_fake_split_cap_takes_effect(analyzer, monkeypatch):
    # identical 文本触发 contains；其他层都给高分，仍必须封顶 0.35
    _stub_layers(monkeypatch, analyzer, lexical=0.9, semantic=0.9, causal='correct')
    result = analyzer.assess_relationship('续约率', '续约率', parent_value=100, child_value=100)
    assert 'fake_split' in result['flags']
    assert result['overall'] == pytest.approx(0.35)
    assert result['level'] == 'weak'


# ============================================================
# 4. 数值链路：单子指标与子指标加总
# ============================================================


@pytest.mark.parametrize('child_value, expected_score, expected_match, expected_flag', [
    (100, 1.0, True, False),    # 100%
    (80, 1.0, True, False),     # 80%：闭合边界
    (120, 1.0, True, False),    # 120%：闭合边界
    (79, 0.5, False, False),    # 79%：中度偏差
    (121, 0.5, False, False),   # 121%：中度偏差
    (50, 0.5, False, False),    # 50%：严重偏差边界，未越界
    (150, 0.5, False, False),   # 150%：严重偏差边界，未越界
    (49, 0.0, False, True),     # <50%：数值断裂
    (151, 0.0, False, True),    # >150%：数值断裂
])
def test_numeric_ratio_boundaries(
    analyzer, monkeypatch, child_value, expected_score, expected_match, expected_flag
):
    _stub_layers(monkeypatch, analyzer, lexical=0.4, semantic=0.4, causal='unclear')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value=100, child_value=child_value
    )
    numeric = result['layers']['numeric']
    assert numeric['score'] == expected_score
    assert numeric['match'] is expected_match
    assert ('numeric_mismatch' in result['flags']) is expected_flag


def test_children_sum_numeric_closure(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.4, semantic=0.4, causal='unclear')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value=100,
        parent_children_values=[30, 25, 45]
    )
    numeric = result['layers']['numeric']
    assert numeric['ratio'] == pytest.approx(1.0)
    assert numeric['match'] is True
    assert numeric['score'] == 1.0


def test_children_sum_numeric_mismatch(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.4, semantic=0.4, causal='unclear')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value=100,
        parent_children_values=[80, 80]
    )
    numeric = result['layers']['numeric']
    assert numeric['ratio'] == pytest.approx(1.6)
    assert numeric['match'] is False
    assert 'numeric_mismatch' in result['flags']


def test_missing_numeric_is_neutral(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.4, semantic=0.4, causal='unclear')
    result = analyzer.assess_relationship('父指标', '子指标')
    numeric = result['layers']['numeric']
    assert numeric['score'] == 0.5
    assert numeric['ratio'] is None
    assert numeric['match'] is None
    assert 'numeric_mismatch' not in result['flags']


def test_invalid_numeric_is_skipped_without_exception(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.4, semantic=0.4, causal='unclear')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value='待补充', child_value='暂无'
    )
    numeric = result['layers']['numeric']
    assert numeric['score'] == 0.5
    assert numeric['match'] is None


def test_zero_parent_value_is_skipped(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.4, semantic=0.4, causal='unclear')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value=0, child_value=10
    )
    numeric = result['layers']['numeric']
    assert numeric['ratio'] is None
    assert numeric['match'] is None


# ============================================================
# 5. 综合分、等级阈值与复核规则（隔离测试）
# ============================================================


@pytest.mark.parametrize('lexical, semantic, causal, numeric_value, expected', [
    # overall = lexical层分*0.15 + semantic层分*0.4 + causal层分*0.25 + numeric层分*0.2
    (0.50, 0.50, 'correct', 100, 'strong'),   # 0.15*0.7 + 0.4*0.8 + .25 + .2 = .875
    (0.30, 0.30, 'unclear', 100, 'medium'),   # .06 + .2 + .125 + .2 = .585
    (0.10, 0.10, 'unclear', None, 'weak'),    # .015 + .08 + .125 + .1 = .32
    (0.10, 0.10, 'reverse', None, 'none'),    # reverse 硬压级且低分
])
def test_overall_level_examples(
    analyzer, monkeypatch, lexical, semantic, causal, numeric_value, expected
):
    _stub_layers(monkeypatch, analyzer, lexical=lexical, semantic=semantic, causal=causal)
    kwargs = {}
    if numeric_value is not None:
        kwargs = {'parent_value': 100, 'child_value': numeric_value}
    result = analyzer.assess_relationship('父指标', '子指标', **kwargs)
    assert result['level'] == expected


def test_strong_without_flags_does_not_need_review(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.5, semantic=0.5, causal='correct')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value=100, child_value=100
    )
    assert result['level'] == 'strong'
    assert result['flags'] == []
    assert result['needs_review'] is False


def test_medium_without_flags_does_not_need_review(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.3, semantic=0.3, causal='unclear')
    result = analyzer.assess_relationship(
        '父指标', '子指标', parent_value=100, child_value=100
    )
    assert result['level'] == 'medium'
    assert result['flags'] == []
    assert result['needs_review'] is False


def test_weak_requires_review(analyzer, monkeypatch):
    _stub_layers(monkeypatch, analyzer, lexical=0.1, semantic=0.1, causal='unclear')
    result = analyzer.assess_relationship('父指标', '子指标')
    assert result['level'] == 'weak'
    assert result['needs_review'] is True


# ============================================================
# 6. 输入容错与返回契约
# ============================================================


@pytest.mark.parametrize('parent, child', [
    ('', ''),
    (None, '子指标'),
    ('父指标', None),
    (None, None),
])
def test_empty_text_inputs_do_not_crash(analyzer, parent, child):
    result = analyzer.assess_relationship(parent, child)
    assert 0.0 <= result['overall'] <= 1.0
    assert result['level'] in {'strong', 'medium', 'weak', 'none'}
    assert result['needs_review'] is True


def test_return_contract(analyzer):
    result = analyzer.assess_relationship('营业收入增长率', '销售拜访完成率')
    assert set(result) == {'overall', 'level', 'layers', 'flags', 'needs_review'}
    assert set(result['layers']) == {'lexical', 'semantic', 'causal', 'numeric'}
    assert set(result['layers']['lexical']) == {'score', 'detail'}
    assert set(result['layers']['semantic']) == {'score', 'detail'}
    assert set(result['layers']['causal']) == {'score', 'direction', 'detail'}
    assert set(result['layers']['numeric']) == {'score', 'ratio', 'match', 'detail'}
    assert isinstance(result['overall'], float)
    assert isinstance(result['flags'], list)
    assert isinstance(result['needs_review'], bool)
