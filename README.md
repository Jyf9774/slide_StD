# 幻灯片智能还原与演讲生成流水线

将幻灯片截图智能分割、重建 PPTX，并自动生成同步解说音频与动画方案。

## 功能特性

- **混合版面检测**：DocLayout-YOLO + VLM 语义增强，识别文本 / 表格 / 图表 / 图像
- **PPTX 还原**：按原始位置关系重建幻灯片
- **智能旁白**：LLM 分段生成（开场 → 逐元素讲解 → 收尾）
- **TTS 语音合成**：Qwen3-TTS 实时流式，自动拼接完整音轨
- **同步动画方案**：LLM 根据语音节奏生成 PPT 动画时间轴

## 目录结构

```
StD/
├── pipeline/              # 幻灯片分割与 PPTX 重建（含 DocLayout-YOLO + VLM）
├── media/                 # TTS 语音合成 + 动画方案生成
├── web/                   # Web Dashboard（前后端，详见 web/README.md）
├── models/                # DocLayout-YOLO 预训练权重（随仓库提交）
├── batch.py               # 命令行：单张 / 批量 / 合并 / 旁白 / TTS
├── demo.py                # 单张图片一键全流程演示
├── narration_generator.py # LLM 旁白生成器
├── openai_client.py       # OpenAI 兼容客户端封装
├── prompts.py             # Prompt 集中管理
└── key_manage.py          # API Key（需本地创建，见下文）
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
brew install ffmpeg          # macOS；Linux 使用 apt install ffmpeg
```

### 2. 配置 LLM / VLM / TTS API Key

项目的 AI 能力统一通过**阿里云百炼 DashScope** 调用：

| 用途 | 模型 | 调用方式 |
|------|------|----------|
| 文本 LLM（旁白 / 动画） | `qwen3.6-plus` | OpenAI 兼容模式 |
| 视觉 VLM（语义增强 / 背景色） | `qwen3.6-plus`（多模态） | OpenAI 兼容模式 |
| 实时 TTS | `qwen3-tts-instruct-flash-realtime` | DashScope 原生 SDK |

**步骤 1**：在 <https://bailian.console.aliyun.com/> 创建 API Key，并开通上表模型权限。

**步骤 2**：在项目根目录创建 `key_manage.py`（已被 `.gitignore` 排除）：

```python
import os

# 阿里云 DashScope API Key（LLM / VLM / TTS 共用）
Ali_Cloud_LLM_Key = "sk-your-dashscope-api-key"

# 以下字段当前版本未使用，保留占位即可
Ali_Cloud_OSS_Key_ID = ""
Ali_Cloud_OSS_Key_Secret = ""
Gemini_API_KEY = ""
Azure_GPT_4_1_Key = ""
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
```

**步骤 3**：验证连通性

```bash
python test_api_health.py
```

> 如需切换到官方 OpenAI / Azure，修改 [`openai_client.py`](./openai_client.py) 的 `DEFAULT_BASE_URL` 与 `DEFAULT_MODEL` 即可；TTS 模块强依赖 DashScope SDK，替换需单独改造或使用 `--no-tts` 跳过。

### 3. 一键全流程（推荐）

```bash
python demo.py slide.png                         # 分割 → 旁白 → TTS + 动画
python demo.py slide.png --lang=en --voice=Alvin # 指定语言和发音人
python demo.py slide.png --no-tts                # 仅分割 + 旁白
python demo.py slide.png --no-vlm                # 纯 CV 模式
```

### 4. 命令行分步使用

```bash
python batch.py process slide.png -o ./output          # 分割 + PPTX 重建
python batch.py batch ./slides -o ./output             # 批量处理目录
python batch.py merge ./output -o presentation.pptx    # 合并为单个 PPTX
python batch.py narrate ./output/slide_dir             # 生成旁白
python batch.py tts narration.json -o ./tts_output     # 生成 TTS + 动画
```

### 5. Python API

```python
from pipeline import process_slide
from narration_generator import generate_narration
from media import generate_tts_and_animations

json_path, pptx_path = process_slide("slide.png", "./output")
narration = generate_narration(json_path, language="zh")
result = generate_tts_and_animations(
    narration_json_path=f"{json_path[:-5]}_narration.json",
    output_dir="./output/slide",
    voice="Cherry",
)
```

## Web Dashboard

前后端一体的 Web 界面（FastAPI + React + Vite）位于 [`web/`](./web)，详细使用说明见 [web/README.md](./web/README.md)。

## 元素类型

| 类型 | 描述 |
|------|------|
| `text` | 纯文本区域 |
| `image` | 图片 |
| `chart` | 图表（柱状图、折线图等） |
| `table` | 表格 |
| `diagram` | 示意图 / 流程图 |
| `decoration` | 装饰元素（Logo 等） |

## 注意事项

1. **DocLayout-YOLO 权重**已随仓库提交（~40MB），克隆后无需额外下载
2. **API Key 必配**：未配置 `key_manage.py` 会在首次 VLM 调用时报错；可用 `--no-vlm` 降级为纯 CV 模式
3. **动画时长**仅覆盖元素讲解段，opening / closing 为纯旁白
4. **PPTX 还原**使用图片插入方式，保持视觉一致但不保留可编辑文本

## License

MIT
