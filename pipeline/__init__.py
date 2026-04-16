"""
幻灯片截图分割与PPTX还原数据流水线 v4.0
Slide Screenshot Segmentation and PPTX Reconstruction Pipeline

核心架构：
1. 优先使用Qwen3.6-Plus VLM大模型进行端到端分析
2. 传统CV仅作为fallback方案
3. 模块化设计，易维护易扩展

模块结构：
- models.py:           数据模型 (ElementType, BoundingBox, SlideElement, SlideMetadata)
- vlm_analyzer.py:     VLM大模型分析器
- layout_analyzer.py:  DocLayout-YOLO版面检测器
- cv_analyzer.py:      传统CV后备分析器
- processor.py:        主处理器 (SlideProcessor)
- reconstructor.py:    PPTX重建器 (SlideReconstructor)
- cli.py:              命令行入口和便捷函数
"""

# 数据模型
from .models import ElementType, BoundingBox, SlideElement, SlideMetadata

# 分析器
from .vlm_analyzer import VLMAnalyzer
from .layout_analyzer import LayoutAnalyzer
from .cv_analyzer import CVFallbackAnalyzer

# 处理器和重建器
from .processor import SlideProcessor
from .reconstructor import SlideReconstructor

# 便捷函数
from .cli import process_slide, main

__all__ = [
    # 数据模型
    'ElementType', 'BoundingBox', 'SlideElement', 'SlideMetadata',
    # 分析器
    'VLMAnalyzer', 'LayoutAnalyzer', 'CVFallbackAnalyzer',
    # 处理器
    'SlideProcessor', 'SlideReconstructor',
    # 便捷函数
    'process_slide', 'main',
]
