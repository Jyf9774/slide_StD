# CLAUDE_CN.md

本文件为 Claude Code (claude.ai/code) 在本代码仓库工作时提供指导。

## 项目概览

**幻灯片截图分割与PPTX还原流水线 v4.0** - 这是一个Python工具，可自动将幻灯片截图转换为可编辑的PowerPoint (PPTX) 文件，并支持完整的语音合成和智能动画生成：
- 采用Qwen3.6-Plus VLM（视觉语言模型）作为主要分析方案
- 集成DocLayout-YOLO专业版面检测器
- 传统计算机视觉/OCR作为后备选项
- OpenCV用于图像处理和轮廓检测
- python-pptx用于PPTX重建
- 基于LLM的旁白生成
- 集成Qwen3-TTS进行语音合成
- LLM驱动的智能动画生成，与语音节奏自动同步

## 常用命令

### 安装依赖

**macOS:**
```bash
brew install tesseract tesseract-lang ffmpeg
pip install -r requirements.txt
```

**Linux:**
```bash
apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng ffmpeg
pip install -r requirements.txt
```

### 运行演示

```bash
python demo.py                    # 使用默认 test_slide.png
python demo.py <image_path>       # 使用自定义图片
python demo.py --lang=en          # 生成英文旁白
python demo.py --no-vlm           # 仅使用传统CV/OCR方法（不使用VLM）
python demo.py --hybrid           # 使用DocLayout-YOLO + VLM混合模式（默认）
```

### 命令行批量处理

```bash
python batch.py process <slide.png> -o ./output        # 处理单张图片
python batch.py process <slide.png> -o ./output --no-vlm  # 不使用VLM处理
python batch.py batch ./slides -o ./output             # 批量处理目录
python batch.py batch ./slides -o ./output --no-vlm    # 批量处理不使用VLM
python batch.py merge ./output -o presentation.pptx    # 合并为单个PPTX
python batch.py narrate ./output -o narration.json     # 生成旁白脚本
python batch.py tts narration.json -o ./tts_output      # 生成TTS音频 + 动画方案
python batch.py tts narration.json -o ./tts_output --no-llm  # 生成TTS但不使用LLM动画
```

### API 用法

```python
from pipeline import process_slide
json_path, pptx_path = process_slide("slide.png", "./output")

from narration_generator import generate_narration
narration = generate_narration(json_path, language="zh")

from media import generate_tts_and_animations
result = generate_tts_and_animations(
    narration_json_path="narration.json",
    output_dir="./tts_output"
)
```

## 架构

### 核心模块

| 文件 | 用途 |
|------|---------|
| `pipeline/` | **v4 主流水线包**，采用模块化架构：
| `pipeline/models.py` | 数据模型: `ElementType`, `BoundingBox`, `SlideElement`, `SlideMetadata` |
| `pipeline/vlm_analyzer.py` | Qwen3.6-Plus VLM语义分析器 |
| `pipeline/layout_analyzer.py` | DocLayout-YOLO专业版面检测器 |
| `pipeline/cv_analyzer.py` | 传统CV后备分析器 |
| `pipeline/processor.py` | 主流水线处理器 `SlideProcessor` |
| `pipeline/reconstructor.py` | PPTX重建器 `SlideReconstructor` |
| `pipeline/cli.py` | 命令行接口和便捷函数 |
| `batch.py` | 带命令行接口的批量处理、配置管理、并行执行，支持完整端到端工作流 |
| `demo.py` | 带命令行接口的演示脚本 |
| `narration_generator.py` | 基于LLM的旁白生成，为TTS服务 |
| `media/` | 媒体处理包：
| `media/tts_synthesizer.py` | Qwen3-TTS语音合成 |
| `media/animation_generator.py` | LLM驱动智能动画生成 |
| `openai_client.py` | OpenAI/百炼API客户端管理 |
| `key_manage.py` | 存储Qwen/OpenAI服务的API密钥 |

### 流水线流程

1. **版面检测** (`LayoutAnalyzer`):
   - 使用DocLayout-YOLO检测专业幻灯片版面元素
   - 为不同元素类型提供高精度边界框

2. **语义分析** (`VLMAnalyzer`):
   - Qwen3.6-Plus VLM分析整张幻灯片（背景色、标题、整体描述）
   - 分析每个检测区域（类型、文本内容、语义含义、重要性）
   - 为所有元素生成结构化元数据

3. **后备处理** (`CVFallbackAnalyzer`):
   - 当VLM不可用时，使用传统CV方法（K-means找背景，Tesseract OCR，基于规则分类）
   - 即使没有互联网/API访问也能保持功能可用

4. **重建阶段** (`SlideReconstructor`):
   - 使用原图作为背景，用背景色对元素区域做遮罩处理
   - 将每个检测到的元素作为图片插入到原始坐标位置
   - 保存为 `.pptx` 文件，保持原始布局和视觉保真度

5. **旁白生成** (可选):
   - 为每张幻灯片和每个元素生成自然语言描述
   - 输出JSON格式，可直接用于文字转语音处理

6. **TTS合成与动画生成** (可选):
   - 使用Qwen3-TTS为每个旁白片段合成语音音频
   - LLM分析语音时序，生成同步的动画方案
   - 输出音频文件和动画配置，可直接用于演示

### 数据结构

- `SlideMetadata`: 完整幻灯片信息，包含所有元素、背景色、标题、描述
- `SlideElement`: 单个元素（类型、边界框、文字内容、图片路径、元数据）
- `ElementType`: 支持的元素类型枚举
- `BoundingBox`: 元素定位坐标系统
- JSON输出保存所有结构化数据，方便下游处理

### 关键设计特性

- **模块化架构**: 清晰的职责分离，易于维护和扩展
- **混合分析**: DocLayout-YOLO版面检测 + Qwen VLM语义增强，提供卓越的分析精度
- **多级降级**: 当VLM/API服务不可用时，优雅降级到传统方法
- **背景策略**: 原图作背景 + 元素遮罩 + 元素重新插入，保持视觉保真度
- **有意义的文件名**: 元素文件命名格式为 `{序号}_{类型}_{关键词}`，方便调试
- **可配置**: 通过 `PipelineConfig` 支持各种宽高比、处理参数配置
- **端到端工作流**: 从截图到带旁白的动画演示，一站式完成

## 输出目录结构

```
output/
└── <slide_name>/
    ├── <slide_id>.json           # 元数据JSON
    ├── elements/                 # 提取的元素图片
    │   ├── 00_text_title.png
    │   ├── 01_chart_sales.png
    │   └── ...
    ├── original_<name>.png      # 原始图片副本
    ├── masked_background.png    # 遮罩后的背景（使用时生成）
    └── <name>_reconstructed.pptx # 重建后的PPTX

tts_output/
├── audio_info.json              # 音频时序信息
├── animation_scheme.json        # LLM生成的同步动画方案
├── segment_00.wav              # 各个分段音频
├── segment_01.wav
└── ...
```

## 元素类型

- `text` - 纯文本区域
- `title` - 幻灯片标题
- `subtitle` - 幻灯片副标题
- `header` - 页眉
- `footer` - 页脚
- `image` - 照片/插图
- `chart` - 柱状图、折线图、饼图等图表
- `table` - 表格数据
- `diagram` - 流程图/示意图
- `list` - 项目符号/编号列表
- `equation` - 数学公式
- `logo` - 标志/图标
- `decoration` - 装饰元素
- `mixed` - 混合内容类型

## 注意事项

- 通义千问/百炼的API密钥配置在 `key_manage.py` 中（不提交到git）
- Tesseract路径会自动检测：`/opt/homebrew/bin/tesseract`、`/usr/local/bin/tesseract`、`/usr/bin/tesseract`
- 默认幻灯片尺寸：16:9 (13.333" × 7.5")，适配大多数现代演示文稿s
- DocLayout-YOLO模型会在首次运行时自动下载
