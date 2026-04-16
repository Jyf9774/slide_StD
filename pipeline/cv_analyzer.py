"""
传统CV分析器（Fallback方案）
CV Fallback Analyzer

VLM不可用时的后备方案，基于OpenCV进行元素检测、区域分类、OCR识别、背景色提取
"""

import os
from typing import List, Dict

import cv2
import numpy as np
from PIL import Image


class CVFallbackAnalyzer:
    """传统CV分析器，VLM不可用时的fallback方案"""

    def __init__(self, min_area: int = 300):
        self.min_area = min_area
        self._init_tesseract()

    def _init_tesseract(self):
        """初始化Tesseract OCR"""
        try:
            import pytesseract
            tesseract_paths = ['/opt/homebrew/bin/tesseract', '/usr/local/bin/tesseract', '/usr/bin/tesseract']
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
            self.pytesseract = pytesseract
            self.ocr_available = True
        except ImportError:
            self.ocr_available = False
            print("警告: pytesseract未安装，OCR功能不可用")

    def _detect_raw_regions(self, image: np.ndarray) -> List[Dict]:
        """
        原始区域检测，不做严格过滤，作为后备方案
        用于正常检测流程返回空时的降级处理
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = image.shape[:2]

        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 15, 3)
        edges = cv2.Canny(gray, 20, 100)
        combined = cv2.bitwise_or(binary, edges)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 6))
        dilated = cv2.dilate(combined, kernel, iterations=1)
        closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE,
                                   cv2.getStructuringElement(cv2.MORPH_RECT, (8, 8)))

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        elements = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cw * ch

            min_area = max(100, self.min_area // 2)
            if area < min_area or area > 0.98 * w * h:
                continue

            aspect = cw / ch if ch > 0 else 0
            if aspect > 50 or aspect < 0.02:
                continue

            padding = 8
            x = max(0, x - padding)
            y = max(0, y - padding)
            cw = min(w - x, cw + 2 * padding)
            ch = min(h - y, ch + 2 * padding)

            crop = image[y:y+ch, x:x+cw]
            elem_type = self._classify_region(crop)
            text_content = self._ocr_region(crop) if elem_type in ['text', 'mixed', 'table'] else ""
            is_title = y < h * 0.25 and cw > w * 0.3 and text_content

            elements.append({
                "bbox": [x, y, cw, ch],
                "type": elem_type,
                "text_content": text_content,
                "is_title": is_title,
                "description": "",
                "confidence": 0.5
            })

        elements = self._merge_overlapping_regions(elements, overlap_threshold=0.5)
        return elements

    def detect_elements(self, image: np.ndarray) -> List[Dict]:
        """CV检测元素边界框"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = image.shape[:2]

        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY_INV, 11, 2)
        edges = cv2.Canny(gray, 30, 120)
        combined = cv2.bitwise_or(binary, edges)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 4))
        dilated = cv2.dilate(combined, kernel, iterations=1)
        closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE,
                                   cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6)))

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        elements = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cw * ch

            if area < self.min_area or area > 0.98 * w * h:
                continue

            aspect = cw / ch if ch > 0 else 0
            if aspect > 25 or aspect < 0.04:
                continue

            padding = 5
            x = max(0, x - padding)
            y = max(0, y - padding)
            cw = min(w - x, cw + 2 * padding)
            ch = min(h - y, ch + 2 * padding)

            crop = image[y:y+ch, x:x+cw]
            elem_type = self._classify_region(crop)
            text_content = self._ocr_region(crop) if elem_type in ['text', 'mixed', 'table'] else ""
            is_title = y < h * 0.25 and cw > w * 0.3 and text_content

            elements.append({
                "bbox": [x, y, cw, ch],
                "type": elem_type,
                "text_content": text_content,
                "is_title": is_title,
                "description": "",
                "confidence": 0.6
            })

        if not elements:
            return []

        elements = self._remove_overlapping_regions(elements)

        if not elements:
            return self._detect_raw_regions(image)

        merged_elements = self._pre_merge_cv_regions(elements, w, h)

        if not merged_elements:
            return elements

        return merged_elements

    def _remove_overlapping_regions(self, elements: List[Dict]) -> List[Dict]:
        """清理重叠区域，确保2D平面布局下没有重叠"""
        if len(elements) <= 1:
            return elements

        elements.sort(key=lambda e: -(e['bbox'][2] * e['bbox'][3]))
        kept = []

        for elem in elements:
            x1, y1, w1, h1 = elem['bbox']
            area1 = w1 * h1
            overlap_found = False
            merge_with = -1

            for i, kept_elem in enumerate(kept):
                x2, y2, w2, h2 = kept_elem['bbox']
                area2 = w2 * h2

                overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
                overlap_area = overlap_x * overlap_y

                if overlap_area == 0:
                    continue

                overlap_ratio1 = overlap_area / area1 if area1 > 0 else 0
                overlap_ratio2 = overlap_area / area2 if area2 > 0 else 0

                if overlap_ratio1 >= 0.95:
                    if elem['type'] == 'text' and elem['text_content'] and elem['text_content'] not in kept_elem['text_content']:
                        if y1 < y2:
                            new_h = y2 - y1
                            if new_h > 0:
                                elem['bbox'] = [x1, y1, w1, new_h]
                            else:
                                overlap_found = True
                        else:
                            new_y = y2 + h2
                            new_h = (y1 + h1) - new_y
                            if new_h > 0:
                                elem['bbox'] = [x1, new_y, w1, new_h]
                            else:
                                overlap_found = True
                    else:
                        overlap_found = True
                    break

                if overlap_ratio2 >= 0.95:
                    kept[i]['bbox'] = [x1, y1, w1, h1]
                    if elem['text_content'] and elem['text_content'] not in kept[i]['text_content']:
                        kept[i]['text_content'] = f"{kept[i]['text_content']}\n{elem['text_content']}".strip()
                    kept[i]['is_title'] = kept[i]['is_title'] or elem['is_title']
                    overlap_found = True
                    break

                if overlap_ratio1 > 0.2 or overlap_ratio2 > 0.2:
                    merge_with = i
                    break

            if overlap_found:
                continue

            if merge_with >= 0:
                kept_elem = kept[merge_with]
                x2, y2, w2, h2 = kept_elem['bbox']
                new_x = min(x1, x2)
                new_y = min(y1, y2)
                new_w = max(x1 + w1, x2 + w2) - new_x
                new_h = max(y1 + h1, y2 + h2) - new_y
                kept_elem['bbox'] = [new_x, new_y, new_w, new_h]
                if elem['text_content'] and elem['text_content'] not in kept_elem['text_content']:
                    kept_elem['text_content'] = f"{kept_elem['text_content']}\n{elem['text_content']}".strip()
                kept_elem['is_title'] = kept_elem['is_title'] or elem['is_title']
            else:
                kept.append(elem)

        if not kept and elements:
            return elements[:10]

        kept.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))
        return kept

    def _pre_merge_cv_regions(self, elements: List[Dict], img_width: int, img_height: int) -> List[Dict]:
        """CV区域预合并优化，减少候选区域数量"""
        if len(elements) <= 8:
            return elements

        min_width = img_width * 0.05
        min_height = img_height * 0.05
        filtered = []
        for elem in elements:
            x, y, w, h = elem['bbox']
            if (not elem['is_title'] and not elem['text_content'] and
                (w < min_width or h < min_height)):
                continue
            filtered.append(elem)

        if len(filtered) <= 8:
            return filtered

        merged = self._merge_overlapping_regions(filtered, overlap_threshold=0.7)
        if len(merged) <= 10:
            return merged

        merged = self._merge_adjacent_regions(merged, distance_threshold=20)
        if len(merged) <= 12:
            return merged

        merged = self._merge_vertical_text_regions(merged)

        return merged[:15]

    def _merge_overlapping_regions(self, elements: List[Dict], overlap_threshold: float = 0.7) -> List[Dict]:
        """合并重叠度超过阈值的区域"""
        if len(elements) <= 1:
            return elements

        elements.sort(key=lambda e: -(e['bbox'][2] * e['bbox'][3]))
        merged = []
        used = set()

        for i, elem1 in enumerate(elements):
            if i in used:
                continue
            current = elem1.copy()
            used.add(i)
            x1, y1, w1, h1 = current['bbox']
            area1 = w1 * h1

            for j, elem2 in enumerate(elements[i+1:], i+1):
                if j in used:
                    continue
                x2, y2, w2, h2 = elem2['bbox']
                area2 = w2 * h2

                overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
                overlap_area = overlap_x * overlap_y

                min_area = min(area1, area2)
                if min_area > 0 and overlap_area / min_area > overlap_threshold:
                    new_x = min(x1, x2)
                    new_y = min(y1, y2)
                    new_w = max(x1 + w1, x2 + w2) - new_x
                    new_h = max(y1 + h1, y2 + h2) - new_y
                    current['bbox'] = [new_x, new_y, new_w, new_h]

                    if elem2['text_content'] and elem2['text_content'] not in current['text_content']:
                        current['text_content'] = f"{current['text_content']}\n{elem2['text_content']}".strip()

                    current['is_title'] = current['is_title'] or elem2['is_title']

                    if current['type'] == 'mixed' and elem2['type'] == 'text':
                        current['type'] = 'text'

                    used.add(j)

                    x1, y1, w1, h1 = current['bbox']
                    area1 = w1 * h1

            merged.append(current)

        merged.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))
        return merged

    def _merge_adjacent_regions(self, elements: List[Dict], distance_threshold: int = 20) -> List[Dict]:
        """合并距离很近的同类型相邻区域"""
        if len(elements) <= 1:
            return elements

        elements.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))
        merged = []
        i = 0
        n = len(elements)

        while i < n:
            current = elements[i].copy()
            x1, y1, w1, h1 = current['bbox']

            if i + 1 < n:
                next_elem = elements[i + 1]
                x2, y2, w2, h2 = next_elem['bbox']

                vertical_dist = max(0, y2 - (y1 + h1))

                overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                min_width = min(w1, w2)
                horizontal_overlap = overlap_x / min_width if min_width > 0 else 0

                if (vertical_dist < distance_threshold and
                    current['type'] == next_elem['type'] and
                    horizontal_overlap > 0.5):
                    new_x = min(x1, x2)
                    new_y = min(y1, y2)
                    new_w = max(x1 + w1, x2 + w2) - new_x
                    new_h = max(y1 + h1, y2 + h2) - new_y
                    current['bbox'] = [new_x, new_y, new_w, new_h]

                    if next_elem['text_content']:
                        current['text_content'] = f"{current['text_content']}\n{next_elem['text_content']}".strip()

                    current['is_title'] = current['is_title'] or next_elem['is_title']
                    i += 1

            merged.append(current)
            i += 1

        return merged

    def _merge_vertical_text_regions(self, elements: List[Dict]) -> List[Dict]:
        """合并垂直方向上相邻的文本区域"""
        if len(elements) <= 1:
            return elements

        text_elements = [e for e in elements if e['type'] in ['text', 'mixed']]
        other_elements = [e for e in elements if e['type'] not in ['text', 'mixed']]

        if len(text_elements) <= 1:
            return elements

        text_elements.sort(key=lambda e: (e['bbox'][1], e['bbox'][0]))
        merged_text = []
        current = text_elements[0].copy()

        for elem in text_elements[1:]:
            x1, y1, w1, h1 = current['bbox']
            x2, y2, w2, h2 = elem['bbox']

            vertical_dist = y2 - (y1 + h1)
            if vertical_dist < min(h1, h2) * 0.5:
                x_overlap = min(x1 + w1, x2 + w2) - max(x1, x2)
                if x_overlap > min(w1, w2) * 0.3:
                    new_x = min(x1, x2)
                    new_y = min(y1, y2)
                    new_w = max(x1 + w1, x2 + w2) - new_x
                    new_h = max(y1 + h1, y2 + h2) - new_y
                    current['bbox'] = [new_x, new_y, new_w, new_h]
                    current['text_content'] = f"{current['text_content']}\n{elem['text_content']}".strip()
                    current['is_title'] = current['is_title'] or elem['is_title']
                    continue

            merged_text.append(current)
            current = elem.copy()

        merged_text.append(current)
        return merged_text + other_elements

    def _classify_region(self, region: np.ndarray) -> str:
        """简单分类区域类型"""
        h, w = region.shape[:2]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        s_std = np.std(hsv[:, :, 1])

        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=30, maxLineGap=10)
        line_count = len(lines) if lines is not None else 0

        if w / h > 10 or h / w > 10:
            return "decoration"
        if line_count > 15:
            return "table"
        if line_count > 5 and s_std > 40:
            return "chart"
        if edge_density < 0.15:
            return "text"
        if s_std > 50:
            return "image"
        return "mixed"

    def _ocr_region(self, region: np.ndarray) -> str:
        """OCR识别文本"""
        if not self.ocr_available:
            return ""
        try:
            enlarged = cv2.resize(region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            pil_image = Image.fromarray(cv2.cvtColor(enlarged, cv2.COLOR_BGR2RGB))
            text = self.pytesseract.image_to_string(pil_image, lang='chi_sim+eng', config='--oem 3 --psm 6')
            return '\n'.join([l.strip() for l in text.split('\n') if l.strip()])
        except Exception as e:
            print(f"OCR错误: {e}")
            return ""

    def extract_background_color(self, image_rgb: np.ndarray) -> str:
        """提取背景色"""
        h, w = image_rgb.shape[:2]
        margin_x, margin_y = int(w * 0.15), int(h * 0.15)
        center = image_rgb[margin_y:h-margin_y, margin_x:w-margin_x]

        if center.size == 0:
            center = image_rgb

        white_mask = np.all(center > 240, axis=2)
        if np.sum(white_mask) / white_mask.size > 0.3:
            return "#ffffff"

        try:
            from sklearn.cluster import KMeans
            pixels = center.reshape(-1, 3)
            sample = pixels[np.random.choice(len(pixels), min(5000, len(pixels)), replace=False)]
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10).fit(sample)
            labels, counts = np.unique(kmeans.labels_, return_counts=True)
            dominant = kmeans.cluster_centers_[labels[np.argmax(counts)]].astype(int)
            return "#{:02x}{:02x}{:02x}".format(*dominant)
        except:
            return "#ffffff"
