#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绩效目标拆解诊断脚本
对目标拆解进行多维度诊断，识别问题并生成优化建议

七大诊断维度：
1. 上下层数据不匹配
2. 无具体执行人
3. 目标重复
4. 责任不清
5. 未向上对齐
6. 层次不准确
7. 指标偏离行业基准（需行业指标库）
"""

import json
import re
import os
import sys
from pathlib import Path
from collections import defaultdict

# 语义分析模块
try:
    from semantic_utils import get_semantic_analyzer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

# 行业指标匹配引擎（v2.2 新增）
try:
    from industry_matcher import (
        IndustryMetricLibrary,
        IndustryRecognizer,
        LayeredMetricMatcher,
        MetricTypeClassifier,
        MatchQualityEvaluator,
        create_matcher
    )
    INDUSTRY_MATCHER_AVAILABLE = True
except ImportError:
    INDUSTRY_MATCHER_AVAILABLE = False



class GoalDiagnoser:
    """目标拆解诊断器"""

    def __init__(self, industry_metrics_path=None, severity_threshold='low', use_semantic=True,
                 industry=None, auto_load_metrics=True):
        self.industry_metrics = {}  # 兼容旧版
        self.severity_threshold = severity_threshold
        self.goals = []
        self.users = []
        self.goal_map = {}
        self.user_goals = defaultdict(list)
        self.issues = []
        self.issue_counter = 0
        self.data_warnings = []

        # v2.2 新增：行业指标匹配引擎
        self.industry = industry  # 用户指定的行业
        self.metric_library = None
        self.industry_recognizer = None
        self.layered_matcher = None
        self.metric_type_classifier = MetricTypeClassifier() if INDUSTRY_MATCHER_AVAILABLE else None
        self.recognized_industry = None  # 自动识别出的行业
        self.industry_match_info = {}  # 行业匹配信息

        # 语义分析器
        self.semantic = None
        self.use_semantic = use_semantic and SEMANTIC_AVAILABLE
        if self.use_semantic:
            self.semantic = get_semantic_analyzer()

        # v2.2：默认自动加载内置指标库
        if INDUSTRY_MATCHER_AVAILABLE and auto_load_metrics:
            try:
                if industry_metrics_path:
                    self.metric_library = IndustryMetricLibrary(industry_metrics_path)
                else:
                    self.metric_library = IndustryMetricLibrary()  # 默认内置库
                self.industry_recognizer = IndustryRecognizer()
                self.layered_matcher = LayeredMetricMatcher(self.metric_library)
                print(f"  ✅ 行业指标库已加载：{self.metric_library.get_stats()['total_metrics']}个指标，{self.metric_library.get_stats()['industries']}个行业")
            except Exception as e:
                print(f"  ⚠️  行业指标库加载失败：{e}")
                self.metric_library = None
        elif industry_metrics_path:
            # 兼容旧版加载方式
            self._load_industry_metrics(industry_metrics_path)

    def _load_industry_metrics(self, metrics_path):
        """加载行业指标库"""
        metrics_path = Path(metrics_path)
        if not metrics_path.exists():
            return

        count = 0
        for md_file in metrics_path.rglob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 跳过 README 文件
                if md_file.name.lower() == 'readme.md':
                    continue

                # 从路径中提取行业名
                industry = md_file.parent.name

                # 解析指标定义（支持单指标和多指标两种格式）
                metrics = self._parse_metric_md(content, industry)
                for metric in metrics:
                    if metric.get('name'):
                        self.industry_metrics[metric['name']] = metric
                        count += 1
            except Exception:
                pass

        # 也支持 JSON 格式
        for json_file in metrics_path.rglob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for metric in data:
                        if metric.get('name'):
                            self.industry_metrics[metric['name']] = metric
                            count += 1
                elif isinstance(data, dict) and data.get('name'):
                    self.industry_metrics[data['name']] = data
                    count += 1
            except Exception:
                pass

        print(f"  ✅ 加载了 {count} 个行业指标")

    def _parse_metric_md(self, content, industry=''):
        """解析 Markdown 格式的指标定义
        支持两种格式：
        1. 单指标格式：一个文件一个指标（旧格式）
        2. 多指标格式：一个文件多个指标（三层指标体系格式）
        返回指标列表
        """
        metrics = []

        # 先尝试解析多指标格式（三层指标体系）
        # 匹配 "### 数字. 指标名" 格式的指标详解部分
        pattern = r'###\s+\d+\.\s+(.+?)\n\n(.*?)(?=\n###\s+\d+\.|\n---|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            # 多指标格式
            for name, detail in matches:
                metric = {
                    'name': name.strip(),
                    'industry': industry
                }

                # 提取基准值（支持加粗格式 **基准值**：）
                benchmark_match = re.search(r'\*?\*?基准值\*?\*?[：:]\s*([^\n]+)', detail)
                if benchmark_match:
                    benchmark_str = benchmark_match.group(1).strip()
                    # 尝试提取数值
                    num_match = re.search(r'([\d.]+)', benchmark_str)
                    if num_match:
                        metric['benchmark'] = float(num_match.group(1))
                    metric['benchmark_display'] = benchmark_str

                # 提取合理范围（支持加粗格式）
                range_match = re.search(r'\*?\*?合理范围\*?\*?[：:]\s*([^\n]+)', detail)
                if range_match:
                    range_str = range_match.group(1).strip()
                    metric['range_display'] = range_str
                    # 尝试提取数值范围
                    num_range_match = re.search(r'([\d.]+)\s*[-~至]\s*([\d.]+)', range_str)
                    if num_range_match:
                        metric['min'] = float(num_range_match.group(1))
                        metric['max'] = float(num_range_match.group(2))

                # 提取说明（支持加粗格式）
                desc_match = re.search(r'\*?\*?说明\*?\*?[：:]\s*([^\n]+)', detail)
                if desc_match:
                    metric['description'] = desc_match.group(1).strip()

                # 提取数据来源（仅战略层，支持加粗格式）
                source_match = re.search(r'\*?\*?数据来源\*?\*?[：:]\s*([^\n]+)', detail)
                if source_match:
                    metric['source'] = source_match.group(1).strip()

                # 提取对应上层指标（仅管理层/执行层，支持加粗格式）
                parent_match = re.search(r'\*?\*?对应上层指标\*?\*?[：:]\s*([^\n]+)', detail)
                if parent_match:
                    metric['parent'] = parent_match.group(1).strip()

                if metric.get('name'):
                    metrics.append(metric)
        else:
            # 单指标格式（旧格式兼容）
            metric = {'industry': industry}

            # 提取标题作为指标名
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                metric['name'] = title_match.group(1).strip()

            # 提取基准值
            benchmark_match = re.search(r'基准值[：:]\s*([\d.]+)', content)
            if benchmark_match:
                metric['benchmark'] = float(benchmark_match.group(1))

            # 提取单位
            unit_match = re.search(r'单位[：:]\s*(\S+)', content)
            if unit_match:
                metric['unit'] = unit_match.group(1)

            # 提取行业（如果文件中有定义）
            industry_match = re.search(r'行业[：:]\s*(\S+)', content)
            if industry_match:
                metric['industry'] = industry_match.group(1)

            # 提取合理范围
            range_match = re.search(r'合理范围[：:]\s*([\d.]+)\s*[-~至]\s*([\d.]+)', content)
            if range_match:
                metric['min'] = float(range_match.group(1))
                metric['max'] = float(range_match.group(2))

            if metric.get('name'):
                metrics.append(metric)

        return metrics

    def _text_similarity(self, text1, text2):
        """计算文本相似度（Jaccard 字符级）"""
        if not text1 or not text2:
            return 0.0

        set1 = set(text1)
        set2 = set(text2)

        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _find_metric_by_name(self, name):
        """根据名称查找最匹配的行业指标"""
        if not self.industry_metrics:
            return None

        best_match = None
        best_score = 0.0

        for metric_name, metric in self.industry_metrics.items():
            score = self._text_similarity(name, metric_name)
            if score > best_score and score >= 0.5:  # 相似度阈值
                best_score = score
                best_match = metric

        return best_match

    def _add_issue(self, dimension, severity, title, description, evidence,
                   goal_id=None, goal_title=None, owner_id=None, suggestion=None):
        """添加一个问题"""
        self.issue_counter += 1
        issue = {
            'issue_id': f'ISSUE-{self.issue_counter:04d}',
            'dimension': dimension,
            'severity': severity,
            'title': title,
            'description': description,
            'evidence': evidence,
            'goal_id': goal_id,
            'goal_title': goal_title,
            'owner_id': owner_id,
            'suggestion': suggestion
        }
        self.issues.append(issue)

    
    def _check_data_quality(self):
        """检查数据质量，生成警告信息"""
        # 检查1：目标数量
        if len(self.goals) == 0:
            self.data_warnings.append({
                'level': 'high',
                'type': '数据严重不足',
                'message': '没有找到任何目标数据',
                'suggestion': '请检查数据来源是否正确，或手动提供目标数据'
            })
            return
        
        # 检查2：人员数据
        if len(self.users) == 0:
            self.data_warnings.append({
                'level': 'medium',
                'type': '人员数据缺失',
                'message': '没有人员信息，部分诊断维度（如责任不清）可能不准确',
                'suggestion': '建议补充人员列表和汇报关系'
            })
        
        # 检查3：有指标的目标比例
        goals_with_indicators = sum(1 for g in self.goals if g.get('indicators'))
        indicator_ratio = goals_with_indicators / len(self.goals) if self.goals else 0
        
        if indicator_ratio < 0.3:
            self.data_warnings.append({
                'level': 'medium',
                'type': '指标数据不足',
                'message': f'只有 {goals_with_indicators}/{len(self.goals)} 个目标有明确的指标数据（{indicator_ratio*100:.0f}%）',
                'suggestion': '建议为目标补充量化指标，以便进行更精准的诊断'
            })
        
        # 检查4：有父目标关系的比例
        goals_with_parent = sum(1 for g in self.goals if g.get('parent_goal_ids'))
        parent_ratio = goals_with_parent / len(self.goals) if self.goals else 0
        
        if parent_ratio < 0.3:
            self.data_warnings.append({
                'level': 'low',
                'type': '层级关系不完整',
                'message': f'只有 {goals_with_parent}/{len(self.goals)} 个目标有明确的父目标关系（{parent_ratio*100:.0f}%）',
                'suggestion': '建议补充目标的上下级对齐关系，以便进行拆解合理性诊断'
            })
        
        # 检查5：层级分布
        levels = defaultdict(int)
        for g in self.goals:
            level = g.get('level', '未知')
            levels[level] += 1
        
        if len(levels) < 2:
            self.data_warnings.append({
                'level': 'low',
                'type': '层级单一',
                'message': '目标只有一个层级，无法进行上下层拆解诊断',
                'suggestion': '建议提供至少两个层级的目标数据'
            })

    def run_all_diagnoses(self, data):
        """运行所有诊断"""
        self.goals = data.get('goals', [])
        self.users = data.get('users', [])
        self.issues = []
        self.issue_counter = 0
        self.data_warnings = []
        self.user_goals = defaultdict(list)

        # 建立索引
        self.goal_map = {g['goal_id']: g for g in self.goals}
        for goal in self.goals:
            owner_id = goal.get('owner_id')
            if owner_id:
                self.user_goals[owner_id].append(goal)
        
        # 数据质量检查
        self._check_data_quality()

        # v2.2：预识别行业（用于报告展示）
        if self.layered_matcher and self.industry_recognizer and not self.industry:
            department = ''
            if self.users:
                department = self.users[0].get('department', '')
            recognized = self.industry_recognizer.recognize(
                department=department,
                goals=self.goals
            )
            if recognized:
                self.recognized_industry = recognized[0][0]
                self.industry_match_info = {
                    'recognized': recognized,
                    'used': recognized[0][0],
                    'confidence': recognized[0][1]
                }

        print("🔍 开始多维度诊断...")
        if self.data_warnings:
            print(f"  ⚠️  数据质量警告：{len(self.data_warnings)} 项")
        print()

        # 八大维度诊断
        diagnoses = [
            ('上下层数据不匹配', self.diagnose_mismatch),
            ('无具体执行人', self.diagnose_no_owner),
            ('目标重复', self.diagnose_duplicate),
            ('责任不清', self.diagnose_unclear_responsibility),
            ('未向上对齐', self.diagnose_not_aligned),
            ('层次不准确', self.diagnose_wrong_level),
            ('指标偏离行业基准', self.diagnose_industry_benchmark),
            ('指标关联性与承接', self.diagnose_indicator_relationship),
        ]

        for i, (name, func) in enumerate(diagnoses, 1):
            print(f"  [{i}/8] {name}... ", end='', flush=True)
            before = len(self.issues)
            func()
            after = len(self.issues)
            print(f"发现 {after - before} 个问题")
        
        # 额外的结构诊断（属于指标关联性与承接维度）
        extra_diagnoses = [
            ('拆解深度与结构', self.diagnose_deep_structure),
            ('横向目标对齐', self.diagnose_horizontal_alignment),
        ]
        
        for name, func in extra_diagnoses:
            print(f"  [+] {name}... ", end='', flush=True)
            before = len(self.issues)
            func()
            after = len(self.issues)
            print(f"发现 {after - before} 个问题")

        print()

        # 生成优化建议
        suggestions = self.generate_suggestions()

        # 计算健康度
        health_score, health_level = self._calculate_health_score()

        # 按维度统计
        by_dimension = defaultdict(int)
        for issue in self.issues:
            by_dimension[issue['dimension']] += 1

        # 按严重度统计
        high_count = sum(1 for i in self.issues if i['severity'] == 'high')
        medium_count = sum(1 for i in self.issues if i['severity'] == 'medium')
        low_count = sum(1 for i in self.issues if i['severity'] == 'low')

        # v2.6：指标作为独立实体建树。显式边与语义推断边严格分开，证据不足只记录数据缺口。
        try:
            from indicator_tree import build_indicator_tree
            indicator_tree = build_indicator_tree(data, analyzer=self.semantic)
        except Exception as e:
            indicator_tree = {
                'version': '2.6',
                'summary': {
                    'total_nodes': sum(len(g.get('indicators', []) or []) for g in self.goals),
                    'total_edges': 0,
                    'explicit_edges': 0,
                    'inferred_edges': 0,
                    'data_gap_count': 0,
                    'build_error': str(e),
                    'provenance_notice': '指标树构建失败；未伪造任何关系。',
                },
                'nodes': [], 'edges': [], 'root_indicator_ids': [],
                'data_gap_indicator_ids': [], 'data_gaps': [], 'dangling_references': [],
            }

        result = {
            'summary': {
                'total_goals': len(self.goals),
                'total_users': len(self.users),
                'total_issues': len(self.issues),
                'high_count': high_count,
                'medium_count': medium_count,
                'low_count': low_count,
                'health_score': health_score,
                'health_level': health_level,
                'by_dimension': dict(by_dimension),
                'data_warnings': self.data_warnings,
                'data_quality': 'good' if len(self.data_warnings) == 0 else ('medium' if len([w for w in self.data_warnings if w['level'] == 'high']) == 0 else 'poor'),
                'disclaimer': '本诊断基于现有数据自动生成，数据不完整时结论仅供参考，建议结合业务实际情况人工复核',
                # v2.2 新增：行业匹配信息
                'industry_info': {
                    'specified_industry': self.industry,
                    'recognized_industry': self.recognized_industry,
                    'match_info': self.industry_match_info,
                    'library_loaded': self.metric_library is not None,
                    'library_stats': self.metric_library.get_stats() if self.metric_library else None
                }
            },
            'issues': self.issues,
            'suggestions': suggestions,
            'goal_tree': self._build_goal_tree(),
            'indicator_tree': indicator_tree,
            'user_summary': self._build_user_summary()
        }

        return result

    def diagnose_mismatch(self):
        """诊断：上下层数据不匹配"""
        # 检查有数值指标的目标，看上下层是否匹配
        for goal in self.goals:
            indicators = goal.get('indicators', [])
            if not indicators:
                continue

            # 找到子目标
            child_goals = [g for g in self.goals if goal['goal_id'] in g.get('parent_goal_ids', [])]
            if not child_goals:
                continue

            for indicator in indicators:
                parent_value = indicator.get('value')
                if parent_value is None:
                    continue

                # 计算子目标的指标总和
                child_sum = 0
                has_child_indicator = False
                for child in child_goals:
                    child_indicators = child.get('indicators', [])
                    for ci in child_indicators:
                        # 简单匹配：名称相似
                        if self._text_similarity(indicator.get('name', ''), ci.get('name', '')) > 0.5:
                            child_sum += ci.get('value', 0)
                            has_child_indicator = True
                            break

                if has_child_indicator and child_sum > 0:
                    # 检查偏差是否超过 20%
                    diff_ratio = abs(child_sum - parent_value) / parent_value if parent_value > 0 else 0
                    if diff_ratio > 0.2:
                        severity = 'high' if diff_ratio > 0.5 else 'medium'
                        self._add_issue(
                            dimension='上下层数据不匹配',
                            severity=severity,
                            title=f"指标不匹配：{indicator.get('name', '')}",
                            description=f"上级目标值 {parent_value}，下级目标加总 {child_sum}，偏差 {diff_ratio*100:.1f}%",
                            evidence=f"偏差超过 {'50%' if severity == 'high' else '20%'} 的合理范围",
                            goal_id=goal['goal_id'],
                            goal_title=goal.get('title'),
                            suggestion="请核对上下层指标定义，确认是口径不同还是数据有误"
                        )

    def diagnose_no_owner(self):
        """诊断：无具体执行人"""
        for goal in self.goals:
            owner_id = goal.get('owner_id')
            owner_name = goal.get('owner_name')

            if not owner_id or not owner_name:
                self._add_issue(
                    dimension='无具体执行人',
                    severity='high',
                    title='目标缺少负责人',
                    description='该目标没有明确的负责人',
                    evidence='owner_id 或 owner_name 为空',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion='请明确该目标的具体负责人'
                )
            elif owner_name in ['团队', '部门', '大家', '全体']:
                self._add_issue(
                    dimension='无具体执行人',
                    severity='medium',
                    title='负责人不明确',
                    description=f'负责人是 "{owner_name}"，不是具体的人',
                    evidence='负责人为集体名词，责任容易分散',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion='建议明确到具体的责任人'
                )

    def diagnose_duplicate(self):
        """诊断：目标重复"""
        # 同一层级的目标两两比较相似度
        level_goals = defaultdict(list)
        for goal in self.goals:
            level = goal.get('level', 'L?')
            level_goals[level].append(goal)

        for level, goals in level_goals.items():
            for i in range(len(goals)):
                for j in range(i + 1, len(goals)):
                    g1 = goals[i]
                    g2 = goals[j]

                    # 计算标题相似度
                    sim = self._text_similarity(g1.get('title', ''), g2.get('title', ''))

                    if sim >= 0.7:
                        severity = 'high' if sim >= 0.85 else 'medium'
                        self._add_issue(
                            dimension='目标重复',
                            severity=severity,
                            title=f'目标高度相似（相似度 {sim*100:.0f}%）',
                            description=f'"{g1.get("title")}" 与 "{g2.get("title")}" 内容高度相似',
                            evidence=f'文本相似度 {sim*100:.0f}%，可能存在重复',
                            goal_id=g1['goal_id'],
                            goal_title=g1.get('title'),
                            suggestion='建议合并重复目标，或明确两者的区别和分工'
                        )

    def diagnose_unclear_responsibility(self):
        """诊断：责任不清"""
        # 检查上级目标的子目标覆盖情况
        for goal in self.goals:
            # 只检查有子目标的上级目标
            child_goals = [g for g in self.goals if goal['goal_id'] in g.get('parent_goal_ids', [])]
            if not child_goals:
                continue

            # 检查 KR 数量和子目标数量的关系
            kr_count = len(goal.get('key_results', []))
            child_count = len(child_goals)

            if kr_count > 0 and child_count == 0:
                # 有 KR 但没有子目标，可能是责任真空
                self._add_issue(
                    dimension='责任不清',
                    severity='high',
                    title='责任真空',
                    description='目标涉及多个方面，但子目标覆盖不全（责任真空）',
                    evidence=f'上级目标有 {kr_count} 个 KR，但仅有 {child_count} 个子目标，可能存在责任真空',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion='请确认这些 KR 是否都有对应的人负责，是否需要补充子目标'
                )
            elif kr_count > 3 and child_count < kr_count / 2:
                # KR 多但子目标少，可能覆盖不全
                self._add_issue(
                    dimension='责任不清',
                    severity='medium',
                    title='子目标覆盖不全',
                    description='上级目标涉及多个方面，子目标可能覆盖不全',
                    evidence=f'上级目标有 {kr_count} 个 KR，但仅有 {child_count} 个子目标，覆盖比例较低',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion='建议检查是否所有重要方面都有对应的子目标和负责人'
                )

        # 检查多人交叉负责的情况
        goal_owners = defaultdict(set)
        for goal in self.goals:
            owner = goal.get('owner_id')
            if owner:
                goal_owners[goal['goal_id']].add(owner)

        # 这里简化处理，实际可以更复杂

    def diagnose_not_aligned(self):
        """诊断：未向上对齐"""
        for goal in self.goals:
            # 顶层目标不需要对齐
            level = goal.get('level', '')
            if level == 'L1':
                continue

            parent_ids = goal.get('parent_goal_ids', [])
            aligned_ids = goal.get('aligned_to_goal_ids', [])

            if not parent_ids and not aligned_ids:
                # 没有对齐到任何上级目标
                owner_id = goal.get('owner_id')
                owner = self._get_user_by_id(owner_id)
                has_manager = owner and owner.get('manager_id')

                if has_manager:
                    severity = 'high' if level in ['L2', 'L3'] else 'medium'
                    self._add_issue(
                        dimension='未向上对齐',
                        severity=severity,
                        title='目标未向上对齐',
                        description='该目标未对齐到任何上级目标',
                        evidence='该目标有上级，但未对齐到上级的任何目标，可能存在方向不一致的风险',
                        goal_id=goal['goal_id'],
                        goal_title=goal.get('title'),
                        suggestion='请确认该目标是否对齐到上级目标，或补充对齐关系'
                    )

    def diagnose_wrong_level(self):
        """诊断：层次不准确"""
        # 简单的启发式：根据目标的粒度判断层级是否合适
        for goal in self.goals:
            level = goal.get('level', '')
            title = goal.get('title', '')
            kr_count = len(goal.get('key_results', []))
            child_count = len([g for g in self.goals if goal['goal_id'] in g.get('parent_goal_ids', [])])

            # L1 目标应该比较宏观，KR 不能太多
            if level == 'L1' and kr_count > 6:
                self._add_issue(
                    dimension='层次不准确',
                    severity='medium',
                    title='L1 目标粒度过细',
                    description=f'L1 目标有 {kr_count} 个 KR，可能粒度过细，应该下移',
                    evidence='L1 目标通常应该是方向型的，KR 数量不宜过多',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion='建议考虑将部分 KR 下移为 L2 目标'
                )

            # L3 目标应该比较具体，KR 不能太少
            if level == 'L3' and kr_count < 2:
                self._add_issue(
                    dimension='层次不准确',
                    severity='low',
                    title='L3 目标粒度过粗',
                    description=f'L3 目标只有 {kr_count} 个 KR，可能粒度过粗，应该更具体',
                    evidence='L3 目标通常应该是执行型的，KR 数量应该更具体',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion='建议将目标拆解得更具体，增加可衡量的 KR'
                )

    def diagnose_industry_benchmark(self):
        """诊断：指标偏离行业基准（v2.2 增强版）

        改进点：
        1. 使用分层匹配器（行业→层级→语义）
        2. 区分正向/反向/区间指标
        3. 使用合理范围而非单点基准
        4. 展示匹配质量和元数据
        """
        # v2.2：使用新的匹配引擎
        if self.layered_matcher:
            self._diagnose_industry_benchmark_v2()
            return

        # 兼容旧版逻辑
        if not self.industry_metrics:
            return

        for goal in self.goals:
            indicators = goal.get('indicators', [])
            for indicator in indicators:
                name = indicator.get('name', '')
                value = indicator.get('value')

                if not name or value is None:
                    continue

                metric = self._find_metric_by_name(name)
                if not metric:
                    continue

                benchmark = metric.get('benchmark')
                if benchmark is None or benchmark == 0:
                    continue

                deviation = (value - benchmark) / benchmark

                if abs(deviation) > 0.5:
                    severity = 'high'
                    level = '严重偏离'
                elif abs(deviation) > 0.2:
                    severity = 'medium'
                    level = '明显偏离'
                elif abs(deviation) > 0.1:
                    severity = 'low'
                    level = '略有偏离'
                else:
                    continue

                direction = '高于' if deviation > 0 else '低于'
                self._add_issue(
                    dimension='指标偏离行业基准',
                    severity=severity,
                    title=f'指标{level}行业基准',
                    description=f'{name} {direction}行业基准 {abs(deviation)*100:.1f}%',
                    evidence=f'当前值：{value} {metric.get("unit", "")}，行业基准：{benchmark} {metric.get("unit", "")}',
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion=f'请确认 {name} 的目标值是否合理，是否需要根据行业基准调整'
                )

    def _diagnose_industry_benchmark_v2(self):
        """v2.2 增强版行业基准诊断"""
        if not self.layered_matcher:
            return

        # 自动识别行业（如果用户没有指定）
        target_industry = self.industry
        if target_industry and not self.recognized_industry:
            self.recognized_industry = target_industry
            self.industry_match_info = {
                'recognized': target_industry,
                'used': target_industry,
                'confidence': target_industry
            }
        if not target_industry and self.industry_recognizer:
            # 从部门和目标内容识别
            department = ''
            if self.users:
                department = self.users[0].get('department', '')
            recognized = self.industry_recognizer.recognize(
                department=department,
                goals=self.goals
            )
            if recognized:
                target_industry = recognized[0][0]
                self.recognized_industry = target_industry
                self.industry_match_info = {
                    'recognized': recognized,
                    'used': target_industry,
                    'confidence': recognized[0][1]
                }

        # 遍历所有指标进行诊断
        for goal in self.goals:
            indicators = goal.get('indicators', [])
            goal_level = goal.get('level', 'L2')

            for indicator in indicators:
                name = indicator.get('name', '')
                value = indicator.get('value')

                if not name or value is None:
                    continue

                # 分层匹配
                matches = self.layered_matcher.match(
                    indicator_name=name,
                    goal_level=goal_level,
                    industry=target_industry,
                    top_k=1
                )

                if not matches:
                    continue

                match_result = matches[0]
                metric = match_result['metric']
                benchmark = metric.get('benchmark')
                metric_type = match_result['metric_type']
                quality = match_result['quality']

                if benchmark is None:
                    continue

                # 智能偏离判断
                deviation_result = self.metric_type_classifier.judge_deviation(
                    current=value,
                    benchmark=benchmark,
                    metric_type=metric_type,
                    min_val=metric.get('min'),
                    max_val=metric.get('max')
                )

                if not deviation_result['is_deviation']:
                    continue

                severity = deviation_result['severity']
                description = deviation_result['description']

                # 构建证据（包含元数据）
                evidence_parts = [
                    f'当前值：{value} {metric.get("unit", "")}',
                    f'行业基准：{metric.get("benchmark_display", benchmark)} {metric.get("unit", "")}'
                ]
                if metric.get('min') and metric.get('max'):
                    evidence_parts.append(f'合理范围：{metric["min"]}~{metric["max"]}')
                if metric.get('data_source'):
                    evidence_parts.append(f'数据来源：{metric["data_source"]}')
                if metric.get('data_date'):
                    evidence_parts.append(f'数据截止：{metric["data_date"]}')
                if metric.get('verification_status'):
                    evidence_parts.append(f'验证状态：{metric["verification_status"]}')

                evidence = '；'.join(evidence_parts)

                # 构建建议（根据指标类型）
                if metric_type == 'positive':
                    suggestion = f'{name} 是正向指标（越高越好），当前低于行业基准，建议分析原因并制定提升计划'
                elif metric_type == 'negative':
                    suggestion = f'{name} 是反向指标（越低越好），当前高于行业基准，建议重点关注并优化'
                elif metric_type == 'range':
                    suggestion = f'{name} 是区间指标，当前超出合理范围，建议调整至最佳区间'
                else:
                    suggestion = f'请确认 {name} 的目标值是否合理，是否需要根据行业基准调整'

                # 添加匹配质量信息到描述
                quality_info = f' [匹配度{match_result["similarity"]*100:.0f}%，{quality["confidence"]}]'

                self._add_issue(
                    dimension='指标偏离行业基准',
                    severity=severity,
                    title=f'指标偏离行业基准（{metric_type}）',
                    description=description + quality_info,
                    evidence=evidence,
                    goal_id=goal['goal_id'],
                    goal_title=goal.get('title'),
                    suggestion=suggestion
                )


    def diagnose_indicator_relationship(self):
        """诊断：指标关联性与承接关系（v2.0 增强版）
        基于语义判断上下级指标之间的关联性和承接关系是否合理
        包含 13 种检测模式
        """
        # 构建目标父子关系
        goal_children = defaultdict(list)
        for goal in self.goals:
            parent_ids = goal.get('parent_goal_ids', [])
            for pid in parent_ids:
                if pid in self.goal_map:
                    goal_children[pid].append(goal)
        
        # 收集所有指标文本（用于 TF-IDF）
        all_metric_texts = []
        for goal in self.goals:
            for ind in goal.get('indicators', []):
                all_metric_texts.append(ind.get('name', ''))
        
        # 对每个有子目标的目标，检查指标承接关系
        for goal in self.goals:
            children = goal_children.get(goal['goal_id'], [])
            if not children:
                continue
            
            parent_indicators = goal.get('indicators', [])
            if not parent_indicators:
                continue
            
            for parent_ind in parent_indicators:
                parent_name = parent_ind.get('name', '')
                if not parent_name:
                    continue
                
                # 收集所有子目标的指标
                child_indicators = []
                for child in children:
                    child_inds = child.get('indicators', [])
                    for ci in child_inds:
                        child_indicators.append({
                            'indicator': ci,
                            'child_goal': child
                        })
                
                if not child_indicators:
                    continue
                
                # 使用语义分析器计算相似度（如果可用）
                if self.semantic:
                    self._diagnose_with_semantic(parent_name, child_indicators, goal)
                else:
                    # 回退到简单关键词匹配
                    self._diagnose_simple_keyword(parent_name, child_indicators, goal)
                
                # 通用检查：子指标数量合理性
                self._check_child_count(parent_name, child_indicators, goal)
                
                # 检查5：因果方向检测
                if self.semantic:
                    self._check_causal_direction(parent_name, child_indicators, goal)
                
                # 检查6：粒度一致性检测
                if self.semantic:
                    self._check_granularity_consistency(parent_name, child_indicators, goal)
                
                # 检查7：维度完整性检测
                if self.semantic:
                    self._check_dimension_completeness(parent_name, child_indicators, goal)
                
                # 检查8：逻辑闭环检测
                if self.semantic:
                    self._check_logical_closure(parent_name, child_indicators, goal)
                
                # 检查9：指标命名质量检测
                if self.semantic:
                    self._check_naming_quality(parent_name, child_indicators, goal)
                
                # 检查10：子指标重叠检测（增强版）
                if self.semantic:
                    self._check_child_overlap(parent_name, child_indicators, goal)
                
                # 检查11：数学关系检测
                if self.semantic:
                    self._check_math_relationship(parent_name, child_indicators, goal)
    
    def _check_child_overlap(self, parent_name, child_indicators, goal):
        """检查10：子指标之间的重叠/重复（增强版）"""
        if len(child_indicators) < 2:
            return
        
        overlap_pairs = []
        
        for i in range(len(child_indicators)):
            for j in range(i + 1, len(child_indicators)):
                name1 = child_indicators[i]['indicator'].get('name', '')
                name2 = child_indicators[j]['indicator'].get('name', '')
                
                if not name1 or not name2:
                    continue
                
                # 语义相似度
                sim = self.semantic.multi_dim_similarity(name1, name2)
                
                if sim > 0.7:
                    overlap_pairs.append((name1, name2, sim))
        
        if overlap_pairs:
            severity = 'medium' if len(overlap_pairs) >= 2 else 'low'
            
            examples = []
            for n1, n2, sim in overlap_pairs[:3]:
                examples.append(f"「{n1}」与「{n2}」（相似度 {sim*100:.0f}%）")
            
            self._add_issue(
                dimension='指标关联性与承接',
                severity=severity,
                title='子指标存在重叠',
                description=f"父指标「{parent_name}」的子指标中有 {len(overlap_pairs)} 对存在语义重叠，可能是重复或分类不清",
                evidence=f"重叠的指标对：{'; '.join(examples)}",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="合并重叠的指标，或者重新分组归类，确保每个指标都有清晰独特的定位"
            )
    
    def _check_math_relationship(self, parent_name, child_indicators, goal):
        """检查11：数学关系检测"""
        if len(child_indicators) < 2:
            return
        
        # 检测是否有加总关系的特征
        sum_keywords = ['总计', '合计', '总数', '总和', '整体', '全部']
        has_sum_indicator = any(kw in parent_name for kw in sum_keywords)
        
        # 检测子指标是否有分类特征（如：A类、B类、C类；线上、线下；新客、老客等）
        child_names = [ci['indicator'].get('name', '') for ci in child_indicators]
        
        # 简单的分类检测：寻找共同的后缀或前缀
        has_classification = False
        if len(child_names) >= 2:
            # 检查是否有共同后缀
            common_suffix = True
            suffix = child_names[0][-2:] if len(child_names[0]) >= 2 else ''
            for name in child_names[1:]:
                if not name.endswith(suffix):
                    common_suffix = False
                    break
            if common_suffix and suffix:
                has_classification = True
            
            # 检查是否有数字分类（1、2、3...）
            has_number_class = any(any(c.isdigit() for c in name) for name in child_names)
            if has_number_class:
                has_classification = True
        
        if has_sum_indicator and has_classification:
            # 可能存在加总关系，但没有明确的数值验证
            self._add_issue(
                dimension='指标关联性与承接',
                severity='low',
                title='建议验证数学关系',
                description=f"父指标「{parent_name}」与子指标之间可能存在加总关系，建议验证数值是否匹配",
                evidence=f"父指标包含总计/合计特征，子指标有分类特征\n建议：验证 父指标值 = 各子指标值之和",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="验证上下级指标的数学关系是否成立，确保数值加总正确"
            )
    
    def diagnose_deep_structure(self):
        """诊断：整体拆解深度和结构合理性（方案二新增）"""
        if not self.goals:
            return
        
        # 构建目标树
        goal_children = defaultdict(list)
        goal_parents = defaultdict(list)
        for goal in self.goals:
            parent_ids = goal.get('parent_goal_ids', [])
            for pid in parent_ids:
                if pid in self.goal_map:
                    goal_children[pid].append(goal)
                    goal_parents[goal['goal_id']].append(pid)
        
        # 计算每个目标的深度
        depths = {}
        
        def calc_depth(goal_id, visited=None):
            if visited is None:
                visited = set()
            if goal_id in visited:
                return 0
            visited.add(goal_id)
            
            if goal_id in depths:
                return depths[goal_id]
            
            parents = goal_parents.get(goal_id, [])
            if not parents:
                depths[goal_id] = 1
                return 1
            
            max_parent_depth = max(calc_depth(pid, visited.copy()) for pid in parents)
            depths[goal_id] = max_parent_depth + 1
            return depths[goal_id]
        
        for goal in self.goals:
            calc_depth(goal['goal_id'])
        
        # 统计各层级的目标数量
        level_counts = defaultdict(int)
        for goal_id, depth in depths.items():
            level_counts[depth] += 1
        
        max_depth = max(depths.values()) if depths else 0
        min_depth = min(depths.values()) if depths else 0
        
        # 检查12：拆解深度是否合理
        if max_depth < 2 and len(self.goals) > 3:
            self._add_issue(
                dimension='指标关联性与承接',
                severity='medium',
                title='拆解深度不足',
                description=f"目标拆解只有 {max_depth} 层，对于 {len(self.goals)} 个目标来说深度可能不足",
                evidence=f"各层级目标数：{dict(level_counts)}",
                suggestion="建议增加拆解层级，将目标进一步分解为更具体的子目标和指标"
            )
        elif max_depth > 5:
            self._add_issue(
                dimension='指标关联性与承接',
                severity='low',
                title='拆解层级过深',
                description=f"目标拆解有 {max_depth} 层，层级过多可能导致管理复杂",
                evidence=f"各层级目标数：{dict(level_counts)}",
                suggestion="建议合并一些中间层级，保持3-4层的合理拆解深度"
            )
        
        # 检查13：各层级目标数量分布是否合理（一头沉）
        if level_counts:
            max_level_count = max(level_counts.values())
            total_goals = sum(level_counts.values())
            max_ratio = max_level_count / total_goals if total_goals > 0 else 0
            
            if max_ratio > 0.7 and len(level_counts) >= 3:
                max_level = max(level_counts.items(), key=lambda x: x[1])[0]
                self._add_issue(
                    dimension='指标关联性与承接',
                    severity='low',
                    title='目标分布不均衡（一头沉）',
                    description=f"第 {max_level} 层集中了 {max_level_count} 个目标（占比 {max_ratio*100:.0f}%），分布不均衡",
                    evidence=f"各层级目标数：{dict(level_counts)}",
                    suggestion="考虑重新调整拆解结构，让各层级的目标数量更均衡"
                )
    
    def diagnose_horizontal_alignment(self):
        """诊断：横向目标对齐（方案二新增）"""
        if not self.goals or not self.semantic:
            return
        
        # 按层级分组
        level_goals = defaultdict(list)
        for goal in self.goals:
            level = goal.get('level', 1)
            level_goals[level].append(goal)
        
        for level, goals in level_goals.items():
            if len(goals) < 2:
                continue
            
            # 检查同层级目标之间的重叠
            overlap_pairs = []
            for i in range(len(goals)):
                for j in range(i + 1, len(goals)):
                    title1 = goals[i].get('title', '')
                    title2 = goals[j].get('title', '')
                    
                    if not title1 or not title2:
                        continue
                    
                    sim = self.semantic.multi_dim_similarity(title1, title2)
                    
                    if sim > 0.6:
                        overlap_pairs.append((goals[i], goals[j], sim))
            
            if overlap_pairs:
                severity = 'medium' if len(overlap_pairs) >= 2 else 'low'
                
                examples = []
                for g1, g2, sim in overlap_pairs[:3]:
                    examples.append(f"「{g1.get('title', '')}」与「{g2.get('title', '')}」（相似度 {sim*100:.0f}%）")
                
                self._add_issue(
                    dimension='指标关联性与承接',
                    severity=severity,
                    title=f'第{level}层目标存在重叠',
                    description=f"第 {level} 层目标中有 {len(overlap_pairs)} 对存在语义重叠，可能存在职责交叉或重复",
                    evidence=f"重叠的目标对：{'; '.join(examples)}",
                    suggestion="合并重叠的目标，或者明确各自的边界和分工，避免重复建设"
                )
    
    def _diagnose_simple_keyword(self, parent_name, child_indicators, goal):
        """简单关键词匹配（回退方案）"""
        parent_keywords = self._extract_keywords(parent_name)
        unrelated_indicators = []
        
        for ci in child_indicators:
            child_name = ci['indicator'].get('name', '')
            child_keywords = self._extract_keywords(child_name)
            
            overlap = len(parent_keywords & child_keywords)
            total = len(parent_keywords | child_keywords) if parent_keywords | child_keywords else 1
            similarity = overlap / total if total > 0 else 0
            
            if similarity <= 0.2 and self._text_similarity(parent_name, child_name) <= 0.3:
                unrelated_indicators.append(child_name)
            
            # 假拆解检测
            sim = self._text_similarity(parent_name, child_name)
            if sim > 0.8:
                self._add_issue(
                    dimension='指标关联性与承接',
                    severity='medium',
                    title='假拆解风险',
                    description=f"子指标「{child_name}」与父指标「{parent_name}」高度相似（相似度 {sim*100:.0f}%），可能只是换了说法，没有真正拆解",
                    evidence=f"父指标：{parent_name}\n子指标：{child_name}",
                    goal_id=ci['child_goal'].get('goal_id'),
                    goal_title=ci['child_goal'].get('title'),
                    suggestion="将指标进一步拆解为具体的驱动因素，避免换汤不换药"
                )
        
        # 关联性弱的指标
        if unrelated_indicators and len(child_indicators) > 0:
            unrelated_ratio = len(unrelated_indicators) / len(child_indicators)
            
            if unrelated_ratio > 0.5:
                severity = 'high'
                title = '指标承接关系弱'
            elif unrelated_ratio > 0.3:
                severity = 'medium'
                title = '部分指标关联性不足'
            else:
                return
            
            self._add_issue(
                dimension='指标关联性与承接',
                severity=severity,
                title=title,
                description=f"父指标「{parent_name}」的 {len(child_indicators)} 个子指标中，有 {len(unrelated_indicators)} 个关联性较弱（占比 {unrelated_ratio*100:.0f}%）",
                evidence=f"关联性较弱的指标：{', '.join(unrelated_indicators[:5])}{'...' if len(unrelated_indicators) > 5 else ''}",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="检查这些指标是否应该归到其他父目标下，或者调整指标表述以明确承接关系"
            )
    
    def _diagnose_with_semantic(self, parent_name, child_indicators, goal):
        """基于语义分析的诊断（增强版）"""
        unrelated_indicators = []
        
        for ci in child_indicators:
            child_name = ci['indicator'].get('name', '')
            
            # 多维度相似度计算
            sim = self.semantic.multi_dim_similarity(parent_name, child_name)
            
            if sim <= 0.20:
                unrelated_indicators.append((child_name, sim, ci))
            
            # 假拆解检测（阈值提高到 85%）
            if sim > 0.80:
                self._add_issue(
                    dimension='指标关联性与承接',
                    severity='medium',
                    title='假拆解风险',
                    description=f"子指标「{child_name}」与父指标「{parent_name}」高度相似（语义相似度 {sim*100:.0f}%），可能只是换了说法，没有真正拆解",
                    evidence=f"父指标：{parent_name}\n子指标：{child_name}\n相似度算法：多维度融合（分词+同义词+字符）",
                    goal_id=ci['child_goal'].get('goal_id'),
                    goal_title=ci['child_goal'].get('title'),
                    suggestion="将指标进一步拆解为具体的驱动因素，避免换汤不换药"
                )
        
        # 关联性弱的指标
        if unrelated_indicators and len(child_indicators) > 0:
            unrelated_ratio = len(unrelated_indicators) / len(child_indicators)
            
            if unrelated_ratio > 0.5:
                severity = 'high'
                title = '指标承接关系弱'
            elif unrelated_ratio > 0.3:
                severity = 'medium'
                title = '部分指标关联性不足'
            else:
                return
            
            indicators_str = ', '.join([f"{name}（{sim*100:.0f}%）" for name, sim, _ in unrelated_indicators[:5]])
            if len(unrelated_indicators) > 5:
                indicators_str += '...'
            
            self._add_issue(
                dimension='指标关联性与承接',
                severity=severity,
                title=title,
                description=f"父指标「{parent_name}」的 {len(child_indicators)} 个子指标中，有 {len(unrelated_indicators)} 个关联性较弱（占比 {unrelated_ratio*100:.0f}%）",
                evidence=f"关联性较弱的指标：{indicators_str}\n相似度算法：多维度融合（jieba分词+同义词+字符重叠）",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="检查这些指标是否应该归到其他父目标下，或者调整指标表述以明确承接关系"
            )
    
    def _check_child_count(self, parent_name, child_indicators, goal):
        """检查子指标数量合理性"""
        if len(child_indicators) < 2:
            self._add_issue(
                dimension='指标关联性与承接',
                severity='low',
                title='子指标数量过少',
                description=f"父指标「{parent_name}」只有 {len(child_indicators)} 个子指标，拆解不够充分",
                evidence="建议每个上层指标至少拆解为2-3个下层驱动指标",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="进一步拆解为更多具体的驱动指标，确保覆盖主要影响因素"
            )
        elif len(child_indicators) > 7:
            self._add_issue(
                dimension='指标关联性与承接',
                severity='low',
                title='子指标数量过多',
                description=f"父指标「{parent_name}」有 {len(child_indicators)} 个子指标，可能粒度过细或分类不清",
                evidence="建议每个上层指标拆解为3-7个下层指标",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="考虑将指标分组归类，或者合并相似的指标，保持3-7个的合理数量"
            )
    
    def _check_causal_direction(self, parent_name, child_indicators, goal):
        """检查5：因果方向检测"""
        reverse_count = 0
        reverse_examples = []
        
        for ci in child_indicators:
            child_name = ci['indicator'].get('name', '')
            direction = self.semantic.detect_causal_direction(parent_name, child_name)
            
            if direction == 'reverse':
                reverse_count += 1
                if len(reverse_examples) < 3:
                    reverse_examples.append(child_name)
        
        if reverse_count > 0 and len(child_indicators) > 0:
            reverse_ratio = reverse_count / len(child_indicators)
            
            if reverse_ratio > 0.5:
                severity = 'high'
                title = '因果倒置风险'
            elif reverse_ratio > 0.3:
                severity = 'medium'
                title = '部分指标因果方向存疑'
            else:
                return
            
            self._add_issue(
                dimension='指标关联性与承接',
                severity=severity,
                title=title,
                description=f"父指标「{parent_name}」的子指标中，有 {reverse_count} 个可能存在因果倒置（占比 {reverse_ratio*100:.0f}%）",
                evidence=f"可能因果倒置的指标：{', '.join(reverse_examples)}\n判断依据：过程指标 vs 结果指标特征词匹配",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="检查上下级指标的因果关系是否正确，子指标应该是因（驱动因素），父指标应该是果（结果产出）"
            )
    
    def _check_granularity_consistency(self, parent_name, child_indicators, goal):
        """检查6：粒度一致性检测"""
        child_names = [ci['indicator'].get('name', '') for ci in child_indicators]
        level_counts, consistency = self.semantic.check_granularity_consistency(child_names)
        
        if consistency < 0.6 and len(child_names) >= 3:
            # 找出最多的层级
            max_level = max(level_counts.items(), key=lambda x: x[1])[0] if level_counts else 'unknown'
            
            level_names = {
                'strategic': '战略级',
                'managerial': '管理级',
                'operational': '执行级'
            }
            
            level_desc = ', '.join([f"{level_names.get(k, k)}: {v}个" for k, v in level_counts.items()])
            
            self._add_issue(
                dimension='指标关联性与承接',
                severity='medium',
                title='子指标粒度不一致',
                description=f"父指标「{parent_name}」的子指标粒度不均匀，一致性得分 {consistency*100:.0f}%",
                evidence=f"粒度分布：{level_desc}\n建议：同一层级的指标应该保持相近的粒度",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="调整子指标的粒度，确保它们在同一个抽象层级上，可以重新分组或重新表述"
            )
    
    def _check_dimension_completeness(self, parent_name, child_indicators, goal):
        """检查7：维度完整性检测"""
        child_names = [ci['indicator'].get('name', '') for ci in child_indicators]
        
        # 尝试多个框架，取覆盖率最高的
        best_result = None
        best_rate = 0
        
        for framework in ['平衡计分卡', '人机料法环', '4P营销', '项目管理铁三角']:
            result = self.semantic.check_dimension_completeness(child_names, framework)
            if result and result['coverage_rate'] > best_rate:
                best_rate = result['coverage_rate']
                best_result = result
        
        if best_result and best_result['coverage_rate'] < 0.75 and len(child_names) >= 3:
            framework = best_result['framework']
            missing = best_result['missing_dims']
            
            if missing:
                self._add_issue(
                    dimension='指标关联性与承接',
                    severity='low',
                    title='维度覆盖不完整',
                    description=f"父指标「{parent_name}」的子指标维度覆盖不完整（基于{framework}框架，覆盖率 {best_rate*100:.0f}%）",
                    evidence=f"缺失的维度：{', '.join(missing)}\n参考框架：{framework}",
                    goal_id=goal.get('goal_id'),
                    goal_title=goal.get('title'),
                    suggestion=f"考虑补充{', '.join(missing)}维度的指标，确保拆解的全面性"
                )
    
    def _check_logical_closure(self, parent_name, child_indicators, goal):
        """检查8：逻辑闭环检测"""
        child_names = [ci['indicator'].get('name', '') for ci in child_indicators]
        counts, is_closed = self.semantic.detect_logical_closure(child_names)
        
        if not is_closed and len(child_names) >= 3:
            missing = []
            if counts['input'] == 0:
                missing.append('输入')
            if counts['process'] == 0:
                missing.append('过程')
            if counts['output'] == 0:
                missing.append('输出')
            
            if missing:
                self._add_issue(
                    dimension='指标关联性与承接',
                    severity='low',
                    title='逻辑闭环不完整',
                    description=f"父指标「{parent_name}」的子指标缺少{', '.join(missing)}类指标，未形成完整逻辑闭环",
                    evidence=f"输入类: {counts['input']}个, 过程类: {counts['process']}个, 输出类: {counts['output']}个",
                    goal_id=goal.get('goal_id'),
                    goal_title=goal.get('title'),
                    suggestion="补充输入、过程、输出三类指标，形成完整的逻辑闭环，便于追踪因果关系"
                )
    
    def _check_naming_quality(self, parent_name, child_indicators, goal):
        """检查9：指标命名质量检测"""
        bad_naming = []
        
        for ci in child_indicators:
            child_name = ci['indicator'].get('name', '')
            quality = self.semantic.check_naming_quality(child_name)
            
            if quality['score'] < 0.7:
                bad_naming.append((child_name, quality['issues']))
        
        if bad_naming and len(child_indicators) > 0:
            bad_ratio = len(bad_naming) / len(child_indicators)
            
            if bad_ratio > 0.5:
                severity = 'medium'
            else:
                severity = 'low'
            
            examples = []
            for name, issues in bad_naming[:3]:
                examples.append(f"{name}（{', '.join(issues)}）")
            
            self._add_issue(
                dimension='指标关联性与承接',
                severity=severity,
                title='指标命名质量待提升',
                description=f"父指标「{parent_name}」的子指标中，有 {len(bad_naming)} 个命名质量较低（占比 {bad_ratio*100:.0f}%）",
                evidence=f"问题示例：{'; '.join(examples)}",
                goal_id=goal.get('goal_id'),
                goal_title=goal.get('title'),
                suggestion="优化指标命名，确保每个指标都有明确的度量单位和清晰的定义，避免模糊表述"
            )
    
    def _extract_keywords(self, text):
        """从文本中提取关键词（简单版，基于分词和停用词过滤）"""
        # 简单的关键词提取：移除常见停用词，保留有意义的词
        stopwords = {'的', '了', '和', '与', '及', '或', '在', '是', '有', '为', '以', '到', '从', '向', '对', '等', '中', '上', '下', '率', '度', '量', '数', '比', '值'}
        
        # 简单分词（按字符，中文场景）
        keywords = set()
        # 提取2-4字的词组
        for n in [2, 3, 4]:
            for i in range(len(text) - n + 1):
                word = text[i:i+n]
                # 过滤纯数字和标点
                if re.match(r'^[\u4e00-\u9fa5]+$', word):
                    # 检查是否包含停用词
                    if not any(sw in word for sw in stopwords):
                        keywords.add(word)
        
        # 也加入单个有意义的字
        for char in text:
            if '\u4e00' <= char <= '\u9fa5' and char not in stopwords:
                keywords.add(char)
        
        return keywords
    def _get_user_by_id(self, user_id):
        """根据 ID 获取用户信息"""
        for user in self.users:
            if user.get('user_id') == user_id:
                return user
        return None

    def generate_suggestions(self):
        """生成优化建议"""
        suggestions = []
        counter = 0

        # 按严重度和维度整理建议
        high_issues = [i for i in self.issues if i['severity'] == 'high']
        medium_issues = [i for i in self.issues if i['severity'] == 'medium']
        low_issues = [i for i in self.issues if i['severity'] == 'low']

        # P0 建议：高严重度问题
        if high_issues:
            counter += 1
            suggestions.append({
                'suggestion_id': f'SUG-{counter:03d}',
                'priority': 'P0',
                'title': f'优先解决 {len(high_issues)} 个高严重度问题',
                'description': f'当前有 {len(high_issues)} 个高严重度问题，建议优先处理，包括：' +
                              '、'.join([i['title'] for i in high_issues[:3]]),
                'owner': '团队负责人',
                'related_issues': [i['issue_id'] for i in high_issues],
                'deadline': '本周内'
            })

        # P1 建议：中严重度问题
        if medium_issues:
            counter += 1
            suggestions.append({
                'suggestion_id': f'SUG-{counter:03d}',
                'priority': 'P1',
                'title': f'逐步解决 {len(medium_issues)} 个中严重度问题',
                'description': f'当前有 {len(medium_issues)} 个中严重度问题，建议在 2 周内处理',
                'owner': '各目标负责人',
                'related_issues': [i['issue_id'] for i in medium_issues],
                'deadline': '2周内'
            })

        # P2 建议：低严重度问题
        if low_issues:
            counter += 1
            suggestions.append({
                'suggestion_id': f'SUG-{counter:03d}',
                'priority': 'P2',
                'title': f'持续优化 {len(low_issues)} 个低严重度问题',
                'description': f'当前有 {len(low_issues)} 个低严重度问题，可在日常迭代中逐步优化',
                'owner': '各目标负责人',
                'related_issues': [i['issue_id'] for i in low_issues],
                'deadline': '1个月内'
            })

        # 通用建议
        if len(self.issues) > 0:
            counter += 1
            suggestions.append({
                'suggestion_id': f'SUG-{counter:03d}',
                'priority': 'P1',
                'title': '建立目标对齐 review 机制',
                'description': '建议每月进行一次目标对齐 review，及时发现和解决目标拆解问题',
                'owner': '团队负责人',
                'related_issues': [],
                'deadline': '长期'
            })

        return suggestions

    def _calculate_health_score(self):
        """计算健康度评分"""
        score = 100

        for issue in self.issues:
            severity = issue['severity']
            if severity == 'high':
                score -= 10
            elif severity == 'medium':
                score -= 5
            elif severity == 'low':
                score -= 2

        score = max(0, score)

        # 等级判定
        if score >= 90:
            level = '优秀'
        elif score >= 70:
            level = '良好'
        elif score >= 50:
            level = '一般'
        else:
            level = '较差'

        return score, level

    def _build_goal_tree(self):
        """构建目标树结构"""
        # 按层级组织
        tree = {}

        for goal in self.goals:
            level = goal.get('level', 'L?')
            if level not in tree:
                tree[level] = []
            tree[level].append({
                'goal_id': goal['goal_id'],
                'title': goal.get('title'),
                'owner': goal.get('owner_name'),
                'progress': goal.get('progress', 0),
                'children': [g['goal_id'] for g in self.goals
                             if goal['goal_id'] in g.get('parent_goal_ids', [])]
            })

        return tree

    def _build_user_summary(self):
        """构建人员摘要"""
        summary = []

        for user in self.users:
            user_id = user.get('user_id')
            user_goals = self.user_goals.get(user_id, [])

            # 统计该用户负责的目标的问题数
            user_issues = [i for i in self.issues if i.get('owner_id') == user_id]

            summary.append({
                'user_id': user_id,
                'name': user.get('name'),
                'level': user.get('level'),
                'department': user.get('department'),
                'goal_count': len(user_goals),
                'issue_count': len(user_issues),
                'high_issue_count': sum(1 for i in user_issues if i['severity'] == 'high')
            })

        return summary

    def generate_text_report(self, result):
        """生成纯文本报告"""
        summary = result.get('summary', {})
        issues = result.get('issues', [])
        suggestions = result.get('suggestions', [])
        data_warnings = summary.get('data_warnings', [])

        lines = []
        lines.append("=" * 60)
        lines.append("绩效目标拆解诊断报告")
        lines.append("=" * 60)
        lines.append("")
        
        # 数据质量警告
        if data_warnings:
            lines.append("⚠️  数据质量警告")
            lines.append("-" * 40)
            for warning in data_warnings:
                level = warning.get('level', '')
                wtype = warning.get('type', '')
                message = warning.get('message', '')
                suggestion = warning.get('suggestion', '')
                level_icon = "🔴" if level == "high" else "🟡" if level == "medium" else "🟢"
                lines.append(f"  {level_icon} [{wtype}] {message}")
                if suggestion:
                    lines.append(f"     💡 建议：{suggestion}")
            lines.append("")
            lines.append("ℹ️  本诊断基于现有数据自动生成，数据不完整时结论仅供参考")
            lines.append("   建议结合业务实际情况人工复核")
            lines.append("")
        
        lines.append(f"健康度评分: {summary.get('health_score', 0)} / 100")
        lines.append(f"等级: {summary.get('health_level', '')}")
        lines.append(f"目标总数: {summary.get('total_goals', 0)}")
        lines.append(f"问题总数: {summary.get('total_issues', 0)}")
        lines.append("")
        lines.append("按严重度:")
        lines.append(f"  high: {summary.get('high_count', 0)} 个")
        lines.append(f"  medium: {summary.get('medium_count', 0)} 个")
        lines.append(f"  low: {summary.get('low_count', 0)} 个")
        lines.append("")
        lines.append("按维度:")
        for dim, count in summary.get('by_dimension', {}).items():
            lines.append(f"  {dim}: {count} 个")
        lines.append("")

        # v2.2：行业匹配信息
        industry_info = summary.get('industry_info', {})
        if industry_info and industry_info.get('library_loaded'):
            lines.append("🏭 行业基准匹配信息")
            lines.append("-" * 40)
            specified = industry_info.get('specified_industry')
            recognized = industry_info.get('recognized_industry')
            match_info = industry_info.get('match_info', {})

            if specified:
                lines.append(f"  指定行业：{specified}")
            elif recognized:
                confidence = match_info.get('confidence', 0)
                lines.append(f"  自动识别：{recognized}（置信度 {confidence*100:.0f}%）")
                # Top3 候选
                candidates = match_info.get('recognized', [])
                if len(candidates) > 1:
                    lines.append("  其他候选：")
                    for ind, score in candidates[1:3]:
                        lines.append(f"    - {ind}（{score*100:.0f}%）")
            else:
                lines.append("  使用行业：通用行业（兜底）")

            stats = industry_info.get('library_stats', {})
            if stats:
                lines.append(f"  指标库：{stats.get('total_metrics', 0)}个指标，{stats.get('industries', 0)}个行业")
            lines.append("")

        lines.append("问题列表:")
        lines.append("")

        for issue in issues:
            lines.append(f"[{issue['issue_id']}] {issue['dimension']} ({issue['severity']})")
            lines.append(f"  目标: {issue.get('goal_title', 'N/A')}")
            lines.append(f"  描述: {issue.get('description', '')}")
            if issue.get('evidence'):
                lines.append(f"  证据: {issue.get('evidence', '')}")
            lines.append("")

        if suggestions:
            lines.append("优化建议:")
            lines.append("")
            for s in suggestions:
                lines.append(f"[{s.get('priority', '')}] {s.get('title', '')}")
                lines.append(f"  责任人: {s.get('owner', '待定')}")
                lines.append(f"  建议: {s.get('description', '')}")
                lines.append("")

        # 添加用户反馈入口
        lines.append("")
        lines.append("=" * 60)
        lines.append("📝 用户反馈")
        lines.append("=" * 60)
        lines.append("如发现本报告中的行业基准指标不准或不对，欢迎反馈：")
        lines.append("")
        lines.append("  📧 反馈邮箱：请联系指标库维护者")
        lines.append("  💬 反馈格式：指标名称 + 问题描述 + 建议值/正确值")
        lines.append("  ⏱️ 响应时间：3个工作日内回复")
        lines.append("")
        lines.append("您的反馈将帮助我们持续优化行业指标库！")
        lines.append("同一指标收到 ≥3 个类似反馈将触发即时更新。")
        lines.append("")
        lines.append("=" * 60)
        lines.append("本报告由绩效目标拆解诊断工具 v2.5 自动生成")
        lines.append("行业指标库版本：v2.5.0（2026-08-11）")
        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='绩效目标拆解诊断工具')
    parser.add_argument('--input', '-i', required=True, help='输入数据文件路径')
    parser.add_argument('--output', '-o', default='diagnosis_result.json', help='输出文件路径')
    parser.add_argument('--industry-metrics', help='行业指标库文件夹路径')
    parser.add_argument('--format', '-f', choices=['json', 'text'], default='json', help='输出格式')
    parser.add_argument('--severity-threshold', choices=['high', 'medium', 'low'], default='low',
                        help='只显示指定严重度及以上的问题')

    args = parser.parse_args()

    # 加载输入数据
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 创建诊断器
    diagnoser = GoalDiagnoser(
        industry_metrics_path=args.industry_metrics,
        severity_threshold=args.severity_threshold
    )

    # 运行诊断
    result = diagnoser.run_all_diagnoses(data)

    # 输出结果
    if args.format == 'text':
        output = diagnoser.generate_text_report(result)
    else:
        output = json.dumps(result, ensure_ascii=False, indent=2)

    # 保存文件
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"💾 诊断结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
