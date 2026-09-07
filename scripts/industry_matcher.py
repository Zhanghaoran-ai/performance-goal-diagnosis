"""
行业指标匹配引擎（v2.2 新增）

封装5大核心能力：
1. IndustryRecognizer - 行业识别引擎
2. LayeredMetricMatcher - 分层指标匹配器
3. MetricTypeClassifier - 指标类型判断器
4. MatchQualityEvaluator - 匹配质量评估器
5. IndustryMetricLibrary - 行业指标库管理器
"""

import re
import os
from pathlib import Path
from collections import defaultdict


# ============================================================
# 1. 行业识别引擎
# ============================================================

class IndustryRecognizer:
    """行业识别引擎：从部门名称、企业名称、目标内容中自动识别行业"""

    # 行业关键词映射表（关键词 → 行业）
    INDUSTRY_KEYWORDS = {
        '制造业': [
            '制造', '生产', '工厂', '车间', '产线', '生产线', 'OEE', '设备综合效率',
            '一次合格率', '订单准时交付', '安全事故', '良品率', '报废率', '在制品',
            '产能', '稼动率', '换型时间', 'SMED', '精益生产', '六西格玛',
            '制造集团', '制造中心', '生产基地', '制造厂', '生产厂', '制造企业',
            '生产企业', '制造业', '工业制造', '离散制造', '流程制造', '装配',
            '注塑', '冲压', '焊接', '机加工', 'CNC', '数控', '自动化产线',
            '智能制造', '工业4.0', 'MES', '班组', '工段', '工序'
        ],
        '消费品行业': [
            '消费品', '快消', 'FMCG', '零售', '商超', '渠道', '经销商', '铺货',
            '动销', '库存周转', '坪效', '客单价', '复购率', '品牌渗透率', '市场份额',
            '促销', '陈列', '终端', 'SKU'
        ],
        '医疗健康行业': [
            '医疗', '医院', '健康', '医药', '药品', '患者', '门诊', '住院',
            '床位', '手术', '诊疗', '医保', 'DRG', 'DIP', '药占比', '耗占比',
            '平均住院日', '床位周转率', '患者满意度', '医疗质量', '院感'
        ],
        '汽车行业': [
            '汽车', '整车', '零部件', '4S', '经销商', '车企', '新能源汽车',
            '充电桩', '动力电池', '续航', '自动驾驶', '车联网', '销量', '交付量',
            '售后', '维修', '保养', '二手车'
        ],
        '电子半导体行业': [
            '电子', '半导体', '芯片', '集成电路', 'IC', '晶圆', '封测', 'PCB',
            '良率', 'yield', '制程', '纳米', '光刻', '蚀刻', '沉积', '洁净室',
            '元器件', '模组', 'SMT', '贴片'
        ],
        '通用行业': [
            '通用', '综合', '集团', '多元化', '控股'
        ],
        '银行业': [
            '银行', '信贷', '风控', '网点', '支行', '不良率', '存贷比', '净息差',
            '资本充足率', '拨备覆盖率', 'ROA', 'ROE', '客户AUM', '财富管理',
            '私人银行', '对公', '零售', '信用卡', '贷款', '存款'
        ],
        '物流行业': [
            '物流', '快递', '仓储', '配送', '运输', '货运', '供应链', '仓配',
            '准时送达率', '破损率', '库存准确率', '拣货效率', '装载率', '周转天数',
            '配送成本', '最后一公里', '冷链', '干线', '支线'
        ],
        '新能源行业': [
            '新能源', '光伏', '风电', '储能', '度电成本', 'LCOE', '系统效率',
            'PR值', '置信出力', '利用小时数', '弃光率', '弃风率', '逆变器',
            '组件', '电池板', '塔筒', '叶片', '并网', '消纳'
        ],
        'SaaS行业': [
            'SaaS', '软件', '订阅', 'ARR', 'MRR', '续费率', '流失率', 'churn',
            '客户成功', 'CSM', 'NDR', 'GRR', 'LTV', 'CAC', '获客成本', '付费转化率',
            '活跃度', '留存率', 'DAU', 'MAU', 'adoption', '使用率'
        ],
        '互联网行业': [
            '互联网', '电商', '平台', '流量', 'DAU', 'MAU', 'GMV', '转化率',
            '点击率', 'CTR', 'CVR', '用户增长', '拉新', '留存', '变现', '广告',
            '直播', '短视频', '内容', '算法', '推荐'
        ]
    }

    # 行业别名映射（别名 → 标准行业名）
    INDUSTRY_ALIASES = {
        '互联网科技': '互联网行业',
        'IT': '互联网行业',
        '信息技术': '互联网行业',
        '软件服务': 'SaaS行业',
        '企业服务': 'SaaS行业',
        '云服务': 'SaaS行业',
        '制造': '制造业',
        '工业': '制造业',
        '工厂': '制造业',
        '快消': '消费品行业',
        '消费': '消费品行业',
        '零售': '消费品行业',
        '医疗': '医疗健康行业',
        '医药': '医疗健康行业',
        '医院': '医疗健康行业',
        '汽车': '汽车行业',
        '新能源车': '汽车行业',
        '半导体': '电子半导体行业',
        '芯片': '电子半导体行业',
        '电子': '电子半导体行业',
        '银行': '银行业',
        '金融': '银行业',
        '物流': '物流行业',
        '快递': '物流行业',
        '供应链': '物流行业',
        '新能源': '新能源行业',
        '光伏': '新能源行业',
        '风电': '新能源行业',
        '储能': '新能源行业',
        '通用': '通用行业',
        '综合': '通用行业'
    }

    # 泛化行业列表（这些行业的关键词权重降低，避免"集团""综合"等词误判）
    GENERIC_INDUSTRIES = {'通用行业'}

    def __init__(self):
        # 构建反向索引：关键词 → 行业
        self._keyword_to_industry = {}
        for industry, keywords in self.INDUSTRY_KEYWORDS.items():
            for kw in keywords:
                self._keyword_to_industry[kw.lower()] = industry

    def recognize_from_department(self, dept_name):
        """从部门名称识别行业"""
        if not dept_name:
            return []
        return self._recognize_from_text(dept_name)

    def recognize_from_company(self, company_name):
        """从企业名称识别行业"""
        if not company_name:
            return []
        return self._recognize_from_text(company_name)

    def recognize_from_goals(self, goals):
        """从目标内容识别行业"""
        if not goals:
            return []
        # 提取所有目标的标题和指标名称
        texts = []
        for goal in goals:
            texts.append(goal.get('title', ''))
            texts.append(goal.get('description', ''))
            for ind in goal.get('indicators', []):
                texts.append(ind.get('name', ''))
        combined = ' '.join(texts)
        return self._recognize_from_text(combined)

    def recognize(self, department='', company='', goals=None, manual_industry=None):
        """
        综合识别行业，返回Top3候选

        Returns:
            list of (industry, confidence) 按置信度降序
        """
        # 如果用户手动指定了行业，直接返回
        if manual_industry:
            standard = self._normalize_industry(manual_industry)
            if standard:
                return [(standard, 1.0)]
            return [(manual_industry, 0.8)]

        # 多源识别
        scores = defaultdict(float)

        # 部门名称（权重0.3）
        for industry, score in self.recognize_from_department(department):
            scores[industry] += score * 0.3

        # 企业名称（权重0.4）
        for industry, score in self.recognize_from_company(company):
            scores[industry] += score * 0.4

        # 目标内容（权重0.3）
        for industry, score in self.recognize_from_goals(goals or []):
            scores[industry] += score * 0.3

        if not scores:
            return [('通用行业', 0.3)]  # 默认兜底

        # 排序并归一化
        sorted_industries = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        max_score = sorted_industries[0][1] if sorted_industries else 1
        result = [(ind, min(score / max_score, 1.0)) for ind, score in sorted_industries[:3]]
        return result

    def _recognize_from_text(self, text):
        """从文本中识别行业，返回 (industry, score) 列表"""
        if not text:
            return []

        text_lower = text.lower()
        industry_hits = defaultdict(int)

        # 关键词匹配
        for keyword, industry in self._keyword_to_industry.items():
            if keyword in text_lower:
                industry_hits[industry] += 1

        if not industry_hits:
            return []

        # 计算得分（命中关键词数 / 该行业总关键词数）
        # 泛化行业（如通用行业）权重降低50%，避免"集团""综合"等词误判
        results = []
        for industry, hits in industry_hits.items():
            total_keywords = len(self.INDUSTRY_KEYWORDS.get(industry, []))
            score = min(hits / max(total_keywords * 0.3, 1), 1.0)
            # 泛化行业降权（降低到0.2，避免"集团""综合"等词误判为通用行业）
            if industry in self.GENERIC_INDUSTRIES:
                score *= 0.2
            results.append((industry, score))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def _normalize_industry(self, industry_name):
        """将行业别名标准化"""
        if not industry_name:
            return None
        # 直接匹配
        if industry_name in self.INDUSTRY_KEYWORDS:
            return industry_name
        # 别名匹配
        return self.INDUSTRY_ALIASES.get(industry_name)


# ============================================================
# 2. 指标类型判断器
# ============================================================

class MetricTypeClassifier:
    """指标类型判断器：区分正向/反向/区间指标"""

    # 正向指标（越高越好）
    POSITIVE_PATTERNS = [
        r'收入', r'营收', r'销售额', r'营业额', r'利润', r'盈利', r'收益',
        r'增长', r'提升', r'增加', r'提高', r'上涨', r'上升',
        r'满意度', r'体验', r'NPS', r'CSAT',
        r'效率', r'效能', r'生产率', r'人效', r'OEE', r'稼动率', r'利用率',
        r'合格率', r'良品率', r'达标率', r'通过率', r'成功率', r'准确率',
        r'留存率', r'保留率', r'复购率', r'续费率', r'续约率',
        r'市场份额', r'渗透率', r'覆盖率', r'占有率',
        r'周转率', r'周转次数',
        r'准时交付率', r'及时率', r'按时完成率',
        r'产能', r'产量', r'销量', r'交付量',
        r'活跃度', r'DAU', r'MAU', r'GMV',
        r'转化率', r'点击率', r'CTR', r'CVR',
        r'净息差', r'ROA', r'ROE', r'资本充足率', r'拨备覆盖率',
        r'系统效率', r'PR值', r'置信出力', r'利用小时数',
        r'床位周转率', r'门诊量', r'手术量',
        r'装载率', r'库存准确率', r'拣货效率', r'准时送达率',
        r'adoption', r'使用率', r'采纳率',
        r'ARR', r'MRR', r'NDR', r'GRR', r'LTV',
        r'良率', r'yield', r'直通率'
    ]

    # 反向指标（越低越好）
    NEGATIVE_PATTERNS = [
        r'成本', r'费用', r'开支', r'支出', r'花费',
        r'流失率', r'churn', r'attrition', r'离职率', r'流失',
        r'缺陷', r'不良', r'瑕疵', r'问题', r'错误', r'bug',
        r'缺陷率', r'不良率', r'报废率', r'故障率', r'损坏率', r'破损率',
        r'投诉', r'投诉率', r'抱怨',
        r'事故', r'事故率', r'安全事故',
        r'延迟', r'延期', r'超时', r'逾期',
        r'周期', r'时长', r'耗时', r'时间', r'周期时间',
        r'等待时间', r'响应时间', r'解决时间',
        r'库存', r'在制品', r'WIP',
        r'度电成本', r'LCOE', r'获客成本', r'CAC',
        r'不良贷款率', r'不良率', r'坏账率',
        r'弃光率', r'弃风率',
        r'平均住院日', r'药占比', r'耗占比', r'院感率',
        r'配送成本', r'运输成本',
        r'换型时间', r'SMED',
        r'客户投诉率', r'退款率', r'退货率'
    ]

    # 区间指标（在范围内最好）
    RANGE_PATTERNS = [
        r'库存周转', r'人员利用率', r'资产负债率', r'负债率',
        r'流动比率', r'速动比率', r'毛利率', r'净利率',
        r'员工满意度', r'eNPS'
    ]

    def classify(self, metric_name):
        """
        判断指标类型

        Returns:
            str: 'positive'（正向，越高越好）/ 'negative'（反向，越低越好）/ 'range'（区间）/ 'unknown'
        """
        if not metric_name:
            return 'unknown'

        name_lower = metric_name.lower()

        # 先检查区间指标（优先级最高，因为有些区间指标也包含正向词）
        for pattern in self.RANGE_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return 'range'

        # 检查反向指标
        for pattern in self.NEGATIVE_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return 'negative'

        # 检查正向指标
        for pattern in self.POSITIVE_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return 'positive'

        return 'unknown'

    def judge_deviation(self, current, benchmark, metric_type='unknown',
                        min_val=None, max_val=None):
        """
        智能偏离判断

        Args:
            current: 当前值
            benchmark: 基准值
            metric_type: 指标类型
            min_val: 合理范围下限
            max_val: 合理范围上限

        Returns:
            dict: {
                'is_deviation': bool,
                'severity': 'high'/'medium'/'low'/'none',
                'direction': 'higher'/'lower'/'out_of_range',
                'deviation_pct': float,
                'description': str
            }
        """
        if benchmark is None or benchmark == 0:
            return {
                'is_deviation': False,
                'severity': 'none',
                'direction': None,
                'deviation_pct': 0,
                'description': '基准值无效'
            }

        deviation = (current - benchmark) / benchmark
        abs_deviation = abs(deviation)

        # 区间指标：使用 min/max 判断
        if metric_type == 'range' and (min_val is not None or max_val is not None):
            out_of_range = False
            direction = None
            if min_val is not None and current < min_val:
                out_of_range = True
                direction = 'lower'
            elif max_val is not None and current > max_val:
                out_of_range = True
                direction = 'higher'

            if out_of_range:
                # 计算超出范围的程度
                if direction == 'lower':
                    range_deviation = (min_val - current) / max(benchmark, 1)
                else:
                    range_deviation = (current - max_val) / max(benchmark, 1)

                severity = self._get_severity(range_deviation)
                return {
                    'is_deviation': True,
                    'severity': severity,
                    'direction': 'out_of_range',
                    'deviation_pct': range_deviation,
                    'description': f'超出合理范围（{min_val}~{max_val}）'
                }
            return {
                'is_deviation': False,
                'severity': 'none',
                'direction': None,
                'deviation_pct': 0,
                'description': '在合理范围内'
            }

        # 正向指标：低于基准才是问题
        if metric_type == 'positive':
            if deviation < -0.1:  # 低于基准10%以上
                severity = self._get_severity(abs_deviation)
                return {
                    'is_deviation': True,
                    'severity': severity,
                    'direction': 'lower',
                    'deviation_pct': abs_deviation,
                    'description': f'低于行业基准 {abs_deviation*100:.1f}%'
                }
            return {
                'is_deviation': False,
                'severity': 'none',
                'direction': 'higher' if deviation > 0 else None,
                'deviation_pct': abs_deviation,
                'description': '高于或达到行业基准（表现良好）' if deviation >= 0 else '略低于基准（可接受）'
            }

        # 反向指标：高于基准才是问题
        if metric_type == 'negative':
            if deviation > 0.1:  # 高于基准10%以上
                severity = self._get_severity(abs_deviation)
                return {
                    'is_deviation': True,
                    'severity': severity,
                    'direction': 'higher',
                    'deviation_pct': abs_deviation,
                    'description': f'高于行业基准 {abs_deviation*100:.1f}%'
                }
            return {
                'is_deviation': False,
                'severity': 'none',
                'direction': 'lower' if deviation < 0 else None,
                'deviation_pct': abs_deviation,
                'description': '低于或达到行业基准（表现良好）' if deviation <= 0 else '略高于基准（可接受）'
            }

        # unknown 类型：使用绝对值偏离（兼容旧逻辑）
        if abs_deviation > 0.1:
            severity = self._get_severity(abs_deviation)
            direction = 'higher' if deviation > 0 else 'lower'
            return {
                'is_deviation': True,
                'severity': severity,
                'direction': direction,
                'deviation_pct': abs_deviation,
                'description': f'{"高于" if deviation > 0 else "低于"}行业基准 {abs_deviation*100:.1f}%'
            }

        return {
            'is_deviation': False,
            'severity': 'none',
            'direction': None,
            'deviation_pct': abs_deviation,
            'description': '在合理范围内'
        }

    def _get_severity(self, deviation_pct):
        """根据偏离度判断严重程度"""
        if deviation_pct > 0.5:
            return 'high'
        elif deviation_pct > 0.2:
            return 'medium'
        else:
            return 'low'


# ============================================================
# 3. 匹配质量评估器
# ============================================================

class MatchQualityEvaluator:
    """匹配质量评估器：评估匹配到的指标的可信度"""

    # 数据源权威性权重
    AUTHORITY_WEIGHTS = {
        5: 1.0,   # ⭐⭐⭐⭐⭐ 国际标准/监管机构
        4: 0.85,  # ⭐⭐⭐⭐ 行业协会/头部咨询
        3: 0.7,   # ⭐⭐⭐ 上市公司财报/行业报告
        2: 0.55,  # ⭐⭐ 第三方数据平台
        1: 0.4    # ⭐ 企业自报/估算
    }

    # 验证状态权重
    VERIFICATION_WEIGHTS = {
        '已验证': 1.0,
        '✅ 已验证': 1.0,
        '待验证': 0.7,
        '⚠️ 待验证': 0.7,
        '参考值': 0.5,
        '📌 参考值': 0.5
    }

    def evaluate(self, metric, match_similarity=1.0):
        """
        评估匹配质量

        Args:
            metric: 匹配到的指标字典
            match_similarity: 名称匹配相似度

        Returns:
            dict: {
                'quality_score': float (0-1),
                'quality_grade': 'A'/'B'/'C'/'D',
                'confidence': str,
                'factors': dict
            }
        """
        factors = {}

        # 1. 匹配相似度（权重30%）
        factors['similarity'] = match_similarity
        similarity_score = match_similarity * 0.3

        # 2. 数据源权威性（权重30%）
        authority = metric.get('authority', 3)
        if isinstance(authority, str):
            # 从星级字符串提取数字
            stars = authority.count('⭐')
            authority = stars if stars > 0 else 3
        factors['authority'] = authority
        authority_score = self.AUTHORITY_WEIGHTS.get(authority, 0.7) * 0.3

        # 3. 数据时效性（权重20%）
        freshness_score = self._evaluate_freshness(metric.get('data_date', ''))
        factors['freshness'] = freshness_score
        freshness_score *= 0.2

        # 4. 验证状态（权重20%）
        verification = metric.get('verification_status', '待验证')
        factors['verification'] = verification
        verification_score = self.VERIFICATION_WEIGHTS.get(verification, 0.7) * 0.2

        # 综合评分
        total_score = similarity_score + authority_score + freshness_score + verification_score

        # 等级判定
        if total_score >= 0.85:
            grade = 'A'
            confidence = '高可信度'
        elif total_score >= 0.7:
            grade = 'B'
            confidence = '中等可信度'
        elif total_score >= 0.55:
            grade = 'C'
            confidence = '较低可信度，仅供参考'
        else:
            grade = 'D'
            confidence = '低可信度，建议人工核实'

        return {
            'quality_score': round(total_score, 3),
            'quality_grade': grade,
            'confidence': confidence,
            'factors': factors
        }

    def _evaluate_freshness(self, data_date):
        """评估数据时效性"""
        if not data_date:
            return 0.5

        try:
            # 解析日期格式 "2025-12" 或 "2026-06"
            match = re.match(r'(\d{4})-(\d{2})', str(data_date))
            if not match:
                return 0.5

            year, month = int(match.group(1)), int(match.group(2))
            # 简化计算：假设当前是2026-08
            months_old = (2026 - year) * 12 + (8 - month)

            if months_old <= 6:
                return 1.0
            elif months_old <= 12:
                return 0.85
            elif months_old <= 24:
                return 0.7
            else:
                return 0.5
        except Exception:
            return 0.5


# ============================================================
# 4. 分层指标匹配器
# ============================================================

class LayeredMetricMatcher:
    """分层指标匹配器：行业 → 层级 → 名称语义 三层匹配"""

    # 目标层级 → 指标库层级映射
    LEVEL_MAPPING = {
        'L1': '战略层',
        'L2': '管理层',
        'L3': '执行层',
        'L4': '执行层'
    }

    # 指标同义词映射（用户常用名 → 指标库标准名）
    # 用于提升匹配率，如"OEE设备综合效率"能匹配到"OEE"
    METRIC_SYNONYMS = {
        # 制造业
        'OEE': ['设备综合效率', '设备综合效率OEE', 'OEE设备综合效率'],
        '设备综合效率': ['OEE', 'OEE设备综合效率', '设备综合效率OEE'],
        '稼动率': ['设备稼动率', '设备利用率', '设备开动率', '产能利用率'],
        '设备稼动率': ['稼动率', '设备利用率', '设备开动率'],
        '一次合格率': ['直通率', '首次合格率', 'FPY', '一次通过率'],
        '直通率': ['一次合格率', '首次合格率', 'FPY'],
        '订单准时交付率': ['准时交付率', 'OTD', '订单交付准时率', '及时交付率'],
        '准时交付率': ['订单准时交付率', 'OTD', '及时交付率'],
        '客诉率': ['客户投诉率', '投诉率'],
        '客户投诉率': ['客诉率', '投诉率'],
        '安全事故率': ['事故率', '安全事故发生率'],
        '换型时间': ['换模时间', 'SMED时间', '切换时间'],
        '换模时间': ['换型时间', 'SMED时间', '切换时间'],
        '单位生产成本': ['单位产品成本', '制造成本', '生产成本', '单位制造成本'],
        '单位产品成本': ['单位生产成本', '制造成本', '生产成本'],
        '人均产出': ['人均产量', '人均效能', '劳动生产率'],
        '人均产量': ['人均产出', '人均效能', '劳动生产率'],
        '库存周转率': ['库存周转次数', '存货周转率'],
        '产能达成率': ['产能利用率', '产能完成率'],
        '设备故障率': ['故障停机率', '设备完好率'],
        '线平衡率': ['生产线平衡率', '产线平衡率'],
        '来料合格率': ['进料合格率', 'IQC合格率'],
        '过程不良率': ['制程不良率', '过程缺陷率', 'PPM'],
        '物料利用率': ['材料利用率', '原材料利用率'],
        '在制品': ['WIP', '在制品库存', '半成品库存'],
        '报废率': ['不良报废率', '废品率'],
        '良品率': ['合格率', '成品率'],
        # 通用
        '成本': ['费用', '开支', '支出'],
        '收入': ['营收', '销售额', '营业额'],
        '利润': ['盈利', '收益'],
        '满意度': ['NPS', 'CSAT', '客户满意度'],
        'NPS': ['净推荐值', '满意度'],
        '离职率': ['人员流失率', '员工流失率', 'attrition'],
        '流失率': ['churn', '客户流失率', '用户流失率'],
    }

    def __init__(self, metric_library):
        """
        Args:
            metric_library: IndustryMetricLibrary 实例
        """
        self.library = metric_library
        self.type_classifier = MetricTypeClassifier()
        self.quality_evaluator = MatchQualityEvaluator()
        # 构建反向同义词索引：同义词 → 标准名
        self._synonym_to_standard = {}
        for standard, synonyms in self.METRIC_SYNONYMS.items():
            self._synonym_to_standard[standard.lower()] = standard
            for syn in synonyms:
                self._synonym_to_standard[syn.lower()] = standard

    def match(self, indicator_name, goal_level='L2', industry=None, top_k=1):
        """
        三层匹配：行业 → 层级 → 名称语义

        Args:
            indicator_name: 指标名称
            goal_level: 目标层级（L1/L2/L3/L4）
            industry: 指定行业（None表示自动）
            top_k: 返回前K个匹配结果

        Returns:
            list of dict: 匹配结果列表，每个包含：
                - metric: 指标完整信息
                - similarity: 名称相似度
                - industry: 匹配的行业
                - level: 匹配的层级
                - metric_type: 指标类型
                - quality: 匹配质量评估
        """
        if not indicator_name:
            return []

        # 1. 获取候选指标（按行业筛选，层级在匹配时加权）
        candidates = self.library.get_metrics(industry=industry)

        # 目标层级
        target_level = self.LEVEL_MAPPING.get(goal_level, '管理层')

        # 2. 计算每个候选的相似度
        scored = []
        for metric in candidates:
            metric_name = metric.get('name', '')
            metric_level = metric.get('level', '')
            metric_industry = metric.get('industry', '')

            # 名称相似度（综合：Jaccard + 同义词 + 包含关系）
            name_sim = self._calc_name_similarity(indicator_name, metric_name)
            if name_sim < 0.25:  # 降低阈值，让更多候选进入
                continue

            # 层级匹配加成（同层级+0.1，跨层级相邻+0.05）
            level_bonus = self._calc_level_bonus(metric_level, target_level)

            # 行业匹配加成（如果指定了行业）
            industry_bonus = 0.1 if (industry and metric_industry == industry) else 0.0

            # 综合得分
            total_score = min(name_sim + level_bonus + industry_bonus, 1.0)

            if total_score >= 0.4:  # 降低匹配阈值从0.5到0.4
                # 指标类型判断
                metric_type = self.type_classifier.classify(indicator_name)

                # 匹配质量评估
                quality = self.quality_evaluator.evaluate(metric, name_sim)

                scored.append({
                    'metric': metric,
                    'similarity': round(name_sim, 3),
                    'total_score': round(total_score, 3),
                    'industry': metric_industry,
                    'level': metric_level,
                    'metric_type': metric_type,
                    'quality': quality
                })

        # 3. 排序并返回TopK
        scored.sort(key=lambda x: x['total_score'], reverse=True)
        return scored[:top_k]

    def _calc_name_similarity(self, text1, text2):
        """
        综合名称相似度计算（v2.4 优化）
        1. 同义词匹配：如果互为同义词，相似度=1.0
        2. 包含关系：如果A包含B或B包含A，相似度至少0.6
        3. Jaccard字符级相似度：基础相似度
        """
        if not text1 or not text2:
            return 0.0

        t1, t2 = text1.lower().strip(), text2.lower().strip()

        # 1. 完全匹配
        if t1 == t2:
            return 1.0

        # 2. 同义词匹配
        std1 = self._synonym_to_standard.get(t1)
        std2 = self._synonym_to_standard.get(t2)
        if std1 and std2 and std1 == std2:
            return 1.0
        if std1 and std1 == t2:
            return 1.0
        if std2 and std2 == t1:
            return 1.0

        # 3. 包含关系匹配（如果一个包含另一个，且长度差异不太大）
        if t1 in t2 or t2 in t1:
            # 计算长度比例，避免"成本"匹配到"单位生产成本"时相似度太低
            shorter = min(len(t1), len(t2))
            longer = max(len(t1), len(t2))
            length_ratio = shorter / longer if longer > 0 else 0
            # 包含关系基础分0.6，长度越接近分越高
            contain_score = 0.6 + length_ratio * 0.3
            return min(contain_score, 0.9)

        # 4. Jaccard字符级相似度（基础）
        jaccard = self._jaccard_similarity(t1, t2)

        # 5. 检查是否有共同的同义词根（如"OEE设备综合效率"和"设备综合效率"）
        # 提取核心词，检查是否有同义词重叠
        synonym_overlap = self._check_synonym_overlap(t1, t2)
        if synonym_overlap > 0:
            return max(jaccard, 0.5 + synonym_overlap * 0.3)

        return jaccard

    def _jaccard_similarity(self, text1, text2):
        """Jaccard 字符级相似度"""
        set1 = set(text1)
        set2 = set(text2)
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _check_synonym_overlap(self, text1, text2):
        """检查两个文本是否包含同一组同义词，返回重叠度0-1"""
        # 收集text1中包含的所有同义词标准名
        standards1 = set()
        for syn, std in self._synonym_to_standard.items():
            if syn in text1 or std.lower() in text1:
                standards1.add(std)

        # 收集text2中包含的所有同义词标准名
        standards2 = set()
        for syn, std in self._synonym_to_standard.items():
            if syn in text2 or std.lower() in text2:
                standards2.add(std)

        if not standards1 or not standards2:
            return 0.0

        intersection = len(standards1 & standards2)
        union = len(standards1 | standards2)
        return intersection / union if union > 0 else 0.0

    def _calc_level_bonus(self, metric_level, target_level):
        """计算层级匹配加成"""
        if metric_level == target_level:
            return 0.1
        # 相邻层级（如战略层↔管理层，管理层↔执行层）给一半加成
        level_order = ['战略层', '管理层', '执行层']
        if metric_level in level_order and target_level in level_order:
            diff = abs(level_order.index(metric_level) - level_order.index(target_level))
            if diff == 1:
                return 0.05
        return 0.0

    def _text_similarity(self, text1, text2):
        """计算文本相似度（兼容旧接口，内部调用新方法）"""
        return self._calc_name_similarity(text1, text2)


# ============================================================
# 5. 行业指标库管理器
# ============================================================

class IndustryMetricLibrary:
    """行业指标库管理器：统一加载、管理、查询行业指标"""

    def __init__(self, library_path=None):
        """
        Args:
            library_path: 指标库路径，None 表示使用内置默认路径
        """
        self.metrics = []  # 扁平列表，每个指标是一个完整字典
        self.industry_index = defaultdict(list)  # 行业 → 指标列表
        self.level_index = defaultdict(list)     # 层级 → 指标列表
        self.industries = set()                  # 所有行业
        self.levels = set()                      # 所有层级

        # 默认使用内置指标库
        if library_path is None:
            # 相对于当前脚本的位置
            current_dir = Path(__file__).parent
            library_path = current_dir.parent / 'examples' / 'industry-metrics'

        self.library_path = Path(library_path)

        if self.library_path.exists():
            self._load_library()

    def _load_library(self):
        """加载整个指标库"""
        # 递归查找所有 .md 和 .json 文件
        for file_path in self.library_path.rglob('*'):
            if file_path.is_file() and file_path.suffix in ('.md', '.json'):
                # 跳过管理文档
                if file_path.name in ['README.md', '数据质量与元数据标准.md',
                                       '更新机制与流程.md', '检验标准与质量控制.md',
                                       '变更日志与版本管理.md']:
                    continue

                # 从路径提取行业和层级
                industry = file_path.parent.name
                level = self._extract_level_from_filename(file_path.name)

                if file_path.suffix == '.md':
                    metrics = self._parse_metric_md(file_path.read_text(encoding='utf-8'),
                                                     industry, level)
                else:
                    import json
                    try:
                        data = json.loads(file_path.read_text(encoding='utf-8'))
                        metrics = [data] if isinstance(data, dict) else data
                    except Exception:
                        metrics = []

                for metric in metrics:
                    metric['industry'] = industry
                    metric['level'] = level
                    metric['source_file'] = str(file_path)
                    self.metrics.append(metric)
                    self.industry_index[industry].append(metric)
                    self.level_index[level].append(metric)
                    self.industries.add(industry)
                    self.levels.add(level)

    def _extract_level_from_filename(self, filename):
        """从文件名提取层级"""
        if '战略层' in filename:
            return '战略层'
        elif '管理层' in filename:
            return '管理层'
        elif '执行层' in filename:
            return '执行层'
        return '未知'

    def _parse_metric_md(self, content, industry='', level=''):
        """解析 Markdown 格式的指标文件"""
        metrics = []

        # 尝试解析三层指标体系格式（表格 + 指标详解）
        # 先提取表格中的指标
        table_pattern = r'\|\s*\d+\s*\|\s*\*?\*?([^*|]+?)\*?\*?\s*\|'
        table_matches = re.findall(table_pattern, content)

        # 提取指标详解部分
        detail_sections = re.split(r'###\s+\d+\.\s+', content)

        if len(detail_sections) > 1:
            # 有指标详解，逐个解析
            for section in detail_sections[1:]:
                metric = self._parse_single_metric_detail(section, industry, level)
                if metric:
                    metrics.append(metric)
        elif table_matches:
            # 只有表格，从表格提取
            for name in table_matches:
                metrics.append({
                    'name': name.strip(),
                    'industry': industry,
                    'level': level
                })
        else:
            # 旧格式：单指标文件
            metric = self._parse_old_format(content, industry, level)
            if metric:
                metrics.append(metric)

        return metrics

    def _parse_single_metric_detail(self, section, industry, level):
        """解析单个指标的详解部分"""
        metric = {'industry': industry, 'level': level}

        # 提取指标名称（第一行）
        first_line = section.strip().split('\n')[0].strip()
        name_match = re.match(r'([^（(]+)', first_line)
        if name_match:
            metric['name'] = name_match.group(1).strip()
        else:
            metric['name'] = first_line

        # 提取基准值
        benchmark_match = re.search(r'基准值\*?\*?[：:]\s*([^\n]+)', section)
        if benchmark_match:
            benchmark_str = benchmark_match.group(1).strip()
            metric['benchmark_display'] = benchmark_str
            num_match = re.search(r'([\d.]+)', benchmark_str)
            if num_match:
                metric['benchmark'] = float(num_match.group(1))

        # 提取合理范围
        range_match = re.search(r'合理范围\*?\*?[：:]\s*([^\n]+)', section)
        if range_match:
            range_str = range_match.group(1).strip()
            metric['range_display'] = range_str
            nums = re.findall(r'([\d.]+)', range_str)
            if len(nums) >= 2:
                metric['min'] = float(nums[0])
                metric['max'] = float(nums[1])

        # 提取单位
        unit_match = re.search(r'单位\*?\*?[：:]\s*([^\n]+)', section)
        if unit_match:
            metric['unit'] = unit_match.group(1).strip()

        # 提取数据来源
        source_match = re.search(r'(?:数据来源|发布机构)\*?\*?[：:]\s*([^\n]+)', section)
        if source_match:
            metric['data_source'] = source_match.group(1).strip()

        # 提取数据截止时间
        date_match = re.search(r'数据截止时间\*?\*?[：:]\s*([^\n]+)', section)
        if date_match:
            metric['data_date'] = date_match.group(1).strip()

        # 提取来源链接
        link_match = re.search(r'来源链接\*?\*?[：:]\s*([^\n]+)', section)
        if link_match:
            metric['source_link'] = link_match.group(1).strip()

        # 提取稳定性
        stability_match = re.search(r'稳定性\*?\*?[：:]\s*([^\n]+)', section)
        if stability_match:
            metric['stability'] = stability_match.group(1).strip()

        # 提取验证状态
        verification_match = re.search(r'验证状态\*?\*?[：:]\s*([^\n]+)', section)
        if verification_match:
            metric['verification_status'] = verification_match.group(1).strip()

        # 提取权威性
        authority_match = re.search(r'权威性\*?\*?[：:]\s*([^\n]+)', section)
        if authority_match:
            metric['authority'] = authority_match.group(1).strip()

        # 提取说明
        desc_match = re.search(r'说明\*?\*?[：:]\s*([^\n]+)', section)
        if desc_match:
            metric['description'] = desc_match.group(1).strip()

        return metric if metric.get('name') else None

    def _parse_old_format(self, content, industry, level):
        """解析旧版单指标格式"""
        metric = {'industry': industry, 'level': level}

        # 提取指标名称
        name_match = re.search(r'指标名称\*?\*?[：:]\s*([^\n]+)', content)
        if name_match:
            metric['name'] = name_match.group(1).strip()
        else:
            # 从标题提取
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                metric['name'] = title_match.group(1).strip()

        # 提取基准值
        benchmark_match = re.search(r'行业基准\*?\*?[：:]\s*([\d.]+)', content)
        if benchmark_match:
            metric['benchmark'] = float(benchmark_match.group(1))

        # 提取合理范围
        min_match = re.search(r'合理范围\*?\*?[：:]\s*([\d.]+)\s*~\s*([\d.]+)', content)
        if min_match:
            metric['min'] = float(min_match.group(1))
            metric['max'] = float(min_match.group(2))

        # 提取单位
        unit_match = re.search(r'单位\*?\*?[：:]\s*([^\n]+)', content)
        if unit_match:
            metric['unit'] = unit_match.group(1).strip()

        # 提取行业
        industry_match = re.search(r'行业\*?\*?[：:]\s*(\S+)', content)
        if industry_match:
            metric['industry'] = industry_match.group(1).strip()

        return metric if metric.get('name') else None

    def get_metrics(self, industry=None, level=None):
        """
        按行业和层级筛选指标

        Args:
            industry: 行业名称（None表示所有行业）
            level: 层级（None表示所有层级）

        Returns:
            list: 指标列表
        """
        result = self.metrics

        if industry:
            result = [m for m in result if m.get('industry') == industry]

        if level:
            result = [m for m in result if m.get('level') == level]

        return result

    def get_industries(self):
        """获取所有支持的行业列表"""
        return sorted(list(self.industries))

    def get_levels(self):
        """获取所有层级"""
        return sorted(list(self.levels))

    def get_stats(self):
        """获取指标库统计信息"""
        return {
            'total_metrics': len(self.metrics),
            'industries': len(self.industries),
            'industry_list': self.get_industries(),
            'levels': self.get_levels(),
            'by_industry': {ind: len(metrics) for ind, metrics in self.industry_index.items()},
            'version': 'v2.4.0',
            'custom_metrics': len(getattr(self, 'custom_metrics', []))
        }

    # ============================================================
    # v2.3 增强功能
    # ============================================================

    def merge_custom_library(self, custom_path, override=False):
        """
        合并自定义行业指标库（v2.3 新增）

        Args:
            custom_path: 自定义指标库路径（文件或目录）
            override: 是否覆盖同名指标（True=覆盖，False=保留内置）

        Returns:
            dict: 合并结果统计
        """
        custom_path = Path(custom_path)
        if not custom_path.exists():
            return {'success': False, 'error': f'路径不存在: {custom_path}', 'merged': 0}

        if not hasattr(self, 'custom_metrics'):
            self.custom_metrics = []

        merged_count = 0
        skipped_count = 0

        # 支持单个文件或目录
        files = []
        if custom_path.is_file():
            files = [custom_path]
        else:
            files = list(custom_path.rglob('*.md')) + list(custom_path.rglob('*.json'))

        for file_path in files:
            # 跳过管理文档
            if file_path.name in ['README.md', '数据质量与元数据标准.md',
                                   '更新机制与流程.md', '检验标准与质量控制.md',
                                   '变更日志与版本管理.md']:
                continue

            industry = file_path.parent.name if custom_path.is_dir() else '自定义'
            level = self._extract_level_from_filename(file_path.name)

            # 解析指标
            if file_path.suffix == '.md':
                metrics = self._parse_metric_md(
                    file_path.read_text(encoding='utf-8'), industry, level
                )
            else:
                import json
                try:
                    data = json.loads(file_path.read_text(encoding='utf-8'))
                    metrics = [data] if isinstance(data, dict) else data
                except Exception:
                    metrics = []

            for metric in metrics:
                metric['industry'] = industry
                metric['level'] = level
                metric['source_file'] = str(file_path)
                metric['is_custom'] = True

                # 检查是否已存在同名同行业指标
                existing = [m for m in self.metrics
                           if m.get('name') == metric.get('name')
                           and m.get('industry') == industry]

                if existing and not override:
                    skipped_count += 1
                    continue
                elif existing and override:
                    # 移除旧的
                    self.metrics = [m for m in self.metrics
                                   if not (m.get('name') == metric.get('name')
                                           and m.get('industry') == industry)]
                    self.industry_index[industry] = [m for m in self.industry_index[industry]
                                                    if m.get('name') != metric.get('name')]

                # 添加新指标
                self.metrics.append(metric)
                self.industry_index[industry].append(metric)
                self.level_index[level].append(metric)
                self.industries.add(industry)
                self.levels.add(level)
                self.custom_metrics.append(metric)
                merged_count += 1

        return {
            'success': True,
            'merged': merged_count,
            'skipped': skipped_count,
            'total_custom': len(self.custom_metrics)
        }

    def check_version_compatibility(self, required_version=None):
        """
        检查指标库版本兼容性（v2.3 新增）

        Args:
            required_version: 要求的最低版本，如 'v2.2.0'，None表示只检查当前版本

        Returns:
            dict: 版本检查结果
        """
        current_version = 'v2.4.0'

        result = {
            'current_version': current_version,
            'required_version': required_version,
            'is_compatible': True,
            'features': [
                '行业自动识别',
                '分层指标匹配',
                '指标类型判断（正向/反向/区间）',
                '匹配质量评估',
                '自定义指标库合并',
                '用户反馈记录',
                '版本兼容性检查'
            ]
        }

        if required_version:
            # 简单版本比较
            def parse_version(v):
                v = v.lstrip('v')
                parts = v.split('.')
                return tuple(int(p) for p in parts[:3])

            try:
                current = parse_version(current_version)
                required = parse_version(required_version)
                result['is_compatible'] = current >= required
            except Exception:
                result['is_compatible'] = False
                result['error'] = '版本号格式错误'

        return result

    def record_feedback(self, metric_name, industry, feedback_type, feedback_value=None,
                        comment='', user_id='anonymous'):
        """
        记录用户反馈（v2.3 新增）

        Args:
            metric_name: 指标名称
            industry: 行业
            feedback_type: 反馈类型（'benchmark_wrong'/'range_wrong'/'metric_not_found'/'other'）
            feedback_value: 建议的正确值
            comment: 补充说明
            user_id: 用户标识

        Returns:
            dict: 反馈记录
        """
        if not hasattr(self, 'feedback_records'):
            self.feedback_records = []

        import time
        record = {
            'feedback_id': f'FB-{len(self.feedback_records) + 1:04d}',
            'metric_name': metric_name,
            'industry': industry,
            'feedback_type': feedback_type,
            'feedback_value': feedback_value,
            'comment': comment,
            'user_id': user_id,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pending'  # pending/reviewed/applied/rejected
        }

        self.feedback_records.append(record)

        # 检查是否触发自动应用（同一指标同一类型反馈 >=3 条）
        same_feedback = [f for f in self.feedback_records
                        if f['metric_name'] == metric_name
                        and f['industry'] == industry
                        and f['feedback_type'] == feedback_type
                        and f['status'] in ('pending', 'applied')]

        if len(same_feedback) >= 3 and feedback_value:
            record['auto_applied'] = True
            self._apply_feedback(metric_name, industry, feedback_type, feedback_value)

        return record

    def _apply_feedback(self, metric_name, industry, feedback_type, new_value):
        """
        应用用户反馈到指标库（v2.3 新增，内部方法）
        """
        for metric in self.metrics:
            if (metric.get('name') == metric_name
                    and metric.get('industry') == industry):
                if feedback_type == 'benchmark_wrong':
                    try:
                        metric['benchmark'] = float(new_value)
                        metric['benchmark_display'] = str(new_value)
                        metric['feedback_updated'] = True
                    except (ValueError, TypeError):
                        pass
                elif feedback_type == 'range_wrong':
                    # 格式: "min~max"
                    if '~' in str(new_value):
                        parts = str(new_value).split('~')
                        try:
                            metric['min'] = float(parts[0])
                            metric['max'] = float(parts[1])
                            metric['range_display'] = str(new_value)
                            metric['feedback_updated'] = True
                        except (ValueError, TypeError):
                            pass

                # 更新反馈状态
                if hasattr(self, 'feedback_records'):
                    for f in self.feedback_records:
                        if (f['metric_name'] == metric_name
                                and f['industry'] == industry
                                and f['feedback_type'] == feedback_type):
                            f['status'] = 'applied'

    def get_feedback_stats(self):
        """
        获取反馈统计（v2.3 新增）
        """
        if not hasattr(self, 'feedback_records'):
            return {'total': 0, 'by_type': {}, 'by_status': {}}

        by_type = defaultdict(int)
        by_status = defaultdict(int)
        for f in self.feedback_records:
            by_type[f['feedback_type']] += 1
            by_status[f['status']] += 1

        return {
            'total': len(self.feedback_records),
            'by_type': dict(by_type),
            'by_status': dict(by_status),
            'records': self.feedback_records[-10:]  # 最近10条
        }


# ============================================================
# 便捷函数
# ============================================================

def create_matcher(library_path=None):
    """创建完整的匹配引擎实例"""
    library = IndustryMetricLibrary(library_path)
    recognizer = IndustryRecognizer()
    matcher = LayeredMetricMatcher(library)
    return library, recognizer, matcher


if __name__ == '__main__':
    # 简单测试
    library, recognizer, matcher = create_matcher()

    print("=== 指标库统计 ===")
    print(library.get_stats())

    print("\n=== 行业识别测试 ===")
    print("部门'制造部':", recognizer.recognize_from_department('制造部'))
    print("企业'比亚迪':", recognizer.recognize_from_company('比亚迪'))
    print("目标含'度电成本':", recognizer.recognize_from_goals([
        {'title': '降低度电成本', 'indicators': [{'name': '度电成本'}]}
    ]))

    print("\n=== 指标匹配测试 ===")
    results = matcher.match('OEE', goal_level='L1', industry='制造业')
    for r in results:
        print(f"匹配: {r['metric']['name']} (相似度:{r['similarity']}, 类型:{r['metric_type']}, 质量:{r['quality']['quality_grade']})")

    print("\n=== 指标类型测试 ===")
    classifier = MetricTypeClassifier()
    print("收入增长率:", classifier.classify('收入增长率'))
    print("客户流失率:", classifier.classify('客户流失率'))
    print("库存周转率:", classifier.classify('库存周转率'))

    print("\n=== 偏离判断测试 ===")
    print("正向指标-收入(80 vs 100):", classifier.judge_deviation(80, 100, 'positive'))
    print("正向指标-收入(120 vs 100):", classifier.judge_deviation(120, 100, 'positive'))
    print("反向指标-流失率(15 vs 10):", classifier.judge_deviation(15, 10, 'negative'))
    print("反向指标-流失率(5 vs 10):", classifier.judge_deviation(5, 10, 'negative'))
