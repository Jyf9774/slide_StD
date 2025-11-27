# 幻灯片截图分割与PPTX还原流水线

将幻灯片截图"切碎"保存，并在PPTX文件中尽可能还原。

## 功能特性

- 🔍 **智能区域检测**: 使用OpenCV检测图表、文本、图像等区域
- 📝 **OCR文本识别**: 支持中英文混合识别
- 🎨 **背景色提取**: 自动提取幻灯片背景颜色
- 📊 **元素分类**: 自动识别文本、图表、表格、图像等类型
- 📁 **结构化存储**: JSON格式保存所有元数据
- 🔄 **PPTX还原**: 按原始位置关系重建幻灯片
- 🎤 **TTS准备**: 生成分段旁白描述

## 目录结构

```
slide_pipeline/
├── pipeline.py      # 核心流水线模块
├── batch.py         # 批量处理和命令行工具
├── demo.py          # 演示脚本
└── output/          # 输出目录
    └── <slide_name>/
        ├── <slide_id>.json           # 元数据JSON
        ├── elements/                 # 提取的元素图片
        │   ├── element_000.png
        │   ├── element_001.png
        │   └── ...
        ├── original_<name>.png       # 原始图片副本
        └── <name>_reconstructed.pptx # 重建的PPTX
```

## 快速开始

### 1. 安装依赖

#### 在macOS上安装

```bash
# 使用Homebrew安装Tesseract OCR及其语言包
brew install tesseract tesseract-lang

# 安装Python依赖
pip install opencv-python-headless pytesseract python-pptx pillow scikit-image numpy
```

#### macOS环境下的注意事项

1. **Tesseract OCR路径配置**：
   - Homebrew安装的Tesseract通常位于`/usr/local/bin/tesseract`或`/opt/homebrew/bin/tesseract`
   - 如果pytesseract找不到Tesseract可执行文件，需要在代码中指定路径：
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract'  # 或 '/opt/homebrew/bin/tesseract'
   ```

2. **字体配置**：
   - 项目已适配macOS系统字体，优先使用SF Pro Display和Arial
   - 如需使用其他字体，请确保字体已安装在系统中

3. **项目路径**：
   - demo.py已调整为在项目根目录下创建和处理文件
   - 输出文件将保存在项目根目录的output文件夹中

#### 在Linux上安装

```bash
# 安装Tesseract OCR及其语言包
apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng

# 安装Python依赖
pip install opencv-python-headless pytesseract python-pptx pillow scikit-image numpy
```

### 2. 处理单张幻灯片

```python
from pipeline import process_slide

json_path, pptx_path = process_slide("slide.png", "./output")
print(f"JSON: {json_path}")
print(f"PPTX: {pptx_path}")
```

### 3. 运行演示

**运行演示脚本**
- 默认使用项目根目录下的 test_slide.png:
  ```bash
  python demo.py
  ```
- 指定自定义图片路径:
  ```bash
  python demo.py <你的图片路径>
  ```
- 使用英文生成讲解:
  ```bash
  python demo.py --lang=en
  ```
- 不使用GPT，仅使用传统CV/OCR方法:
  ```bash
  python demo.py --no-gpt
  ```
- 查看帮助信息:
  ```bash
  python demo.py --help
  ```

程序将处理提供的幻灯片截图，输出目录为 `./output`

### 4. 命令行使用

```bash
# 处理单张图片
python batch.py process slide.png -o ./output

# 批量处理目录
python batch.py batch ./slides -o ./output

# 合并多个页面为单个PPTX
python batch.py merge ./output -o presentation.pptx

# 生成旁白（为TTS准备）
python batch.py narrate ./output -o narration.json
```

## JSON元数据结构

```json
{
  "slide_id": "abc123",
  "source_image": "slide.png",
  "width": 1920,
  "height": 1080,
  "aspect_ratio": "16:9",
  "background_color": "#1a365d",
  "background_colors_palette": ["#1a365d", "#234471", ...],
  "element_count": 5,
  "elements": [
    {
      "id": "abc123_elem_000",
      "name": "element_000",
      "type": "text",
      "bbox": {"x": 100, "y": 80, "width": 800, "height": 120},
      "image_path": "elements/element_000.png",
      "text_content": "标题文本...",
      "confidence": 0.85,
      "dominant_colors": ["#ffffff", "#1a365d"],
      "has_border": false,
      "is_title": true,
      "z_order": 0,
      "metadata": {
        "aspect_ratio": 6.67,
        "relative_size": 96000
      }
    }
  ],
  "title": "幻灯片标题",
  "description": "页面内容描述...",
  "keywords": ["关键词1", "关键词2"]
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
| `icon` | 图标 |
| `mixed` | 混合类型 |

## 配置选项

```python
from batch import PipelineConfig, SlidePipeline

config = PipelineConfig(
    min_area=500,           # 最小区域面积
    merge_threshold=20,     # 区域合并阈值
    ocr_lang="chi_sim+eng", # OCR语言
    max_workers=4,          # 并行处理数
    generate_description=True,
    extract_keywords=True
)

pipeline = SlidePipeline(config)
```

## 后续扩展：TTS语音生成

```python
from batch import SlideNarrator

narrator = SlideNarrator()

# 从JSON生成旁白
with open("output/slide/metadata.json") as f:
    metadata = json.load(f)

narration = narrator.generate_narration(metadata)
print(narration['full_narration'])

# 批量生成
narrator.generate_batch("./output", "narration.json")
```

旁白输出格式：
```json
{
  "slide_id": "abc123",
  "title": "数据分析报告",
  "full_narration": "这张幻灯片的标题是「数据分析报告」。营收同比增长23.5%...",
  "segments": [
    {
      "element_id": "abc123_elem_000",
      "element_name": "element_000",
      "element_type": "text",
      "narration": "这张幻灯片的标题是「数据分析报告」。",
      "bbox": {"x": 100, "y": 80, "width": 800, "height": 120}
    }
  ],
  "estimated_duration_seconds": 15.4
}
```

## API参考

### SlideSegmenter

```python
segmenter = SlideSegmenter(min_area=500, merge_threshold=20, ocr_lang="chi_sim+eng")
metadata = segmenter.segment(image_path, output_dir)
```

### SlideReconstructor

```python
reconstructor = SlideReconstructor(slide_width_inches=13.333, slide_height_inches=7.5)
reconstructor.reconstruct(json_path, output_pptx)
```

### SlidePipeline

```python
pipeline = SlidePipeline(config)
result = pipeline.process_single(image_path, output_dir)
batch_result = pipeline.process_batch(image_paths, output_dir)
batch_result = pipeline.process_directory(input_dir, output_dir)
```

### PresentationBuilder

```python
builder = PresentationBuilder()
builder.add_slide_from_json(json_path)
builder.add_slides_from_directory(directory)
builder.save(output_path)
```

## 注意事项

1. **OCR准确性**: OCR识别准确性取决于图像质量和字体，建议使用清晰的截图
2. **背景色**: 背景色通过边缘采样提取，渐变背景会取主要颜色
3. **元素合并**: 相邻的小元素可能被合并，可通过调整`merge_threshold`控制
4. **PPTX还原**: 还原使用图片插入方式，保持视觉一致性但不保留可编辑文本

## License

MIT
