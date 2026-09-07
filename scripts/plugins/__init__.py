#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件系统
提供可选的增强功能插件，包括：
- 词向量相似度插件
- LLM 语义理解插件
- 主动学习反馈插件

所有插件都是可选的，不会影响核心功能的正常运行。
"""

from .base_plugin import BasePlugin
from .plugin_manager import PluginManager

__all__ = ['BasePlugin', 'PluginManager']
