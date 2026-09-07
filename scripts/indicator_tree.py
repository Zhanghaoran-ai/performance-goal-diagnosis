#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立指标拆解树模型与 HTML 渲染器（v2.6）。

指标是独立节点，不再是目标节点的附属摘要。关系严格区分：
1. explicit：输入数据明确提供的指标父子关系；
2. semantic_inference：在明确的父目标/对齐目标范围内，由四层语义算法推断；
3. data_gap：证据不足，不生成伪关系，只记录数据缺口。
"""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter, defaultdict

try:
    from semantic_utils import get_semantic_analyzer
except ImportError:  # pragma: no cover - 仅用于模块被单独复制时降级
    get_semantic_analyzer = None


EXPLICIT_PARENT_FIELDS = (
    'parent_indicator_ids', 'parent_metric_ids', 'upstream_indicator_ids',
    'parent_indicator_id', 'parent_metric_id', 'upstream_indicator_id',
)
EXPLICIT_ID_FIELDS = ('indicator_id', 'metric_id', 'id')


def _as_list(value):
    if value is None or value == '':
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v not in (None, '')]
    return [str(value)]


def _level_number(level):
    text = str(level or '')
    digits = ''.join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 99


def _safe_float(value):
    try:
        if value is None or value == '':
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_value(indicator):
    for key in ('target_value', 'target', 'value', 'current_value'):
        if indicator.get(key) not in (None, ''):
            return indicator.get(key)
    return None


def _display_value(node):
    value = node.get('value')
    unit = node.get('unit') or ''
    if value in (None, ''):
        return '未提供目标值'
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f'{value}{unit}'


def _relationship_diagnosis(assessment, inferred=False):
    flags = assessment.get('flags', [])
    if 'causal_reverse' in flags:
        text = '因果方向疑似倒置：下级更像结果，而不是上级结果的驱动因素'
        status = 'risk'
    elif 'fake_split' in flags:
        text = '疑似假拆解：上下级指标高度重复，未形成真正的驱动分解'
        status = 'risk'
    elif 'numeric_mismatch' in flags:
        text = '数值链路不闭合，需核对统计口径或目标值'
        status = 'risk'
    elif assessment.get('level') == 'strong':
        text = '语义、因果或数值证据较强，承接关系相对清晰'
        status = 'good'
    elif assessment.get('level') == 'medium':
        text = '存在一定承接证据，但仍需结合业务口径确认'
        status = 'review'
    else:
        text = '关联证据较弱，不能据此确认真实父子关系'
        status = 'risk'
    if inferred:
        text += '；该连线为算法候选，必须人工复核'
    return text, status


class IndicatorTreeBuilder:
    """从目标、人员和指标明细构建可审计的指标关系树。"""

    def __init__(self, data, analyzer=None):
        self.data = data or {}
        self.goals = self.data.get('goals', []) or []
        self.users = self.data.get('users', []) or []
        self.goal_map = {str(g.get('goal_id')): g for g in self.goals if g.get('goal_id')}
        self.user_map = {str(u.get('user_id')): u for u in self.users if u.get('user_id')}
        self.analyzer = analyzer or (get_semantic_analyzer() if get_semantic_analyzer else None)
        self.nodes = []
        self.node_map = {}
        self.alias_map = defaultdict(list)
        self.goal_nodes = defaultdict(list)
        self.edges = []
        self.edge_keys = set()
        self.gaps = []
        self.dangling_references = []
        raw_decisions = self.data.get('indicator_relation_decisions', []) or []
        if isinstance(raw_decisions, dict):
            raw_decisions = raw_decisions.get('decisions', []) or []
        self.relation_decisions = {
            str(item.get('child_indicator_id')): item
            for item in raw_decisions if isinstance(item, dict) and item.get('child_indicator_id')
        }
        self.decision_results = []
        self.blocked_children = set()

    def build(self):
        self._collect_nodes()
        self._collect_explicit_edges()
        self._apply_user_decisions()
        self._infer_missing_edges()
        self._attach_relationships()
        return self._serialize()

    def _collect_nodes(self):
        seen_ids = set()
        for goal in self.goals:
            goal_id = str(goal.get('goal_id') or '')
            owner_id = str(goal.get('owner_id') or '')
            owner = self.user_map.get(owner_id, {})
            for index, indicator in enumerate(goal.get('indicators', []) or [], 1):
                if not isinstance(indicator, dict):
                    indicator = {'name': str(indicator)}
                explicit_id = ''
                for field in EXPLICIT_ID_FIELDS:
                    if indicator.get(field) not in (None, ''):
                        explicit_id = str(indicator[field])
                        break
                base_id = explicit_id or f'{goal_id}::I{index:03d}'
                node_id = base_id
                suffix = 2
                while node_id in seen_ids:
                    node_id = f'{base_id}#{suffix}'
                    suffix += 1
                seen_ids.add(node_id)
                parent_refs = []
                for field in EXPLICIT_PARENT_FIELDS:
                    parent_refs.extend(_as_list(indicator.get(field)))
                node = {
                    'indicator_id': node_id,
                    'explicit_indicator_id': explicit_id or None,
                    'name': str(indicator.get('name') or '').strip() or '未命名指标',
                    'value': _metric_value(indicator),
                    'unit': str(indicator.get('unit') or ''),
                    'goal_id': goal_id,
                    'goal_title': str(goal.get('title') or ''),
                    'level': str(goal.get('level') or 'L?'),
                    'owner_id': owner_id,
                    'owner_name': str(goal.get('owner_name') or owner.get('name') or '未知'),
                    'department': str(goal.get('department') or owner.get('department') or '未分组'),
                    'metric_type': self.analyzer.classify_metric_type(str(indicator.get('name') or '')) if self.analyzer else '其他',
                    'explicit_parent_refs': list(dict.fromkeys(parent_refs)),
                    'upstream_edge_ids': [],
                    'downstream_edge_ids': [],
                    'relation_state': 'unprocessed',
                    'gap_reason': '',
                }
                self.nodes.append(node)
                self.node_map[node_id] = node
                self.goal_nodes[goal_id].append(node_id)
                self.alias_map[node_id].append(node_id)
                if explicit_id:
                    self.alias_map[explicit_id].append(node_id)

    def _resolve_ref(self, ref, child_node=None):
        candidates = list(dict.fromkeys(self.alias_map.get(str(ref), [])))
        if len(candidates) <= 1:
            return candidates[0] if candidates else None
        if child_node:
            goal = self.goal_map.get(child_node.get('goal_id'), {})
            parent_goals = set(_as_list(goal.get('parent_goal_ids')) + _as_list(goal.get('aligned_to_goal_ids')))
            scoped = [nid for nid in candidates if self.node_map[nid].get('goal_id') in parent_goals]
            if len(scoped) == 1:
                return scoped[0]
        return None

    def _collect_explicit_edges(self):
        for child in self.nodes:
            for ref in child.get('explicit_parent_refs', []):
                parent_id = self._resolve_ref(ref, child)
                if not parent_id:
                    self.dangling_references.append({
                        'child_indicator_id': child['indicator_id'],
                        'reference': ref,
                        'reason': '显式父指标引用不存在或不唯一',
                    })
                    continue
                self._add_edge(parent_id, child['indicator_id'], 'explicit', '指标字段显式指定')

        for rel in self.data.get('indicator_relations', []) or []:
            if not isinstance(rel, dict):
                continue
            parent_ref = rel.get('parent_indicator_id') or rel.get('parent_metric_id') or rel.get('source_id')
            child_ref = rel.get('child_indicator_id') or rel.get('child_metric_id') or rel.get('target_id')
            parent_id = self._resolve_ref(parent_ref)
            child_id = self._resolve_ref(child_ref)
            if parent_id and child_id:
                self._add_edge(parent_id, child_id, 'explicit', str(rel.get('relation_type') or '显式关系表'))
            else:
                self.dangling_references.append({
                    'child_indicator_id': child_ref,
                    'reference': parent_ref,
                    'reason': 'indicator_relations 中的引用不存在或不唯一',
                })

    def _candidate_parent_goal_ids(self, child_goal):
        direct = _as_list(child_goal.get('parent_goal_ids'))
        aligned = _as_list(child_goal.get('aligned_to_goal_ids'))
        return list(dict.fromkeys(direct + aligned)), set(direct), set(aligned)

    def _apply_user_decisions(self):
        """用户确认优先于语义推断，但不会覆盖输入中的显式关系。"""
        incoming = {e['child_indicator_id'] for e in self.edges}
        valid_actions = {'confirm', 'reject', 'reassign', 'pending'}
        for child_id, decision in self.relation_decisions.items():
            child = self.node_map.get(child_id)
            action = decision.get('action')
            result = {'child_indicator_id': child_id, 'action': action, 'applied': False}
            if not child:
                result['reason'] = '决策引用的下级指标不存在'
            elif child_id in incoming:
                result['reason'] = '该指标已有输入显式关系，用户决策未覆盖事实关系'
            elif action not in valid_actions:
                result['reason'] = '未知决策动作'
            elif action in ('reject', 'pending'):
                self.blocked_children.add(child_id)
                child['relation_state'] = 'user_rejected' if action == 'reject' else 'user_pending'
                child['gap_reason'] = decision.get('note') or ('用户已拒绝算法候选关系' if action == 'reject' else '用户标记为待核实')
                self.gaps.append({
                    'indicator_id': child_id, 'goal_id': child['goal_id'],
                    'reason': child['gap_reason'], 'decision_action': action,
                    'required_fields': ['人工补充或重新选择上级指标'],
                })
                result['applied'] = True
            else:
                parent_ref = decision.get('parent_indicator_id')
                parent_id = self._resolve_ref(parent_ref, child)
                if not parent_id:
                    result['reason'] = '确认/改选的上级指标不存在或不唯一'
                else:
                    self._add_edge(
                        parent_id, child_id, 'user_confirmed',
                        decision.get('note') or ('用户确认算法候选' if action == 'confirm' else '用户改选上级指标'),
                    )
                    self.blocked_children.add(child_id)
                    incoming.add(child_id)
                    result.update({'applied': True, 'parent_indicator_id': parent_id})
            self.decision_results.append(result)

    def _infer_missing_edges(self):
        incoming = {e['child_indicator_id'] for e in self.edges}
        min_level = min((_level_number(n['level']) for n in self.nodes), default=99)
        for child in self.nodes:
            if child['indicator_id'] in incoming or child['indicator_id'] in self.blocked_children:
                continue
            child_goal = self.goal_map.get(child['goal_id'], {})
            parent_goal_ids, direct_ids, aligned_ids = self._candidate_parent_goal_ids(child_goal)
            if not parent_goal_ids:
                if _level_number(child['level']) == min_level:
                    child['relation_state'] = 'top_level'
                    child['gap_reason'] = '当前数据中的顶层指标，不要求继续向上关联'
                else:
                    self._mark_gap(child, '缺少父目标/对齐目标，无法限定上级指标候选范围')
                continue

            candidates = []
            for parent_goal_id in parent_goal_ids:
                for parent_node_id in self.goal_nodes.get(parent_goal_id, []):
                    parent = self.node_map[parent_node_id]
                    assessment = self._assess(parent, child)
                    rank_score = assessment.get('overall', 0)
                    if assessment.get('layers', {}).get('causal', {}).get('direction') == 'correct':
                        rank_score += 0.08
                    if 'fake_split' in assessment.get('flags', []):
                        rank_score += 0.18  # 保留高风险“复制型”候选，供诊断而非认定为健康关系
                    candidates.append((rank_score, parent, assessment, parent_goal_id))

            if not candidates:
                self._mark_gap(child, '父目标存在，但父目标中没有可用指标')
                continue
            candidates.sort(key=lambda item: item[0], reverse=True)
            _, parent, assessment, parent_goal_id = candidates[0]
            semantic_layer = assessment.get('layers', {}).get('semantic', {}).get('score', 0)
            causal_direction = assessment.get('layers', {}).get('causal', {}).get('direction')
            flags = set(assessment.get('flags', []))
            admissible = (
                assessment.get('overall', 0) >= 0.50
                or 'fake_split' in flags
                or (semantic_layer >= 0.80 and causal_direction != 'reverse')
                or (causal_direction == 'correct' and assessment.get('overall', 0) >= 0.40)
            )
            if admissible:
                scope = '父目标关系' if parent_goal_id in direct_ids else '目标对齐关系'
                self._add_edge(
                    parent['indicator_id'], child['indicator_id'], 'semantic_inference',
                    f'{scope}限定候选 + 四层语义评分', assessment=assessment,
                )
                incoming.add(child['indicator_id'])
            else:
                best_name = parent.get('name', '未命名指标')
                score = assessment.get('overall', 0)
                self._mark_gap(child, f'存在父目标，但最佳候选“{best_name}”证据不足（综合分 {score:.0%}）')

    def _assess(self, parent, child):
        if not self.analyzer:
            return {
                'overall': 0.0, 'level': 'none', 'flags': [], 'needs_review': True,
                'layers': {
                    'lexical': {'score': 0, 'detail': '语义分析器不可用'},
                    'semantic': {'score': 0, 'detail': '语义分析器不可用'},
                    'causal': {'score': 0, 'direction': 'unknown', 'detail': '语义分析器不可用'},
                    'numeric': {'score': 0.5, 'ratio': None, 'match': None, 'detail': '未校验'},
                },
            }
        return self.analyzer.assess_relationship(
            parent.get('name'), child.get('name'),
            parent_value=_safe_float(parent.get('value')),
            child_value=_safe_float(child.get('value')),
        )

    def _add_edge(self, parent_id, child_id, source, evidence, assessment=None):
        if parent_id == child_id or (parent_id, child_id) in self.edge_keys:
            return
        parent = self.node_map.get(parent_id)
        child = self.node_map.get(child_id)
        if not parent or not child:
            return
        assessment = assessment or self._assess(parent, child)
        diagnosis, status = _relationship_diagnosis(assessment, inferred=(source == 'semantic_inference'))
        edge_id = f'E-{len(self.edges) + 1:04d}'
        source_labels = {
            'explicit': '显式指标关系',
            'semantic_inference': '语义推断关系',
            'user_confirmed': '用户确认关系',
        }
        edge = {
            'edge_id': edge_id,
            'parent_indicator_id': parent_id,
            'child_indicator_id': child_id,
            'source': source,
            'source_label': source_labels.get(source, source),
            'line_style': 'dashed' if source == 'semantic_inference' else 'solid',
            'source_confidence': 1.0 if source in ('explicit', 'user_confirmed') else assessment.get('overall', 0),
            'relationship_score': assessment.get('overall', 0),
            'relationship_level': assessment.get('level', 'none'),
            'scope_evidence': evidence,
            'diagnosis': diagnosis,
            'diagnosis_status': status,
            'flags': assessment.get('flags', []),
            'needs_review': bool(source == 'semantic_inference' or (source == 'explicit' and assessment.get('needs_review'))),
            'layers': assessment.get('layers', {}),
        }
        self.edges.append(edge)
        self.edge_keys.add((parent_id, child_id))

    def _mark_gap(self, node, reason):
        node['relation_state'] = 'data_gap'
        node['gap_reason'] = reason
        self.gaps.append({
            'indicator_id': node['indicator_id'],
            'goal_id': node['goal_id'],
            'reason': reason,
            'required_fields': ['indicator_id', 'parent_indicator_ids 或 indicator_relations'],
        })

    def _attach_relationships(self):
        for edge in self.edges:
            self.node_map[edge['parent_indicator_id']]['downstream_edge_ids'].append(edge['edge_id'])
            self.node_map[edge['child_indicator_id']]['upstream_edge_ids'].append(edge['edge_id'])
        for node in self.nodes:
            if node['upstream_edge_ids']:
                sources = {next(e['source'] for e in self.edges if e['edge_id'] == eid) for eid in node['upstream_edge_ids']}
                if sources == {'explicit'}:
                    node['relation_state'] = 'explicit'
                elif 'user_confirmed' in sources:
                    node['relation_state'] = 'user_confirmed'
                else:
                    node['relation_state'] = 'inferred'
            elif node['relation_state'] == 'unprocessed':
                node['relation_state'] = 'top_level'
                node['gap_reason'] = '当前数据中的顶层指标'

    def _serialize(self):
        counts = Counter(edge['source'] for edge in self.edges)
        levels = Counter(node['level'] for node in self.nodes)
        root_ids = [n['indicator_id'] for n in self.nodes if not n['upstream_edge_ids'] and n['relation_state'] == 'top_level']
        gap_ids = [
            n['indicator_id'] for n in self.nodes
            if n['relation_state'] in ('data_gap', 'user_rejected', 'user_pending')
        ]
        explicit_id_count = sum(1 for n in self.nodes if n.get('explicit_indicator_id'))
        summary = {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'explicit_edges': counts.get('explicit', 0),
            'inferred_edges': counts.get('semantic_inference', 0),
            'user_confirmed_edges': counts.get('user_confirmed', 0),
            'decision_count': len(self.decision_results),
            'applied_decision_count': sum(1 for item in self.decision_results if item.get('applied')),
            'data_gap_count': len(gap_ids),
            'top_level_count': len(root_ids),
            'dangling_reference_count': len(self.dangling_references),
            'explicit_indicator_id_count': explicit_id_count,
            'level_counts': dict(sorted(levels.items())),
            'provenance_notice': (
                '指标关系包含显式关系、算法推断关系和用户确认关系；三类来源相互区分。'
                '推断关系不等同于业务已确认关系；用户确认会被记录为人工裁决而非原始事实。'
                '证据不足的节点以数据缺口呈现，不生成确定性连线。'
            ),
        }
        return {
            'version': '2.7',
            'summary': summary,
            'nodes': self.nodes,
            'edges': self.edges,
            'root_indicator_ids': root_ids,
            'data_gap_indicator_ids': gap_ids,
            'data_gaps': self.gaps,
            'dangling_references': self.dangling_references,
            'decision_results': self.decision_results,
        }


def build_indicator_tree(data, analyzer=None):
    """构建独立指标树的公开入口。"""
    return IndicatorTreeBuilder(data, analyzer=analyzer).build()


def _token(value):
    return hashlib.sha1(str(value).encode('utf-8')).hexdigest()[:12]


def _edge_badge(edge):
    source = edge.get('source')
    if source == 'explicit':
        return '<span class="it-edge-badge it-explicit">实线 · 显式</span>'
    if source == 'user_confirmed':
        return '<span class="it-edge-badge it-confirmed">实线 · 用户确认</span>'
    return '<span class="it-edge-badge it-inferred">虚线 · 推断</span>'


def _decision_controls(edge, other_node, direction):
    if edge.get('source') != 'semantic_inference' or direction != 'up':
        return ''
    edge_id = html.escape(edge.get('edge_id', ''))
    child_id = html.escape(edge.get('child_indicator_id', ''))
    parent_id = html.escape(edge.get('parent_indicator_id', ''))
    return f'''<div class="it-decision" data-decision-edge="{edge_id}">
        <div class="it-decision-title">请确认这条弱/推断关系如何处理</div>
        <div class="it-decision-actions">
          <button type="button" onclick="setIndicatorDecision('{edge_id}','{child_id}','confirm','{parent_id}',this)">确认保留</button>
          <button type="button" onclick="setIndicatorDecision('{edge_id}','{child_id}','reject','',this)">拒绝关系</button>
          <button type="button" onclick="setIndicatorDecision('{edge_id}','{child_id}','pending','',this)">待核实</button>
        </div>
        <label>改选上级指标
          <select aria-label="改选上级指标" data-parent-picker="{edge_id}"></select>
        </label>
        <button type="button" onclick="reassignIndicatorDecision('{edge_id}','{child_id}',this)">保存改选</button>
        <textarea data-decision-note="{edge_id}" placeholder="可选：记录判断依据"></textarea>
        <div class="it-decision-status" data-decision-status="{edge_id}">尚未确认</div>
    </div>'''


def _relation_detail(edge, other_node, direction):
    arrow = '↑' if direction == 'up' else '↓'
    role = '上级' if direction == 'up' else '下级'
    flags = edge.get('flags') or []
    flag_text = '、'.join(flags) if flags else '无硬风险标记'
    review = '需人工复核' if edge.get('needs_review') else '关系来源明确'
    return f'''<div class="it-rel-card" data-edge-source="{html.escape(edge.get('source', ''))}">
        <div class="it-rel-title">{arrow} {role}：{html.escape(other_node.get('name', ''))} {_edge_badge(edge)}</div>
        <div class="it-rel-meta">所属目标：{html.escape(other_node.get('goal_title', ''))} · {html.escape(other_node.get('level', ''))} · {html.escape(other_node.get('owner_name', ''))}</div>
        <div class="it-rel-score">关系质量：{edge.get('relationship_score', 0):.0%}（{html.escape(edge.get('relationship_level', ''))}） · {review}</div>
        <div class="it-rel-diagnosis">{html.escape(edge.get('diagnosis', ''))}</div>
        <div class="it-rel-evidence">依据：{html.escape(edge.get('scope_evidence', ''))}；风险标记：{html.escape(flag_text)}</div>
        {_decision_controls(edge, other_node, direction)}
    </div>'''


def build_indicator_tree_html(indicator_tree, data=None):
    """渲染独立指标拆解树；每个指标节点可查看向上/向下关系诊断。"""
    tree = indicator_tree or build_indicator_tree(data or {})
    nodes = tree.get('nodes', [])
    edges = tree.get('edges', [])
    summary = tree.get('summary', {})
    node_map = {n['indicator_id']: n for n in nodes}
    edge_map = {e['edge_id']: e for e in edges}
    child_edges = defaultdict(list)
    for edge in edges:
        child_edges[edge['parent_indicator_id']].append(edge)

    def node_card(node, incoming=None, visited=None):
        visited = set(visited or ())
        node_id = node['indicator_id']
        if node_id in visited:
            return ''
        visited.add(node_id)
        token = _token(node_id)
        state = node.get('relation_state', '')
        source_text = {
            'explicit': '显式关联', 'inferred': '推断关联', 'user_confirmed': '用户确认',
            'user_rejected': '用户拒绝', 'user_pending': '待核实',
            'data_gap': '数据缺口', 'top_level': '顶层指标',
        }.get(state, state)
        line_class = ''
        edge_label = ''
        if incoming:
            if incoming.get('source') in ('explicit', 'user_confirmed'):
                line_class = 'it-branch-confirmed' if incoming.get('source') == 'user_confirmed' else 'it-branch-explicit'
            else:
                line_class = 'it-branch-inferred'
            edge_label = f'<div class="it-edge-label">{_edge_badge(incoming)}<span>关系质量 {incoming.get("relationship_score", 0):.0%}</span></div>'
        children = sorted(child_edges.get(node_id, []), key=lambda e: (_level_number(node_map[e['child_indicator_id']]['level']), node_map[e['child_indicator_id']]['name']))
        children_html = ''.join(node_card(node_map[e['child_indicator_id']], e, visited.copy()) for e in children)
        gap = f'<div class="it-gap-note">数据缺口：{html.escape(node.get("gap_reason", ""))}</div>' if state in ('data_gap', 'user_rejected', 'user_pending') else ''
        return f'''<div class="it-branch {line_class}" data-edge-source="{html.escape(incoming.get('source', '') if incoming else '')}">
            {edge_label}
            <button type="button" class="it-node it-level-{html.escape(node.get('level', 'Lx').lower())} it-state-{html.escape(state)}" data-node-id="{html.escape(node_id)}" data-detail-id="{token}" data-level="{html.escape(node.get('level', ''))}" onclick="showIndicatorDetail('{token}', this)">
                <span class="it-level-tag">{html.escape(node.get('level', ''))}</span>
                <span class="it-node-main"><strong>{html.escape(node.get('name', ''))}</strong><small>{html.escape(node.get('goal_title', ''))} · {html.escape(node.get('owner_name', ''))}</small></span>
                <span class="it-node-value">{html.escape(_display_value(node))}<small>{html.escape(source_text)}</small></span>
            </button>
            {gap}
            {f'<div class="it-children">{children_html}</div>' if children_html else ''}
        </div>'''

    departments = defaultdict(list)
    for root_id in tree.get('root_indicator_ids', []):
        root = node_map.get(root_id)
        if root:
            departments[root.get('department') or '未分组'].append(root)

    forest_parts = []
    for department, roots in sorted(departments.items()):
        roots_html = ''.join(node_card(root) for root in sorted(roots, key=lambda n: n['name']))
        forest_parts.append(f'''<details class="it-department" open>
            <summary>{html.escape(department)} <span>{len(roots)} 个顶层指标</span></summary>
            <div class="it-department-body">{roots_html}</div>
        </details>''')

    gap_nodes = [node_map[nid] for nid in tree.get('data_gap_indicator_ids', []) if nid in node_map]
    gap_html = ''.join(node_card(node) for node in sorted(gap_nodes, key=lambda n: (_level_number(n['level']), n['department'], n['name'])))
    if gap_html:
        forest_parts.append(f'''<details class="it-department it-gap-group">
            <summary>未连接指标（数据缺口） <span>{len(gap_nodes)} 个</span></summary>
            <div class="it-department-body">{gap_html}</div>
        </details>''')

    templates = []
    for node in nodes:
        upstream = []
        downstream = []
        for edge_id in node.get('upstream_edge_ids', []):
            edge = edge_map.get(edge_id)
            if edge:
                upstream.append(_relation_detail(edge, node_map[edge['parent_indicator_id']], 'up'))
        for edge_id in node.get('downstream_edge_ids', []):
            edge = edge_map.get(edge_id)
            if edge:
                downstream.append(_relation_detail(edge, node_map[edge['child_indicator_id']], 'down'))
        up_html = ''.join(upstream) or f'<div class="it-empty">{html.escape(node.get("gap_reason") or "无上级指标关系")}</div>'
        down_html = ''.join(downstream) or '<div class="it-empty">无下级指标承接</div>'
        token = _token(node['indicator_id'])
        templates.append(f'''<template id="it-detail-{token}">
            <div class="it-detail-header"><span class="it-level-tag">{html.escape(node.get('level', ''))}</span><h3>{html.escape(node.get('name', ''))}</h3></div>
            <div class="it-detail-meta">{html.escape(node.get('department', ''))} · {html.escape(node.get('owner_name', ''))} · {_display_value(node)}</div>
            <div class="it-detail-goal"><b>所属目标</b><br>{html.escape(node.get('goal_title', ''))}</div>
            <h4>向上关联诊断（{len(upstream)}）</h4>{up_html}
            <h4>向下承接诊断（{len(downstream)}）</h4>{down_html}
        </template>''')

    if not nodes:
        return '<div class="card" data-component="indicator-decomposition-tree"><div class="it-empty">未提供任何指标，无法构建指标拆解树。</div></div>'

    notice = summary.get('provenance_notice', '')
    quality_note = ''
    if summary.get('explicit_edges', 0) == 0:
        quality_note = '<div class="it-quality-warning"><b>数据质量提示：</b>当前输入没有指标级显式父子关系。树中虚线全部是“父目标范围约束 + 四层语义算法”生成的候选关系，不是企业已确认配置。</div>'
    node_options_json = json.dumps([
        {'indicator_id': n['indicator_id'], 'name': n['name'], 'goal_title': n.get('goal_title', ''), 'level': n.get('level', '')}
        for n in nodes
    ], ensure_ascii=False).replace('</', '<\\/')
    initial_decisions_json = json.dumps([
        item for item in tree.get('decision_results', []) if item.get('applied')
    ], ensure_ascii=False).replace('</', '<\\/')

    return f'''<div class="it-root" data-component="indicator-decomposition-tree">
<style>
.it-root{{font-size:13px;color:#1f2937}}.it-summary{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}}.it-stat{{flex:1 1 120px;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px}}.it-stat b{{display:block;font-size:22px}}.it-stat span{{color:#6b7280}}.it-legend,.it-quality-warning{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px;margin-bottom:12px;line-height:1.7}}.it-quality-warning{{background:#fffbeb;border-color:#f59e0b}}.it-layout{{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:14px;align-items:start}}.it-tree,.it-detail{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px;min-width:0}}.it-detail{{position:sticky;top:76px;max-height:720px;overflow:auto}}.it-department{{border:1px solid #e5e7eb;border-radius:10px;margin-bottom:12px;overflow:hidden}}.it-department>summary{{cursor:pointer;padding:12px 14px;background:#f8fafc;font-size:15px;font-weight:700}}.it-department>summary span{{font-size:12px;color:#6b7280;font-weight:400;margin-left:8px}}.it-department-body{{padding:12px}}.it-branch{{position:relative;margin:7px 0}}.it-children{{margin-left:28px;padding-left:16px;border-left:2px solid #cbd5e1}}.it-branch.it-branch-explicit{{border-left:3px solid #2563eb;padding-left:8px}}.it-branch.it-branch-confirmed{{border-left:3px solid #16a34a;padding-left:8px}}.it-branch.it-branch-inferred{{border-left:3px dashed #7c3aed;padding-left:8px}}.it-edge-label{{display:flex;gap:8px;align-items:center;margin:4px 0 4px 8px;font-size:11px;color:#6b7280}}.it-edge-badge{{display:inline-block;padding:2px 7px;border-radius:8px;font-size:10px;font-weight:700}}.it-explicit{{background:#dbeafe;color:#1d4ed8}}.it-inferred{{background:#ede9fe;color:#6d28d9}}.it-confirmed{{background:#dcfce7;color:#166534}}.it-node{{width:100%;min-height:58px;border:1px solid #dbe2ea;border-left:5px solid #94a3b8;border-radius:9px;background:#fff;padding:9px 10px;display:flex;align-items:center;gap:10px;text-align:left;cursor:pointer;color:#1f2937}}.it-node:hover,.it-node.it-selected{{background:#eff6ff;border-color:#60a5fa}}.it-level-l2{{border-left-color:#3b82f6}}.it-level-l3{{border-left-color:#8b5cf6}}.it-level-l4{{border-left-color:#64748b}}.it-state-data_gap{{border-style:dashed;border-color:#f59e0b}}.it-level-tag{{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:25px;padding:0 6px;border-radius:7px;background:#e2e8f0;font-weight:800;font-size:11px}}.it-node-main{{min-width:0;flex:1}}.it-node-main strong{{display:block;font-size:13px;line-height:1.4}}.it-node-main small,.it-node-value small{{display:block;color:#64748b;margin-top:3px;font-size:11px}}.it-node-value{{flex:0 0 120px;text-align:right;font-weight:700}}.it-gap-note{{margin:3px 0 4px 44px;padding:5px 8px;background:#fffbeb;color:#92400e;border-radius:6px;font-size:11px}}.it-detail-header{{display:flex;align-items:center;gap:8px}}.it-detail-header h3{{font-size:17px;margin:0}}.it-detail-meta{{color:#64748b;margin:8px 0}}.it-detail-goal{{background:#f8fafc;border-radius:8px;padding:10px;line-height:1.5}}.it-detail h4{{font-size:13px;margin:15px 0 7px}}.it-rel-card{{border-left:3px solid #8b5cf6;background:#f8fafc;padding:9px;border-radius:6px;margin-bottom:7px}}.it-rel-title{{font-weight:700}}.it-rel-meta,.it-rel-score,.it-rel-evidence{{font-size:11px;color:#64748b;margin-top:4px;line-height:1.45}}.it-rel-diagnosis{{font-size:12px;margin-top:5px;line-height:1.5}}.it-decision{{margin-top:10px;padding:10px;background:#fff;border:1px solid #ddd6fe;border-radius:8px}}.it-decision-title{{font-weight:700;margin-bottom:7px}}.it-decision-actions{{display:flex;gap:6px;flex-wrap:wrap}}.it-decision button,.it-export button{{min-height:44px;border:1px solid #cbd5e1;background:#fff;border-radius:7px;padding:7px 10px;cursor:pointer}}.it-decision button:hover,.it-decision button.it-active{{border-color:#2563eb;background:#eff6ff}}.it-decision label{{display:block;margin-top:8px;font-size:12px}}.it-decision select,.it-decision textarea{{width:100%;box-sizing:border-box;margin-top:5px;border:1px solid #cbd5e1;border-radius:7px;padding:8px;font:inherit}}.it-decision textarea{{min-height:58px;resize:vertical}}.it-decision-status{{margin-top:7px;color:#64748b;font-size:12px}}.it-export{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:12px;margin-bottom:12px}}.it-export span{{color:#166534}}.it-empty{{padding:10px;color:#64748b;background:#f8fafc;border-radius:7px}}.it-gap-group>summary{{background:#fffbeb;color:#92400e}}.it-detail-close{{display:none}}@media(max-width:900px){{.it-layout{{display:block}}.it-detail{{display:none;position:fixed;left:10px;right:10px;bottom:10px;top:auto;z-index:9999;max-height:72vh;overflow:auto;box-shadow:0 12px 40px rgba(15,23,42,.25);border:2px solid #60a5fa}}.it-detail.it-mobile-open{{display:block}}.it-detail-close{{display:block;position:sticky;top:0;float:right;z-index:2;min-width:44px;min-height:44px;border:1px solid #cbd5e1;background:#fff;border-radius:8px;cursor:pointer}}.it-node-value{{flex-basis:90px}}.it-children{{margin-left:12px;padding-left:9px}}}}
</style>
<div class="it-summary">
 <div class="it-stat"><b>{summary.get('total_nodes', 0)}</b><span>独立指标节点</span></div>
 <div class="it-stat"><b>{summary.get('explicit_edges', 0)}</b><span>显式关系（实线）</span></div>
 <div class="it-stat"><b>{summary.get('inferred_edges', 0)}</b><span>语义推断（虚线）</span></div>
 <div class="it-stat"><b>{summary.get('user_confirmed_edges', 0)}</b><span>用户确认关系</span></div>
 <div class="it-stat"><b>{summary.get('data_gap_count', 0)}</b><span>关系数据缺口</span></div>
</div>
<div class="it-legend"><b>关系图例：</b> <span class="it-edge-badge it-explicit">实线 · 显式</span> 输入中明确配置的指标父子关系； <span class="it-edge-badge it-inferred">虚线 · 推断</span> 父目标关系限定候选后由语义/因果/数值算法选出的候选边； <span class="it-edge-badge it-confirmed">实线 · 用户确认</span> 人工确认或改选的关系，独立于原始显式关系； <span class="it-edge-badge" style="background:#fef3c7;color:#92400e">虚框 · 缺口</span> 证据不足，未生成关系。<br><span style="color:#64748b">{html.escape(notice)}</span></div>
{quality_note}
<div class="it-export"><button type="button" onclick="exportIndicatorDecisions()">导出关系确认 JSON</button><button type="button" onclick="clearIndicatorDecisions()">清空本次确认</button><span id="it-decision-count">尚未记录本次人工确认</span></div>
<div class="it-layout"><div class="it-tree">{''.join(forest_parts)}</div><aside class="it-detail" id="it-detail-panel"><button type="button" class="it-detail-close" onclick="closeIndicatorDetail()" aria-label="关闭指标详情">关闭</button><div class="it-empty">点击任一指标节点，查看其向上关联、向下承接及关系诊断。</div></aside></div>
<div style="display:none">{''.join(templates)}</div>
<script>(function(){{try{{
var nodes={node_options_json},decisions={{}};
function updateCount(){{var el=document.getElementById('it-decision-count'),count=Object.keys(decisions).length;if(el)el.textContent=count?('已记录 '+count+' 条人工确认；导出后可用 --relation-decisions 回读'): '尚未记录本次人工确认';}}
function noteFor(edgeId){{var el=document.querySelector('[data-decision-note="'+edgeId+'"]');return el?el.value.trim():'';}}
function applyDecision(edgeId,childId,action,parentId,button){{decisions[childId]={{child_indicator_id:childId,parent_indicator_id:parentId||null,action:action,note:noteFor(edgeId),decision_source:'html_user_review',decided_at:new Date().toISOString()}};document.querySelectorAll('[data-decision-edge="'+edgeId+'"] button').forEach(function(b){{b.classList.remove('it-active')}});if(button)button.classList.add('it-active');var s=document.querySelector('[data-decision-status="'+edgeId+'"]');if(s)s.textContent={{confirm:'已确认保留',reject:'已拒绝，回读后转为数据缺口',pending:'已标记待核实',reassign:'已改选上级指标'}}[action]||action;try{{localStorage.setItem('performance-goal-diagnosis:indicator-decisions',JSON.stringify(decisions));}}catch(_e){{}}updateCount();}}
window.setIndicatorDecision=function(edgeId,childId,action,parentId,button){{applyDecision(edgeId,childId,action,parentId,button);}};
window.reassignIndicatorDecision=function(edgeId,childId,button){{var picker=document.querySelector('[data-parent-picker="'+edgeId+'"]');if(!picker||!picker.value){{var s=document.querySelector('[data-decision-status="'+edgeId+'"]');if(s)s.textContent='请先选择新的上级指标';return;}}applyDecision(edgeId,childId,'reassign',picker.value,button);}};
window.exportIndicatorDecisions=function(){{var payload={{version:'1.0',decisions:Object.keys(decisions).map(function(k){{return decisions[k];}})}};var blob=new Blob([JSON.stringify(payload,null,2)],{{type:'application/json;charset=utf-8'}}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='indicator-relation-decisions.json';document.body.appendChild(a);a.click();a.remove();setTimeout(function(){{URL.revokeObjectURL(a.href);}},1000);}};
window.clearIndicatorDecisions=function(){{decisions={{}};try{{localStorage.removeItem('performance-goal-diagnosis:indicator-decisions');}}catch(_e){{}}document.querySelectorAll('.it-decision-status').forEach(function(s){{s.textContent='尚未确认'}});document.querySelectorAll('.it-decision button').forEach(function(b){{b.classList.remove('it-active')}});updateCount();}};
window.closeIndicatorDetail=function(){{var panel=document.getElementById('it-detail-panel');if(panel)panel.classList.remove('it-mobile-open');}};
window.showIndicatorDetail=function(token,el,silent){{document.querySelectorAll('.it-node').forEach(function(n){{n.classList.remove('it-selected')}});if(el)el.classList.add('it-selected');var tpl=document.getElementById('it-detail-'+token),panel=document.getElementById('it-detail-panel');if(tpl&&panel){{panel.innerHTML='<button type="button" class="it-detail-close" onclick="closeIndicatorDetail()" aria-label="关闭指标详情">关闭</button>'+tpl.innerHTML;if(window.innerWidth<=900&&!silent)panel.classList.add('it-mobile-open');panel.querySelectorAll('[data-parent-picker]').forEach(function(select){{var childId=el?el.getAttribute('data-node-id'):'';nodes.forEach(function(n){{if(n.indicator_id!==childId){{var option=document.createElement('option');option.value=n.indicator_id;option.textContent=n.level+' · '+n.name+' · '+n.goal_title;select.appendChild(option);}}}});}});}}}};
try{{var saved=JSON.parse(localStorage.getItem('performance-goal-diagnosis:indicator-decisions')||'{{}}');if(saved&&typeof saved==='object')decisions=saved;}}catch(_e){{}}
var initial={initial_decisions_json};initial.forEach(function(item){{if(item.child_indicator_id&&item.action)decisions[item.child_indicator_id]=item;}});updateCount();var first=document.querySelector('.it-node');if(first)window.showIndicatorDetail(first.getAttribute('data-detail-id'),first,true);
}}catch(e){{console.error(e);var p=document.getElementById('it-detail-panel');if(p)p.innerHTML='<div class="it-empty">交互脚本加载失败，静态指标树仍可查看。</div>';}}}})();</script>
</div>'''
