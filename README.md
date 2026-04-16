# 幻灯片智能还原与演讲生成流水线

将幻灯片截图智能分割、重建PPTX，并自动生成同步解说音频与动画方案。

## 功能特性

- 🔍 **混合版面检测**: DocLayout-YOLO 版面区域检测 + VLM 语义增强，精准识别文本/表格/图表/图像
- 🎨 **背景色提取**: VLM 智能分析幻灯片背景颜色
- 📊 **结构化存储**: JSON 格式保存所有元数据，元素图片独立存放
- 🔄 **PPTX还原**: 按原始位置关系重建幻灯片
- 📝 **智能旁白生成**: LLM 驱动的分段讲解文本生成（开场 → 逐元素讲解 → 收尾）
- 🎙️ **TTS语音合成**: Qwen3-TTS 实时流式生成分段解说音频，自动拼接完整音轨
- ✨ **智能动画方案**: LLM 根据语音节奏自动生成同步PPT动画方案（淡入/飞入/擦除等）

## 目录结构

```
StD/
├── pipeline/                   # 幻灯片分割与重建模块
│   ├── __init__.py             # 统一导出 process_slide 等接口
│   ├── processor.py            # 核心处理器：调度检测→分割→保存
│   ├── vlm_analyzer.py         # VLM 语义分析器（整体分析 + 语义增强）
│   ├── layout_analyzer.py      # DocLayout-YOLO 版面检测器
│   ├── cv_analyzer.py          # CV/OCR 后备分析器
│   ├── reconstructor.py        # PPTX 重建器
│   ├── models.py               # 数据模型定义
│   └── cli.py                  # pipeline 子命令行接口
│
├── media/                      # TTS语音合成与动画方案生成模块
│   ├── __init__.py             # 统一导出 + generate_tts_and_animations 便捷函数
│   ├── tts_synthesizer.py      # Qwen3-TTS 实时流式语音合成器
│   ├── animation_generator.py  # LLM 智能动画方案生成器
│   └── progress.py             # 通用进度显示工具（Spinner + 分段进度）
│
├── batch.py                    # 命令行工具：单张/批量/合并/旁白/TTS 全流程
├── demo.py                     # 单张图片一键全流程演示脚本
├── narration_generator.py      # LLM 智能旁白生成器
├── openai_client.py            # 统一 OpenAI 兼容客户端封装
├── prompts.py                  # 所有 Prompt 集中管理
├── key_manage.py               # API Key 管理
├── tts_generator.py            # 兼容层（旧导入路径转发至 media/）
│
├── models/                     # 预训练模型存放目录
│   └── doclayout_yolo_*.pt     # DocLayout-YOLO 权重（自动下载）
│
└── output/                     # 输出目录
    └── <slide_name>/
        ├── <slide_id>.json              # 元数据
        ├── <slide_id>_narration.json    # 旁白数据
        ├── <slide_id>_narration.txt     # 旁白纯文本
        ├── original_<name>.png          # 原始图片备份
        ├── <name>_reconstructed.pptx    # 重建的PPTX
        ├── elements/                    # 提取的元素图片
        │   ├── 00_text_title.png
        │   └── ...
        ├── tts/                         # TTS音频
        │   ├── segment_000_opening.wav
        │   ├── segment_001_elem0.wav
        │   ├── ...
        │   ├── full_narration.wav       # 完整拼接音频
        │   └── audio_info.json          # 音频元数据
        └── animation/                   # 动画方案
            └── animation_scheme.json    # PPT动画时间轴
```

## 快速开始

### 1. 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 系统依赖
brew install ffmpeg          # macOS（音频处理）
# apt install ffmpeg         # Linux

# 可选：Tesseract OCR（仅 CV 后备模式需要）
brew install tesseract tesseract-lang    # macOS
# apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng  # Linux
```

### 2. 配置 API Key

项目使用阿里云 DashScope API（Qwen 系列模型），需配置环境变量：

```bash
export DASHSCOPE_API_KEY="sk-your-api-key"
```

### 3. 一键全流程处理（推荐）

```bash
# 处理单张幻灯片截图：分割 → 旁白 → TTS + 动画
python demo.py slide.png

# 指定语言和发音人
python demo.py slide.png --lang=en --voice=Alvin

# 跳过TTS语音生成（仅分割+旁白）
python demo.py slide.png --no-tts

# 纯CV模式（不使用VLM）
python demo.py slide.png --no-vlm
```

### 4. 命令行分步使用

```bash
# 处理单张图片（分割 + PPTX重建）
python batch.py process slide.png -o ./output

# 批量处理目录
python batch.py batch ./slides -o ./output

# 合并多个页面为单个PPTX
python batch.py merge ./output -o presentation.pptx

# 生成智能旁白
python batch.py narrate ./output/slide_dir

# 生成TTS音频 + 动画方案
python batch.py tts narration.json -o ./tts_output

# 不使用LLM动画（规则生成，速度更快）
python batch.py tts narration.json -o ./tts_output --no-llm
```

### 5. Python API

```python
# 分割幻灯片
from pipeline import process_slide
json_path, pptx_path = process_slide("slide.png", "./output")

# 生成旁白
from narration_generator import generate_narration
narration = generate_narration(json_path, language="zh")

# TTS + 动画
from media import generate_tts_and_animations
result = generate_tts_and_animations(
    narration_json_path="output/slide/xxx_narration.json",
    output_dir="output/slide",
    voice="Cherry",
    use_llm_animation=True
)
```

## 处理流程

```
幻灯片截图
    │
    ▼
┌─────────────────────────────┐
│ 第一步: 分割 + PPTX重建     │  pipeline/
│  DocLayout-YOLO 版面检测     │
│  + VLM 语义增强              │
│  → elements/ + .pptx        │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 第二步: 旁白生成             │  narration_generator.py
│  LLM 逐元素生成讲解文本      │
│  → _narration.json          │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 第三步: TTS + 动画方案       │  media/
│  Qwen3-TTS 分段语音合成      │  → tts/
│  LLM 同步动画方案生成        │  → animation/
└─────────────────────────────┘
```

## 输出格式

### 元数据 JSON

```json
{
  "slide_id": "abc123",
  "source_image": "slide.png",
  "width": 1920,
  "height": 1080,
  "background_color": "#FFFFFF",
  "element_count": 5,
  "elements": [
    {
      "id": "abc123_elem_000",
      "name": "00_text_title",
      "type": "text",
      "bbox": {"x": 100, "y": 80, "width": 800, "height": 120},
      "image_path": "elements/00_text_title.png",
      "text_content": "标题文本...",
      "is_title": true
    }
  ]
}
```

### 动画方案 JSON

```json
{
  "slide_id": "abc123",
  "total_duration": 131.2,
  "element_duration": 131.2,
  "narration_duration": 152.8,
  "animations": [
    {
      "element_id": "abc123_elem_000",
      "effect": "fade_in",
      "start_time": 0.0,
      "duration": 1.0,
      "trigger": "with_previous"
    }
  ]
}
```

## 元素类型

| 类型 | 描述 |
|------|------|
| `text` | 纯文本区域 |
| `image` | 图片 |
| `chart` | 图表（柱状图、折线图等） |
| `table` | 表格 |
| `diagram` | 示意图/流程图 |
| `decoration` | 装饰元素（Logo等） |

## 注意事项

1. **首次运行**会自动从 HuggingFace 下载 DocLayout-YOLO 模型权重（~100MB）
2. **VLM/LLM 调用**依赖网络和 DashScope API，处理速度受 API 响应时间影响
3. **TTS 合成**使用 Qwen3-TTS 实时流式 API，需要 DashScope API Key
4. **动画时长**仅覆盖元素讲解段（opening/closing 为纯旁白，不生成动画）
5. **PPTX还原**使用图片插入方式，保持视觉一致性但不保留可编辑文本

## License

MIT
