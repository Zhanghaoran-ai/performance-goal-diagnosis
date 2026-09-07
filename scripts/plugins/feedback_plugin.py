#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主动学习反馈插件
收集用户反馈，持续优化诊断结果

【可选插件】启用后可以收集用户对诊断结果的反馈，
用于后续优化算法和阈值
"""

import json
from pathlib import Path
from datetime import datetime
from .base_plugin import BasePlugin


class FeedbackPlugin(BasePlugin):
    """主动学习反馈插件"""
    
    def __init__(self):
        super().__init__('FeedbackPlugin', '1.0.0')
        self.feedback_data = []
        self.feedback_file = None
    
    def initialize(self, feedback_file=None, **kwargs):
        """
        初始化反馈插件
        
        Args:
            feedback_file: 反馈数据保存路径
        """
        if feedback_file is None:
            feedback_file = Path.home() / '.cache' / 'performance_diagnosis' / 'feedback.json'
        
        self.feedback_file = Path(feedback_file)
        
        # 确保目录存在
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载已有反馈
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    self.feedback_data = json.load(f)
                print(f"  ✅ 已加载 {len(self.feedback_data)} 条历史反馈")
            except Exception as e:
                print(f"  ⚠️  加载反馈数据失败: {e}")
                self.feedback_data = []
        
        self.initialized = True
        return True
    
    def get_capabilities(self):
        return [
            'add_feedback',
            'get_feedback_stats',
            'export_feedback',
            'get_optimization_suggestions',
        ]
    
    def add_feedback(self, issue_id, is_correct, user_comment='', context=None):
        """
        添加用户反馈
        
        Args:
            issue_id: 问题 ID
            is_correct: 诊断是否正确（True/False）
            user_comment: 用户评论
            context: 上下文信息（指标名称、目标名称等）
        """
        if not self.initialized:
            return False
        
        feedback = {
            'id': len(self.feedback_data) + 1,
            'issue_id': issue_id,
            'is_correct': is_correct,
            'user_comment': user_comment,
            'context': context or {},
            'timestamp': datetime.now().isoformat(),
        }
        
        self.feedback_data.append(feedback)
        self._save_feedback()
        
        return True
    
    def get_feedback_stats(self):
        """获取反馈统计"""
        if not self.initialized:
            return None
        
        total = len(self.feedback_data)
        if total == 0:
            return {
                'total': 0,
                'correct_rate': 0,
                'by_dimension': {},
                'by_severity': {},
            }
        
        correct = sum(1 for f in self.feedback_data if f['is_correct'])
        correct_rate = correct / total
        
        # 按维度统计
        by_dimension = {}
        for f in self.feedback_data:
            dim = f.get('context', {}).get('dimension', 'unknown')
            if dim not in by_dimension:
                by_dimension[dim] = {'total': 0, 'correct': 0}
            by_dimension[dim]['total'] += 1
            if f['is_correct']:
                by_dimension[dim]['correct'] += 1
        
        # 计算各维度的准确率
        for dim in by_dimension:
            d = by_dimension[dim]
            d['correct_rate'] = d['correct'] / d['total'] if d['total'] > 0 else 0
        
        return {
            'total': total,
            'correct': correct,
            'correct_rate': correct_rate,
            'by_dimension': by_dimension,
        }
    
    def get_optimization_suggestions(self):
        """
        基于反馈数据给出优化建议
        """
        if not self.initialized:
            return None
        
        stats = self.get_feedback_stats()
        if stats['total'] < 10:
            return {
                'status': 'insufficient_data',
                'message': f'反馈数据不足（当前 {stats["total"]} 条），建议收集至少 10 条反馈后再分析',
                'suggestions': []
            }
        
        suggestions = []
        
        # 找出准确率最低的维度
        dim_rates = []
        for dim, data in stats['by_dimension'].items():
            dim_rates.append((dim, data['correct_rate'], data['total']))
        
        dim_rates.sort(key=lambda x: x[1])
        
        if dim_rates and dim_rates[0][1] < 0.7:
            dim, rate, count = dim_rates[0]
            suggestions.append({
                'priority': 'high',
                'dimension': dim,
                'issue': f'准确率偏低（{rate*100:.0f}%）',
                'suggestion': f'建议重点优化「{dim}」维度的诊断规则，调整阈值或增加新的判断逻辑',
            })
        
        return {
            'status': 'ok',
            'overall_accuracy': stats['correct_rate'],
            'total_feedback': stats['total'],
            'suggestions': suggestions,
        }
    
    def export_feedback(self, output_file=None):
        """导出反馈数据"""
        if not self.initialized:
            return None
        
        if output_file is None:
            output_file = self.feedback_file
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.feedback_data, f, ensure_ascii=False, indent=2)
            return str(output_file)
        except Exception as e:
            print(f"  ❌ 导出反馈失败: {e}")
            return None
    
    def _save_feedback(self):
        """保存反馈数据"""
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(self.feedback_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️  保存反馈数据失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        self._save_feedback()
        self.feedback_data.clear()
        self.initialized = False
