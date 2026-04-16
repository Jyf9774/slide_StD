"""
幻灯片主处理器
Slide Processor - Main Pipeline Controller

负责端到端处理流程：图像读取 → VLM/CV分析 → 元素检测 → 元数据保存 → PPTX重建
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path
from typing import List, Tuple, Dict

import cv2
import numpy as np
from PIL import Image
from datetime import datetime

from .models import ElementType, BoundingBox, SlideElement, SlideMetadata
from .vlm_analyzer import VLMAnalyzer
from .cv_analyzer import CVFallbackAnalyzer
from .layout_analyzer import LayoutAnalyzer
from .reconstructor import SlideReconstructor


class SlideProcessor:
    """幻灯片处理器，主流程控制"""

    def __init__(self, use_vlm: bool = True, min_area: int = 300, verbose: bool = True, hybrid_mode: bool = True):
        self.use_vlm = use_vlm
        self.min_area = min_area
        self.verbose = verbose
        self.hybrid_mode = hybrid_mode

        # 初始化分析器
        self.vlm_analyzer = VLMAnalyzer() if use_vlm else None
        self.cv_analyzer = CVFallbackAnalyzer(min_area=min_area)

        # 初始化 DocLayout-YOLO 版面检测器
        self.layout_analyzer = LayoutAnalyzer(verbose=verbose)

        self.vlm_available = self.vlm_analyzer and self.vlm_analyzer.enabled

        if verbose:
            print(f"🔧 处理器初始化完成:")
            print(f"   - VLM启用: {use_vlm}")
            print(f"   - VLM可用: {self.vlm_available}")
            print(f"   - DocLayout-YOLO可用: {self.layout_analyzer.available}")
            print(f"   - 混合模式: {hybrid_mode if use_vlm else '禁用(VLM未启用)'}")
            print(f"   - 最小元素面积: {min_area}px")
            if use_vlm and not self.vlm_available:
                print("   ⚠️  VLM不可用，将使用传统CV/OCR fallback方案")

    def process_slide(self, image_path: str, output_base_dir: str = "./output",
                      use_original_bg: bool = True, mask_elements: bool = True) -> Tuple[str, str]:
        """
        处理单张幻灯片，端到端流程
        :return: (元数据JSON路径, 重建PPTX路径)
        """
        start_time = time.time()

        # 准备输出目录
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = os.path.join(output_base_dir, image_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        elements_dir = os.path.join(output_dir, "elements")
        Path(elements_dir).mkdir(exist_ok=True)

        if self.verbose:
            print(f"\n📷 开始处理图像: {image_path}")
            print(f"   输出目录: {output_dir}")
            print(f"   原图背景: {'启用' if use_original_bg else '禁用'}")
            print(f"   元素遮罩: {'启用' if mask_elements else '禁用'}")

        # 读取图像
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图像: {image_path}")
        height, width = image.shape[:2]
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if self.verbose:
            print(f"   图像尺寸: {width}x{height}px")

        # 生成slide_id
        slide_id = hashlib.md5(f"{image_path}{datetime.now()}".encode()).hexdigest()[:12]
        if self.verbose:
            print(f"   幻灯片ID: {slide_id}")

        # 1. 整体分析幻灯片
        slide_analysis = {}
        if self.vlm_available:
            if self.verbose:
                print("\n🔍 步骤1: VLM分析幻灯片整体信息...")
            slide_analysis = self.vlm_analyzer.analyze_slide(image_path)
            if self.verbose:
                if slide_analysis:
                    print(f"   识别标题: {slide_analysis.get('title', '未识别')}")
                    print(f"   背景颜色: {slide_analysis.get('background_color', '自动提取')}")
                    key_points = slide_analysis.get('key_points', [])
                    if key_points:
                        print(f"   核心要点: {len(key_points)}个")

        # 提取背景色
        bg_color_start = time.time()
        if slide_analysis.get('background_color'):
            bg_color = slide_analysis['background_color']
            if self.verbose:
                print(f"\n🎨 背景色来自VLM分析: {bg_color}")
        else:
            bg_color = self.cv_analyzer.extract_background_color(image_rgb)
            if self.verbose:
                print(f"\n🎨 背景色来自CV提取: {bg_color}")
        if self.verbose:
            print(f"   背景色提取耗时: {time.time() - bg_color_start:.2f}s")

        # 2. 检测元素
        print("\n🔍 步骤2: 检测幻灯片元素...")
        elements_data = []
        detect_start = time.time()
        detection_method = "VLM"

        if self.vlm_available:
            if self.hybrid_mode:
                detection_method = "DocLayout-YOLO+VLM混合模式"
                if self.verbose:
                    print("   🔹 混合模式: DocLayout-YOLO版面检测 + VLM语义增强...")
                elements_data = self._hybrid_detect_elements(image, image_path, width, height)
                if not elements_data:
                    if self.verbose:
                        print("   ⚠️  版面检测无结果，降级到纯VLM模式...")
                    elements_data = self.vlm_analyzer.detect_elements(image_path, width, height, self.min_area)
            else:
                if self.verbose:
                    print("   正在调用VLM进行元素检测...")
                elements_data = self.vlm_analyzer.detect_elements(image_path, width, height, self.min_area)
                if self.verbose:
                    print(f"   VLM返回 {len(elements_data)} 个原始元素")

        # VLM失败或者不可用，用CV fallback
        if not elements_data:
            detection_method = "传统CV"
            if self.verbose:
                print("   ⚠️  VLM检测无结果，切换到传统CV fallback方案...")
            elements_data = self.cv_analyzer.detect_elements(image)
            if self.verbose:
                print(f"   CV检测到 {len(elements_data)} 个原始元素")

        # 最终容错
        if not elements_data:
            if self.verbose:
                print("   ⚠️  所有检测都失败，创建全图区域作为后备")
            elements_data = [{
                "bbox": [0, 0, width, height],
                "type": "mixed",
                "text_content": "",
                "is_title": False,
                "description": "整个幻灯片内容",
                "confidence": 0.5
            }]

        if self.verbose:
            print(f"   元素检测总耗时: {time.time() - detect_start:.2f}s")
            print(f"   使用检测方法: {detection_method}")

        # 3. 处理元素，保存裁剪图片
        process_start = time.time()
        elements = []
        invalid_count = 0

        if self.verbose:
            print(f"\n✂️  步骤3: 处理并过滤元素...")

        for idx, elem_data in enumerate(elements_data):
            try:
                x, y, w, h = map(int, elem_data.get("bbox", [0, 0, 0, 0]))
                x = max(0, x)
                y = max(0, y)
                w = min(width - x, w)
                h = min(height - y, h)
                area = w * h

                if w <= 0 or h <= 0 or area < self.min_area:
                    invalid_count += 1
                    if self.verbose:
                        print(f"   ⚠️  过滤元素#{idx}: 尺寸无效或面积过小 ({area}px < {self.min_area}px)")
                    continue

                bbox = BoundingBox(x, y, w, h)
                crop = image_rgb[y:y+h, x:x+w]
                if crop.size == 0:
                    invalid_count += 1
                    if self.verbose:
                        print(f"   ⚠️  过滤元素#{idx}: 裁剪区域为空")
                    continue

                elem_type_str = elem_data.get("type", "mixed").lower()
                try:
                    elem_type = ElementType(elem_type_str)
                except ValueError:
                    elem_type = ElementType.MIXED

                text_content = elem_data.get("text_content", "")
                is_title = elem_data.get("is_title", False)
                description = elem_data.get("description", "")
                element_name = self._generate_element_name(idx, elem_type_str, text_content, is_title, description)
                element_id = f"{slide_id}_{element_name}"

                image_filename = f"{element_name}.png"
                image_save_path = os.path.join(elements_dir, image_filename)
                Image.fromarray(crop).save(image_save_path)

                element = SlideElement(
                    id=element_id,
                    name=element_name,
                    type=elem_type,
                    bbox=bbox,
                    image_path=f"elements/{image_filename}",
                    text_content=text_content,
                    confidence=elem_data.get("confidence", 0.6),
                    is_title=is_title,
                    description=elem_data.get("description", "")
                )
                elements.append(element)

                if self.verbose:
                    title_marker = "🏆 " if is_title else ""
                    text_preview = text_content[:30].replace('\n', ' ') if text_content else elem_data.get("description", "")[:30]
                    print(f"   ✅ {title_marker}元素#{idx}: [{elem_type_str}] {bbox.x},{bbox.y},{bbox.width},{bbox.height} | {text_preview}...")

            except Exception as e:
                invalid_count += 1
                if self.verbose:
                    print(f"   ❌ 处理元素#{idx}失败: {e}")
                continue

        # 设置z_order
        elements.sort(key=lambda e: (e.bbox.y, e.bbox.x))
        for idx, elem in enumerate(elements):
            elem.z_order = idx

        if self.verbose:
            print(f"\n📊 元素处理结果:")
            print(f"   原始检测到: {len(elements_data)}个")
            print(f"   无效过滤: {invalid_count}个")
            print(f"   最终有效: {len(elements)}个")
            print(f"   元素处理耗时: {time.time() - process_start:.2f}s")

            type_counts = {}
            title_count = 0
            for elem in elements:
                t = elem.type.value
                type_counts[t] = type_counts.get(t, 0) + 1
                if elem.is_title:
                    title_count += 1

            print(f"   元素类型统计:")
            for t, count in type_counts.items():
                print(f"     - {t}: {count}个")
            if title_count > 0:
                print(f"   其中标题元素: {title_count}个")

        # 4. 保存元数据
        if self.verbose:
            print("\n💾 步骤4: 保存元数据...")
            save_start = time.time()

        metadata = SlideMetadata(
            slide_id=slide_id,
            source_image=os.path.basename(image_path),
            width=width,
            height=height,
            background_color=bg_color,
            element_count=len(elements),
            elements=elements,
            title=slide_analysis.get('title', ''),
            description=slide_analysis.get('description', ''),
            key_points=slide_analysis.get('key_points', [])
        )

        json_path = os.path.join(output_dir, f"{slide_id}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)

        original_copy = os.path.join(output_dir, f"original_{os.path.basename(image_path)}")
        cv2.imwrite(original_copy, image)

        if self.verbose:
            print(f"   元数据已保存: {json_path}")
            print(f"   原图已备份: {original_copy}")
            print(f"   保存耗时: {time.time() - save_start:.2f}s")

        # 5. 重建PPTX
        if self.verbose:
            print("\n📊 步骤5: 重建PPTX文件...")
            pptx_start = time.time()

        pptx_path = os.path.join(output_dir, f"{image_name}_reconstructed.pptx")
        reconstructor = SlideReconstructor(
            use_original_as_background=use_original_bg,
            mask_elements=mask_elements
        )
        reconstructor.reconstruct(json_path, pptx_path)

        if self.verbose:
            print(f"   PPTX已保存: {pptx_path}")
            print(f"   PPTX重建耗时: {time.time() - pptx_start:.2f}s")
            print(f"\n🎉 处理完成! 总耗时: {time.time() - start_time:.2f}s")
            print("=" * 80)

        return json_path, pptx_path

    def _hybrid_detect_elements(self, image: np.ndarray, image_path: str, img_width: int, img_height: int) -> List[Dict]:
        """
        混合检测模式：DocLayout-YOLO 精准版面检测 + VLM 语义增强

        策略：
        1. DocLayout-YOLO 检测版面区域（精准边界框 + 区域分类）
        2. VLM 对检测到的区域做语义增强（描述、文本内容、分组）
        3. 回退链：Layout不可用 → VLM直接检测 → CV fallback
        """
        layout_elements = []

        # === 步骤1: DocLayout-YOLO 版面检测 ===
        if self.layout_analyzer.available:
            if self.verbose:
                print("   🔹 步骤1: DocLayout-YOLO 版面区域检测...")
            layout_start = time.time()

            layout_elements = self.layout_analyzer.detect_and_merge(
                image_path, min_area=self.min_area
            )

            if self.verbose:
                print(f"   版面检测完成，得到 {len(layout_elements)} 个区域，耗时: {time.time() - layout_start:.2f}s")

            # 预过滤：在送VLM之前移除低价值区域，减少API耗时
            if layout_elements:
                layout_elements = self._pre_filter_layout(layout_elements, img_width, img_height)

        else:
            if self.verbose:
                print("   ⚠️  DocLayout-YOLO 不可用，回退到 VLM 直接检测...")

        # === 步骤2: VLM 语义增强 ===
        if layout_elements and self.vlm_available:
            if self.verbose:
                print("\n   🔹 步骤2: VLM 语义增强（描述、文本、分组）...")

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            regions_info = []
            for idx, elem in enumerate(layout_elements):
                x, y, w, h = elem['bbox']
                crop = image_rgb[y:y+h, x:x+w]
                if crop.size == 0:
                    continue
                regions_info.append({
                    'idx': idx,
                    'bbox': [x, y, w, h],
                    'crop': crop,
                    'cv_text': elem.get('text_content', ''),
                    'cv_type': elem.get('type', 'mixed')
                })

            if regions_info:
                vlm_analysis = self.vlm_analyzer.batch_analyze_regions(
                    image_path, regions_info, img_width, img_height
                )

                if vlm_analysis and 'semantic_blocks' in vlm_analysis:
                    layout_elements = self._apply_vlm_semantics(
                        layout_elements, regions_info, vlm_analysis['semantic_blocks']
                    )
                    if self.verbose:
                        print(f"   VLM识别出 {len(vlm_analysis['semantic_blocks'])} 个语义块，已应用到 Layout 结果")
                else:
                    if self.verbose:
                        print("   ⚠️  VLM语义增强失败，使用 Layout 原始结果")

        # === 回退：Layout不可用时，用VLM直接检测 ===
        if not layout_elements and self.vlm_available:
            if self.verbose:
                print("   🔹 回退: VLM 全局语义块检测...")
            layout_elements = self.vlm_analyzer.detect_elements(
                image_path, img_width, img_height, self.min_area, verbose=self.verbose
            )
            if self.verbose:
                print(f"   VLM检测到 {len(layout_elements)} 个语义块")

        # === 最终回退：纯CV ===
        if not layout_elements:
            if self.verbose:
                print("   ⚠️  所有检测都失败，回退到纯CV...")
            layout_elements = self.cv_analyzer.detect_elements(image)

        if self.verbose:
            print(f"\n   🔹 混合模式检测完成: 共 {len(layout_elements)} 个区域")

        return layout_elements

    def _pre_filter_layout(self, elements: List[Dict], img_width: int, img_height: int) -> List[Dict]:
        """
        预过滤 DocLayout-YOLO 检测结果，在送 VLM 之前移除低价值区域。
        减少 VLM prompt 中的区域数量 → 降低 token 消耗 → 加速推理。
        """
        total_area = img_width * img_height
        filtered = []
        removed = 0

        for elem in elements:
            x, y, w, h = elem['bbox']
            area = w * h
            conf = elem.get('confidence', 1.0)
            layout_class = elem.get('layout_class', '')
            elem_type = elem.get('type', '')

            # 1. 过滤 decoration / abandon 类型（Logo、页脚装饰等）
            if elem_type == 'decoration' or layout_class in ('abandon',):
                removed += 1
                continue

            # 2. 过滤置信度过低的区域（< 0.35）
            if conf < 0.35:
                removed += 1
                continue

            # 3. 过滤面积极小的区域（< 最小面积阈值）
            if area < self.min_area:
                removed += 1
                continue

            # 4. 过滤面积占全图90%以上的（误检整页为一个区域）
            if area > total_area * 0.9:
                removed += 1
                continue

            filtered.append(elem)

        if self.verbose and removed > 0:
            print(f"   🗑️  预过滤: 移除 {removed} 个低价值区域（decoration/低置信度/过小），剩余 {len(filtered)} 个送VLM")

        return filtered

    def _apply_vlm_semantics(self, layout_elements: List[Dict], regions_info: List[Dict],
                             semantic_blocks: List[Dict]) -> List[Dict]:
        """
        将VLM的语义分析结果应用到Layout检测的区域上

        VLM可能会合并多个Layout区域为一个语义块，此时使用合并后的边界框。
        VLM也提供每个块的描述、文本内容等语义信息。
        """
        type_mapping = {
            'title_block': 'text', 'content_block': 'text', 'list_block': 'text',
            'chart_block': 'chart', 'image_block': 'image', 'table_block': 'table',
            'mixed_block': 'mixed', 'decoration_block': 'decoration'
        }

        enhanced = []
        used_layout_indices = set()

        for block in semantic_blocks:
            region_indices = block.get('region_indices', [])
            valid_indices = [i for i in region_indices if i < len(regions_info)]

            if not valid_indices:
                continue

            # 标记已使用的 layout 区域
            used_layout_indices.update(valid_indices)

            # 合并所有关联区域的边界框
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = -float('inf'), -float('inf')

            for idx in valid_indices:
                region = regions_info[idx]
                x, y, w, h = region['bbox']
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x + w)
                max_y = max(max_y, y + h)

            block_type = block.get('type', 'mixed_block')
            mapped_type = type_mapping.get(block_type, 'mixed')

            # 直接丢弃 decoration 类型（Logo、校训、页眉页脚等装饰元素）
            # 这些散布在页面四角的小区域合并后会覆盖整页，导致与内容块重叠
            if mapped_type == 'decoration':
                if self.verbose:
                    print(f"   🗑️  过滤 decoration 块: {block.get('description', '')}")
                continue

            enhanced.append({
                'bbox': [min_x, min_y, max_x - min_x, max_y - min_y],
                'type': mapped_type,
                'text_content': block.get('text_content', ''),
                'description': block.get('description', ''),
                'is_title': block.get('is_title', False),
                'is_key_block': block.get('is_key_block', False),
                'confidence': block.get('confidence', 0.8)
            })

        # 保留 VLM 没有涉及的 layout 区域（VLM可能过滤了一些，或者没覆盖到）
        for idx, elem in enumerate(layout_elements):
            if idx not in used_layout_indices:
                # 检查是否是 decoration（VLM 有意过滤的）
                if elem.get('type') != 'decoration':
                    enhanced.append(elem)

        enhanced.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))
        return enhanced

    def _generate_element_name(self, idx: int, elem_type: str, text_content: str, is_title: bool, description: str = "") -> str:
        """生成有意义的语义块文件名"""
        prefix = f"{idx:02d}_{elem_type}"

        if is_title:
            suffix = "title"
        elif description:
            clean_desc = re.sub(r'[^\w\u4e00-\u9fff]', '', description)
            if any('\u4e00' <= c <= '\u9fff' for c in clean_desc):
                suffix = clean_desc[:8]
            else:
                suffix = clean_desc[:12].lower()
        elif text_content:
            first_line = text_content.strip().split('\n')[0]
            clean_text = re.sub(r'[^\w\u4e00-\u9fff]', '', first_line)
            if any('\u4e00' <= c <= '\u9fff' for c in clean_text):
                suffix = clean_text[:6]
            else:
                suffix = clean_text[:10].lower()
            if not suffix:
                suffix = "content"
        else:
            type_defaults = {
                "image": "img", "chart": "chart", "table": "table",
                "logo": "logo", "diagram": "diagram", "decoration": "deco",
                "mixed": "mixed"
            }
            suffix = type_defaults.get(elem_type, "elem")

        suffix = re.sub(r'[<>:"/\\|?*]', '', suffix)
        suffix = re.sub(r'\s+', '_', suffix)
        suffix = suffix.strip('_') or "elem"

        return f"{prefix}_{suffix}"
