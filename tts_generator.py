"""
兼容层 - 保持旧导入路径 `from tts_generator import ...` 可用
实际实现已迁移至 media/ 模块包
"""

from media import (
    Qwen3TTSGenerator,
    TTSRealtimeCallback,
    AnimationGenerator,
    generate_tts_and_animations,
)

__all__ = [
    'Qwen3TTSGenerator',
    'TTSRealtimeCallback',
    'AnimationGenerator',
    'generate_tts_and_animations',
]
