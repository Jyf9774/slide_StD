"""
基于 DocLayout-YOLO 的版面检测器
Layout Analyzer based on DocLayout-YOLO

使用专门训练的文档版面检测模型，替代传统 CV 边缘检测，
能精准检测标题、正文、图表、表格等版面区域，不依赖边缘对比度。
"""

import os
from typing import List, Dict, Optional

import numpy as np


class LayoutAnalyzer:
    """基于 DocLayout-YOLO 的版面检测器"""

    # DocLayout-YOLO DocStructBench 类别 → 项目 ElementType 映射
    CLASS_MAPPING = {
        'title': ('text', True),            # (type, is_title)
        'plain text': ('text', False),
        'abandon': ('text', False),         # 废弃文本（如参考文献编号等）
        'figure': ('image', False),
        'figure_caption': ('text', False),
        'table': ('table', False),
        'table_caption': ('text', False),
        'table_footnote': ('text', False),
        'isolate_formula': ('text', False),
        'formula_caption': ('text', False),
    }

    # 这些类别在幻灯片场景中通常是无关装饰（页眉页脚、logo等）
    DECORATION_CLASSES = {'abandon'}

    def __init__(self, model_path: Optional[str] = None, conf: float = 0.25,
                 imgsz: int = 1024, device: str = "cpu", verbose: bool = True):
        """
        初始化版面检测器

        :param model_path: 模型文件路径，None 则自动从 HuggingFace 下载
        :param conf: 置信度阈值
        :param imgsz: 推理图像尺寸
        :param device: 推理设备 ("cpu" / "cuda:0" / "mps")
        """
        self.conf = conf
        self.imgsz = imgsz
        self.device = device
        self.verbose = verbose
        self.model = None
        self.available = False

        try:
            self._load_model(model_path)
            self.available = True
            if verbose:
                print(f"   ✅ DocLayout-YOLO 版面检测器加载成功 (device={device}, conf={conf})")
        except Exception as e:
            if verbose:
                print(f"   ⚠️  DocLayout-YOLO 加载失败: {e}")
                print(f"   将回退到传统 CV 检测")

    # 项目本地模型路径（相对于 pipeline/ 目录的上级）
    LOCAL_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                     "models", "doclayout_yolo_docstructbench_imgsz1024.pt")

    def _load_model(self, model_path: Optional[str] = None):
        """加载 DocLayout-YOLO 模型，优先从项目本地路径加载"""
        from doclayout_yolo import YOLOv10

        # 优先级：显式指定 > 项目本地 > HuggingFace 下载
        if model_path and os.path.exists(model_path):
            self.model = YOLOv10(model_path)
        elif os.path.exists(self.LOCAL_MODEL_PATH):
            self.model = YOLOv10(self.LOCAL_MODEL_PATH)
        else:
            from huggingface_hub import hf_hub_download
            filepath = hf_hub_download(
                repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
                filename="doclayout_yolo_docstructbench_imgsz1024.pt"
            )
            self.model = YOLOv10(filepath)

    def detect_elements(self, image_path: str, min_area: int = 300) -> List[Dict]:
        """
        检测版面区域，返回与现有 pipeline 格式兼容的结果列表

        :param image_path: 图像文件路径
        :param min_area: 最小区域面积（像素）
        :return: [{"bbox": [x,y,w,h], "type": str, "confidence": float, ...}, ...]
        """
        if not self.available or self.model is None:
            return []

        det_res = self.model.predict(
            image_path,
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            verbose=False
        )

        if not det_res or len(det_res) == 0:
            return []

        result = det_res[0]
        elements = []

        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = result.names.get(cls_id, 'unknown')
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # 转为 [x, y, w, h] 格式
            x, y = int(x1), int(y1)
            w, h = int(x2 - x1), int(y2 - y1)
            area = w * h

            if area < min_area:
                continue

            # 映射类别
            elem_type, is_title = self.CLASS_MAPPING.get(cls_name, ('mixed', False))

            # abandon 类在幻灯片场景中标记为 decoration
            if cls_name in self.DECORATION_CLASSES:
                elem_type = 'decoration'

            elements.append({
                'bbox': [x, y, w, h],
                'type': elem_type,
                'is_title': is_title,
                'confidence': round(conf, 3),
                'layout_class': cls_name,  # 保留原始类别名，方便调试
                'text_content': '',
                'description': '',
            })

        # 按位置排序（上→下，左→右）
        elements.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))

        if self.verbose:
            class_counts = {}
            for e in elements:
                c = e['layout_class']
                class_counts[c] = class_counts.get(c, 0) + 1
            print(f"   📐 DocLayout-YOLO 检测到 {len(elements)} 个版面区域")
            print(f"   📊 类别统计: {class_counts}")

        return elements

    def detect_and_merge(self, image_path: str, min_area: int = 300,
                         merge_captions: bool = True) -> List[Dict]:
        """
        检测版面区域并智能合并（如图表+标题合并为一个块）

        :param merge_captions: 是否将 caption 合并到对应的 figure/table
        :return: 合并后的区域列表
        """
        elements = self.detect_elements(image_path, min_area)
        if not elements or not merge_captions:
            return elements

        # 分离主体区域和 caption 区域
        main_elements = []
        caption_elements = []

        for elem in elements:
            if elem['layout_class'] in ('figure_caption', 'table_caption', 'table_footnote', 'formula_caption'):
                caption_elements.append(elem)
            else:
                main_elements.append(elem)

        if not caption_elements:
            return main_elements

        # 将每个 caption 合并到最近的对应主体区域
        merged = list(main_elements)
        for caption in caption_elements:
            cx, cy, cw, ch = caption['bbox']
            caption_center_y = cy + ch / 2
            caption_center_x = cx + cw / 2

            # 根据 caption 类型找对应的主体类型
            target_types = set()
            if 'figure' in caption['layout_class']:
                target_types = {'image'}
            elif 'table' in caption['layout_class']:
                target_types = {'table'}
            else:
                target_types = {'image', 'table', 'text'}

            best_match = None
            best_dist = float('inf')

            for i, main in enumerate(merged):
                if main['type'] not in target_types:
                    continue

                mx, my, mw, mh = main['bbox']
                main_center_y = my + mh / 2
                main_center_x = mx + mw / 2

                # 计算距离（优先垂直方向接近的）
                dist = abs(caption_center_y - main_center_y) + abs(caption_center_x - main_center_x) * 0.3

                if dist < best_dist:
                    best_dist = dist
                    best_match = i

            if best_match is not None:
                # 合并 bbox
                main = merged[best_match]
                mx, my, mw, mh = main['bbox']
                new_x = min(mx, cx)
                new_y = min(my, cy)
                new_w = max(mx + mw, cx + cw) - new_x
                new_h = max(my + mh, cy + ch) - new_y
                merged[best_match]['bbox'] = [new_x, new_y, new_w, new_h]
            else:
                # 没有匹配到主体，作为独立元素
                merged.append(caption)

        merged.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))
        return merged
