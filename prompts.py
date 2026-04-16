#!/usr/bin/env python3
"""
Prompt仓库 - 集中管理所有GPT调用提示词
Prompt Repository - Centralized management of all GPT prompts
"""

from typing import Dict, List

# =============================================================================
# pipeline.py - GPT幻灯片分析相关Prompts
# =============================================================================

PROMPT_ANALYZE_SLIDE = """请分析这张幻灯片截图，返回JSON格式的分析结果：

{
    "background_color": "#RRGGBB格式的背景色，优先识别主要背景区域的颜色",
    "title": "幻灯片的主标题文本",
    "subtitle": "副标题（如果有）",
    "slide_type": "封面页/内容页/图表页/结束页 等",
    "main_language": "中文/英文/中英混合",
    "description": "用1-2句话描述这张幻灯片的主要内容",
    "key_points": ["要点1", "要点2", "..."]
}

注意：
1. 背景色请识别幻灯片的主要背景区域（通常是白色或浅色），忽略边缘装饰
2. 只返回JSON，不要其他文字"""

SYSTEM_PROMPT_ANALYZE_SLIDE = "你是一个专业的幻灯片分析助手，擅长识别和提取幻灯片中的结构化信息。"

PROMPT_ANALYZE_ELEMENT = """请分析这个幻灯片元素区域，返回JSON格式的分析结果：

{{
    "type": "text/image/chart/table/logo/diagram/decoration/mixed",
    "text_content": "提取所有可见文本，保持原始换行格式",
    "description": "简短描述这个元素的内容",
    "is_title": true/false,
    "estimated_font_size": 数字（估计的主要字体大小，单位pt）,
    "text_color": "#RRGGBB格式的主要文字颜色",
    "has_border": true/false
}}

注意：
- type必须从给定选项中选择
- 如果没有可见文本，text_content留空字符串
- 只返回JSON，不要其他文字"""

SYSTEM_PROMPT_ANALYZE_ELEMENT = "你是一个专业的幻灯片元素分析助手，擅长分类和识别幻灯片中的各种元素。"

# =============================================================================
# narration_generator.py - 旁白生成相关Prompts
# =============================================================================

def get_system_prompt_narration(language: str, style: str) -> str:
    """
    获取旁白生成的系统prompt
    :param language: 语言 "zh" 或 "en"
    :param style: 风格 "formal", "casual", "academic"
    :return: 系统prompt字符串
    """
    style_map = {
        "zh": {"formal": "正式、专业", "casual": "轻松、亲和", "academic": "学术、严谨"},
        "en": {"formal": "formal and professional", "casual": "casual and friendly", "academic": "academic and rigorous"}
    }
    style_desc = style_map[language].get(style, style_map[language]["formal"])

    if language == "zh":
        return f"""你是一个专业的演示文稿讲解专家。
你的任务是为幻灯片生成{style_desc}的讲解文本。
讲解应该自然流畅，适合语音朗读（TTS）。
请严格按照要求的JSON格式输出。"""
    else:
        return f"""You are a professional presentation narrator.
Your task is to generate {style_desc} narration for slides.
The narration should be natural and suitable for text-to-speech (TTS).
Please strictly follow the required JSON format."""


def build_prompt_narration(metadata: Dict, elements: List[Dict], language: str, include_transitions: bool) -> str:
    """
    构建旁白生成的用户prompt
    :param metadata: 幻灯片元数据
    :param elements: 元素摘要列表
    :param language: 语言 "zh" 或 "en"
    :param include_transitions: 是否包含过渡语句
    :return: 构建好的prompt
    """
    import json
    elements_json = json.dumps(elements, ensure_ascii=False, indent=2)

    if language == "zh":
        prompt = f"""请为这张幻灯片生成讲解脚本。

## 幻灯片信息
- 标题: {metadata.get('title', '未知')}
- 类型: {metadata.get('slide_type', '内容页')}
- 描述: {metadata.get('description', '')}

## 检测到的元素
```json
{elements_json}
```

## 要求

1. **确定讲解顺序**:
   - 分析图像，确定哪些元素需要讲解以及最自然的讲解顺序
   - 通常从标题开始，然后是主要内容
   - 装饰性元素（如logo、边框、装饰条）可以跳过不讲

2. **生成讲解文本**:
   - 为每个需要讲解的元素生成自然连贯的讲解文本
   - 讲解要口语化，适合朗读，不要有书面语气
   - 不要简单复述文字，要有解释和补充说明
   - {"加入自然的过渡语句连接各部分" if include_transitions else "直接讲解内容"}

3. **输出格式（严格JSON）**:

```json
{{
    "opening": "开场白（1-2句话自然地引入这张幻灯片）",
    "segments": [
        {{
            "order": 1,
            "element_name": "元素名称（必须与上面的name完全一致）",
            "narration": "这部分的讲解文本..."
        }}
    ],
    "closing": "结束语（可选，简短总结或过渡）"
}}
```

请仔细观察图像，生成专业、自然、连贯的讲解。只输出JSON。"""
    else:
        prompt = f"""Please generate a narration script for this slide.

## Slide Information
- Title: {metadata.get('title', 'Unknown')}
- Type: {metadata.get('slide_type', 'Content')}
- Description: {metadata.get('description', '')}

## Detected Elements
```json
{elements_json}
```

## Requirements

1. **Determine narration order**:
   - Analyze the image and determine which elements need narration and the natural order
   - Usually start with the title, then main content
   - Skip decorative elements (logos, borders, decorations)

2. **Generate narration text**:
   - Create natural, coherent narration for each element
   - Keep it conversational, suitable for TTS
   - Don't just read the text, explain and elaborate
   - {"Include smooth transitions between sections" if include_transitions else "Direct narration"}

3. **Output format (strict JSON)**:

```json
{{
    "opening": "Opening statement (1-2 sentences to introduce the slide)",
    "segments": [
        {{
            "order": 1,
            "element_name": "exact element name from above",
            "narration": "Narration text for this part..."
        }}
    ],
    "closing": "Closing statement (optional, brief summary or transition)"
}}
```

Please observe the image carefully and generate professional, natural narration. Output JSON only."""

    return prompt


FALLBACK_OPENING = {
    "zh": "让我们来看这张幻灯片。",
    "en": "Let's look at this slide."
}

def get_fallback_narration_segment(text: str, element_name: str, language: str) -> str:
    """获取fallback旁白文本"""
    if language == "zh":
        return f"接下来看这部分内容：{text[:150]}"
    else:
        return f"Now let's look at this section: {text[:150]}"

# =============================================================================
# tts_generator.py - 动画生成相关Prompts
# =============================================================================

PROMPT_GENERATE_ANIMATIONS = """
Please generate a JSON output with the following REQUIRED structure based on animation descriptions:
{{
    "animations": [
        {{
            "element": "<element_name>",
            "animation_type": "<type>",
            "effect": "<animation_effect>",
            "duration": <duration_in_seconds>,
            "delay": <delay_in_seconds>,
            "repeat_count": <repeat_count>
        }},
        ...
    ]
}}

Animation Type Options:
1. "Entrance"
2. "Emphasis"
3. "Exit"

Available Effects

Entrance Effects (45 total)
1. "Appear"
2. "ArcUP"
3. "Blinds"
4. "Boomerang"
5. "Bounce"
6. "Box"
7. "CenterRevolve"
8. "Checkerboard"
9. "Circle"
10. "Crawl"
11. "Diamond"
12. "Dissolve"
13. "EaseIn"
14. "Expand"
15. "Fade"
16. "FadedSwivel"
17. "FadedZoom"
18. "Float"
19. "Fold"
20. "Glide"
21. "GrowAndTurn"
22. "LightSpeed"
23. "Peek"
24. "Pinwheel"
25. "Plus"
26. "RandomBars"
27. "RiseUp"
28. "Sling"
29. "Spinner"
30. "Spiral"
31. "Split"
32. "Stretch"
33. "Stretchy"
34. "Strips"
35. "Swivel"
36. "ThinLine"
37. "Wedge"
38. "Wheel"
39. "Wipe"
40. "Zip"
41. "Zoom"
42. "FlyFromLeft"
43. "FlyFromRight"
44. "FlyFromTop"
45. "FlyFromBottom"

Emphasis Effects (10 total; only for elements that have appeared)
1. "Blast"
2. "ChangeFillColor"
3. "ChangeLineColor"
4. "FlashBulb"
5. "GrowShrink"
6. "Shimmer"
7. "Spin"
8. "Teeter"
9. "Transparency"
10. "VerticalGrow"

Exit Effects (45 total; same as Entrance but FlyFrom→FlyTo)
1. "Appear"
2. "ArcUP"
3. "Blinds"
4. "Boomerang"
5. "Bounce"
6. "Box"
7. "CenterRevolve"
8. "Checkerboard"
9. "Circle"
10. "Crawl"
11. "Diamond"
12. "Dissolve"
13. "EaseIn"
14. "Expand"
15. "Fade"
16. "FadedSwivel"
17. "FadedZoom"
18. "Float"
19. "Fold"
20. "Glide"
21. "GrowAndTurn"
22. "LightSpeed"
23. "Peek"
24. "Pinwheel"
25. "Plus"
26. "RandomBars"
27. "RiseUp"
28. "Sling"
29. "Spinner"
30. "Spiral"
31. "Split"
32. "Stretch"
33. "Stretchy"
34. "Strips"
35. "Swivel"
36. "ThinLine"
37. "Wedge"
38. "Wheel"
39. "Wipe"
40. "Zip"
41. "Zoom"
42. "FlyToLeft"
43. "FlyToRight"
44. "FlyToTop"
45. "FlyToBottom"

Special Requirements:
- If effect is unspecified or invalid, SELECT RANDOMLY from same animation_type category
- All numerical values must be valid numbers (no text)
- Maintain strict JSON format with proper syntax
- duration between 0.5 and 2.5 seconds
- delay >= 0 seconds
- repeat_count is 1 by default, can be 2-3 for emphasis effects

## Narration Segment Information (for timing reference)
Slide Title: {title}
Total Narration Duration: {total_duration} seconds

Segment Details:
{segments_json}

## Generation Logic (strictly aligned with voice timing):
### Timing Rules:
Each narration segment has accurate start_time and duration:
1. **Entrance Animation**: Must fully complete 0.5 seconds before the corresponding narration starts
   - Entrance delay = max(0, segment.start_time - 0.5 - entrance.duration)
   - Ensure audience sees the element before hearing the narration

2. **Emphasis Animation**:
   - Segment duration < 3s: No emphasis animation needed
   - Segment duration >=3s: Add one emphasis animation every 2-3 seconds, unlimited count, cover entire narration process
   - Emphasis delay = segment.start_time + N * interval (N starts from 0, until near segment end)
   - Add more emphasis animations for long text content to keep page dynamic, avoid long static periods

3. **Exit Animation (Optional)**: Freely decide whether to add based on content needs, not mandatory for every element
   - If exit needed: Start at appropriate time after narration ends, delay = segment.start_time + segment.duration + appropriate delay
   - Background elements and elements that need to remain can skip exit animation
   - Elements not needed for subsequent content can have exit animation

### Effect Selection Suggestions:
- Title elements: Prefer Fade, Zoom, FlyFromTop for entrance
- Text elements: Prefer FlyFromLeft/FlyFromRight for entrance
- Charts/Images: Prefer Zoom, Wipe for entrance
- Important data: Use GrowShrink, FlashBulb etc. for emphasis

Response Requirements:
1. Output ONLY the complete JSON object
2. No additional text or explanations
3. Use double quotes for all strings
4. Numerical values without quotes
"""

SYSTEM_PROMPT_GENERATE_ANIMATIONS_ZH = "你是专业的PPT动画设计专家，擅长根据解说节奏设计精准的动画效果。"
SYSTEM_PROMPT_GENERATE_ANIMATIONS_EN = "You are a professional PPT animation design expert, skilled at designing precise animation effects according to narration timing."

# 动画效果列表
ENTRANCE_EFFECTS = [
    "Appear", "ArcUP", "Blinds", "Boomerang", "Bounce", "Box",
    "CenterRevolve", "Checkerboard", "Circle", "Crawl", "Diamond",
    "Dissolve", "EaseIn", "Expand", "Fade", "FadedSwivel", "FadedZoom",
    "Float", "Fold", "Glide", "GrowAndTurn", "LightSpeed", "Peek",
    "Pinwheel", "Plus", "RandomBars", "RiseUp", "Sling", "Spinner",
    "Spiral", "Split", "Stretch", "Stretchy", "Strips", "Swivel",
    "ThinLine", "Wedge", "Wheel", "Wipe", "Zip", "Zoom",
    "FlyFromLeft", "FlyFromRight", "FlyFromTop", "FlyFromBottom"
]

EMPHASIS_EFFECTS = [
    "Blast", "ChangeFillColor", "ChangeLineColor", "FlashBulb",
    "GrowShrink", "Shimmer", "Spin", "Teeter", "Transparency",
    "VerticalGrow"
]

EXIT_EFFECTS = [
    "Appear", "ArcUP", "Blinds", "Boomerang", "Bounce", "Box",
    "CenterRevolve", "Checkerboard", "Circle", "Crawl", "Diamond",
    "Dissolve", "EaseIn", "Expand", "Fade", "FadedSwivel", "FadedZoom",
    "Float", "Fold", "Glide", "GrowAndTurn", "LightSpeed", "Peek",
    "Pinwheel", "Plus", "RandomBars", "RiseUp", "Sling", "Spinner",
    "Spiral", "Split", "Stretch", "Stretchy", "Strips", "Swivel",
    "ThinLine", "Wedge", "Wheel", "Wipe", "Zip", "Zoom",
    "FlyToLeft", "FlyToRight", "FlyToTop", "FlyToBottom"
]

# 默认效果索引
DEFAULT_ENTRANCE_EFFECT_INDEX = 14  # Fade
DEFAULT_EMPHASIS_EFFECT_INDEX = 4   # GrowShrink
DEFAULT_EXIT_EFFECT_INDEX = 11      # Dissolve
