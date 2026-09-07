#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 语义理解插件
使用大语言模型进行深层语义理解和判断

【可选插件】需要配置 LLM API 密钥
如果没有配置，插件会自动禁用，不影响核心功能
"""

import json
from .base_plugin import BasePlugin


class LLMPlugin(BasePlugin):
    """LLM 语义理解插件"""
    
    def __init__(self):
        super().__init__('LLMPlugin', '1.0.0')
        self.api_key = None
        self.api_base = None
        self.model = None
        self.client = None
    
    def initialize(self, api_key=None, api_base=None, model='gpt-3.5-turbo', **kwargs):
        """
        初始化 LLM 插件
        
        Args:
            api_key: API 密钥
            api_base: API 基础地址
            model: 使用的模型名称
        """
        if api_key is None:
            # 尝试从环境变量获取
            import os
            api_key = os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY')
            
            if api_key is None:
                print("  ℹ️  未配置 LLM API 密钥，LLM 插件将不启用")
                return False
        
        self.api_key = api_key
        self.api_base = api_base or 'https://api.openai.com/v1'
        self.model = model
        
        try:
            # 尝试导入 openai 库
            import openai
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
            self.initialized = True
            print(f"  ✅ LLM 插件初始化成功（模型: {self.model}）")
            return True
        except ImportError:
            print("  ℹ️  未安装 openai 库，LLM 插件将不启用")
            print("     安装命令: pip install openai")
            return False
        except Exception as e:
            print(f"  ❌ LLM 插件初始化失败: {e}")
            return False
    
    def get_capabilities(self):
        return [
            'deep_semantic_analysis',
            'causal_relationship_detection',
            'metric_quality_evaluation',
            'goal_alignment_check',
            'industry_best_practice',
        ]
    
    def deep_semantic_analysis(self, text1, text2):
        """
        深层语义分析，判断两个指标的语义关系
        返回：{similarity: float, relationship: str, explanation: str}
        """
        if not self.initialized:
            return None
        
        prompt = f"""
请分析以下两个绩效指标之间的语义关系：

指标1：{text1}
指标2：{text2}

请从以下几个维度分析：
1. 语义相似度（0-1之间的数值）
2. 关系类型（同义/包含/交叉/无关/因果）
3. 简要说明理由

请以 JSON 格式返回，格式如下：
{{
  "similarity": 0.85,
  "relationship": "包含",
  "explanation": "指标2是指标1的一个具体方面"
}}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个绩效指标分析专家，擅长分析指标之间的语义关系。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            # 尝试解析 JSON
            try:
                # 提取 JSON 部分
                if '```json' in result_text:
                    result_text = result_text.split('```json')[1].split('```')[0]
                elif '```' in result_text:
                    result_text = result_text.split('```')[1].split('```')[0]
                
                result = json.loads(result_text)
                return result
            except json.JSONDecodeError:
                return {"similarity": 0.5, "relationship": "unknown", "explanation": result_text}
                
        except Exception as e:
            print(f"  ⚠️  LLM 调用失败: {e}")
            return None
    
    def causal_relationship_detection(self, parent_metric, child_metric):
        """
        检测因果关系是否正确
        返回：{is_correct: bool, direction: str, explanation: str}
        """
        if not self.initialized:
            return None
        
        prompt = f"""
请判断以下绩效指标的因果关系是否正确：

父指标（结果）：{parent_metric}
子指标（驱动）：{child_metric}

请判断：
1. 因果方向是否正确（子指标应该是因，父指标应该是果）
2. 如果不正确，正确的方向应该是什么
3. 简要说明理由

请以 JSON 格式返回。
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个绩效管理专家，擅长分析指标之间的因果关系。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            return {"result": result_text}
            
        except Exception as e:
            print(f"  ⚠️  LLM 调用失败: {e}")
            return None
    
    def metric_quality_evaluation(self, metric_name):
        """
        评估指标命名质量
        返回：{score: float, issues: list, suggestions: list}
        """
        if not self.initialized:
            return None
        
        prompt = f"""
请评估以下绩效指标的命名质量：

指标名称：{metric_name}

请从以下几个维度评估（满分100分）：
1. 是否有明确的度量单位
2. 是否清晰可衡量
3. 是否有明确的对象和范围
4. 是否避免了模糊表述

请指出存在的问题，并给出改进建议。

请以 JSON 格式返回。
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个绩效管理专家，擅长设计和评估绩效指标。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content.strip()
            return {"result": result_text}
            
        except Exception as e:
            print(f"  ⚠️  LLM 调用失败: {e}")
            return None
    
    def cleanup(self):
        """清理资源"""
        self.client = None
        self.initialized = False
