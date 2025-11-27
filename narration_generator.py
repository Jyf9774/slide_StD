#!/usr/bin/env python3
"""
幻灯片讲解生成器 v1.1
Slide Narration Generator

功能：
1. 读取分割后的JSON元数据和原始页面图像
2. 使用GPT-4.1分析确定讲解元素和顺序
3. 生成自然流畅的讲解文本
4. 输出结构化讲解脚本（支持TTS）
"""

import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

# ============ 配置 ============

# 语言设置: "zh" = 中文, "en" = 英文
NARRATION_LANGUAGE = "zh"

# 讲解风格: "formal" = 正式, "casual" = 轻松, "academic" = 学术
NARRATION_STYLE = "formal"

# 是否包含过渡语句
INCLUDE_TRANSITIONS = True

# 估计每个字符的朗读时间（秒）
CHAR_DURATION_ZH = 0.18  # 中文
CHAR_DURATION_EN = 0.06  # 英文


# ============ GPT客户端 ============

def get_gpt_client():
    """获取Azure OpenAI客户端"""
    try:
        from openai import AzureOpenAI
        from key_manage import Azure_GPT_4_1_Key
        
        client = AzureOpenAI(
            api_version="2024-12-01-preview",
            api_key=Azure_GPT_4_1_Key,
            azure_endpoint="https://admin-m9uwcx36-eastus2.cognitiveservices.azure.com/"
        )
        return client
    except ImportError as e:
        raise ImportError(f"请确保已创建key_manage.py并设置Azure_GPT_4_1_Key: {e}")


def image_to_base64(image_path: str) -> str:
    """将图片转换为base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============ 数据结构 ============

@dataclass
class NarrationSegment:
    """讲解片段"""
    order: int                      # 讲解顺序
    element_name: str               # 元素名称
    element_type: str               # 元素类型
    narration_text: str             # 讲解文本
    duration_estimate: float        # 预估时长（秒）
    
    def to_dict(self) -> Dict:
        return {
            "order": self.order,
            "element_name": self.element_name,
            "element_type": self.element_type,
            "narration_text": self.narration_text,
            "duration_estimate": self.duration_estimate
        }


@dataclass
class SlideNarration:
    """完整幻灯片讲解"""
    slide_id: str
    title: str
    language: str
    style: str
    opening: str                    # 开场白
    segments: List[NarrationSegment]
    closing: str                    # 结束语
    total_duration: float           # 总时长
    created_at: str
    
    def to_dict(self) -> Dict:
        return {
            "slide_id": self.slide_id,
            "title": self.title,
            "language": self.language,
            "style": self.style,
            "opening": self.opening,
            "segments": [s.to_dict() for s in self.segments],
            "closing": self.closing,
            "total_duration": self.total_duration,
            "created_at": self.created_at
        }
    
    def to_plain_text(self) -> str:
        """转换为纯文本讲解稿"""
        lines = []
        
        if self.opening:
            lines.append(self.opening)
            lines.append("")
        
        for seg in self.segments:
            lines.append(seg.narration_text)
            lines.append("")
        
        if self.closing:
            lines.append(self.closing)
        
        return "\n".join(lines).strip()
    
    def to_tts_script(self) -> str:
        """转换为TTS脚本格式（带元素标记）"""
        lines = []
        lines.append(f"# 幻灯片讲解脚本")
        lines.append(f"# 语言: {self.language}")
        lines.append(f"# 预估总时长: {self.total_duration:.1f}秒")
        lines.append(f"# 生成时间: {self.created_at}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("")
        
        if self.opening:
            lines.append(f"[开场]")
            lines.append(self.opening)
            lines.append("")
        
        for seg in self.segments:
            lines.append(f"[{seg.order}] 元素: {seg.element_name} ({seg.element_type}) | 时长: {seg.duration_estimate:.1f}秒")
            lines.append(seg.narration_text)
            lines.append("")
        
        if self.closing:
            lines.append(f"[结束]")
            lines.append(self.closing)
        
        return "\n".join(lines)


# ============ 讲解生成器 ============

class NarrationGenerator:
    """讲解生成器"""
    
    def __init__(self, 
                 language: str = NARRATION_LANGUAGE,
                 style: str = NARRATION_STYLE,
                 include_transitions: bool = INCLUDE_TRANSITIONS):
        """
        Args:
            language: 语言 "zh" 或 "en"
            style: 风格 "formal", "casual", "academic"
            include_transitions: 是否包含过渡语句
        """
        self.language = language
        self.style = style
        self.include_transitions = include_transitions
        self.client = get_gpt_client()
        
        self.char_duration = CHAR_DURATION_ZH if language == "zh" else CHAR_DURATION_EN
    
    def generate(self, json_path: str, output_dir: str = None) -> SlideNarration:
        """
        生成讲解
        
        Args:
            json_path: JSON元数据文件路径
            output_dir: 输出目录（默认与JSON同目录）
            
        Returns:
            SlideNarration: 讲解数据
        """
        # 读取JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        base_dir = os.path.dirname(json_path)
        output_dir = output_dir or base_dir
        
        # 查找原始图像
        original_image = None
        for fname in os.listdir(base_dir):
            if fname.startswith("original_"):
                original_image = os.path.join(base_dir, fname)
                break
        
        if not original_image:
            raise FileNotFoundError(f"未找到原始图像，请检查目录: {base_dir}")
        
        print(f"正在使用GPT-4.1生成{'中文' if self.language == 'zh' else '英文'}讲解...")
        
        # 调用GPT生成讲解
        narration_data = self._call_gpt_for_narration(metadata, original_image)
        
        # 构建讲解对象
        narration = self._build_narration(metadata, narration_data)
        
        # 保存输出
        self._save_outputs(narration, output_dir, metadata['slide_id'])
        
        return narration
    
    def _call_gpt_for_narration(self, metadata: Dict, image_path: str) -> Dict:
        """调用GPT生成讲解"""
        
        base64_image = image_to_base64(image_path)
        
        # 构建元素信息摘要
        elements_summary = []
        for elem in metadata['elements']:
            elem_info = {
                "name": elem['name'],
                "type": elem['type'],
                "text_content": elem.get('text_content', '')[:300],
                "is_title": elem.get('is_title', False),
                "bbox": elem['bbox']
            }
            elements_summary.append(elem_info)
        
        # 构建prompt
        prompt = self._build_prompt(metadata, elements_summary)
        
        try:
            resp = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            result_text = resp.choices[0].message.content.strip()
            
            # 清理markdown代码块
            if "```" in result_text:
                parts = result_text.split("```")
                for part in parts:
                    if part.strip().startswith("json"):
                        result_text = part.strip()[4:]
                        break
                    elif part.strip().startswith("{"):
                        result_text = part.strip()
                        break
            
            return json.loads(result_text)
            
        except Exception as e:
            print(f"GPT调用失败: {e}")
            return self._generate_fallback_narration(metadata)
    
    def _get_system_prompt(self) -> str:
        """获取系统提示"""
        style_map = {
            "zh": {"formal": "正式、专业", "casual": "轻松、亲和", "academic": "学术、严谨"},
            "en": {"formal": "formal and professional", "casual": "casual and friendly", "academic": "academic and rigorous"}
        }
        style_desc = style_map[self.language].get(self.style, style_map[self.language]["formal"])
        
        if self.language == "zh":
            return f"""你是一个专业的演示文稿讲解专家。
你的任务是为幻灯片生成{style_desc}的讲解文本。
讲解应该自然流畅，适合语音朗读（TTS）。
请严格按照要求的JSON格式输出。"""
        else:
            return f"""You are a professional presentation narrator.
Your task is to generate {style_desc} narration for slides.
The narration should be natural and suitable for text-to-speech (TTS).
Please strictly follow the required JSON format."""
    
    def _build_prompt(self, metadata: Dict, elements: List[Dict]) -> str:
        """构建prompt"""
        
        elements_json = json.dumps(elements, ensure_ascii=False, indent=2)
        
        if self.language == "zh":
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
   - {"加入自然的过渡语句连接各部分" if self.include_transitions else "直接讲解内容"}

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
   - {"Include smooth transitions between sections" if self.include_transitions else "Direct narration"}

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
    
    def _generate_fallback_narration(self, metadata: Dict) -> Dict:
        """生成备用讲解（GPT失败时）"""
        segments = []
        
        for idx, elem in enumerate(metadata['elements']):
            if elem.get('type') in ['decoration', 'logo']:
                continue
            
            text = elem.get('text_content', '')
            if not text:
                continue
            
            if self.language == "zh":
                narration = f"接下来看这部分内容：{text[:150]}"
            else:
                narration = f"Now let's look at this section: {text[:150]}"
            
            segments.append({
                "order": len(segments) + 1,
                "element_name": elem['name'],
                "narration": narration
            })
        
        return {
            "opening": "让我们来看这张幻灯片。" if self.language == "zh" else "Let's look at this slide.",
            "segments": segments,
            "closing": ""
        }
    
    def _build_narration(self, metadata: Dict, gpt_result: Dict) -> SlideNarration:
        """构建讲解对象"""
        
        segments = []
        elem_map = {e['name']: e for e in metadata['elements']}
        
        for seg_data in gpt_result.get('segments', []):
            elem_name = seg_data.get('element_name', '')
            elem = elem_map.get(elem_name, {})
            
            narration_text = seg_data.get('narration', '')
            duration = len(narration_text) * self.char_duration
            
            segment = NarrationSegment(
                order=seg_data.get('order', 0),
                element_name=elem_name,
                element_type=elem.get('type', 'unknown'),
                narration_text=narration_text,
                duration_estimate=round(duration, 1)
            )
            segments.append(segment)
        
        # 计算总时长
        opening = gpt_result.get('opening', '')
        closing = gpt_result.get('closing', '')
        total_duration = (
            len(opening) * self.char_duration +
            sum(s.duration_estimate for s in segments) +
            len(closing) * self.char_duration
        )
        
        return SlideNarration(
            slide_id=metadata['slide_id'],
            title=metadata.get('title', ''),
            language=self.language,
            style=self.style,
            opening=opening,
            segments=segments,
            closing=closing,
            total_duration=round(total_duration, 1),
            created_at=datetime.now().isoformat()
        )
    
    def _save_outputs(self, narration: SlideNarration, output_dir: str, slide_id: str):
        """保存输出文件"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 1. 保存JSON（完整数据）
        json_path = os.path.join(output_dir, f"{slide_id}_narration.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(narration.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"已保存: {json_path}")
        
        # 2. 保存TTS脚本（带元素标记）
        script_path = os.path.join(output_dir, f"{slide_id}_narration_script.txt")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(narration.to_tts_script())
        print(f"已保存: {script_path}")
        
        # 3. 保存纯文本（直接用于TTS）
        text_path = os.path.join(output_dir, f"{slide_id}_narration.txt")
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(narration.to_plain_text())
        print(f"已保存: {text_path}")


# ============ 便捷函数 ============

def generate_narration(json_path: str, 
                       language: str = "zh",
                       style: str = "formal",
                       output_dir: str = None) -> SlideNarration:
    """
    生成幻灯片讲解
    
    Args:
        json_path: JSON元数据文件路径
        language: 语言 "zh"(中文) 或 "en"(英文)
        style: 风格 "formal"(正式) / "casual"(轻松) / "academic"(学术)
        output_dir: 输出目录
        
    Returns:
        SlideNarration: 讲解数据
    """
    generator = NarrationGenerator(language=language, style=style)
    return generator.generate(json_path, output_dir)


# ============ 主程序 ============

if __name__ == "__main__":
    import sys
    
    print("""
幻灯片讲解生成器 v1.1
====================
用法: python narration_generator.py <json_path> [options]

选项:
  --lang=zh/en      语言（默认: zh）
  --style=formal/casual/academic  风格（默认: formal）
  --output=DIR      输出目录（默认: JSON同目录）

示例:
  python narration_generator.py ./output/slide/abc123.json
  python narration_generator.py ./output/slide/abc123.json --lang=en
  python narration_generator.py ./output/slide/abc123.json --style=casual
""")
    
    if len(sys.argv) < 2:
        sys.exit(1)
    
    json_path = sys.argv[1]
    language = "zh"
    style = "formal"
    output_dir = None
    
    for arg in sys.argv[2:]:
        if arg.startswith("--lang="):
            language = arg.split("=")[1]
        elif arg.startswith("--style="):
            style = arg.split("=")[1]
        elif arg.startswith("--output="):
            output_dir = arg.split("=")[1]
    
    print(f"输入: {json_path}")
    print(f"语言: {'中文' if language == 'zh' else '英文'}")
    print(f"风格: {style}")
    print()
    
    try:
        narration = generate_narration(json_path, language, style, output_dir)
        
        print(f"\n" + "=" * 50)
        print(f"生成完成!")
        print(f"总时长: {narration.total_duration:.1f}秒")
        print(f"讲解段落: {len(narration.segments)}个")
        print(f"\n讲解预览:")
        print("-" * 50)
        preview = narration.to_plain_text()
        print(preview[:500])
        if len(preview) > 500:
            print("...")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
