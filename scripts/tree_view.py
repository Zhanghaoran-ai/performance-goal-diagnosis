# -*- coding: utf-8 -*-
"""
tree_view.py — 层级强化版目标拆解树渲染器（v2.5 新增）

在标准输出框架的"目标拆解树"页面之上，提供更强的层级呈现与上下关联诊断：

1. 部门分组卡片：5 个部门以彩色卡片分组，部门头含图标/名称/负责人/进度/问题数，可折叠
2. 层级强化区分：L2 蓝 / L3 紫 / L4 灰，彩色左缘条 + 层级徽标 + 缩进逐级递进
3. 上下关联诊断：点击任意节点，右侧面板展示 路径 / 指标 / ↑父级对齐 / ↓子级承接 / 自身结构问题
4. 四层语义关联：语义层基于 semantic_utils.assess_relationship 四层判断（词面/语义/因果/数值链路）

用法（由 standard_report.py 调用，也可独立使用）：
    from tree_view import build_enhanced_tree_html
    html_fragment = build_enhanced_tree_html(result, data)

返回：可直接嵌入页面 body 的 HTML 片段（含内联 style + script）。
"""

import html as html_mod
from collections import defaultdict

# 部门图标映射（可扩展）
DEPT_ICONS = {
    '人力资源部': '👥',
    '产品研发部': '🛠️',
    '产品部': '📦',
    '市场部': '📣',
    '销售部': '💼',
    '财务部': '💰',
    '客户成功部': '🤝',
    '客服部': '🎧',
    '技术部': '💻',
    '运营部': '⚙️',
    '法务部': '⚖️',
}

# 层级样式（颜色 / 背景 / 左缘条 / 缩进）
LEVEL_STYLE = {
    'L1': {'badge': 'L1', 'color': '#0f766e', 'bg': '#f0fdfa', 'bar': '#14b8a6', 'indent': 0, 'weight': 700},
    'L2': {'badge': 'L2', 'color': '#1d4ed8', 'bg': '#eff6ff', 'bar': '#2563eb', 'indent': 0, 'weight': 700},
    'L3': {'badge': 'L3', 'color': '#6d28d9', 'bg': '#f5f3ff', 'bar': '#8b5cf6', 'indent': 30, 'weight': 600},
    'L4': {'badge': 'L4', 'color': '#475569', 'bg': '#f1f5f9', 'bar': '#94a3b8', 'indent': 60, 'weight': 500},
}


def _esc(s):
    return html_mod.escape(str(s if s is not None else ''))


def _dept_icon(dept):
    return DEPT_ICONS.get(dept, '🏢')


def _collect_nodes(result, data):
    """
    从诊断结果 + 输入数据构建节点统一结构。

    返回：
      nodes:  {goal_id: {id, level, title, owner, department, progress, indicators, children[]}}
      parents: {goal_id: parent_goal_id}
      issues_by_goal: {goal_id: [issue,...]}
    """
    goals = {}
    # 优先从输入 data 取完整信息
    for g in (data.get('goals') or []):
        gid = g.get('goal_id') or g.get('id')
        if not gid:
            continue
        goals[gid] = {
            'id': gid,
            'level': g.get('level', 'L?'),
            'title': g.get('title') or g.get('name') or gid,
            'owner': g.get('owner_name') or g.get('owner') or '',
            'department': g.get('department') or '',
            'progress': g.get('progress'),
            'indicators': g.get('indicators') or [],
            'parent_goal_ids': g.get('parent_goal_ids') or [],
            'aligned_to_goal_ids': g.get('aligned_to_goal_ids') or [],
        }
        # 补 KR 作为指标（若无 indicators）
        if not goals[gid]['indicators'] and g.get('key_results'):
            goals[gid]['indicators'] = [
                {'name': kr.get('title', ''), 'value': kr.get('progress', '')}
                for kr in g.get('key_results') or []
            ]

    # 从 goal_tree 补 children 关系
    goal_tree = result.get('goal_tree') or {}
    for level, items in goal_tree.items():
        for it in items:
            gid = it.get('goal_id')
            if not gid or gid not in goals:
                continue
            goals[gid]['children'] = it.get('children') or []
            if it.get('owner'):
                goals[gid]['owner'] = it['owner']
            if it.get('title'):
                goals[gid]['title'] = it['title']
            if it.get('progress') is not None:
                goals[gid]['progress'] = it['progress']

    # 兜底：若某些节点只在 goal_tree 里，则创建
    for level, items in goal_tree.items():
        for it in items:
            gid = it.get('goal_id')
            if gid and gid not in goals:
                goals[gid] = {
                    'id': gid, 'level': level,
                    'title': it.get('title') or gid,
                    'owner': it.get('owner') or '',
                    'department': '',
                    'progress': it.get('progress'),
                    'indicators': [],
                    'children': it.get('children') or [],
                    'parent_goal_ids': [], 'aligned_to_goal_ids': [],
                }

    # 建立 parent 映射
    parents = {}
    for gid, node in goals.items():
        for ch in node.get('children') or []:
            if ch in goals:
                parents[ch] = gid

    # issues 按 goal_id 分组
    issues_by_goal = defaultdict(list)
    for issue in (result.get('issues') or []):
        gid = issue.get('goal_id')
        if gid:
            issues_by_goal[gid].append(issue)
        # 无 goal_id 但 title 含 owner 名时，尝试关联
        elif issue.get('owner_id'):
            for g in goals.values():
                if g['owner'] == issue.get('owner_id'):
                    issues_by_goal[g['id']].append(issue)
                    break

    return goals, parents, issues_by_goal


def _progress_color(p):
    p = p if p is not None else 0
    if p >= 0.8:
        return '#10b981'
    if p >= 0.5:
        return '#f59e0b'
    return '#ef4444'


def _severity_count(issues):
    high = sum(1 for i in issues if i.get('severity') == 'high')
    med = sum(1 for i in issues if i.get('severity') == 'medium')
    low = sum(1 for i in issues if i.get('severity') == 'low')
    return high, med, low


def _issue_badge(issues):
    high, med, low = _severity_count(issues)
    if high > 0:
        return f'🔴 {high}高', 'high'
    if med > 0:
        return f'🟡 {med}中', 'medium'
    if low > 0:
        return f'🔵 {low}低', 'low'
    return '✅ 健康', 'none'


def build_enhanced_tree_html(result, data):
    """
    构建层级强化版目标拆解树 HTML 片段。

    参数：
      result: 诊断结果 dict（含 summary/issues/suggestions/goal_tree）
      data:   输入数据 dict（含 goals/users/meta）

    返回：HTML 字符串（含 style + script + 树结构 + 诊断面板）。
    """
    goals, parents, issues_by_goal = _collect_nodes(result, data)

    # —— 部门分组 ——
    depts = defaultdict(list)
    for gid, node in goals.items():
        dept = node['department'] or '未分配部门'
        depts[dept].append(node)

    # 部门排序：按 L2 数降序，再按部门名
    def _dept_key(item):
        dept, nodes = item
        l2 = sum(1 for n in nodes if n['level'] == 'L2')
        return (-l2, dept)
    ordered_depts = sorted(depts.items(), key=_dept_key)

    # —— 部门问题数统计 ——
    def _dept_issue_total(nodes):
        return sum(len(issues_by_goal.get(n['id'], [])) for n in nodes)

    # —— 部门头平均进度（L2 优先） ——
    def _dept_progress(nodes):
        l2 = [n for n in nodes if n['level'] == 'L2']
        pool = l2 or nodes
        vals = [n['progress'] for n in pool if n.get('progress') is not None]
        return sum(vals) / len(vals) if vals else None

    # —— 构建部门卡片 ——
    dept_html = []
    for dept, nodes in ordered_depts:
        total_issues = _dept_issue_total(nodes)
        avg_p = _dept_progress(nodes)
        p_text = f"{round(avg_p * 100)}%" if avg_p is not None else "—"
        p_color = _progress_color(avg_p if avg_p is not None else 0)
        icon = _dept_icon(dept)
        l2_nodes = [n for n in nodes if n['level'] == 'L2']
        l2_owner = l2_nodes[0]['owner'] if l2_nodes else (nodes[0]['owner'] if nodes else '')
        gid_of_l2 = l2_nodes[0]['id'] if l2_nodes else (nodes[0]['id'] if nodes else '')

        # 部门内按层级排序渲染
        level_order = {'L1': 0, 'L2': 1, 'L3': 2, 'L4': 3, 'L?': 9}
        sorted_nodes = sorted(nodes, key=lambda n: level_order.get(n['level'], 9))

        node_html = []
        for node in sorted_nodes:
            nid = node['id']
            lvl = node['level']
            style = LEVEL_STYLE.get(lvl, LEVEL_STYLE['L4'])
            issues = issues_by_goal.get(nid, [])
            badge_text, badge_cls = _issue_badge(issues)
            title = _esc(node['title'])
            owner = _esc(node['owner'])
            p = node.get('progress')
            p_t = pct_text = f"{round(p * 100)}%" if p is not None else "—"
            p_c = _progress_color(p if p is not None else 0)
            n_inds = len(node.get('indicators') or [])
            # 是否部门头（L2 首节点）
            is_dept_head = (node is l2_nodes[0]) if l2_nodes else False

            indicator_summary = ""
            inds = node.get('indicators') or []
            if inds:
                names = "、".join(_esc(i.get('name', '')) for i in inds[:3])
                more = f" 等{len(inds)}项" if len(inds) > 3 else ""
                indicator_summary = f'<span class="node-inds">📊 {names}{more}</span>'

            # 左侧缘条 + 层级徽标 + 标题
            node_html.append(f'''
            <li class="tnode" data-id="{_esc(nid)}" data-parent="{_esc(parents.get(nid, ''))}"
                style="margin-left:{style['indent']}px;border-left:4px solid {style['bar']};background:{style['bg']};">
                <div class="node-row">
                    <span class="lv-badge" style="background:{style['color']}">{style['badge']}</span>
                    <span class="node-title" style="font-weight:{style['weight']}">{title}</span>
                    <span class="node-owner">· {owner}</span>
                    <span class="issue-badge {badge_cls}">{badge_text}</span>
                    <span class="node-progress" style="color:{p_c}">{p_t}</span>
                </div>
                {indicator_summary}
            </li>''')

        children_html = "\n".join(node_html)
        # 部门头：可折叠
        dept_html.append(f'''
        <div class="dept-card" style="border-top:3px solid {p_color};">
            <div class="dept-head" data-id="{_esc(gid_of_l2)}">
                <span class="dept-icon">{icon}</span>
                <span class="dept-name">{_esc(dept)}</span>
                <span class="dept-owner">{_esc(l2_owner)} · {p_text}</span>
                <span class="dept-issues">● {total_issues} 问题</span>
                <span class="dept-toggle">▾</span>
            </div>
            <ul class="tlist">{children_html}</ul>
        </div>''')

    dept_section = "\n".join(dept_html)

    # —— 序列化节点数据供 JS 使用 ——
    js_nodes = []
    for gid, node in goals.items():
        js_nodes.append({
            'id': gid,
            'level': node['level'],
            'title': node['title'],
            'owner': node['owner'],
            'department': node['department'],
            'progress': node['progress'],
            'children': node.get('children') or [],
            'parent': parents.get(gid, ''),
            'inds': [
                {'name': i.get('name', ''), 'value': i.get('value', ''),
                 'unit': i.get('unit', '')}
                for i in (node.get('indicators') or [])
            ],
            'issues': [
                {'severity': i.get('severity', 'low'), 'dimension': i.get('dimension', ''),
                 'title': i.get('title', ''), 'description': i.get('description', ''),
                 'suggestion': i.get('suggestion', '')}
                for i in issues_by_goal.get(gid, [])
            ],
        })
    # JSON 直接嵌入 <script>，无需 HTML 转义（JSON 不含 <script> 标记）
    js_nodes_json = json_dumps(js_nodes)

    # 统计
    total_goals = len(goals)
    total_depts = len(ordered_depts)
    level_counts = defaultdict(int)
    for n in goals.values():
        level_counts[n['level']] += 1
    level_stat = " · ".join(f"{lvl} {level_counts[lvl]}个" for lvl in sorted(level_counts))

    return (_TREE_TEMPLATE
            .replace('__TOTAL_GOALS__', str(total_goals))
            .replace('__TOTAL_DEPTS__', str(total_depts))
            .replace('__LEVEL_STAT__', level_stat)
            .replace('__DEPT_SECTION__', dept_section)
            .replace('__JS_NODES__', js_nodes_json))


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


_TREE_TEMPLATE = """<style>
.tree-v2 { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 14px; }
.tree-v2 .tree-layout { display: flex; gap: 16px; align-items: flex-start; }
.tree-v2 .tree-main { flex: 1 1 60%; min-width: 0; }
.tree-v2 .detail-panel { flex: 0 0 40%; max-width: 460px; position: sticky; top: 16px; background: white; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 2px 8px rgba(0,0,0,0.06); padding: 16px; max-height: 78vh; overflow-y: auto; }
.tree-v2 .dept-card { background: white; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 1px 4px rgba(0,0,0,0.05); margin-bottom: 14px; overflow: hidden; }
.tree-v2 .dept-head { display: flex; align-items: center; gap: 10px; padding: 12px 16px; cursor: pointer; user-select: none; background: #f8fafc; font-weight: 600; }
.tree-v2 .dept-head:hover { background: #f1f5f9; }
.tree-v2 .dept-icon { font-size: 18px; }
.tree-v2 .dept-name { font-size: 15px; font-weight: 700; }
.tree-v2 .dept-owner { font-size: 12px; color: #64748b; }
.tree-v2 .dept-issues { font-size: 12px; color: #ef4444; font-weight: 600; margin-left: auto; }
.tree-v2 .dept-toggle { color: #94a3b8; transition: transform .2s; }
.tree-v2 .dept-card.collapsed .dept-toggle { transform: rotate(-90deg); }
.tree-v2 .dept-card.collapsed .tlist { display: none; }
.tree-v2 .tlist { list-style: none; margin: 0; padding: 8px 12px 12px; }
.tree-v2 .tnode { border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; cursor: pointer; transition: transform .15s, box-shadow .15s; }
.tree-v2 .tnode:hover { transform: translateX(2px); box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.tree-v2 .tnode.sel { outline: 2px solid #2563eb; }
.tree-v2 .node-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tree-v2 .lv-badge { color: white; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; flex-shrink: 0; }
.tree-v2 .node-title { font-size: 13px; }
.tree-v2 .node-owner { font-size: 12px; color: #64748b; }
.tree-v2 .node-progress { font-size: 12px; font-weight: 600; margin-left: auto; }
.tree-v2 .node-inds { display: block; font-size: 11px; color: #94a3b8; margin-top: 4px; }
.tree-v2 .issue-badge { font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 9px; }
.tree-v2 .issue-badge.high { background: #fee2e2; color: #ef4444; }
.tree-v2 .issue-badge.medium { background: #fef3c7; color: #d97706; }
.tree-v2 .issue-badge.low { background: #dbeafe; color: #2563eb; }
.tree-v2 .issue-badge.none { background: #d1fae5; color: #10b981; }
.tree-v2 .detail-panel h4 { margin: 10px 0 6px; font-size: 13px; color: #334155; }
.tree-v2 .crumb { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; }
.tree-v2 .ind-item { display: flex; justify-content: space-between; gap: 8px; padding: 5px 0; border-bottom: 1px dashed #eef2f7; font-size: 12px; }
.tree-v2 .ind-item .iv { color: #475569; font-weight: 600; }
.tree-v2 .rel-item { padding: 8px 10px; border-radius: 6px; margin-bottom: 6px; font-size: 12px; background: #f8fafc; border-left: 3px solid #94a3b8; }
.tree-v2 .rel-item.strong { border-left-color: #10b981; }
.tree-v2 .rel-item.weak { border-left-color: #f59e0b; }
.tree-v2 .rel-item.none { border-left-color: #ef4444; }
.tree-v2 .rel-item .rt { font-weight: 600; }
.tree-v2 .rel-item .rd { color: #64748b; margin-top: 2px; }
.tree-v2 .empty { color: #94a3b8; font-size: 13px; padding: 20px; text-align: center; }
.tree-v2 .tree-toolbar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.tree-v2 .tree-toolbar .tt-title { font-weight: 700; font-size: 15px; }
.tree-v2 .tree-toolbar .tt-sub { color: #64748b; font-size: 12px; }
.tree-v2 .btn { padding: 5px 12px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 12px; color: #334155; }
.tree-v2 .btn:hover { background: #f1f5f9; }
@media (max-width: 900px) { .tree-v2 .tree-layout { flex-direction: column; } .tree-v2 .detail-panel { max-width: 100%; position: static; } }
</style>
<div class="tree-v2">
  <div class="tree-toolbar">
    <span class="tt-title">🌲 目标拆解树（层级强化版）</span>
    <span class="tt-sub">__TOTAL_DEPTS__ 部门 · __TOTAL_GOALS__ 目标 · __LEVEL_STAT__</span>
    <button class="btn" onclick="tvExpandAll(true)">全部展开</button>
    <button class="btn" onclick="tvExpandAll(false)">全部收起</button>
  </div>
  <div class="tree-layout">
    <div class="tree-main" id="tv-tree">__DEPT_SECTION__</div>
    <div class="detail-panel" id="tv-detail">
      <div class="empty">点击左侧节点，查看该目标的路径 / 指标 / ↑向上对齐 / ↓向下承接 / 自身结构诊断</div>
    </div>
  </div>
</div>
<script>
(function () {
  var NODES = __JS_NODES__;
  var IDX = {};
  for (var i = 0; i < NODES.length; i++) IDX[NODES[i].id] = i;
  var SEV = {'high':'高','medium':'中','low':'低'};
  function esc(s) { return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function pct(p) { return p == null ? '—' : (Math.round(p*100) + '%'); }
  function renderDetail(id) {
    var n = NODES[IDX[id]]; if (!n) return;
    var crumbs = []; var cur = n; var guard = 0;
    while (cur && guard < 5) { crumbs.unshift(cur.title.split(' · ').pop() + '（' + cur.level + '·' + cur.owner + '）'); cur = (cur.parent && IDX[cur.parent] != null) ? NODES[IDX[cur.parent]] : null; guard++; }
    var h = '<div class="crumb">路径：' + crumbs.join(' → ') + '</div>';
    h += '<h4>ℹ 基本信息</h4>';
    h += '<div style="font-size:12px;color:#64748b">' + esc(n.title) + '<br>部门：' + esc(n.department) + ' ｜ 层级：' + esc(n.level) + ' ｜ 进度：' + pct(n.progress) + '</div>';
    if (n.inds && n.inds.length) {
      h += '<h4>📊 指标目标值（' + n.inds.length + '）</h4>';
      for (var j = 0; j < n.inds.length; j++) {
        var it = n.inds[j];
        h += '<div class="ind-item"><span>' + esc(it.name) + '</span><span class="iv">' + esc(it.value) + esc(it.unit) + '</span></div>';
      }
    }
    var par = (n.parent && IDX[n.parent] != null) ? NODES[IDX[n.parent]] : null;
    if (par) {
      h += '<h4>↑ 向上关联（父级对齐）</h4>';
      h += '<div class="rel-item strong"><div class="rt">父级：' + esc(par.owner) + '（' + esc(par.level) + ' · ' + esc(par.title) + '）</div></div>';
      var upIssues = (par.issues || []).filter(function(x){ return x.dimension && x.dimension.indexOf('对齐') >= 0; });
      if (upIssues.length) { for (var u=0;u<upIssues.length;u++) { var x=upIssues[u]; h += '<div class="rel-item none"><div class="rt">['+SEV[x.severity]+'] '+esc(x.title)+'</div><div class="rd">'+esc(x.description)+'</div></div>'; } }
      else { h += '<div class="rel-item strong"><div class="rd">未发现向上对齐问题 ✓</div></div>'; }
    }
    if (n.children && n.children.length) {
      h += '<h4>↓ 向下关联（子级承接，' + n.children.length + ' 个）</h4>';
      var cnames = [];
      for (var c = 0; c < n.children.length; c++) { var ch = IDX[n.children[c]] != null ? NODES[IDX[n.children[c]]] : null; if (ch) cnames.push(ch.owner + '·' + ch.title); }
      h += '<div class="rel-item strong"><div class="rt">' + esc(cnames.join('；')) + '</div></div>';
      var downIssues = (n.issues || []).filter(function(x){ return x.dimension && (x.dimension.indexOf('承接') >= 0 || x.dimension.indexOf('关联') >= 0); });
      if (downIssues.length) { for (var d=0;d<downIssues.length;d++) { var y=downIssues[d]; h += '<div class="rel-item weak"><div class="rt">['+SEV[y.severity]+'] '+esc(y.title)+'</div><div class="rd">'+esc(y.description)+'</div></div>'; } }
      else { h += '<div class="rel-item strong"><div class="rd">子级承接关系良好 ✓</div></div>'; }
    }
    var selfIssues = (n.issues || []).filter(function(x){ return !x.dimension || (x.dimension.indexOf('承接') < 0 && x.dimension.indexOf('关联') < 0 && x.dimension.indexOf('对齐') < 0); });
    if (selfIssues.length) {
      h += '<h4>自身结构问题（' + selfIssues.length + '）</h4>';
      for (var s = 0; s < selfIssues.length; s++) {
        var z = selfIssues[s];
        h += '<div class="rel-item ' + (z.severity==='high'?'none':z.severity==='medium'?'weak':'strong') + '"><div class="rt">['+SEV[z.severity]+'] '+esc(z.title)+'</div><div class="rd">'+esc(z.description)+'</div></div>';
      }
    }
    var d = document.getElementById('tv-detail');
    if (d) d.innerHTML = h;
  }
  var tnodes = document.querySelectorAll('.tnode');
  for (var k = 0; k < tnodes.length; k++) {
    tnodes[k].addEventListener('click', function(e) {
      e.stopPropagation();
      var sel = document.querySelectorAll('.tnode.sel');
      for (var m = 0; m < sel.length; m++) sel[m].classList.remove('sel');
      this.classList.add('sel');
      renderDetail(this.getAttribute('data-id'));
    });
  }
  var heads = document.querySelectorAll('.dept-head');
  for (var hh = 0; hh < heads.length; hh++) {
    heads[hh].addEventListener('click', function(e) {
      e.stopPropagation();
      var card = this.parentNode;
      card.classList.toggle('collapsed');
      var gid = this.getAttribute('data-id');
      if (gid) {
        var sel = document.querySelectorAll('.tnode.sel');
        for (var m = 0; m < sel.length; m++) sel[m].classList.remove('sel');
        renderDetail(gid);
      }
    });
  }
  window.tvExpandAll = function(open) {
    var cards = document.querySelectorAll('.dept-card');
    for (var i = 0; i < cards.length; i++) { cards[i].classList.toggle('collapsed', !open); }
  };
})();
</script>
"""
