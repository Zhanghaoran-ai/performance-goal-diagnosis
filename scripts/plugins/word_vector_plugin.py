#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
词向量相似度插件
使用预训练的中文词向量计算语义相似度

【可选插件】需要额外下载词向量文件（约几十MB）
如果没有词向量文件，插件会自动禁用，不影响核心功能
"""

import numpy as np
from pathlib import Path
from .base_plugin import BasePlugin


class WordVectorPlugin(BasePlugin):
    """词向量相似度插件"""
    
    def __init__(self):
        super().__init__('WordVectorPlugin', '1.0.0')
        self.word_vectors = {}
        self.vector_dim = 0
    
    def initialize(self, vector_file=None, **kwargs):
        """
        初始化词向量插件
        
        Args:
            vector_file: 词向量文件路径（支持 txt 格式）
        """
        if vector_file is None:
            # 尝试默认路径
            default_paths = [
                Path(__file__).parent.parent / 'data' / 'word_vectors.txt',
                Path.home() / '.cache' / 'performance_diagnosis' / 'word_vectors.txt',
            ]
            for path in default_paths:
                if path.exists():
                    vector_file = path
                    break
            
            if vector_file is None:
                print("  ℹ️  未找到词向量文件，词向量插件将不启用")
                return False
        
        try:
            vector_file = Path(vector_file)
            if not vector_file.exists():
                print(f"  ℹ️  词向量文件不存在: {vector_file}")
                return False
            
            # 加载词向量
            print(f"  📦 正在加载词向量文件: {vector_file.name}...")
            count = 0
            with open(vector_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                parts = first_line.split()
                if len(parts) == 2:
                    # 第一行是 词数 维度
                    total_count = int(parts[0])
                    self.vector_dim = int(parts[1])
                else:
                    # 没有头信息，从第一行推断维度
                    self.vector_dim = len(parts) - 1
                    f.seek(0)
                
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < self.vector_dim + 1:
                        continue
                    
                    word = parts[0]
                    vector = np.array([float(x) for x in parts[1:self.vector_dim+1]])
                    self.word_vectors[word] = vector
                    count += 1
            
            self.initialized = True
            print(f"  ✅ 已加载 {count} 个词向量，维度 {self.vector_dim}")
            return True
            
        except Exception as e:
            print(f"  ❌ 加载词向量失败: {e}")
            return False
    
    def get_capabilities(self):
        return ['semantic_similarity', 'word_embedding']
    
    def semantic_similarity(self, text1, text2):
        """
        基于词向量计算语义相似度
        """
        if not self.initialized:
            return None
        
        # 简单的词向量平均
        vec1 = self._get_text_vector(text1)
        vec2 = self._get_text_vector(text2)
        
        if vec1 is None or vec2 is None:
            return None
        
        # 余弦相似度
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        return float(similarity)
    
    def word_embedding(self, text):
        """获取文本的词向量表示"""
        return self._get_text_vector(text)
    
    def _get_text_vector(self, text):
        """获取文本的平均词向量"""
        words = text.lower().split()
        vectors = []
        
        for word in words:
            if word in self.word_vectors:
                vectors.append(self.word_vectors[word])
        
        if not vectors:
            return None
        
        return np.mean(vectors, axis=0)
    
    def cleanup(self):
        """清理资源"""
        self.word_vectors.clear()
        self.initialized = False
