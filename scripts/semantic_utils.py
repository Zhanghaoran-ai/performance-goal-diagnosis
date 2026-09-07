#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义分析工具模块
提供中文分词、同义词、相似度计算等语义分析能力

v2.0 新增：
- jieba 分词集成
- HR/绩效领域同义词词典
- TF-IDF 关键词权重
- 多维度相似度融合
- 指标类型分类
- 因果方向检测
- 否定词/反向词处理
"""

import re
import math
from collections import defaultdict, Counter
from pathlib import Path

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


class SemanticAnalyzer:
    """语义分析器"""
    
    def __init__(self):
        self.stopwords = self._load_stopwords()
        self.synonyms = self._load_synonyms()
        self.causal_words = self._load_causal_words()
        self.negative_words = self._load_negative_words()
        self.metric_types = self._load_metric_types()
        self.framework_keywords = self._load_framework_keywords()
        
        # 词频统计（用于 TF-IDF）
        self.doc_freq = defaultdict(int)
        self.total_docs = 0
    
    def _load_stopwords(self):
        """加载停用词"""
        return {
            '的', '了', '和', '与', '及', '或', '在', '是', '有', '为', '以', '到', '从',
            '向', '对', '等', '中', '上', '下', '率', '度', '量', '数', '比', '值', '个',
            '项', '次', '天', '月', '年', '人', '元', '万', '亿', '之', '其', '此', '该',
            '每', '各', '某', '其他', '其它', '以及', '或者', '还是', '就是', '可以',
            '能够', '需要', '应该', '必须', '将', '会', '要', '把', '被', '让', '使',
        }
    
    def _load_synonyms(self):
        """加载 HR/绩效领域同义词词典"""
        # 格式：{标准词: [同义词1, 同义词2, ...]}
        synonyms = {
            # 收入相关
            '收入': ['营收', '销售额', '营业额', '流水', '销售收入'],
            '利润': ['盈利', '收益', '获益', '净利', '毛利'],
            '成本': ['费用', '开支', '支出', '花费'],
            
            # 用户/客户相关
            '用户': ['客户', '顾客', '客群', '使用者', '用户群'],
            '客户满意度': ['用户满意度', '客户体验', '用户体验', '满意度', 'CSAT', 'NPS'],
            '留存': ['保留', '留存率', '保留率', '复购', '续费率'],
            '流失': ['流失率', '流失率', ' churn ', ' attrition '],
            '增长': ['提升', '增加', '提高', '上涨', '上升', '增长', '增幅'],
            
            # 效率相关
            '效率': ['效能', '生产率', '产出率', '人效'],
            '人均': ['平均每人', '人均产出', '人均效率'],
            
            # 质量相关
            '质量': ['品质', '质量水平', '品质水平'],
            '合格率': ['良品率', '达标率', '通过率'],
            '缺陷': ['不良', '瑕疵', '问题', '错误'],
            
            # 时间相关
            '周期': ['时长', '时间', '耗时', '周期时间'],
            '速度': ['效率', '快慢', '响应速度'],
            '及时': ['准时', '按时', '按期', '准时率', '及时率'],
            
            # 员工相关
            '员工': ['人员', '人力', '团队成员', '职工'],
            '员工满意度': ['员工体验', '团队满意度', '组织满意度', 'eNPS'],
            '培训': ['培养', '学习', '发展', '赋能'],
            '绩效': ['业绩', '表现', '成效', '成果'],
            
            # 目标相关
            '目标': ['指标', 'KPI', 'OKR', '目的', '方向'],
            '达成': ['完成', '实现', '达到', '达标'],
            '落地': ['执行', '实施', '推行', '落实'],
            
            # 产品/服务相关
            '产品': ['服务', '解决方案', ' offerings '],
            '功能': ['特性', '能力', '模块'],
            '体验': ['感受', '使用体验', '用户感受'],
            
            # 运营相关
            '运营': ['运作', '经营', '运维'],
            '流程': ['过程', '工序', '流程化'],
            '优化': ['改进', '提升', '完善', '升级'],
            
            # 销售/市场相关
            '销售': ['售卖', '营收', '业绩'],
            '市场': ['营销', '品牌', '推广'],
            '渠道': ['通路', '途径', '销售渠道'],
            
            # 技术相关
            '技术': ['科技', '研发', '技术能力'],
            '系统': ['平台', '工具', '软件'],
            '稳定性': ['可靠性', '可用性', '健壮性'],
            
            # 创新相关
            '创新': ['革新', '突破', '新事物'],
            '研发': ['开发', '研究', '技术开发'],
            
            # 战略相关
            '战略': ['策略', '规划', '方向'],
            '布局': ['规划', '排布', '战略布局'],
            
            # HR 特有
            '招聘': ['招募', '招人', '人才引进'],
            '入职': ['到岗', '入职率', '到岗率'],
            '离职': ['离职率', '流失率', ' attrition '],
            '晋升': ['升迁', '升职', '晋升率'],
            '薪酬': ['薪资', '工资', '报酬', '薪酬福利'],
            '绩效': ['业绩', '考核', '绩效管理'],
            '人才': ['骨干', '核心员工', '人才梯队'],
            '组织': ['团队', '部门', '组织架构'],
            '文化': ['企业文化', '团队文化', '价值观'],
            '赋能': ['授权', '能力建设', '能力提升'],
            '梯队': ['人才梯队', '后备力量', '接班人计划'],
            
            # 客户成功特有
            '客户成功': ['CS', '客户成功经理', 'CSM'],
            '续约': ['续费', '续签', '续约率'],
            '增购': ['扩容', '升级', 'upsell'],
            '健康度': ['客户健康', '健康评分', '客户健康度'],
            '价值': ['价值实现', '价值交付', '客户价值'],
            '落地': ['上线', '实施', '交付'],
            ' adoption ': ['使用率', '采纳率', '使用深度'],
            '激活': ['活跃', '启动', '用户激活'],
        }
        
        # 构建反向索引
        reverse_map = {}
        for standard, syn_list in synonyms.items():
            for syn in syn_list:
                syn_lower = syn.lower().strip()
                if syn_lower not in reverse_map:
                    reverse_map[syn_lower] = standard
            # 标准词自己也映射到自己
            reverse_map[standard.lower().strip()] = standard
        
        self.synonym_reverse = reverse_map
        return synonyms
    
    def _load_causal_words(self):
        """加载因果关系词"""
        return {
            # 原因/驱动词（因在前，果在后）
            'cause': [
                '驱动', '导致', '带来', '引起', '促使', '使得', '造成', '影响',
                '推动', '促进', '提升', '提高', '增加', '减少', '降低', '改善',
                '因为', '由于', '源于', '来源于', '出自',
                '通过', '依靠', '凭借', '基于',
            ],
            # 结果/产出词（果在前，因在后）
            'result': [
                '结果', '成果', '效果', '产出', '收益', '回报',
                '所以', '因此', '因而', '于是', '从而',
                '实现', '达成', '完成', '达到',
                '体现为', '表现为', '反映在',
            ],
            # 过程指标特征词
            'process': [
                '完成率', '达成率', '执行率', '覆盖率', '参与率',
                '数量', '次数', '频次', '时长', '周期',
                '速度', '效率', '及时率', '准时率',
                '质量', '合格率', '良品率', '缺陷率',
                '投入', '成本', '费用', '资源',
            ],
            # 结果指标特征词
            'result_metric': [
                '收入', '营收', '利润', '增长', '增长率',
                '满意度', '留存率', '市场份额', '市场占比',
                'ROI', '回报率', '收益率',
                '市场地位', '品牌影响力', '竞争力',
            ]
        }
    
    def _load_negative_words(self):
        """加载否定词和反向词"""
        return {
            'negation': [
                '不', '没', '无', '非', '未', '否', '莫', '勿', '别',
                '不是', '没有', '不会', '不能', '不可', '不要',
            ],
            'reverse_direction': [
                '降低', '减少', '下降', '削减', '压缩', '控制',
                '优化成本', '降本', '减耗', '节流',
                '缩短', '加快', '提升效率', '提高效率',
            ],
            'reverse_metrics': [
                '流失率', '离职率', '缺陷率', '错误率', '故障率',
                '投诉率', '退货率', '差评率', '风险', '成本',
                '费用', '耗时', '周期', '延迟',
            ]
        }
    
    def _load_metric_types(self):
        """加载指标类型分类关键词"""
        return {
            '财务': ['收入', '营收', '利润', '成本', '费用', 'ROI', '回报率', '收益率', '毛利', '净利', '销售额', '营业额', '预算', '支出', '节约'],
            '客户': ['客户', '用户', '满意度', '留存', '流失', 'NPS', 'CSAT', '体验', '续约', '增购', '投诉', '表扬', '口碑', '市场份额'],
            '内部流程': ['流程', '效率', '质量', '合格率', '周期', '速度', '及时率', '准时率', '完成率', '执行率', '优化', '改进', '运营'],
            '学习成长': ['培训', '学习', '发展', '成长', '人才', '能力', '技能', '知识', '创新', '研发', '组织能力', '梯队', '赋能'],
            '员工': ['员工', '人员', '人力', '团队', '满意度', '敬业度', '离职', '入职', '招聘', '晋升', '绩效', '薪酬', '文化'],
            '产品': ['产品', '功能', '体验', '质量', '性能', '稳定性', '可用性', '迭代', '版本', '上线', '发布'],
            '技术': ['技术', '系统', '平台', '架构', '性能', '稳定性', '安全', '研发', '代码', '算法', '数据'],
            '运营': ['运营', '活动', '推广', '营销', '渠道', '用户增长', '拉新', '促活', '转化', '留存'],
            '销售': ['销售', '业绩', '订单', '成交', '客户', '商机', ' pipeline ', '转化率', '客单价', '复购'],
            '市场': ['市场', '品牌', '知名度', '影响力', '曝光', '流量', '公关', '活动', '发布会'],
        }
    
    def _load_framework_keywords(self):
        """加载管理框架关键词（用于维度完整性检测）"""
        return {
            '平衡计分卡': {
                '财务': ['收入', '利润', '成本', 'ROI', '增长', '营收', '销售额'],
                '客户': ['客户', '用户', '满意度', '留存', '市场份额', 'NPS'],
                '内部流程': ['流程', '效率', '质量', '周期', '速度', '运营'],
                '学习成长': ['培训', '学习', '创新', '人才', '能力', '发展'],
            },
            '人机料法环': {
                '人': ['员工', '人员', '团队', '人才', '能力', '技能', '培训'],
                '机': ['设备', '系统', '工具', '平台', '技术', '机器'],
                '料': ['物料', '材料', '原料', '资源', '供应', '库存'],
                '法': ['方法', '流程', '制度', '规范', '标准', '工艺'],
                '环': ['环境', '氛围', '文化', '条件', '场景'],
            },
            '4P营销': {
                '产品': ['产品', '功能', '质量', '服务', '体验'],
                '价格': ['价格', '定价', '成本', '利润', '优惠'],
                '渠道': ['渠道', '通路', '销售', '分销', '网点'],
                '促销': ['促销', '推广', '营销', '广告', '活动'],
            },
            '项目管理铁三角': {
                '范围': ['范围', '需求', '功能', '内容', '交付物'],
                '时间': ['时间', '进度', '周期', '截止', '里程碑', '按时'],
                '成本': ['成本', '预算', '费用', '投入', '资源'],
                '质量': ['质量', '品质', '标准', '要求', '达标'],
            },
        }
    
    def tokenize(self, text):
        """
        分词
        优先使用 jieba，回退到简单 n-gram
        """
        text = text.lower().strip()
        
        if JIEBA_AVAILABLE:
            # 使用 jieba 分词
            words = jieba.lcut(text)
            # 过滤停用词和单字
            result = []
            for w in words:
                w = w.strip()
                if len(w) < 2:
                    continue
                if w in self.stopwords:
                    continue
                if re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', w):
                    result.append(w)
            return result
        else:
            # 简单 n-gram 分词
            return self._simple_tokenize(text)
    
    def _simple_tokenize(self, text):
        """简单分词（n-gram）"""
        keywords = set()
        # 提取2-4字的词组
        for n in [2, 3, 4]:
            for i in range(len(text) - n + 1):
                word = text[i:i+n]
                if re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', word):
                    if not any(sw in word for sw in self.stopwords):
                        keywords.add(word)
        
        # 也加入单个有意义的字
        for char in text:
            if '\u4e00' <= char <= '\u9fa5' and char not in self.stopwords:
                keywords.add(char)
        
        return list(keywords)
    
    def normalize_word(self, word):
        """
        词归一化（同义词替换为标准词）
        """
        word_lower = word.lower().strip()
        return self.synonym_reverse.get(word_lower, word)
    
    def extract_keywords(self, text, use_tfidf=False):
        """
        提取关键词（带同义词归一化）
        结合 jieba 分词 + 字符级 n-gram，确保同义词能被识别
        """
        # 1. jieba 分词
        words = self.tokenize(text)
        
        # 2. 补充字符级 bigram 和 trigram（确保常见词能被提取）
        chars = list(text.lower().strip())
        if len(chars) >= 2:
            bigrams = [''.join(chars[i:i+2]) for i in range(len(chars)-1)]
            words.extend(bigrams)
        if len(chars) >= 3:
            trigrams = [''.join(chars[i:i+3]) for i in range(len(chars)-2)]
            words.extend(trigrams)
        
        # 3. 同义词归一化
        normalized = [self.normalize_word(w) for w in words]
        
        # 4. 过滤停用词和单字
        filtered = [w for w in normalized if w not in self.stopwords and len(w) > 1]
        
        # 5. 去重
        unique = list(set(filtered))
        
        if use_tfidf and self.total_docs > 0:
            # 按 TF-IDF 权重排序
            scored = []
            for w in unique:
                tf = 1  # 单文档中词频都是1
                df = self.doc_freq.get(w, 1)
                idf = math.log(self.total_docs / df)
                score = tf * idf
                scored.append((w, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [w for w, s in scored]
        
        return unique
    
    def add_document(self, text):
        """
        添加文档到语料库（用于计算 TF-IDF）
        """
        words = self.tokenize(text)
        unique_words = set(words)
        for w in unique_words:
            self.doc_freq[w] += 1
        self.total_docs += 1
    
    def jaccard_similarity(self, set1, set2):
        """Jaccard 相似度"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def char_similarity(self, text1, text2):
        """字符级相似度（编辑距离）"""
        # 简单的字符重叠度
        chars1 = set(text1)
        chars2 = set(text2)
        return self.jaccard_similarity(chars1, chars2)
    
    def word_similarity(self, text1, text2):
        """词语级相似度（基于分词和同义词）
        使用改进的相似度计算：考虑共同核心词的比例
        """
        keywords1 = set(self.extract_keywords(text1))
        keywords2 = set(self.extract_keywords(text2))
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # 共同关键词
        common = keywords1 & keywords2
        
        # 使用重叠系数（overlap coefficient）：交集 / 较小集合的大小
        # 这样更适合检测"是否包含共同核心词"的场景
        min_size = min(len(keywords1), len(keywords2))
        if min_size == 0:
            return 0.0
        
        overlap_sim = len(common) / min_size
        
        # Jaccard 相似度
        jaccard_sim = self.jaccard_similarity(keywords1, keywords2)
        
        # 融合两种相似度（重叠系数权重更高，因为我们更关心是否有共同核心词）
        final_sim = overlap_sim * 0.6 + jaccard_sim * 0.4
        
        return final_sim
    
    def structural_similarity(self, metric1_info, metric2_info):
        """
        结构相似度（基于指标在树中的位置、层级、类型等）
        metric_info: {'level': int, 'type': str, 'parent_type': str, 'siblings': list}
        """
        score = 0.0
        factors = 0
        
        # 同层级加分
        if metric1_info.get('level') and metric2_info.get('level'):
            factors += 1
            if metric1_info['level'] == metric2_info['level']:
                score += 1
        
        # 同类型加分
        if metric1_info.get('type') and metric2_info.get('type'):
            factors += 1
            if metric1_info['type'] == metric2_info['type']:
                score += 1
        
        # 同父类型加分
        if metric1_info.get('parent_type') and metric2_info.get('parent_type'):
            factors += 1
            if metric1_info['parent_type'] == metric2_info['parent_type']:
                score += 1
        
        return score / factors if factors > 0 else 0.0
    
    def multi_dim_similarity(self, text1, text2, metric1_info=None, metric2_info=None,
                             weights=None):
        """
        多维度相似度融合
        维度：字符相似度 + 词语相似度 + 结构相似度
        """
        if weights is None:
            weights = {
                'char': 0.2,
                'word': 0.6,
                'structure': 0.2,
            }
        
        char_sim = self.char_similarity(text1, text2)
        word_sim = self.word_similarity(text1, text2)
        
        if metric1_info and metric2_info:
            struct_sim = self.structural_similarity(metric1_info, metric2_info)
        else:
            struct_sim = 0.0
            weights['structure'] = 0
            # 重新归一化权重
            total = weights['char'] + weights['word']
            weights['char'] /= total
            weights['word'] /= total
        
        total_sim = (
            char_sim * weights['char'] +
            word_sim * weights['word'] +
            struct_sim * weights['structure']
        )
        
        return total_sim
    
    def classify_metric_type(self, text):
        """
        分类指标类型（财务/客户/内部流程/学习成长等）
        """
        text_lower = text.lower()
        scores = defaultdict(int)
        
        for mtype, keywords in self.metric_types.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    scores[mtype] += 1
        
        if not scores:
            return '其他'
        
        # 返回得分最高的类型
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def detect_causal_direction(self, parent_text, child_text):
        """
        检测因果方向是否正确
        返回：
        - 'correct': 因果方向正确（子是因，父是果）
        - 'reverse': 因果倒置（父是因，子是果）
        - 'unclear': 无法判断
        """
        parent_lower = parent_text.lower()
        child_lower = child_text.lower()
        
        # 检查父指标是否是结果指标
        parent_is_result = any(kw in parent_lower for kw in self.causal_words['result_metric'])
        # 检查子指标是否是过程指标
        child_is_process = any(kw in child_lower for kw in self.causal_words['process'])
        
        if parent_is_result and child_is_process:
            return 'correct'
        
        # 检查父指标是否有过程特征
        parent_is_process = any(kw in parent_lower for kw in self.causal_words['process'])
        # 检查子指标是否有结果特征
        child_is_result = any(kw in child_lower for kw in self.causal_words['result_metric'])
        
        if parent_is_process and child_is_result:
            return 'reverse'
        
        # 检查因果词
        parent_has_cause = any(kw in parent_lower for kw in self.causal_words['cause'])
        child_has_result = any(kw in child_lower for kw in self.causal_words['result'])
        
        if parent_has_cause and child_has_result:
            return 'reverse'
        
        child_has_cause = any(kw in child_lower for kw in self.causal_words['cause'])
        parent_has_result = any(kw in parent_lower for kw in self.causal_words['result'])
        
        if child_has_cause and parent_has_result:
            return 'correct'
        
        return 'unclear'
    
    def is_negative_metric(self, text):
        """判断是否是反向指标（越低越好）"""
        text_lower = text.lower()
        
        # 检查是否有反向指标特征词
        for kw in self.negative_words['reverse_metrics']:
            if kw in text_lower:
                return True
        
        # 检查是否有否定词 + 正向词的组合
        for neg in self.negative_words['negation']:
            if neg in text_lower:
                return True
        
        return False
    
    def check_dimension_completeness(self, metrics_text_list, framework='平衡计分卡'):
        """
        检查维度完整性
        返回：{维度: 覆盖数, ...}，以及缺失的维度
        """
        framework_kw = self.framework_keywords.get(framework, {})
        if not framework_kw:
            return None
        
        coverage = {}
        for dim, keywords in framework_kw.items():
            count = 0
            for metric_text in metrics_text_list:
                metric_lower = metric_text.lower()
                if any(kw.lower() in metric_lower for kw in keywords):
                    count += 1
            coverage[dim] = count
        
        # 计算覆盖率
        covered_dims = sum(1 for c in coverage.values() if c > 0)
        total_dims = len(coverage)
        coverage_rate = covered_dims / total_dims if total_dims > 0 else 0
        
        missing_dims = [dim for dim, count in coverage.items() if count == 0]
        
        return {
            'framework': framework,
            'coverage': coverage,
            'coverage_rate': coverage_rate,
            'covered_dims': covered_dims,
            'total_dims': total_dims,
            'missing_dims': missing_dims,
        }
    
    def detect_granularity(self, text):
        """
        检测指标粒度
        返回：'strategic'（战略级）, 'managerial'（管理级）, 'operational'（执行级）
        """
        text_lower = text.lower()
        
        # 战略级特征词
        strategic_words = [
            '战略', '整体', '全局', '公司', '集团', '总体', '综合',
            '收入', '利润', '市场份额', '品牌', '竞争力', '增长',
            '满意度', '留存率', 'ROI', '回报率',
        ]
        
        # 执行级特征词
        operational_words = [
            '日', '班', '次', '个', '件', '单',
            '完成率', '合格率', '及时率', '准确率',
            '数量', '次数', '时长', '速度',
            '点检', '巡检', '操作', '执行',
            '拜访', '电话', '邮件', '工单',
        ]
        
        strategic_score = sum(1 for w in strategic_words if w in text_lower)
        operational_score = sum(1 for w in operational_words if w in text_lower)
        
        if strategic_score > operational_score:
            return 'strategic'
        elif operational_score > strategic_score:
            return 'operational'
        else:
            return 'managerial'
    
    def check_granularity_consistency(self, metrics_text_list):
        """
        检查一组指标的粒度一致性
        返回：{level: count, ...}, consistency_score
        """
        levels = [self.detect_granularity(t) for t in metrics_text_list]
        level_counts = Counter(levels)
        
        # 一致性得分：最多的层级占比
        if not levels:
            return {}, 0.0
        
        max_count = max(level_counts.values())
        consistency = max_count / len(levels)
        
        return dict(level_counts), consistency
    
    def detect_logical_closure(self, metrics_text_list):
        """
        检测逻辑闭环（输入-过程-输出）
        返回：{input: count, process: count, output: count}, is_closed
        """
        input_words = ['投入', '资源', '成本', '人力', '预算', '输入', '原料', '设备']
        process_words = ['效率', '质量', '速度', '周期', '完成率', '执行', '流程', '过程']
        output_words = ['收入', '利润', '产出', '结果', '成果', '满意度', '增长', '价值']
        
        counts = {'input': 0, 'process': 0, 'output': 0}
        
        for text in metrics_text_list:
            text_lower = text.lower()
            if any(w in text_lower for w in input_words):
                counts['input'] += 1
            if any(w in text_lower for w in process_words):
                counts['process'] += 1
            if any(w in text_lower for w in output_words):
                counts['output'] += 1
        
        # 是否形成闭环（三个维度都有指标）
        is_closed = all(c > 0 for c in counts.values())
        
        return counts, is_closed
    
    def check_naming_quality(self, text):
        """
        检查指标命名质量
        返回：{has_unit: bool, is_actionable: bool, has_verb: bool, score: float}
        """
        issues = []
        score = 1.0
        
        # 检查是否有明确的度量单位/量化方式
        unit_patterns = ['率', '度', '量', '数', '比', '值', '时间', '周期', '金额', '元', '个', '次', '天']
        has_unit = any(p in text for p in unit_patterns)
        if not has_unit:
            issues.append('缺少明确的度量单位')
            score -= 0.3
        
        # 检查是否是模糊表述
        vague_words = ['提升', '优化', '加强', '改善', '提高', '降低', '减少', '增加', '推动', '促进']
        is_vague = any(w in text for w in vague_words) and not has_unit
        if is_vague:
            issues.append('表述模糊，缺少量化标准')
            score -= 0.2
        
        # 检查是否有明确的对象
        has_object = len(text) >= 4  # 简单判断，太短可能不明确
        if not has_object:
            issues.append('指标名称过短，可能不明确')
            score -= 0.2
        
        # 检查是否包含否定词（可能表述不清）
        has_negation = any(neg in text for neg in self.negative_words['negation'])
        if has_negation:
            issues.append('包含否定词，建议用正向表述')
            score -= 0.1
        
        score = max(0.0, min(1.0, score))
        
        return {
            'score': score,
            'has_unit': has_unit,
            'is_vague': is_vague,
            'issues': issues,
        }

    def assess_relationship(self, parent_text, child_text,
                            parent_value=None, child_value=None,
                            parent_children_values=None):
        """
        四层语义关联评估（v2.5 新增）

        判断"上级指标能否被下级指标真正支撑"，而非仅看指标名是否相似。
        由粗到细四层判定，每层独立计分，供诊断与树视图复用：

        1. 词面层（lexical）：字符重叠 / Jaccard 相似度 —— 捕捉明显重复与复制嫌疑
        2. 语义层（semantic）：分词 + 同义词的多维相似度 —— 捕捉"换说法"的假拆解
        3. 因果层（causal）：过程(因) → 结果(果) 方向判定 —— 判断下级是否真正驱动上级
        4. 数值链路层（numeric）：下级目标值加总 vs 上级目标值 —— 判断数值是否闭合

        返回结构化结果：
        {
          'overall': float,          # 综合关联度 0~1
          'level': 'strong'|'medium'|'weak'|'none',
          'layers': {
             'lexical': {'score': float, 'detail': str},
             'semantic': {'score': float, 'detail': str},
             'causal': {'score': float, 'direction': 'correct'|'reverse'|'unknown', 'detail': str},
             'numeric': {'score': float, 'ratio': float|None, 'match': bool|None, 'detail': str},
          },
          'flags': [str],            # 风险标记：如 'fake_split'(假拆解) 'numeric_mismatch'(数值不闭合) 'causal_reverse'(因果倒置)
          'needs_review': bool,      # 是否建议人工复核
        }
        """
        # 输入容错：真实数据中的指标名称可能为空或为 None。
        # 统一转为空字符串，保证分词、字符集合和因果判断不抛异常。
        parent_text = str(parent_text or '').strip()
        child_text = str(child_text or '').strip()

        flags = []

        # —— 第1层：词面相似度 ——
        lexical_sim = self.multi_dim_similarity(parent_text, child_text)
        lexical_detail = f"多维度相似度 {lexical_sim:.0%}"
        # 包含关系检测：子指标名包含父指标名（典型"岗位前缀+父指标名"复制模式）
        contains = False
        if parent_text and child_text:
            if parent_text in child_text or child_text in parent_text:
                contains = True
        if contains and lexical_sim >= 0.6:
            flags.append('fake_split')
            lexical_score = 1.0
            lexical_detail += f"（{parent_text} 与 {child_text} 互为包含，疑似岗位前缀复制）"
        elif lexical_sim >= 0.85:
            flags.append('fake_split')
            lexical_score = 1.0
            lexical_detail += "（词面高度相似，存在假拆解风险）"
        elif lexical_sim >= 0.5:
            lexical_score = 0.7
        elif lexical_sim >= 0.3:
            lexical_score = 0.4
        else:
            lexical_score = 0.1

        # —— 第2层：语义相似度（同义词映射后） ——
        semantic_sim = self.word_similarity(parent_text, child_text)
        semantic_detail = f"语义相似度 {semantic_sim:.0%}"
        if semantic_sim >= 0.85:
            flags.append('semantic_overlap')
            semantic_score = 1.0
            semantic_detail += "（语义高度重叠）"
        elif semantic_sim >= 0.5:
            semantic_score = 0.8
        elif semantic_sim >= 0.3:
            semantic_score = 0.5
        else:
            semantic_score = 0.2

        # —— 第3层：因果方向 ——
        causal = self.detect_causal_direction(parent_text, child_text)
        # 兼容当前字符串返回值，也兼容插件/未来实现可能返回的结构化字典。
        if isinstance(causal, dict):
            direction = causal.get('direction', 'unknown')
        elif causal in ('correct', 'reverse', 'unclear', 'unknown'):
            direction = 'unknown' if causal == 'unclear' else causal
        else:
            direction = 'unknown'
        causal_detail = "因果方向"
        if direction == 'reverse':
            flags.append('causal_reverse')
            causal_score = 0.0
            causal_detail += "倒置（下级是结果而非驱动因素）"
        elif direction == 'correct':
            causal_score = 1.0
            causal_detail += "正确（下级是因，上级是果）"
        else:
            causal_score = 0.5
            causal_detail += "不明显，需人工判断"

        # —— 第4层：数值链路 ——
        numeric_score = 0.5   # 默认中性（无数值时不判定，不罚分）
        numeric_detail = "未提供数值，跳过数值链路校验"
        numeric_ratio = None
        numeric_match = None
        if parent_value is not None and child_value is not None:
            try:
                pv = float(parent_value)
                cv = float(child_value)
                if pv > 0:
                    ratio = cv / pv
                    numeric_ratio = ratio
                    numeric_detail = f"子指标值 {cv:g} vs 父指标值 {pv:g}（比值 {ratio:.1%}）"
                    if ratio > 1.5 or ratio < 0.5:
                        numeric_score = 0.0
                        numeric_match = False
                        flags.append('numeric_mismatch')
                        numeric_detail += "：数值缺口过大，链路断裂"
                    elif ratio > 1.2 or ratio < 0.8:
                        numeric_score = 0.5
                        numeric_match = False
                        numeric_detail += "：数值存在偏差，建议复核"
                    else:
                        numeric_score = 1.0
                        numeric_match = True
                        numeric_detail += "：数值基本闭合"
            except (TypeError, ValueError):
                pass
        elif parent_value is not None and parent_children_values:
            # 父值 vs 子值加总
            try:
                pv = float(parent_value)
                sum_children = sum(float(v) for v in parent_children_values
                                   if v is not None)
                if pv > 0 and sum_children > 0:
                    ratio = sum_children / pv
                    numeric_ratio = ratio
                    numeric_detail = f"子指标值加总 {sum_children:g} vs 父指标值 {pv:g}（比值 {ratio:.1%}）"
                    if ratio > 1.5 or ratio < 0.5:
                        numeric_score = 0.0
                        numeric_match = False
                        flags.append('numeric_mismatch')
                        numeric_detail += "：数值缺口过大，链路断裂"
                    elif ratio > 1.2 or ratio < 0.8:
                        numeric_score = 0.5
                        numeric_match = False
                        numeric_detail += "：数值存在偏差，建议复核"
                    else:
                        numeric_score = 1.0
                        numeric_match = True
                        numeric_detail += "：数值基本闭合"
            except (TypeError, ValueError):
                pass

        # —— 综合判定 ——
        # 权重：语义层最高，因果层其次，词面与数值链路辅助
        overall = (lexical_score * 0.15 +
                   semantic_score * 0.4 +
                   causal_score * 0.25 +
                   numeric_score * 0.2)

        # 假拆解与因果倒置是"硬"风险信号，直接压级
        if 'causal_reverse' in flags:
            overall = min(overall, 0.2)
        elif 'fake_split' in flags:
            overall = min(overall, 0.35)

        if overall >= 0.75:
            level = 'strong'
        elif overall >= 0.5:
            level = 'medium'
        elif overall >= 0.3:
            level = 'weak'
        else:
            level = 'none'

        needs_review = (bool(flags) or level in ('weak', 'none'))

        return {
            'overall': round(overall, 3),
            'level': level,
            'layers': {
                'lexical': {'score': lexical_score, 'detail': lexical_detail},
                'semantic': {'score': semantic_score, 'detail': semantic_detail},
                'causal': {'score': causal_score, 'direction': direction, 'detail': causal_detail},
                'numeric': {'score': numeric_score, 'ratio': numeric_ratio,
                            'match': numeric_match, 'detail': numeric_detail},
            },
            'flags': flags,
            'needs_review': needs_review,
        }


# 全局单例
_semantic_analyzer = None

def get_semantic_analyzer():
    """获取语义分析器单例"""
    global _semantic_analyzer
    if _semantic_analyzer is None:
        _semantic_analyzer = SemanticAnalyzer()
    return _semantic_analyzer


if __name__ == '__main__':
    # 测试
    analyzer = SemanticAnalyzer()
    
    print("=== 分词测试 ===")
    test_texts = [
        "客户满意度提升",
        "营收增长率",
        "员工培训完成率",
        "产品迭代速度",
    ]
    for text in test_texts:
        words = analyzer.tokenize(text)
        keywords = analyzer.extract_keywords(text)
        print(f"{text}: {words}")
        print(f"  关键词: {keywords}")
    
    print("\n=== 相似度测试 ===")
    pairs = [
        ("客户满意度", "用户满意度"),
        ("营收增长", "收入提升"),
        ("员工培训", "人才发展"),
        ("产品质量", "客户体验"),
    ]
    for t1, t2 in pairs:
        sim = analyzer.multi_dim_similarity(t1, t2)
        print(f"{t1} vs {t2}: {sim:.2%}")
    
    print("\n=== 指标类型分类 ===")
    for text in test_texts:
        mtype = analyzer.classify_metric_type(text)
        print(f"{text}: {mtype}")
    
    print("\n=== 粒度检测 ===")
    for text in test_texts:
        level = analyzer.detect_granularity(text)
        print(f"{text}: {level}")
    
    print("\n=== 命名质量检查 ===")
    for text in test_texts:
        quality = analyzer.check_naming_quality(text)
        print(f"{text}: {quality['score']:.0%} - {quality['issues']}")
