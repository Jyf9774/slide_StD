# StD Web Dashboard

幻灯片智能还原与演讲生成流水线的 Web 管理面板，包含 FastAPI 后端和 React 前端。

## 架构概览

```
web/
├── server.py          # FastAPI 后端服务（REST API + WebSocket）
├── start.sh           # 一键启动脚本（同时启动前后端）
├── requirements.txt   # 完整依赖清单
├── __init__.py
└── frontend/          # React 前端应用
    ├── src/
    │   ├── components/        # 可复用组件
    │   │   ├── ui/           # 基础 UI 组件 (Button, Card)
    │   │   └── Layout.tsx    # 页面布局
    │   ├── pages/            # 页面组件
    │   │   ├── DashboardPage.tsx   # 幻灯片列表
    │   │   ├── ProcessPage.tsx     # 上传与处理
    │   │   └── ResultPage.tsx      # 结果展示
    │   ├── lib/utils.ts      # API 封装、工具函数
    │   ├── App.tsx           # 路由配置
    │   └── main.tsx          # 入口
    ├── package.json
    ├── vite.config.ts
    └── tailwind.config.ts
```

## 功能特性

### 后端 (FastAPI)
- REST API 封装 pipeline/narration/TTS 全流程
- WebSocket 实时任务进度推送
- 异步任务队列管理
- 静态文件服务（输出结果、上传图片）
- CORS 跨域支持

### 前端 (React + TypeScript)
- 📊 **Dashboard**: 已处理幻灯片列表，缩略图预览，状态标签
- 📤 **上传处理**: 拖拽上传 + 三步配置向导（Pipeline / Narration / TTS）
- 🎨 **结果展示**:
  - 元素边界框叠加可视化
  - 旁白分段展示（Opening → 逐元素 → Closing）
  - 动画时间轴可视化
  - TTS 音频分段播放
  - PPTX 文件下载

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据验证 | Pydantic v2 |
| 实时通信 | WebSocket |
| 前端框架 | React 18 + TypeScript |
| 路由 | React Router v7 |
| 构建工具 | Vite 6 |
| 样式 | Tailwind CSS 3 |
| 图标 | Lucide React |

## 快速开始

### 1. 安装依赖

```bash
# 后端 Python 依赖
pip install -r web/requirements.txt

# 前端 Node.js 依赖
cd web/frontend && npm install
```

### 2. 一键启动

```bash
bash web/start.sh
```

这将同时启动：
- **后端**: `http://localhost:8765`
- **前端**: `http://localhost:5173`

### 3. 分别启动

```bash
# 启动后端
python web/server.py

# 启动前端（另一个终端）
cd web/frontend && npm run dev
```

### 4. 构建生产版本

```bash
cd web/frontend && npm run build
```

构建输出位于 `frontend/dist/` 目录。

## API 接口

### 幻灯片管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/slides` | GET | 获取所有已处理幻灯片列表 |
| `/api/slides/{name}` | GET | 获取幻灯片详情（元数据+旁白+动画+音频） |
| `/api/files/{name}/{path}` | GET | 静态文件服务（图片/音频/PPTX） |

### 文件上传

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/uploads` | GET | 获取已上传文件列表 |
| `/api/upload` | POST | 上传图片文件（支持 PNG/JPG/BMP/WebP） |

### 处理流水线

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/process?filename=xxx` | POST | 启动幻灯片处理（版面检测+PPTX重建） |
| `/api/narrate/{name}` | POST | 生成智能旁白 |
| `/api/tts/{name}` | POST | 生成 TTS 语音 + 动画方案 |

### 任务管理

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/tasks` | GET | 获取所有任务列表 |
| `/api/tasks/{id}` | GET | 查询任务状态 |
| `/api/config/defaults` | GET | 获取默认配置项 |
| `ws://host/ws/progress/{id}` | WebSocket | 实时任务进度 |

## 前端路由

| 路径 | 页面 | 描述 |
|------|------|------|
| `/` | Dashboard | 幻灯片列表和概览 |
| `/process` | Process | 上传和处理幻灯片 |
| `/result/:slideName` | Result | 查看处理结果详情 |

## 配置选项

### Pipeline 处理配置

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `use_vlm` | `true` | 使用 VLM 语义分析 |
| `hybrid_mode` | `true` | DocLayout-YOLO + VLM 混合检测 |
| `min_area` | `300` | 最小元素面积阈值 (px) |
| `use_original_bg` | `true` | 使用原图作为幻灯片背景 |
| `mask_elements` | `true` | 在背景上遮罩元素区域 |

### 旁白生成配置

| 参数 | 默认值 | 选项 |
|------|--------|------|
| `language` | `zh` | `zh` / `en` |
| `style` | `formal` | `formal` / `casual` / `academic` |

### TTS 配置

| 参数 | 默认值 | 选项 |
|------|--------|------|
| `voice` | `Cherry` | `Cherry` (甜美女声) / `Alvin` (成熟男声) / `Wanwan` (可爱童声) |
| `use_llm_animation` | `true` | LLM 智能动画 / 规则动画 |

## 许可证

MIT
