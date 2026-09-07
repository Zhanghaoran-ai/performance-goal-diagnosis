#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准输出框架生成器
参考「绩效目标拆解诊断系统」飞书应用的 UI 和内容维度
6 页面标准化输出：概览 Dashboard / 指标拆解树 / 目标拆解树 / 诊断结果 / 优化建议 / 人员视图
"""

import time
import html
from collections import defaultdict


class StandardReportGenerator:
    """标准输出框架生成器"""

    # 颜色体系
    COLORS = {
        'sidebar_bg': '#1a1a2e',
        'sidebar_active': '#16213e',
        'main_bg': '#f5f5f7',
        'card_bg': '#ffffff',
        'text_primary': '#1f2937',
        'text_secondary': '#6b7280',
        'text_muted': '#9ca3af',
        'health_green': '#10b981',
        'normal_purple': '#8b5cf6',
        'warning_yellow': '#f59e0b',
        'danger_red': '#ef4444',
        'info_blue': '#3b82f6',
        'dim_orange': '#f97316',
        'repeat_purple': '#a855f7',
        'align_cyan': '#06b6d4',
        'level_pink': '#ec4899',
    }

    # 维度颜色映射
    DIMENSION_COLORS = {
        '上下层数据不匹配': '#f97316',
        '无具体执行人': '#eab308',
        '目标重复': '#a855f7',
        '责任不清': '#3b82f6',
        '未向上对齐': '#06b6d4',
        '层次不准确': '#ec4899',
        '指标偏离行业基准': '#ef4444',
        '指标关联性与承接': '#8b5cf6',
    }

    def __init__(self, result, data, tree_style='enhanced'):
        """
        初始化标准报告生成器
        :param result: 诊断结果字典
        :param data: 原始输入数据字典
        :param tree_style: 目标拆解树样式，'enhanced'（v2.5 层级强化版，默认）/ 'legacy'（v2.4 按层级分组）
        """
        self.tree_style = tree_style
        self.result = result
        self.data = data
        self.summary = result.get('summary', {})
        self.issues = result.get('issues', [])
        self.suggestions = result.get('suggestions', [])
        self.goals = data.get('goals', [])
        self.users = data.get('users', [])
        self.industry_info = result.get('summary', {}).get('industry_info', result.get('industry_info', {}))

    def generate_html(self):
        """生成标准 HTML 报告（6 页面 Tab 切换）"""
        score = self.summary.get('health_score', 0)
        level = self.summary.get('health_level', '')

        # 构建各页面内容
        dashboard_html = self._build_dashboard_html()
        goal_tree_html = self._build_goal_tree_html()
        indicator_tree_html = self._build_indicator_tree_html()
        diagnosis_html = self._build_diagnosis_html()
        suggestions_html = self._build_suggestions_html()
        people_html = self._build_people_html()

        # 行业信息
        industry_name = self.industry_info.get('recognized_industry', '通用行业')
        industry_conf = self.industry_info.get('confidence', 0)
        if isinstance(industry_conf, float):
            industry_conf = f"{int(industry_conf * 100)}%"

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绩效目标拆解诊断报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: {self.COLORS['main_bg']};
            color: {self.COLORS['text_primary']};
        }}
        /* 布局 */
        .app-layout {{ display: flex; min-height: 100vh; }}
        .sidebar {{
            width: 220px;
            background: {self.COLORS['sidebar_bg']};
            color: white;
            padding: 20px 0;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }}
        .sidebar-logo {{
            padding: 0 20px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 10px;
        }}
        .sidebar-logo h2 {{ font-size: 16px; font-weight: 600; }}
        .sidebar-logo p {{ font-size: 12px; opacity: 0.6; margin-top: 4px; }}
        .nav-item {{
            padding: 12px 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            transition: all 0.2s;
            border-left: 3px solid transparent;
        }}
        .nav-item:hover {{ background: rgba(255,255,255,0.05); }}
        .nav-item.active {{
            background: {self.COLORS['sidebar_active']};
            border-left-color: {self.COLORS['info_blue']};
        }}
        .nav-icon {{ font-size: 18px; }}
        .main-content {{
            margin-left: 220px;
            flex: 1;
            min-height: 100vh;
        }}
        .topbar {{
            background: white;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 30px;
            border-bottom: 1px solid #e5e7eb;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .topbar-title {{ font-size: 18px; font-weight: 600; }}
        .topbar-meta {{ display: flex; align-items: center; gap: 20px; font-size: 13px; color: {self.COLORS['text_secondary']}; }}
        .topbar-badge {{
            background: #eff6ff;
            color: {self.COLORS['info_blue']};
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 500;
        }}
        .page-content {{ padding: 24px 30px; display: none; }}
        .page-content.active {{ display: block; }}
        .page-header {{ margin-bottom: 20px; }}
        .page-header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; }}
        .page-header p {{ font-size: 14px; color: {self.COLORS['text_secondary']}; }}
        /* 卡片 */
        .card {{
            background: {self.COLORS['card_bg']};
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 16px;
        }}
        .card-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
        /* 指标卡片网格 */
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .metric-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
        }}
        .metric-value {{ font-size: 32px; font-weight: 700; margin-bottom: 4px; }}
        .metric-label {{ font-size: 13px; color: {self.COLORS['text_secondary']}; }}
        .metric-trend {{ font-size: 12px; margin-top: 6px; }}
        .trend-up {{ color: {self.COLORS['danger_red']}; }}
        .trend-down {{ color: {self.COLORS['health_green']}; }}
        /* 健康度环形图 */
        .health-ring-container {{ display: flex; align-items: center; justify-content: center; gap: 40px; padding: 20px 0; }}
        .health-ring {{
            width: 160px;
            height: 160px;
            border-radius: 50%;
            background: conic-gradient({self._get_health_color(score)} {score}%, #e5e7eb {score}%);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        .health-ring-inner {{
            width: 128px;
            height: 128px;
            border-radius: 50%;
            background: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .health-score {{ font-size: 40px; font-weight: 700; color: {self._get_health_color(score)}; }}
        .health-level {{ font-size: 14px; color: {self.COLORS['text_secondary']}; }}
        .health-desc {{ max-width: 300px; font-size: 14px; line-height: 1.6; color: {self.COLORS['text_secondary']}; }}
        /* 图表区域 */
        .charts-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }}
        .chart-container {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        .chart-title {{ font-size: 14px; font-weight: 600; margin-bottom: 16px; color: {self.COLORS['text_primary']}; }}
        /* 条形图 */
        .bar-chart {{ display: flex; flex-direction: column; gap: 10px; }}
        .bar-row {{ display: flex; align-items: center; gap: 10px; }}
        .bar-label {{ width: 120px; font-size: 12px; color: {self.COLORS['text_secondary']}; text-align: right; flex-shrink: 0; }}
        .bar-track {{ flex: 1; height: 24px; background: #f3f4f6; border-radius: 4px; overflow: hidden; position: relative; }}
        .bar-fill {{ height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; color: white; font-size: 11px; font-weight: 500; transition: width 0.5s; }}
        /* 环形图（CSS模拟） */
        .donut-chart {{ display: flex; align-items: center; gap: 20px; }}
        .donut {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        .donut-inner {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 600;
        }}
        .donut-legend {{ display: flex; flex-direction: column; gap: 8px; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 12px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 3px; }}
        /* 目标树 */
        .tree-container {{ font-size: 14px; }}
        .tree-level {{ margin-bottom: 16px; }}
        .tree-level-title {{ font-size: 13px; font-weight: 600; color: {self.COLORS['text_secondary']}; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb; }}
        .goal-node {{
            background: #f9fafb;
            border-radius: 10px;
            margin-bottom: 10px;
            border-left: 4px solid #d1d5db;
            overflow: hidden;
            transition: all 0.2s;
        }}
        .goal-node.health {{ border-left-color: {self.COLORS['health_green']}; }}
        .goal-node.warning {{ border-left-color: {self.COLORS['warning_yellow']}; }}
        .goal-node.danger {{ border-left-color: {self.COLORS['danger_red']}; }}
        .goal-node-header {{
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
        }}
        .goal-node-header:hover {{ background: #f3f4f6; }}
        .goal-node-left {{ flex: 1; min-width: 0; }}
        .goal-node-title {{ font-weight: 600; font-size: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }}
        .goal-node-meta {{ font-size: 12px; color: {self.COLORS['text_secondary']}; display: flex; gap: 12px; flex-wrap: wrap; }}
        .goal-node-right {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; }}
        .goal-progress-bar {{ width: 80px; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }}
        .goal-progress-fill {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}
        .goal-progress-text {{ font-size: 12px; font-weight: 600; min-width: 36px; text-align: right; }}
        .issue-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        .issue-badge.high {{ background: #fee2e2; color: {self.COLORS['danger_red']}; }}
        .issue-badge.medium {{ background: #fef3c7; color: #d97706; }}
        .issue-badge.low {{ background: #dbeafe; color: {self.COLORS['info_blue']}; }}
        .issue-badge.none {{ background: #d1fae5; color: {self.COLORS['health_green']}; }}
        .expand-icon {{ font-size: 12px; color: #9ca3af; transition: transform 0.2s; width: 16px; text-align: center; }}
        .goal-node.expanded .expand-icon {{ transform: rotate(90deg); }}
        .goal-detail-panel {{
            display: none;
            padding: 0 16px 16px;
            border-top: 1px solid #e5e7eb;
            background: white;
        }}
        .goal-node.expanded .goal-detail-panel {{ display: block; }}
        .detail-section {{ margin-top: 14px; }}
        .detail-section-title {{ font-size: 12px; font-weight: 600; color: {self.COLORS['text_secondary']}; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .indicator-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }}
        .indicator-item {{ background: #f9fafb; padding: 8px 10px; border-radius: 6px; font-size: 12px; }}
        .indicator-name {{ color: {self.COLORS['text_secondary']}; margin-bottom: 2px; }}
        .indicator-value {{ font-weight: 600; }}
        .indicator-target {{ color: #9ca3af; font-size: 11px; }}
        .mini-issue-card {{
            background: #fef2f2;
            border-left: 3px solid {self.COLORS['danger_red']};
            padding: 8px 12px;
            border-radius: 4px;
            margin-bottom: 6px;
            font-size: 12px;
        }}
        .mini-issue-card.medium {{ background: #fffbeb; border-left-color: #f59e0b; }}
        .mini-issue-card.low {{ background: #eff6ff; border-left-color: {self.COLORS['info_blue']}; }}
        .mini-issue-title {{ font-weight: 600; margin-bottom: 2px; }}
        .mini-issue-desc {{ color: {self.COLORS['text_secondary']}; }}
        .mini-suggestion-card {{
            background: #f0fdf4;
            border-left: 3px solid {self.COLORS['health_green']};
            padding: 8px 12px;
            border-radius: 4px;
            margin-bottom: 6px;
            font-size: 12px;
        }}
        .mini-suggestion-priority {{ font-weight: 600; font-size: 11px; margin-bottom: 2px; }}
        .mini-suggestion-text {{ color: {self.COLORS['text_secondary']}; }}
        .tree-children {{ margin-left: 24px; margin-top: 8px; }}
        .empty-hint {{ color: #9ca3af; font-size: 12px; font-style: italic; }}
        /* 诊断维度卡片 */
        .dimension-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }}
        .dimension-card {{
            background: white;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            cursor: pointer;
            transition: transform 0.2s;
            border-top: 3px solid;
        }}
        .dimension-card:hover {{ transform: translateY(-2px); }}
        .dimension-name {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
        .dimension-desc {{ font-size: 12px; color: {self.COLORS['text_secondary']}; margin-bottom: 10px; }}
        .dimension-count {{ font-size: 24px; font-weight: 700; }}
        /* 问题列表 */
        .issue-list {{ display: flex; flex-direction: column; gap: 10px; }}
        .issue-card {{
            background: white;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
            border-left: 4px solid;
        }}
        .issue-card.high {{ border-left-color: {self.COLORS['danger_red']}; }}
        .issue-card.medium {{ border-left-color: {self.COLORS['warning_yellow']}; }}
        .issue-card.low {{ border-left-color: {self.COLORS['info_blue']}; }}
        .issue-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }}
        .issue-title {{ font-size: 14px; font-weight: 600; }}
        .severity-badge {{
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        .severity-high {{ background: #fef2f2; color: {self.COLORS['danger_red']}; }}
        .severity-medium {{ background: #fffbeb; color: {self.COLORS['warning_yellow']}; }}
        .severity-low {{ background: #eff6ff; color: {self.COLORS['info_blue']}; }}
        .issue-meta {{ font-size: 12px; color: {self.COLORS['text_secondary']}; margin-bottom: 6px; }}
        .issue-desc {{ font-size: 13px; color: {self.COLORS['text_primary']}; line-height: 1.5; }}
        .issue-evidence {{ font-size: 12px; color: {self.COLORS['text_secondary']}; margin-top: 8px; padding: 8px; background: #f9fafb; border-radius: 6px; }}
        .dimension-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            color: white;
            margin-right: 6px;
        }}
        /* 建议卡片 */
        .suggestion-group {{ margin-bottom: 20px; }}
        .suggestion-group-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .suggestion-avatar {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: {self.COLORS['info_blue']};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 14px;
        }}
        .suggestion-owner {{ font-size: 15px; font-weight: 600; }}
        .suggestion-count {{ font-size: 12px; color: {self.COLORS['text_secondary']}; }}
        .suggestion-card {{
            background: white;
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }}
        .priority-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-right: 8px;
        }}
        .priority-P0 {{ background: #fef2f2; color: {self.COLORS['danger_red']}; }}
        .priority-P1 {{ background: #fffbeb; color: {self.COLORS['warning_yellow']}; }}
        .priority-P2 {{ background: #eff6ff; color: {self.COLORS['info_blue']}; }}
        .suggestion-title {{ font-size: 14px; font-weight: 500; margin-bottom: 6px; }}
        .suggestion-desc {{ font-size: 13px; color: {self.COLORS['text_secondary']}; line-height: 1.5; }}
        .suggestion-meta {{ font-size: 12px; color: {self.COLORS['text_muted']}; margin-top: 8px; }}
        /* 人员视图 */
        .people-layout {{ display: grid; grid-template-columns: 280px 1fr; gap: 16px; }}
        .people-tree {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); max-height: 600px; overflow-y: auto; }}
        .people-detail {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        .person-node {{
            padding: 10px 12px;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 4px;
            transition: background 0.2s;
        }}
        .person-node:hover {{ background: #f3f4f6; }}
        .person-node.active {{ background: #eff6ff; }}
        .person-avatar {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: {self.COLORS['normal_purple']};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 600;
            flex-shrink: 0;
        }}
        .person-info {{ flex: 1; min-width: 0; }}
        .person-name {{ font-size: 13px; font-weight: 500; }}
        .person-position {{ font-size: 11px; color: {self.COLORS['text_secondary']}; }}
        .issue-badge {{
            background: {self.COLORS['danger_red']};
            color: white;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 10px;
            min-width: 20px;
            text-align: center;
        }}
        .person-detail-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #e5e7eb; }}
        .person-detail-avatar {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: {self.COLORS['normal_purple']};
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 600;
        }}
        .person-detail-name {{ font-size: 20px; font-weight: 700; }}
        .person-detail-meta {{ font-size: 13px; color: {self.COLORS['text_secondary']}; margin-top: 4px; }}
        .person-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }}
        .person-stat {{ text-align: center; padding: 12px; background: #f9fafb; border-radius: 8px; }}
        .person-stat-value {{ font-size: 22px; font-weight: 700; }}
        .person-stat-label {{ font-size: 12px; color: {self.COLORS['text_secondary']}; margin-top: 2px; }}
        .section-title {{ font-size: 15px; font-weight: 600; margin: 16px 0 12px; }}
        /* 页脚 */
        .report-footer {{
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: {self.COLORS['text_muted']};
            border-top: 1px solid #e5e7eb;
            margin-top: 20px;
        }}
        /* 响应式 */
        @media (max-width: 768px) {{
            .sidebar {{ width: 60px; padding-top: 8px; }}
            .sidebar-logo {{ display: none; }}
            .nav-item {{ min-height: 52px; padding: 12px 0; justify-content: center; border-left-width: 4px; }}
            .sidebar-logo p, .nav-item span:not(.nav-icon) {{ display: none; }}
            .nav-icon {{ display: block; font-size: 22px; line-height: 1; }}
            .main-content {{ margin-left: 60px; }}
            .charts-grid, .dimension-grid {{ grid-template-columns: 1fr; }}
            .people-layout {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="app-layout">
        <!-- 左侧导航 -->
        <div class="sidebar">
            <div class="sidebar-logo">
                <h2>🎯 目标拆解诊断</h2>
                <p>Performance Diagnosis</p>
            </div>
            <div class="nav-item active" onclick="switchPage('dashboard', this)">
                <span class="nav-icon">📊</span><span>概览 Dashboard</span>
            </div>
            <div class="nav-item" onclick="switchPage('indicator-tree', this)">
                <span class="nav-icon">🌳</span><span>指标拆解树</span>
            </div>
            <div class="nav-item" onclick="switchPage('goal-tree', this)">
                <span class="nav-icon">🎯</span><span>目标拆解树</span>
            </div>
            <div class="nav-item" onclick="switchPage('diagnosis', this)">
                <span class="nav-icon">🔍</span><span>诊断结果</span>
            </div>
            <div class="nav-item" onclick="switchPage('suggestions', this)">
                <span class="nav-icon">💡</span><span>优化建议</span>
            </div>
            <div class="nav-item" onclick="switchPage('people', this)">
                <span class="nav-icon">👥</span><span>人员视图</span>
            </div>
        </div>

        <!-- 主内容区 -->
        <div class="main-content">
            <!-- 顶部栏 -->
            <div class="topbar">
                <div class="topbar-title">绩效目标拆解诊断报告</div>
                <div class="topbar-meta">
                    <span class="topbar-badge">🏭 {html.escape(industry_name)}</span>
                    <span>诊断时间：{time.strftime('%Y-%m-%d %H:%M')}</span>
                </div>
            </div>

            <!-- 页面1：概览 Dashboard -->
            <div id="page-dashboard" class="page-content active">
                <div class="page-header">
                    <h1>📊 概览 Dashboard</h1>
                    <p>绩效目标拆解健康度总览，覆盖 {len(self.goals)} 个目标 · {len(self.users)} 名人员</p>
                </div>
                {dashboard_html}
            </div>

            <!-- 页面2：指标拆解树（独立指标节点与关系边） -->
            <div id="page-indicator-tree" class="page-content">
                <div class="page-header">
                    <h1>🌳 指标拆解树与上下关联诊断</h1>
                    <p>指标是独立节点；实线为显式关系，虚线为算法推断，证据不足单列数据缺口</p>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
                        <button type="button" class="tree-btn active" onclick="switchPage('indicator-tree', document.querySelectorAll('.nav-item')[1])">指标树（默认）</button>
                        <button type="button" class="tree-btn" onclick="switchPage('goal-tree', document.querySelectorAll('.nav-item')[2])">切换到目标树</button>
                    </div>
                </div>
                {indicator_tree_html}
            </div>

            <!-- 页面3：目标拆解树 -->
            <div id="page-goal-tree" class="page-content">
                <div class="page-header">
                    <h1>🌲 目标拆解树</h1>
                    <p>4层目标体系可视化，共 {len(self.goals)} 个目标</p>
                </div>
                {goal_tree_html}
            </div>

            <!-- 页面3：诊断结果 -->
            <div id="page-diagnosis" class="page-content">
                <div class="page-header">
                    <h1>🔍 诊断结果</h1>
                    <p>八大维度详细诊断，共发现 {len(self.issues)} 个问题</p>
                </div>
                {diagnosis_html}
            </div>

            <!-- 页面4：优化建议 -->
            <div id="page-suggestions" class="page-content">
                <div class="page-header">
                    <h1>💡 优化建议</h1>
                    <p>按责任人分组的行动项清单，推动问题落地解决</p>
                </div>
                {suggestions_html}
            </div>

            <!-- 页面5：人员视图 -->
            <div id="page-people" class="page-content">
                <div class="page-header">
                    <h1>👥 人员视图</h1>
                    <p>按人员/部门查看目标和问题分布，共 {len(self.users)} 人</p>
                </div>
                {people_html}
            </div>

            <div class="report-footer">
                本报告由绩效目标拆解诊断工具 v2.7 自动生成 · 独立指标拆解树 · 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </div>

    <script>
        function switchPage(pageId, navEl) {{
            // 隐藏所有页面
            document.querySelectorAll('.page-content').forEach(p => p.classList.remove('active'));
            // 取消所有导航激活
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            // 显示目标页面
            document.getElementById('page-' + pageId).classList.add('active');
            // 激活导航
            navEl.classList.add('active');
        }}

        // 人员视图：点击人员切换详情
        function selectPerson(personId, el) {{
            document.querySelectorAll('.person-node').forEach(n => n.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.person-detail-panel').forEach(p => p.style.display = 'none');
            const panel = document.getElementById('person-detail-' + personId);
            if (panel) panel.style.display = 'block';
        }}

        // 目标拆解树：点击展开/收起详情
        function toggleGoalNode(nodeId) {{
            const node = document.getElementById('goal-node-' + nodeId);
            if (node) {{
                node.classList.toggle('expanded');
            }}
        }}

        // 全部展开/收起
        function expandAllGoals(expand) {{
            document.querySelectorAll('.goal-node').forEach(n => {{
                if (expand) n.classList.add('expanded');
                else n.classList.remove('expanded');
            }});
        }}
    </script>
</body>
</html>"""

    def generate_markdown(self):
        """生成标准 Markdown 报告（按 6 页面分章节）"""
        md = []
        score = self.summary.get('health_score', 0)
        level = self.summary.get('health_level', '')

        # 报告头
        md.append("# 绩效目标拆解诊断报告")
        md.append("")
        md.append(f"> **诊断时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}  ")
        md.append(f"> **目标总数**：{len(self.goals)} 个  ")
        md.append(f"> **参与人数**：{len(self.users)} 人  ")
        industry_name = self.industry_info.get('recognized_industry', '通用行业')
        md.append(f"> **识别行业**：{industry_name}")
        md.append("")
        md.append("---")
        md.append("")

        # 页面1：概览 Dashboard
        md.extend(self._build_dashboard_markdown())
        md.append("")
        md.append("---")
        md.append("")

        # 页面2：指标拆解树（独立指标节点）
        md.extend(self._build_indicator_tree_markdown())
        md.append("")
        md.append("---")
        md.append("")

        # 页面3：目标拆解树（保留旧视图）
        md.extend(self._build_goal_tree_markdown())
        md.append("")
        md.append("---")
        md.append("")

        # 页面4：诊断结果
        md.extend(self._build_diagnosis_markdown())
        md.append("")
        md.append("---")
        md.append("")

        # 页面5：优化建议
        md.extend(self._build_suggestions_markdown())
        md.append("")
        md.append("---")
        md.append("")

        # 页面6：人员视图
        md.extend(self._build_people_markdown())
        md.append("")
        md.append("---")
        md.append("")

        # 页脚
        md.append("*本报告由绩效目标拆解诊断工具 v2.7 自动生成 · 含独立指标拆解树与人工关系决策契约*")

        return "\n".join(md)

    # ==================== HTML 构建方法 ====================

    def _build_dashboard_html(self):
        """构建概览 Dashboard HTML"""
        score = self.summary.get('health_score', 0)
        level = self.summary.get('health_level', '')
        health_color = self._get_health_color(score)

        # 6个核心指标卡片
        metrics_html = f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" style="color: {health_color}">{score}</div>
                <div class="metric-label">整体健康度</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self.summary.get('total_goals', len(self.goals))}</div>
                <div class="metric-label">目标总数</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self._calc_avg_progress()}%</div>
                <div class="metric-label">平均完成率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['danger_red']}">{self.summary.get('total_issues', len(self.issues))}</div>
                <div class="metric-label">问题总数</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['danger_red']}">{self.summary.get('high_count', 0)}</div>
                <div class="metric-label">高严重度问题</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{len(self.users)}</div>
                <div class="metric-label">涉及人员</div>
            </div>
        </div>
        """

        # 健康度说明
        health_desc = self._get_health_description(score)

        health_section = f"""
        <div class="card">
            <div class="card-title">🎯 整体健康度</div>
            <div class="health-ring-container">
                <div class="health-ring">
                    <div class="health-ring-inner">
                        <div class="health-score">{score}</div>
                        <div class="health-level">{level}</div>
                    </div>
                </div>
                <div class="health-desc">{health_desc}</div>
            </div>
        </div>
        """

        # 严重度分布环形图
        high = self.summary.get('high_count', 0)
        medium = self.summary.get('medium_count', 0)
        low = self.summary.get('low_count', 0)
        total = max(high + medium + low, 1)
        severity_donut = self._build_donut_html(
            [('高严重度', high, self.COLORS['danger_red']),
             ('中严重度', medium, self.COLORS['warning_yellow']),
             ('低严重度', low, self.COLORS['info_blue'])],
            total
        )

        # 各维度问题数量条形图
        by_dimension = self.summary.get('by_dimension', {})
        dim_bars = ""
        if by_dimension:
            max_count = max(by_dimension.values()) if by_dimension else 1
            for dim, count in sorted(by_dimension.items(), key=lambda x: -x[1]):
                color = self.DIMENSION_COLORS.get(dim, self.COLORS['info_blue'])
                width_pct = int(count / max_count * 100) if max_count > 0 else 0
                dim_bars += f"""
                <div class="bar-row">
                    <div class="bar-label">{html.escape(dim)}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width: {width_pct}%; background: {color}">{count}</div>
                    </div>
                </div>"""

        # 各层级问题分布
        level_issues = self._count_issues_by_level()
        level_bars = ""
        if level_issues:
            max_level = max(level_issues.values()) if level_issues else 1
            for lvl in ['L1', 'L2', 'L3', 'L4']:
                count = level_issues.get(lvl, 0)
                width_pct = int(count / max_level * 100) if max_level > 0 else 0
                level_bars += f"""
                <div class="bar-row">
                    <div class="bar-label">{lvl}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width: {width_pct}%; background: {self.COLORS['normal_purple']}">{count}</div>
                    </div>
                </div>"""

        # TOP5 问题责任人
        top_owners = self._get_top_issue_owners(5)
        owner_bars = ""
        if top_owners:
            max_owner = top_owners[0][1] if top_owners else 1
            for name, count in top_owners:
                width_pct = int(count / max_owner * 100) if max_owner > 0 else 0
                owner_bars += f"""
                <div class="bar-row">
                    <div class="bar-label">{html.escape(name)}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width: {width_pct}%; background: {self.COLORS['dim_orange']}">{count}</div>
                    </div>
                </div>"""

        charts_html = f"""
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">问题严重度分布</div>
                {severity_donut}
            </div>
            <div class="chart-container">
                <div class="chart-title">八大维度问题数量</div>
                <div class="bar-chart">{dim_bars}</div>
            </div>
            <div class="chart-container">
                <div class="chart-title">各层级问题分布</div>
                <div class="bar-chart">{level_bars or '<p style="color:#9ca3af;font-size:13px">暂无数据</p>'}</div>
            </div>
            <div class="chart-container">
                <div class="chart-title">TOP5 问题责任人</div>
                <div class="bar-chart">{owner_bars or '<p style="color:#9ca3af;font-size:13px">暂无数据</p>'}</div>
            </div>
        </div>
        """

        return metrics_html + health_section + charts_html

    def _build_indicator_tree_html(self):
        """构建真正的指标拆解树：指标独立成节点并携带上下关系诊断。"""
        try:
            from indicator_tree import build_indicator_tree, build_indicator_tree_html
            tree = self.result.get('indicator_tree') or build_indicator_tree(self.data)
            return build_indicator_tree_html(tree, self.data)
        except Exception as e:
            import sys
            sys.stderr.write(f"[indicator_tree] 指标树生成失败: {e}\n")
            return f'<div class="card"><div class="empty-hint">指标树生成失败：{html.escape(str(e))}。未伪造任何指标关系。</div></div>'

    def _build_goal_tree_html(self):
        """构建目标拆解树 HTML（融入诊断结果和优化建议）"""
        # v2.5：enhanced 模式使用层级强化版（部门分组 + 层级颜色 + 折叠 + 上下关联诊断）
        if self.tree_style == 'enhanced':
            try:
                from tree_view import build_enhanced_tree_html
                return build_enhanced_tree_html(self.result, self.data)
            except Exception as e:
                # 增强视图失败时回退到 legacy，避免报告生成中断
                import sys
                sys.stderr.write(f"[tree_view] 增强视图生成失败，回退 legacy: {e}\n")
        # 按层级分组
        levels = defaultdict(list)
        for goal in self.goals:
            level = goal.get('level', 'L?')
            levels[level].append(goal)

        # 层级统计
        level_stats = " | ".join([f"{lvl}: {len(goals)}个" for lvl, goals in sorted(levels.items())])

        # 构建单个目标节点的辅助函数
        def build_goal_node(goal, is_child=False):
            goal_id = goal.get('goal_id', '')
            node_id = goal_id.replace('-', '_')
            node_class = self._get_goal_node_class(goal)
            owner = html.escape(goal.get('owner_name') or '未知')
            title = html.escape(goal.get('title') or '无标题')
            level = html.escape(goal.get('level') or '')
            progress = int(goal.get('progress', 0) * 100)
            indicators = goal.get('indicators', []) or []

            # 进度条颜色
            if progress >= 80:
                progress_color = self.COLORS['health_green']
            elif progress >= 50:
                progress_color = self.COLORS['warning_yellow']
            else:
                progress_color = self.COLORS['danger_red']

            # 关联的诊断问题
            goal_issues = [i for i in self.issues if i.get('goal_id') == goal_id]
            high_count = len([i for i in goal_issues if i.get('severity') == 'high'])
            medium_count = len([i for i in goal_issues if i.get('severity') == 'medium'])
            low_count = len([i for i in goal_issues if i.get('severity') == 'low'])

            # 问题徽章
            if high_count > 0:
                badge_class = 'high'
                badge_text = f"🔴 {high_count}高"
            elif medium_count > 0:
                badge_class = 'medium'
                badge_text = f"🟡 {medium_count}中"
            elif low_count > 0:
                badge_class = 'low'
                badge_text = f"🔵 {low_count}低"
            else:
                badge_class = 'none'
                badge_text = "✅ 健康"

            # 构建指标列表
            indicator_html = ""
            if indicators:
                indicator_items = ""
                for ind in indicators:
                    ind_name = html.escape(str(ind.get('name', '')))
                    ind_value = html.escape(str(ind.get('value', '')))
                    ind_target = html.escape(str(ind.get('target', '')))
                    ind_unit = html.escape(str(ind.get('unit', '')))
                    indicator_items += f"""
                    <div class="indicator-item">
                        <div class="indicator-name">{ind_name}</div>
                        <div class="indicator-value">{ind_value}{ind_unit} <span class="indicator-target">/ 目标 {ind_target}{ind_unit}</span></div>
                    </div>"""
                indicator_html = f"""
                <div class="detail-section">
                    <div class="detail-section-title">📊 关键指标</div>
                    <div class="indicator-list">{indicator_items}</div>
                </div>"""

            # 构建诊断问题列表（含优化建议）
            issue_html = ""
            if goal_issues:
                # 按严重度排序
                severity_order = {'high': 0, 'medium': 1, 'low': 2}
                sorted_issues = sorted(goal_issues, key=lambda x: severity_order.get(x.get('severity', 'low'), 3))
                issue_items = ""
                for issue in sorted_issues:
                    sev = issue.get('severity', 'low')
                    iss_title = html.escape(issue.get('title') or '')
                    iss_desc = html.escape(issue.get('description') or '')
                    iss_suggestion = html.escape(issue.get('suggestion') or '')
                    iss_dimension = html.escape(issue.get('dimension') or '')
                    suggestion_block = f'<div style="margin-top:4px;color:{self.COLORS["health_green"]};font-weight:500">💡 建议：{iss_suggestion}</div>' if iss_suggestion else ''
                    issue_items += f"""
                    <div class="mini-issue-card {sev}">
                        <div class="mini-issue-title">[{iss_dimension}] {iss_title}</div>
                        <div class="mini-issue-desc">{iss_desc}</div>
                        {suggestion_block}
                    </div>"""
                issue_html = f"""
                <div class="detail-section">
                    <div class="detail-section-title">🔍 诊断问题与优化建议（{len(goal_issues)}个）</div>
                    {issue_items}
                </div>"""

            # 子目标
            children = [g for g in self.goals if goal_id in g.get('parent_goal_ids', [])
                       or goal_id in g.get('aligned_to_goal_ids', [])]
            children_html = ""
            if children:
                child_nodes = ""
                for child in children:
                    child_nodes += build_goal_node(child, is_child=True)
                children_html = f"""
                <div class="detail-section">
                    <div class="detail-section-title">🌿 下级目标（{len(children)}个）</div>
                    <div class="tree-children">{child_nodes}</div>
                </div>"""

            # 如果没有详情内容，显示提示
            if not indicator_html and not issue_html and not children_html:
                detail_content = '<div class="empty-hint" style="padding:12px 0">暂无详细信息</div>'
            else:
                detail_content = indicator_html + issue_html + children_html

            prefix = "└─ " if is_child else ""
            return f"""
            <div class="goal-node {node_class}" id="goal-node-{node_id}">
                <div class="goal-node-header" onclick="toggleGoalNode('{node_id}')">
                    <div class="goal-node-left">
                        <div class="goal-node-title">
                            <span class="expand-icon">▶</span>
                            <span class="issue-badge {badge_class}">{badge_text}</span>
                            {prefix}{title}
                        </div>
                        <div class="goal-node-meta">
                            <span>👤 {owner}</span>
                            <span>🏷️ {level}</span>
                            <span>📊 {len(indicators)}个指标</span>
                        </div>
                    </div>
                    <div class="goal-node-right">
                        <div class="goal-progress-bar">
                            <div class="goal-progress-fill" style="width:{progress}%;background:{progress_color}"></div>
                        </div>
                        <span class="goal-progress-text">{progress}%</span>
                    </div>
                </div>
                <div class="goal-detail-panel">
                    {detail_content}
                </div>
            </div>"""

        # 顶部操作栏
        toolbar = f"""
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
                <div class="card-title" style="margin:0">📊 层级统计：{level_stats}</div>
                <div style="display:flex;gap:8px">
                    <button onclick="expandAllGoals(true)" style="padding:6px 14px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:12px">全部展开</button>
                    <button onclick="expandAllGoals(false)" style="padding:6px 14px;border:1px solid #d1d5db;border-radius:6px;background:white;cursor:pointer;font-size:12px">全部收起</button>
                </div>
            </div>
        </div>"""

        html_parts = [toolbar]

        # 按层级构建
        for level in sorted(levels.keys()):
            level_goals = levels[level]
            html_parts.append(f'<div class="card"><div class="card-title">{level} 层级目标（{len(level_goals)} 个）</div>')
            html_parts.append('<div class="tree-container">')

            for goal in level_goals:
                html_parts.append(build_goal_node(goal))

            html_parts.append('</div></div>')

        return "\n".join(html_parts)

    def _build_diagnosis_html(self):
        """构建诊断结果 HTML"""
        high = self.summary.get('high_count', 0)
        medium = self.summary.get('medium_count', 0)
        low = self.summary.get('low_count', 0)

        # 严重度统计
        stats_html = f"""
        <div class="metrics-grid" style="grid-template-columns: repeat(3, 1fr);">
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['danger_red']}">{high}</div>
                <div class="metric-label">🔴 高严重度</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['warning_yellow']}">{medium}</div>
                <div class="metric-label">🟡 中严重度</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['info_blue']}">{low}</div>
                <div class="metric-label">🔵 低严重度</div>
            </div>
        </div>
        """

        # 八大维度卡片
        by_dimension = self.summary.get('by_dimension', {})
        dimension_descs = {
            '上下层数据不匹配': '上级目标与下级目标合计数据存在偏差',
            '无具体执行人': '目标缺少明确的负责人或主责人',
            '目标重复': '不同部门/人员设置了高度相似的目标',
            '责任不清': '目标边界模糊，多人交叉或真空',
            '未向上对齐': '下级目标未对齐到任何上级目标',
            '层次不准确': '目标粒度过粗/过细，应上移或下移',
            '指标偏离行业基准': '目标指标偏离行业基准值',
            '指标关联性与承接': '上下级指标语义关联性、因果关系等',
        }

        dim_cards = '<div class="dimension-grid">'
        all_dims = list(self.DIMENSION_COLORS.keys())
        for dim in all_dims:
            count = by_dimension.get(dim, 0)
            color = self.DIMENSION_COLORS.get(dim, self.COLORS['info_blue'])
            desc = dimension_descs.get(dim, '')
            dim_cards += f"""
            <div class="dimension-card" style="border-top-color: {color}">
                <div class="dimension-name">{html.escape(dim)}</div>
                <div class="dimension-desc">{desc}</div>
                <div class="dimension-count" style="color: {color if count > 0 else '#d1d5db'}">{count}</div>
            </div>"""
        dim_cards += '</div>'

        # 问题列表（按维度分组）
        issues_by_dim = defaultdict(list)
        for issue in self.issues:
            dim = issue.get('dimension', '其他')
            issues_by_dim[dim].append(issue)

        issue_sections = ""
        for dim, dim_issues in issues_by_dim.items():
            color = self.DIMENSION_COLORS.get(dim, self.COLORS['info_blue'])
            issue_sections += f'<div class="card"><div class="card-title"><span class="dimension-tag" style="background:{color}">{html.escape(dim)}</span>共 {len(dim_issues)} 个问题</div>'
            issue_sections += '<div class="issue-list">'

            # 按严重度排序
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            dim_issues.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))

            for issue in dim_issues:
                severity = issue.get('severity', 'low')
                title = html.escape(issue.get('title') or '')
                desc = html.escape(issue.get('description') or '')
                goal_title = html.escape(issue.get('goal_title') or 'N/A')
                evidence = html.escape(issue.get('evidence') or '')

                issue_sections += f"""
                <div class="issue-card {severity}">
                    <div class="issue-header">
                        <div class="issue-title">{title}</div>
                        <span class="severity-badge severity-{severity}">{self._get_severity_label(severity)}</span>
                    </div>
                    <div class="issue-meta">🎯 关联目标：{goal_title}</div>
                    <div class="issue-desc">{desc}</div>
                    {f'<div class="issue-evidence">📋 证据：{evidence}</div>' if evidence else ''}
                </div>"""

            issue_sections += '</div></div>'

        return stats_html + dim_cards + issue_sections

    def _build_suggestions_html(self):
        """构建优化建议 HTML"""
        if not self.suggestions:
            return '<div class="card"><p style="color:#9ca3af;text-align:center;padding:40px">暂无优化建议</p></div>'

        # 优先级统计
        p0 = len([s for s in self.suggestions if s.get('priority') == 'P0'])
        p1 = len([s for s in self.suggestions if s.get('priority') == 'P1'])
        p2 = len([s for s in self.suggestions if s.get('priority') == 'P2'])

        stats_html = f"""
        <div class="metrics-grid" style="grid-template-columns: repeat(3, 1fr);">
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['danger_red']}">{p0}</div>
                <div class="metric-label">🚨 P0 紧急</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['warning_yellow']}">{p1}</div>
                <div class="metric-label">⚡ P1 重要</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: {self.COLORS['info_blue']}">{p2}</div>
                <div class="metric-label">📌 P2 一般</div>
            </div>
        </div>
        """

        # 按责任人分组
        suggestions_by_owner = defaultdict(list)
        for s in self.suggestions:
            owner = s.get('owner', '待定')
            suggestions_by_owner[owner].append(s)

        groups_html = ""
        for owner, owner_suggestions in suggestions_by_owner.items():
            owner_p0 = len([s for s in owner_suggestions if s.get('priority') == 'P0'])
            owner_p1 = len([s for s in owner_suggestions if s.get('priority') == 'P1'])
            initial = owner[0] if owner else '?'

            groups_html += f"""
            <div class="suggestion-group">
                <div class="suggestion-group-header">
                    <div class="suggestion-avatar">{html.escape(initial)}</div>
                    <div>
                        <div class="suggestion-owner">{html.escape(owner)}</div>
                        <div class="suggestion-count">{len(owner_suggestions)} 条建议
                            {f'· P0×{owner_p0}' if owner_p0 else ''}
                            {f'· P1×{owner_p1}' if owner_p1 else ''}
                        </div>
                    </div>
                </div>
            """

            # 按优先级排序
            priority_order = {'P0': 0, 'P1': 1, 'P2': 2}
            owner_suggestions.sort(key=lambda x: priority_order.get(x.get('priority', 'P2'), 3))

            for s in owner_suggestions:
                priority = s.get('priority', 'P2')
                title = html.escape(s.get('title', ''))
                desc = html.escape(s.get('description', ''))
                deadline = html.escape(s.get('deadline', ''))
                dim = html.escape(s.get('dimension', ''))

                groups_html += f"""
                <div class="suggestion-card">
                    <div class="suggestion-title">
                        <span class="priority-badge priority-{priority}">{priority}</span>
                        {title}
                    </div>
                    <div class="suggestion-desc">{desc}</div>
                    <div class="suggestion-meta">
                        {f'📅 截止：{deadline}' if deadline else ''}
                        {f' · 🏷️ {dim}' if dim else ''}
                    </div>
                </div>"""

            groups_html += '</div>'

        return stats_html + '<div class="card">' + groups_html + '</div>'

    def _build_people_html(self):
        """构建人员视图 HTML"""
        if not self.users:
            return '<div class="card"><p style="color:#9ca3af;text-align:center;padding:40px">暂无人员数据</p></div>'

        # 人员统计
        executives = len([u for u in self.users if u.get('level') in ['L1', '高管']])
        directors = len([u for u in self.users if u.get('level') in ['L2', '总监']])
        employees = len(self.users) - executives - directors

        stats_html = f"""
        <div class="metrics-grid" style="grid-template-columns: repeat(3, 1fr);">
            <div class="metric-card">
                <div class="metric-value">{executives}</div>
                <div class="metric-label">高管</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{directors}</div>
                <div class="metric-label">总监/经理</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{employees}</div>
                <div class="metric-label">员工</div>
            </div>
        </div>
        """

        # 左侧人员列表
        people_list = ""
        detail_panels = ""
        first = True

        for user in self.users:
            user_id = user.get('user_id', '')
            name = user.get('name', '未知')
            position = user.get('position', '')
            initial = name[0] if name else '?'

            # 统计该用户的问题数
            user_issues = [i for i in self.issues if i.get('owner_id') == user_id
                          or i.get('goal_owner') == name]
            issue_count = len(user_issues)

            active_class = 'active' if first else ''
            people_list += f"""
            <div class="person-node {active_class}" onclick="selectPerson('{user_id}', this)">
                <div class="person-avatar">{html.escape(initial)}</div>
                <div class="person-info">
                    <div class="person-name">{html.escape(name)}</div>
                    <div class="person-position">{html.escape(position)}</div>
                </div>
                {f'<div class="issue-badge">{issue_count}</div>' if issue_count > 0 else ''}
            </div>"""

            # 右侧详情面板
            user_goals = [g for g in self.goals if g.get('owner_id') == user_id]
            avg_progress = self._calc_user_avg_progress(user_id)

            display_style = 'block' if first else 'none'
            detail_panels += f"""
            <div id="person-detail-{user_id}" class="person-detail-panel" style="display: {display_style}">
                <div class="person-detail-header">
                    <div class="person-detail-avatar">{html.escape(initial)}</div>
                    <div>
                        <div class="person-detail-name">{html.escape(name)}</div>
                        <div class="person-detail-meta">
                            {html.escape(position)} · {html.escape(user.get('department', ''))} · {html.escape(user.get('level', ''))}
                        </div>
                    </div>
                </div>
                <div class="person-stats">
                    <div class="person-stat">
                        <div class="person-stat-value">{len(user_goals)}</div>
                        <div class="person-stat-label">目标数</div>
                    </div>
                    <div class="person-stat">
                        <div class="person-stat-value">{avg_progress}%</div>
                        <div class="person-stat-label">平均完成率</div>
                    </div>
                    <div class="person-stat">
                        <div class="person-stat-value" style="color: {self.COLORS['danger_red'] if issue_count > 0 else self.COLORS['health_green']}">{issue_count}</div>
                        <div class="person-stat-label">问题数</div>
                    </div>
                </div>
            """

            # 目标列表
            if user_goals:
                detail_panels += '<div class="section-title">📋 目标列表</div>'
                for goal in user_goals:
                    goal_title = html.escape(goal.get('title', '无标题'))
                    progress = int(goal.get('progress', 0) * 100)
                    level = goal.get('level', '')
                    detail_panels += f"""
                    <div class="tree-node" style="margin-bottom: 8px;">
                        <div>
                            <div class="tree-node-title">[{level}] {goal_title}</div>
                        </div>
                        <div class="tree-node-meta">📈 {progress}%</div>
                    </div>"""

            # 关联问题
            if user_issues:
                detail_panels += '<div class="section-title">⚠️ 关联问题</div>'
                for issue in user_issues:
                    severity = issue.get('severity', 'low')
                    title = html.escape(issue.get('title') or '')
                    dim = html.escape(issue.get('dimension') or '')
                    detail_panels += f"""
                    <div class="issue-card {severity}" style="margin-bottom: 8px;">
                        <div class="issue-title">
                            <span class="severity-badge severity-{severity}">{self._get_severity_label(severity)}</span>
                            [{dim}] {title}
                        </div>
                    </div>"""

            detail_panels += '</div>'
            first = False

        layout_html = f"""
        {stats_html}
        <div class="people-layout">
            <div class="people-tree">
                <div class="card-title" style="margin-bottom: 12px;">👥 组织架构</div>
                {people_list}
            </div>
            <div class="people-detail">
                {detail_panels}
            </div>
        </div>
        """

        return layout_html

    # ==================== Markdown 构建方法 ====================

    def _build_dashboard_markdown(self):
        """构建概览 Dashboard Markdown"""
        score = self.summary.get('health_score', 0)
        level = self.summary.get('health_level', '')
        emoji = self._get_health_emoji(score)

        md = []
        md.append("## 📊 页面1：概览 Dashboard")
        md.append("")
        md.append(f"### 综合健康度：{emoji} {score} / 100（{level}）")
        md.append("")
        md.append(self._get_health_description(score))
        md.append("")

        # 核心指标
        md.append("### 核心指标")
        md.append("")
        md.append("| 指标 | 数值 |")
        md.append("|------|------|")
        md.append(f"| 整体健康度 | {score} / 100 |")
        md.append(f"| 目标总数 | {self.summary.get('total_goals', len(self.goals))} |")
        md.append(f"| 平均完成率 | {self._calc_avg_progress()}% |")
        md.append(f"| 问题总数 | {self.summary.get('total_issues', len(self.issues))} |")
        md.append(f"| 高严重度问题 | {self.summary.get('high_count', 0)} |")
        md.append(f"| 涉及人员 | {len(self.users)} |")
        md.append("")

        # 严重度分布
        md.append("### 问题严重度分布")
        md.append("")
        high = self.summary.get('high_count', 0)
        medium = self.summary.get('medium_count', 0)
        low = self.summary.get('low_count', 0)
        md.append(f"- 🔴 高严重度：{high} 个")
        md.append(f"- 🟡 中严重度：{medium} 个")
        md.append(f"- 🔵 低严重度：{low} 个")
        md.append("")

        # 各维度问题分布
        by_dimension = self.summary.get('by_dimension', {})
        if by_dimension:
            md.append("### 八大维度问题分布")
            md.append("")
            md.append("| 诊断维度 | 问题数 |")
            md.append("|----------|--------|")
            for dim, count in sorted(by_dimension.items(), key=lambda x: -x[1]):
                md.append(f"| {dim} | {count} |")
            md.append("")

        # TOP5 问题责任人
        top_owners = self._get_top_issue_owners(5)
        if top_owners:
            md.append("### TOP5 问题责任人")
            md.append("")
            md.append("| 排名 | 责任人 | 问题数 |")
            md.append("|------|--------|--------|")
            for i, (name, count) in enumerate(top_owners, 1):
                md.append(f"| {i} | {name} | {count} |")
            md.append("")

        return md

    def _build_indicator_tree_markdown(self):
        """构建指标拆解树 Markdown 摘要和关系清单。"""
        tree = self.result.get('indicator_tree', {}) or {}
        summary = tree.get('summary', {})
        nodes = {n.get('indicator_id'): n for n in tree.get('nodes', [])}
        md = ["## 🌳 页面2：指标拆解树与上下关联诊断", ""]
        md.append(summary.get('provenance_notice', ''))
        md.append("")
        md.append("| 项目 | 数量 |")
        md.append("|---|---:|")
        md.append(f"| 独立指标节点 | {summary.get('total_nodes', 0)} |")
        md.append(f"| 显式关系（实线） | {summary.get('explicit_edges', 0)} |")
        md.append(f"| 语义推断（虚线） | {summary.get('inferred_edges', 0)} |")
        md.append(f"| 用户确认/改选关系 | {summary.get('user_confirmed_edges', 0)} |")
        md.append(f"| 已应用人工决策 | {summary.get('applied_decision_count', 0)} |")
        md.append(f"| 关系数据缺口 | {summary.get('data_gap_count', 0)} |")
        md.append("")
        if summary.get('explicit_edges', 0) == 0:
            md.append("> **数据质量提示**：输入没有指标级显式父子关系；推断边仅为候选关系，需人工复核。")
            md.append("")
        md.append("### 指标关系（逐边可审计）")
        md.append("")
        if tree.get('edges'):
            md.append("| 来源 | 上级指标 | 下级指标 | 关系质量 | 诊断 |")
            md.append("|---|---|---|---:|---|")
            for edge in tree.get('edges', []):
                parent = nodes.get(edge.get('parent_indicator_id'), {})
                child = nodes.get(edge.get('child_indicator_id'), {})
                source = {
                    'explicit': '显式',
                    'semantic_inference': '推断（需复核）',
                    'user_confirmed': '用户确认/改选',
                }.get(edge.get('source'), edge.get('source', '未知'))
                diagnosis = str(edge.get('diagnosis', '')).replace('|', '｜')
                md.append(f"| {source} | {parent.get('name', '')} | {child.get('name', '')} | {edge.get('relationship_score', 0):.0%} | {diagnosis} |")
        else:
            md.append("未识别到可成立的指标关系。")
        md.append("")
        if tree.get('data_gaps'):
            md.append("### 关系数据缺口")
            md.append("")
            for gap in tree.get('data_gaps', []):
                node = nodes.get(gap.get('indicator_id'), {})
                md.append(f"- **{node.get('name', '未命名指标')}**（{node.get('level', '')} / {node.get('goal_title', '')}）：{gap.get('reason', '')}")
        return md

    def _build_goal_tree_markdown(self):
        """构建目标拆解树 Markdown（v2.4：融入诊断结果和优化建议）"""
        md = []
        md.append("## 🎯 页面3：目标拆解树")
        md.append("")

        # 按层级分组
        levels = defaultdict(list)
        for goal in self.goals:
            level = goal.get('level', 'L?')
            levels[level].append(goal)

        # 层级统计
        stats = " | ".join([f"{lvl}: {len(goals)}个" for lvl, goals in sorted(levels.items())])
        md.append(f"**层级统计**：{stats}")
        md.append("")

        # 构建 goal_id → 问题列表 索引
        issues_by_goal = defaultdict(list)
        for issue in self.issues:
            goal_id = issue.get('goal_id')
            if goal_id:
                issues_by_goal[goal_id].append(issue)

        # 构建 goal_id → 建议列表 索引
        suggestions_by_goal = defaultdict(list)
        for sug in self.suggestions:
            goal_id = sug.get('goal_id')
            if goal_id:
                suggestions_by_goal[goal_id].append(sug)

        for level in sorted(levels.keys()):
            level_goals = levels[level]
            md.append(f"### {level} 层级（{len(level_goals)} 个目标）")
            md.append("")

            for goal in level_goals:
                goal_id = goal.get('goal_id', '')
                owner = goal.get('owner_name', '未知')
                title = goal.get('title', '无标题')
                progress = int(goal.get('progress', 0) * 100)
                indicators = goal.get('indicators', [])

                # 关联的问题和建议
                goal_issues = issues_by_goal.get(goal_id, [])
                goal_suggestions = suggestions_by_goal.get(goal_id, [])

                # 问题徽章
                if goal_issues:
                    high_count = len([i for i in goal_issues if i.get('severity') == 'high'])
                    medium_count = len([i for i in goal_issues if i.get('severity') == 'medium'])
                    low_count = len([i for i in goal_issues if i.get('severity') == 'low'])
                    badge_parts = []
                    if high_count: badge_parts.append(f"🔴{high_count}高")
                    if medium_count: badge_parts.append(f"🟡{medium_count}中")
                    if low_count: badge_parts.append(f"🔵{low_count}低")
                    badge = f" {' '.join(badge_parts)}"
                else:
                    badge = " ✅健康"

                md.append(f"- **{title}**{badge}")
                md.append(f"  - 👤 负责人：{owner}")
                md.append(f"  - 📈 进度：{progress}%")

                # 指标列表
                if indicators:
                    md.append(f"  - 📊 关键指标（{len(indicators)}个）：")
                    for ind in indicators:
                        ind_name = ind.get('name', '未命名')
                        ind_current = ind.get('current_value', 'N/A')
                        ind_target = ind.get('target_value', 'N/A')
                        md.append(f"    - {ind_name}：当前 {ind_current} / 目标 {ind_target}")
                else:
                    md.append(f"  - 📊 无指标")

                # 关联诊断问题
                if goal_issues:
                    md.append(f"  - 🔍 诊断问题（{len(goal_issues)}个）：")
                    # 按严重度排序
                    severity_order = {'high': 0, 'medium': 1, 'low': 2}
                    goal_issues.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))
                    for issue in goal_issues:
                        severity = issue.get('severity', 'low')
                        severity_emoji = '🔴' if severity == 'high' else ('🟡' if severity == 'medium' else '🔵')
                        issue_title = issue.get('title', '')
                        issue_desc = issue.get('description', '')
                        dim = issue.get('dimension', '')
                        md.append(f"    - {severity_emoji} **[{dim}] {issue_title}**")
                        if issue_desc:
                            md.append(f"      - {issue_desc[:150]}")
                        # 关联建议
                        issue_sugs = [s for s in goal_suggestions if s.get('issue_id') == issue.get('issue_id')]
                        for sug in issue_sugs:
                            priority = sug.get('priority', 'P2')
                            sug_text = sug.get('suggestion', sug.get('title', ''))
                            md.append(f"      - 💡 [{priority}] {sug_text[:120]}")

                # 未关联到具体问题的建议
                orphan_sugs = [s for s in goal_suggestions if not s.get('issue_id')]
                if orphan_sugs:
                    md.append(f"  - 💡 优化建议（{len(orphan_sugs)}条）：")
                    for sug in orphan_sugs:
                        priority = sug.get('priority', 'P2')
                        sug_text = sug.get('suggestion', sug.get('title', ''))
                        md.append(f"    - [{priority}] {sug_text[:150]}")

                # 子目标
                children = [g for g in self.goals if goal.get('goal_id') in g.get('parent_goal_ids', [])
                           or goal.get('goal_id') in g.get('aligned_to_goal_ids', [])]
                if children:
                    md.append(f"  - 📂 子目标（{len(children)}个）：")
                    for child in children:
                        child_owner = child.get('owner_name', '未知')
                        child_title = child.get('title', '无标题')
                        child_progress = int(child.get('progress', 0) * 100)
                        child_id = child.get('goal_id', '')
                        child_issues = issues_by_goal.get(child_id, [])
                        child_badge = f" 🔴{len([i for i in child_issues if i.get('severity')=='high'])}" if child_issues else " ✅"
                        md.append(f"    - [{child.get('level', '')}] {child_title}（{child_owner}, {child_progress}%）{child_badge}")

                md.append("")

        return md

    def _build_diagnosis_markdown(self):
        """构建诊断结果 Markdown"""
        md = []
        md.append("## 🔍 页面4：诊断结果")
        md.append("")

        high = self.summary.get('high_count', 0)
        medium = self.summary.get('medium_count', 0)
        low = self.summary.get('low_count', 0)
        md.append(f"**严重度统计**：🔴 高 {high} 个 | 🟡 中 {medium} 个 | 🔵 低 {low} 个")
        md.append("")

        if not self.issues:
            md.append("> ✅ 未发现诊断问题，目标拆解质量良好！")
            return md

        # 按维度分组
        issues_by_dim = defaultdict(list)
        for issue in self.issues:
            dim = issue.get('dimension', '其他')
            issues_by_dim[dim].append(issue)

        for dim, dim_issues in issues_by_dim.items():
            md.append(f"### 🏷️ {dim}（{len(dim_issues)} 个问题）")
            md.append("")

            # 按严重度排序
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            dim_issues.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))

            for i, issue in enumerate(dim_issues, 1):
                severity = issue.get('severity', 'low')
                severity_label = self._get_severity_label(severity)
                severity_emoji = '🔴' if severity == 'high' else ('🟡' if severity == 'medium' else '🔵')
                title = issue.get('title', '')
                desc = issue.get('description', '')
                goal_title = issue.get('goal_title', 'N/A')
                evidence = issue.get('evidence', '')

                md.append(f"**{i}. {severity_emoji} [{severity_label}] {title}**")
                md.append(f"- 🎯 关联目标：{goal_title}")
                md.append(f"- 📝 问题描述：{desc}")
                if evidence:
                    md.append(f"- 📋 证据：{evidence}")
                md.append("")

        return md

    def _build_suggestions_markdown(self):
        """构建优化建议 Markdown"""
        md = []
        md.append("## 💡 页面5：优化建议")
        md.append("")

        if not self.suggestions:
            md.append("> ✅ 暂无优化建议")
            return md

        # 优先级统计
        p0 = len([s for s in self.suggestions if s.get('priority') == 'P0'])
        p1 = len([s for s in self.suggestions if s.get('priority') == 'P1'])
        p2 = len([s for s in self.suggestions if s.get('priority') == 'P2'])
        md.append(f"**优先级统计**：🚨 P0 {p0} 条 | ⚡ P1 {p1} 条 | 📌 P2 {p2} 条")
        md.append("")

        # 按责任人分组
        suggestions_by_owner = defaultdict(list)
        for s in self.suggestions:
            owner = s.get('owner', '待定')
            suggestions_by_owner[owner].append(s)

        for owner, owner_suggestions in suggestions_by_owner.items():
            md.append(f"### 👤 {owner}（{len(owner_suggestions)} 条建议）")
            md.append("")

            # 按优先级排序
            priority_order = {'P0': 0, 'P1': 1, 'P2': 2}
            owner_suggestions.sort(key=lambda x: priority_order.get(x.get('priority', 'P2'), 3))

            for i, s in enumerate(owner_suggestions, 1):
                priority = s.get('priority', 'P2')
                priority_emoji = '🚨' if priority == 'P0' else ('⚡' if priority == 'P1' else '📌')
                title = s.get('title', '')
                desc = s.get('description', '')
                deadline = s.get('deadline', '')
                dim = s.get('dimension', '')

                md.append(f"**{i}. {priority_emoji} [{priority}] {title}**")
                md.append(f"- 💬 建议内容：{desc}")
                if deadline:
                    md.append(f"- 📅 截止时间：{deadline}")
                if dim:
                    md.append(f"- 🏷️ 问题维度：{dim}")
                md.append("")

        return md

    def _build_people_markdown(self):
        """构建人员视图 Markdown"""
        md = []
        md.append("## 👥 页面6：人员视图")
        md.append("")

        if not self.users:
            md.append("> 暂无人员数据")
            return md

        # 人员统计
        executives = len([u for u in self.users if u.get('level') in ['L1', '高管']])
        directors = len([u for u in self.users if u.get('level') in ['L2', '总监']])
        employees = len(self.users) - executives - directors
        md.append(f"**人员分类**：高管 {executives} 名 | 总监/经理 {directors} 名 | 员工 {employees} 名")
        md.append("")

        # 人员列表表格
        md.append("### 人员概览")
        md.append("")
        md.append("| 姓名 | 职位 | 部门 | 层级 | 目标数 | 问题数 | 平均完成率 |")
        md.append("|------|------|------|------|--------|--------|-----------|")

        for user in self.users:
            user_id = user.get('user_id', '')
            name = user.get('name', '未知')
            position = user.get('position', '')
            department = user.get('department', '')
            level = user.get('level', '')
            user_goals = [g for g in self.goals if g.get('owner_id') == user_id]
            user_issues = [i for i in self.issues if i.get('owner_id') == user_id
                          or i.get('goal_owner') == name]
            avg_progress = self._calc_user_avg_progress(user_id)

            md.append(f"| {name} | {position} | {department} | {level} | {len(user_goals)} | {len(user_issues)} | {avg_progress}% |")
        md.append("")

        # 每人详情
        md.append("### 人员详情")
        md.append("")
        for user in self.users:
            user_id = user.get('user_id', '')
            name = user.get('name', '未知')
            position = user.get('position', '')
            user_goals = [g for g in self.goals if g.get('owner_id') == user_id]
            user_issues = [i for i in self.issues if i.get('owner_id') == user_id
                          or i.get('goal_owner') == name]

            md.append(f"#### 👤 {name}（{position}）")
            md.append("")

            if user_goals:
                md.append("**目标列表：**")
                for goal in user_goals:
                    goal_title = goal.get('title', '无标题')
                    progress = int(goal.get('progress', 0) * 100)
                    goal_level = goal.get('level', '')
                    md.append(f"- [{goal_level}] {goal_title}（{progress}%）")
                md.append("")

            if user_issues:
                md.append("**关联问题：**")
                for issue in user_issues:
                    severity = issue.get('severity', 'low')
                    severity_emoji = '🔴' if severity == 'high' else ('🟡' if severity == 'medium' else '🔵')
                    title = issue.get('title', '')
                    dim = issue.get('dimension', '')
                    md.append(f"- {severity_emoji} [{dim}] {title}")
                md.append("")

        return md

    # ==================== 辅助方法 ====================

    def _get_health_color(self, score):
        """获取健康度颜色"""
        if score >= 90:
            return self.COLORS['health_green']
        elif score >= 70:
            return self.COLORS['info_blue']
        elif score >= 50:
            return self.COLORS['warning_yellow']
        else:
            return self.COLORS['danger_red']

    def _get_health_emoji(self, score):
        """获取健康度 emoji"""
        if score >= 90:
            return '🟢'
        elif score >= 70:
            return '🔵'
        elif score >= 50:
            return '🟡'
        else:
            return '🔴'

    def _get_health_description(self, score):
        """获取健康度描述"""
        if score >= 90:
            return "目标拆解质量很高，各维度表现优秀，继续保持。建议关注细节优化和持续改进。"
        elif score >= 70:
            return "整体不错，有少量优化空间。建议重点关注高严重度问题，及时调整目标拆解策略。"
        elif score >= 50:
            return "有明显问题，需要改进。建议优先解决高严重度问题，完善目标对齐和责任分配。"
        else:
            return "问题较多，建议重点优化。建议重新审视目标拆解逻辑，明确责任人和对齐关系。"

    def _get_severity_label(self, severity):
        """获取严重度标签"""
        labels = {'high': '高', 'medium': '中', 'low': '低'}
        return labels.get(severity, '低')

    def _calc_avg_progress(self):
        """计算平均完成率"""
        if not self.goals:
            return 0
        progresses = [g.get('progress', 0) for g in self.goals]
        return int(sum(progresses) / len(progresses) * 100)

    def _calc_user_avg_progress(self, user_id):
        """计算用户平均完成率"""
        user_goals = [g for g in self.goals if g.get('owner_id') == user_id]
        if not user_goals:
            return 0
        progresses = [g.get('progress', 0) for g in user_goals]
        return int(sum(progresses) / len(progresses) * 100)

    def _count_issues_by_level(self):
        """按层级统计问题数"""
        level_count = defaultdict(int)
        goal_level_map = {g.get('goal_id'): g.get('level', 'L?') for g in self.goals}
        for issue in self.issues:
            goal_id = issue.get('goal_id', '')
            level = goal_level_map.get(goal_id, 'L?')
            level_count[level] += 1
        return level_count

    def _get_top_issue_owners(self, top_n=5):
        """获取问题最多的前N个责任人"""
        owner_count = defaultdict(int)
        goal_owner_map = {g.get('goal_id'): g.get('owner_name', '未知') for g in self.goals}

        for issue in self.issues:
            # 优先使用 issue 中的 owner_id 对应的人名
            owner_id = issue.get('owner_id', '')
            if owner_id:
                owner = next((u.get('name', '未知') for u in self.users if u.get('user_id') == owner_id), None)
                if owner:
                    owner_count[owner] += 1
                    continue
            # 其次使用 goal_id 对应的目标负责人
            goal_id = issue.get('goal_id', '')
            if goal_id and goal_id in goal_owner_map:
                owner_count[goal_owner_map[goal_id]] += 1
            else:
                owner_count[issue.get('goal_owner', '未知')] += 1

        return sorted(owner_count.items(), key=lambda x: -x[1])[:top_n]

    def _get_goal_node_class(self, goal):
        """获取目标节点样式类"""
        goal_id = goal.get('goal_id', '')
        goal_issues = [i for i in self.issues if i.get('goal_id') == goal_id]
        high_count = len([i for i in goal_issues if i.get('severity') == 'high'])

        if high_count > 0:
            return 'danger'
        elif len(goal_issues) > 0:
            return 'warning'
        else:
            return 'health'

    def _build_donut_html(self, items, total):
        """构建环形图 HTML（CSS conic-gradient 模拟）"""
        if total == 0:
            return '<div style="text-align:center;color:#9ca3af;padding:20px">暂无数据</div>'

        # 计算各部分角度
        colors = []
        current = 0
        for name, count, color in items:
            if count > 0:
                pct = count / total * 100
                colors.append(f"{color} {current}% {current + pct}%")
                current += pct

        gradient = ", ".join(colors)
        donut_style = f"background: conic-gradient({gradient});"

        legend = ""
        for name, count, color in items:
            if count > 0:
                pct = int(count / total * 100)
                legend += f"""
                <div class="legend-item">
                    <div class="legend-dot" style="background: {color}"></div>
                    <span>{name}: {count} ({pct}%)</span>
                </div>"""

        return f"""
        <div class="donut-chart">
            <div class="donut" style="{donut_style}">
                <div class="donut-inner">{total}个</div>
            </div>
            <div class="donut-legend">{legend}</div>
        </div>
        """
