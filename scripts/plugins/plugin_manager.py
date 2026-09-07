#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件管理器
负责加载、初始化和管理所有插件
"""

import importlib
from pathlib import Path


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins = {}
        self.plugin_dir = Path(__file__).parent
    
    def discover_plugins(self):
        """自动发现插件目录中的所有插件"""
        plugins = []
        
        for file in self.plugin_dir.glob('*_plugin.py'):
            if file.name.startswith('_'):
                continue
            
            module_name = f"plugins.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                # 查找模块中的插件类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and hasattr(attr, 'initialize') and hasattr(attr, 'get_capabilities'):
                        if attr.__name__ != 'BasePlugin':
                            plugins.append(attr)
            except Exception as e:
                print(f"  ⚠️  加载插件 {file.name} 失败: {e}")
        
        return plugins
    
    def load_plugin(self, plugin_class, **kwargs):
        """加载并初始化一个插件"""
        try:
            plugin = plugin_class()
            success = plugin.initialize(**kwargs)
            
            if success:
                plugin.enabled = True
                self.plugins[plugin.name] = plugin
                print(f"  ✅ 插件 {plugin.name} v{plugin.version} 加载成功")
                return True
            else:
                print(f"  ⚠️  插件 {plugin.name} 初始化失败")
                return False
        except Exception as e:
            print(f"  ❌ 插件加载异常: {e}")
            return False
    
    def get_plugin(self, name):
        """获取指定名称的插件"""
        return self.plugins.get(name)
    
    def has_capability(self, capability):
        """检查是否有插件提供指定能力"""
        for plugin in self.plugins.values():
            if plugin.is_available() and capability in plugin.get_capabilities():
                return True
        return False
    
    def call_capability(self, capability, *args, **kwargs):
        """调用指定能力（使用第一个提供该能力的插件）"""
        for plugin in self.plugins.values():
            if plugin.is_available() and capability in plugin.get_capabilities():
                method = getattr(plugin, capability, None)
                if method and callable(method):
                    return method(*args, **kwargs)
        return None
    
    def list_plugins(self):
        """列出所有已加载的插件"""
        return list(self.plugins.values())
    
    def cleanup_all(self):
        """清理所有插件"""
        for plugin in self.plugins.values():
            try:
                plugin.cleanup()
            except Exception:
                pass
        self.plugins.clear()


# 全局单例
_plugin_manager = None

def get_plugin_manager():
    """获取插件管理器单例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
