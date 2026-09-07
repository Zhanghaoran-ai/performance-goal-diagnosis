#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件基类
所有插件都继承自这个基类
"""

from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """插件基类"""
    
    def __init__(self, name, version='1.0.0'):
        self.name = name
        self.version = version
        self.enabled = False
        self.initialized = False
    
    @abstractmethod
    def initialize(self, **kwargs):
        """
        初始化插件
        返回 True 表示初始化成功，False 表示失败
        """
        pass
    
    @abstractmethod
    def get_capabilities(self):
        """
        返回插件提供的能力列表
        例如：['semantic_similarity', 'causal_detection', 'classification']
        """
        pass
    
    def is_available(self):
        """检查插件是否可用"""
        return self.enabled and self.initialized
    
    def cleanup(self):
        """清理资源"""
        pass
    
    def __str__(self):
        return f"{self.name} v{self.version} ({'enabled' if self.enabled else 'disabled'})"
