"""
媒体生成模块 - TTS语音合成 + 智能动画方案生成
Media Generation Module - TTS Speech Synthesis & Intelligent Animation

模块结构：
- tts_synthesizer.py:     Qwen3-TTS 语音合成器
- animation_generator.py: LLM 智能动画方案生成器
- progress.py:            通用进度显示工具
"""

import os
import json
from typing import Dict

from .tts_synthesizer import Qwen3TTSGenerator, TTSRealtimeCallback
from .animation_generator import AnimationGenerator
from .progress import Spinner, print_step_progress

__all__ = [
    'Qwen3TTSGenerator',
    'TTSRealtimeCallback',
    'AnimationGenerator',
    'Spinner',
    'print_step_progress',
    'generate_tts_and_animations',
]


def generate_tts_and_animations(
    narration_json_path: str,
    output_dir: str,
    voice: str = "Cherry",
    use_llm_animation: bool = True
) -> Dict:
    """
    一键生成TTS音频和对应动画方案

    输出目录结构：
      output_dir/tts/        - 分段音频 + 完整拼接音频 + audio_info.json
      output_dir/animation/  - animation_scheme.json

    :param narration_json_path: 旁白JSON文件路径，支持单页和批量两种格式
    :param output_dir: 输出根目录（tts/ 和 animation/ 子目录会自动创建）
    :param voice: 发音人，可选：Cherry(甜美女声)、Alvin(成熟男声)、Wanwan(可爱童声)等
    :param use_llm_animation: 是否使用LLM生成动画方案
    :return: 包含音频和动画信息的字典
    """
    with open(narration_json_path, "r", encoding='utf-8') as f:
        narration_data = json.load(f)

    # 兼容批量和单页两种narration格式
    is_batch = "slides" in narration_data and isinstance(narration_data["slides"], list)
    if is_batch:
        return _process_batch(narration_data, output_dir, voice, use_llm_animation)
    else:
        return _process_single(narration_data, output_dir, voice, use_llm_animation)


def _process_single(narration_data: Dict, output_dir: str, voice: str, use_llm_animation: bool) -> Dict:
    """处理单页旁白"""
    tts_output_dir = os.path.join(output_dir, "tts")
    animation_output_dir = os.path.join(output_dir, "animation")
    os.makedirs(tts_output_dir, exist_ok=True)
    os.makedirs(animation_output_dir, exist_ok=True)

    # 生成TTS音频 → tts/
    tts_generator = Qwen3TTSGenerator(voice=voice)
    audio_info = tts_generator.generate_segmented_audio(narration_data, tts_output_dir)

    # 生成动画方案 → animation/
    animation_generator = AnimationGenerator(use_llm=use_llm_animation)
    animation_path = os.path.join(animation_output_dir, "animation_scheme.json")
    animation_scheme = animation_generator.generate_animation_scheme(audio_info, animation_path)

    return {
        "type": "single",
        "audio_info": audio_info,
        "animation_scheme": animation_scheme
    }


def _process_batch(narration_data: Dict, output_dir: str, voice: str, use_llm_animation: bool) -> Dict:
    """处理批量旁白"""
    results = []
    for idx, slide_data in enumerate(narration_data["slides"]):
        slide_output_dir = os.path.join(output_dir, f"slide_{idx+1}_{slide_data['slide_id']}")

        result = _process_single(slide_data, slide_output_dir, voice, use_llm_animation)
        results.append({
            "slide_id": slide_data["slide_id"],
            "audio_info": result["audio_info"],
            "animation_scheme": result["animation_scheme"],
            "output_dir": slide_output_dir
        })

    # 保存批量处理结果
    batch_result_path = os.path.join(output_dir, "batch_result.json")
    with open(batch_result_path, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(results),
            "results": results
        }, f, ensure_ascii=False, indent=2)

    return {
        "type": "batch",
        "count": len(results),
        "results": results
    }
