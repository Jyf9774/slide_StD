"""
智能动画方案生成器
基于解说文本和语音节奏，使用LLM生成同步PPT动画方案
"""

import json
import random
from typing import Dict, List

from openai_client import get_gpt_client, DEFAULT_MODEL
import prompts
from .progress import Spinner


class AnimationGenerator:
    """基于解说文本和语音节奏的动画方案生成器"""

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm and (get_gpt_client() is not None)
        self.client = None

        if self.use_llm:
            self.client = get_gpt_client()

        # 从统一Prompt仓库获取动画效果列表
        self.entrance_effects = prompts.ENTRANCE_EFFECTS
        self.emphasis_effects = prompts.EMPHASIS_EFFECTS
        self.exit_effects = prompts.EXIT_EFFECTS

    def generate_animation_scheme(self, audio_info: Dict, output_path: str) -> Dict:
        """
        生成动画方案（必须传入TTS生成后的实际音频信息，禁止使用估算时长）
        :param audio_info: TTS生成的音频信息，必须包含实际时长和音频路径
        :param output_path: 输出JSON文件路径
        :return: 动画方案字典
        """
        # 严格校验：确保是TTS完成后的实际数据
        required_fields = ["slide_id", "total_duration", "segments"]
        for field in required_fields:
            if field not in audio_info:
                raise ValueError(f"audio_info缺少必要字段: {field}，请确保先完成TTS生成再生成动画")

        required_segment_fields = ["duration", "start_time", "audio_path"]
        for seg in audio_info["segments"]:
            for field in required_segment_fields:
                if field not in seg:
                    raise ValueError(f"分段信息缺少必要字段: {field}，请确保先完成TTS生成再生成动画")
            # 明确禁止使用估算时长
            if "duration_estimate" in seg:
                del seg["duration_estimate"]

        # 过滤掉 opening/closing（narration类型，无对应幻灯片视觉元素）
        element_segments = [
            seg for seg in audio_info["segments"]
            if seg.get("element_type") != "narration"
        ]

        # 构建仅含元素段的 audio_info 副本，供动画生成使用
        element_audio_info = {
            **audio_info,
            "segments": element_segments
        }

        # 计算元素段的实际时间范围
        if element_segments:
            element_start = element_segments[0]["start_time"]
            last_seg = element_segments[-1]
            element_end = last_seg["start_time"] + last_seg["duration"]
            element_duration = element_end - element_start
        else:
            element_start = 0
            element_end = 0
            element_duration = 0

        # 生成动画
        spinner = Spinner("LLM生成动画方案")
        if self.use_llm:
            spinner.start()
            try:
                animations = self._generate_animations_with_llm(element_audio_info)
            finally:
                spinner.stop("✅ 动画方案生成完成")
        else:
            animations = self._generate_animations_rule_based(element_audio_info)

        # 计算动画总时长
        anim_total = max([anim["delay"] + anim["duration"] for anim in animations]) if animations else 0
        narration_duration = audio_info["total_duration"]

        # 校验动画时长与元素段时长的匹配度（不再与含opening/closing的总时长比较）
        if element_duration > 0:
            duration_diff = abs(anim_total - element_end)
            if duration_diff > 3.0:
                print(f"   ⚠️ 动画覆盖到{anim_total:.1f}s，元素段结束于{element_end:.1f}s，偏差{duration_diff:.1f}s")

        # 确保动画不超过元素段结束太多
        if anim_total > element_end + 1.0:
            if animations:
                last_anim = animations[-1]
                excess = anim_total - (element_end + 0.5)
                last_anim["duration"] = max(0.1, last_anim["duration"] - excess)
                anim_total = max([anim["delay"] + anim["duration"] for anim in animations])

        animation_scheme = {
            "slide_id": audio_info["slide_id"],
            "title": audio_info["title"],
            "total_duration": round(anim_total, 2),
            "element_duration": round(element_duration, 2),
            "element_time_range": [round(element_start, 2), round(element_end, 2)],
            "narration_duration": round(narration_duration, 2),
            "duration_source": "TTS实际生成时长",
            "animations": animations
        }

        # 确保输出目录存在
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存动画方案
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(animation_scheme, f, ensure_ascii=False, indent=2)

        return animation_scheme

    def _generate_animations_with_llm(self, audio_info: Dict) -> List[Dict]:
        """使用LLM生成符合语音节奏的动画方案"""
        segments_info = []
        for seg in audio_info["segments"]:
            segments_info.append({
                "order": seg.get("order", 0),
                "element_name": seg["element_name"],
                "element_type": seg["element_type"],
                "narration_text": seg.get("narration_text", seg.get("narration", "")),
                "start_time": round(seg["start_time"], 2),
                "duration": round(seg["duration"], 2)
            })

        segments_json = json.dumps(segments_info, ensure_ascii=False, indent=2)
        prompt = prompts.PROMPT_GENERATE_ANIMATIONS.format(
            title=audio_info["title"],
            total_duration=round(audio_info["total_duration"], 2),
            segments_json=segments_json
        )

        try:
            response = self.client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": prompts.SYSTEM_PROMPT_GENERATE_ANIMATIONS_ZH},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            animations = result.get("animations", []) if isinstance(result, dict) else result

            # 验证和清理动画数据
            cleaned_animations = []
            for anim in animations:
                anim_type = anim.get("animation_type", "Entrance")
                effect = anim.get("effect", "Fade")

                if anim_type == "Entrance" and effect not in self.entrance_effects:
                    effect = random.choice(self.entrance_effects)
                elif anim_type == "Emphasis" and effect not in self.emphasis_effects:
                    effect = random.choice(self.emphasis_effects)
                elif anim_type == "Exit" and effect not in self.exit_effects:
                    effect = random.choice(self.exit_effects)

                cleaned = {
                    "element": anim.get("element", ""),
                    "animation_type": anim_type,
                    "effect": effect,
                    "duration": round(max(0.5, min(2.5, float(anim.get("duration", 1.0)))), 2),
                    "delay": round(max(0.0, float(anim.get("delay", 0.0))), 2),
                    "repeat_count": max(1, int(anim.get("repeat_count", 1)))
                }
                cleaned_animations.append(cleaned)

            return cleaned_animations

        except Exception as e:
            print(f"   LLM生成动画失败，使用规则生成 fallback: {e}")
            return self._generate_animations_rule_based(audio_info)

    def _generate_animations_rule_based(self, audio_info: Dict) -> List[Dict]:
        """基于规则的动画生成（fallback方案）"""
        animations = []

        for i, segment in enumerate(audio_info["segments"]):
            element_name = segment["element_name"]
            element_type = segment["element_type"]
            segment_start = segment["start_time"]
            segment_duration = segment["duration"]

            # 入场动画：在片段开始前播放
            entrance_delay = max(0, segment_start - 0.5)
            entrance_duration = min(1.5, segment_duration * 0.2)
            animations.append({
                "element": element_name,
                "animation_type": "Entrance",
                "effect": self.entrance_effects[prompts.DEFAULT_ENTRANCE_EFFECT_INDEX],
                "duration": round(entrance_duration, 2),
                "delay": round(entrance_delay, 2),
                "repeat_count": 1
            })

            # 强调动画：每2.5秒一次，覆盖整个解说片段
            if segment_duration > 3:
                interval = 2.5
                num_emphasis = max(1, int(segment_duration / interval))

                for n in range(num_emphasis):
                    emphasis_delay = segment_start + n * interval
                    if emphasis_delay + 1.0 <= segment_start + segment_duration:
                        animations.append({
                            "element": element_name,
                            "animation_type": "Emphasis",
                            "effect": self.emphasis_effects[prompts.DEFAULT_EMPHASIS_EFFECT_INDEX],
                            "duration": 1.0,
                            "delay": round(emphasis_delay, 2),
                            "repeat_count": 1
                        })

            # 规则模式下默认不添加退场动画，除非是最后一个元素
            is_last_element = (i == len(audio_info["segments"]) - 1)
            if is_last_element:
                animations.append({
                    "element": element_name,
                    "animation_type": "Exit",
                    "effect": self.exit_effects[prompts.DEFAULT_EXIT_EFFECT_INDEX],
                    "duration": 0.8,
                    "delay": 0,
                    "repeat_count": 1
                })

        return animations
