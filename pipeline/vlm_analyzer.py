"""
VLM大模型分析器
VLM (Vision Language Model) Analyzer

统一处理所有视觉分析任务：幻灯片整体分析、语义块检测、边界框优化、批量区域分析
"""

import json
import time
import io
import base64
from typing import List, Dict, Any

import cv2
import numpy as np
from PIL import Image

from openai_client import (
    get_gpt_client,
    encode_image_to_base64,
    DEFAULT_MODEL
)
import prompts


from media.progress import Spinner as _VLMSpinner


class VLMAnalyzer:
    """VLM大模型分析器，统一处理所有视觉分析任务"""

    def __init__(self):
        self.client = get_gpt_client()
        self.enabled = self.client is not None
        self.max_image_size = (1920, 1080)  # VLM输入最大分辨率，保持纵横比压缩

    def _encode_resized_image(self, image_path: str) -> str:
        """
        把图像保持纵横比压缩到最大1920x1080后编码成base64
        节省Token同时不影响分析效果
        """
        with Image.open(image_path) as img:
            w, h = img.size
            max_w, max_h = self.max_image_size

            # 已经小于限制，直接编码
            if w <= max_w and h <= max_h:
                return encode_image_to_base64(image_path)

            # 计算缩放比例，保持纵横比
            scale = min(max_w / w, max_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            # 高质量缩放
            resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # 编码成base64
            buffer = io.BytesIO()
            resized_img.save(buffer, format="PNG", optimize=True)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def analyze_slide(self, image_path: str) -> Dict:
        """分析整张幻灯片的整体信息：背景色、标题、描述等"""
        if not self.enabled:
            return {}

        base64_image = self._encode_resized_image(image_path)

        try:
            spinner = _VLMSpinner("VLM分析幻灯片整体信息").start()
            resp = self.client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": prompts.SYSTEM_PROMPT_ANALYZE_SLIDE},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompts.PROMPT_ANALYZE_SLIDE},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            spinner.stop("✅ 幻灯片整体分析完成")

            result_text = resp.choices[0].message.content.strip()
            return self._parse_json_result(result_text)
        except Exception as e:
            if 'spinner' in locals():
                spinner.stop(f"❌ 分析失败: {e}")
            else:
                print(f"VLM分析幻灯片失败: {e}")
            return {}

    def detect_elements(self, image_path: str, image_width: int, image_height: int, min_area: int = 300, verbose: bool = True) -> List[Dict]:
        """
        【语义块优化版】VLM检测逻辑完整的内容块，而不是细碎元素
        每个块都是可以独立讲解的语义单元，完美适配PPT讲解场景
        """
        if not self.enabled:
            if verbose:
                print("   🚫 VLM分析器未启用，跳过检测")
            return []

        if verbose:
            print(f"   📤 调用VLM API进行语义块检测，图像尺寸: {image_width}x{image_height}")
            print(f"   目标：输出逻辑完整、适合作为讲解单元的内容块，数量控制在3-8个")

        base64_image = self._encode_resized_image(image_path)

        prompt = f"""
你是专业的幻灯片内容结构分析专家，请把这张幻灯片分解为逻辑完整、可以独立讲解的语义块。

⚠️  核心要求（非常重要，必须严格遵守）：
1.  每个语义块是逻辑上完整的一个讲解单元，绝对不要拆得过细
    ✅ 比如：主标题 + 副标题 → 作为1个块
    ✅ 比如：小标题 + 下面的整段正文 → 作为1个块
    ✅ 比如：完整的列表（包含所有列表项）→ 作为1个块
    ✅ 比如：图表 + 它的标题/说明文字 → 作为1个块
    ✅ 比如：图片 + 配图说明 → 作为1个块
    ✅ 比如：完整的表格 + 表格标题 → 作为1个块
    ❌ 不要把一个段落拆成多个块
    ❌ 不要把列表的每个项单独作为一个块
    ❌ 不要把图片和它的说明文字分成两个块

2.  块的数量要合适：一张普通幻灯片通常分解为 3-8 个语义块即可，最多不要超过10个
    - 内容简单的幻灯片可以少到2个块
    - 内容复杂的不要超过10个块

3.  边界框要求：
    - 边界框要完整包围整个语义块的所有内容，不要只框一部分
    - 也不要框太多无关的空白区域
    - 【重要】坐标使用0~1000归一化相对坐标，与实际图像尺寸无关：
      * 左上角为(0, 0)，右下角为(1000, 1000)
      * 例如：半宽半高的左上角块应输出 [0, 0, 500, 500]
      * 坐标必须是0~1000之间的整数
    - 后续会自动根据实际图像尺寸映射到真实像素坐标

4.  块类型分类（只能用以下类型）：
    - title_block: 页面主标题 + 副标题（如果有），整个作为一个块
    - content_block: 正文段落 + 小标题，整块内容
    - list_block: 完整的列表（包含所有列表项）
    - chart_block: 图表 + 图表标题/说明
    - image_block: 图片 + 图片标题/说明
    - table_block: 完整的表格 + 表格标题
    - mixed_block: 混合了多种元素的内容块
    - irrelevant_block: 无关内容（logo、校训、页脚、页眉、装饰性元素等）

5.  内容提取要求：
    - text_content：提取块内完整的文本内容，保留原来的换行和格式
    - summary：用一句话概括这个块的核心内容（10-30字）
    - is_key_block：如果是页面核心内容块，设为true，否则false

6.  重要过滤规则（必须严格遵守）：
    - 学校/单位logo、校训、页脚、页眉、水印、装饰性元素等与讲解主题无关的内容，标记为irrelevant_block，会被自动过滤
    - 位于页面边缘的极小装饰性元素，不要作为单独的块
    - 页码、日期、版权声明等非核心内容，也标记为irrelevant_block
    - 如果logo和标题在同一个区域，标题为主，不要单独拆分logo作为独立块

7.  返回严格的JSON数组，不要任何其他内容，不要markdown标记，不要解释说明

每个块的JSON格式：
{{
  "bbox": [x, y, width, height],
  "type": "title_block/content_block/list_block/chart_block/image_block/table_block/mixed_block",
  "text_content": "完整的文本内容，保留原有的换行",
  "description": "这个块的核心内容摘要",
  "is_title": "如果是标题类块填true，否则false",
  "is_key_block": true/false,
  "confidence": 0.9
}}
"""

        try:
            api_start = time.time()
            spinner = _VLMSpinner("VLM语义块检测").start()
            resp = self.client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": "你是专业的幻灯片结构分析专家，只返回严格的JSON格式数据。"},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            api_time = time.time() - api_start
            spinner.stop(f"✅ VLM语义块检测完成")

            result_text = resp.choices[0].message.content.strip()
            if verbose:
                print(f"   📥 响应长度: {len(result_text)}字符，耗时: {api_time:.1f}s")

            parsed_result = self._parse_json_result(result_text)
            if not parsed_result:
                if verbose:
                    print(f"   ❌ JSON解析失败，尝试清理格式后重新解析")
                cleaned = self._clean_json_text(result_text)
                parsed_result = self._parse_json_result(cleaned)

            if parsed_result and verbose:
                print(f"   ✅ JSON解析成功，原始检测到 {len(parsed_result)} 个语义块")
                for i, block in enumerate(parsed_result[:5]):
                    block_type = block.get('type', 'unknown')
                    text_preview = block.get('text_content', '')[:30].replace('\n', ' ')
                    print(f"     块[{i}]: [{block_type}] {text_preview}...")
                if len(parsed_result) > 5:
                    print(f"     ... 还有 {len(parsed_result)-5} 个块")

            # 语义块后处理：过滤、合并
            if parsed_result:
                parsed_result = self._post_process_semantic_blocks(
                    parsed_result, min_area, image_width, image_height, verbose, image_path
                )

            return parsed_result or []
        except Exception as e:
            if verbose:
                print(f"   ❌ VLM检测语义块失败: {str(e)[:100]}")
            return []

    def _clean_json_text(self, text: str) -> str:
        """清理可能有格式问题的JSON文本"""
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        if not text.startswith("["):
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end >= 0 and end > start:
                text = text[start:end+1]
        return text

    def _post_process_semantic_blocks(self, blocks: List[Dict], min_area: int, img_width: int, img_height: int, verbose: bool = True, image_path: str = None) -> List[Dict]:
        """语义块后处理：过滤无效块，合并语义相关的相邻块"""
        if not blocks:
            return []

        # 坐标自动检测与映射
        is_normalized = True
        sample_count = min(5, len(blocks))
        for i in range(sample_count):
            try:
                bbox = blocks[i].get('bbox', [0, 0, 0, 0])
                x, y, w, h = map(int, bbox)
                if x > 1000 or y > 1000 or w > 1000 or h > 1000 or x < 0 or y < 0 or w < 0 or h < 0:
                    is_normalized = False
                    break
            except:
                pass

        if verbose:
            if is_normalized:
                print(f"   🔍 检测到0~1000归一化坐标格式，将映射到实际像素尺寸 {img_width}x{img_height}")
            else:
                print(f"   🔍 检测到像素坐标格式，直接使用")

        # 坐标映射转换
        converted_blocks = []
        for block in blocks:
            try:
                bbox = block.get('bbox', [0, 0, 0, 0])
                x, y, w, h = map(int, bbox)

                if is_normalized:
                    x = int(x * img_width / 1000)
                    y = int(y * img_height / 1000)
                    w = int(w * img_width / 1000)
                    h = int(h * img_height / 1000)
                    w = max(1, w)
                    h = max(1, h)
                    block['bbox'] = [x, y, w, h]

                converted_blocks.append(block)
            except Exception as e:
                if verbose:
                    print(f"   ⚠️  坐标转换失败，跳过块: {e}")
                continue

        blocks = converted_blocks
        if not blocks:
            return []

        # 第一步：边界框坐标修正、无关内容过滤和基础过滤
        valid_blocks = []
        irrelevant_count = 0
        for block in blocks:
            try:
                block_type = block.get('type', '')
                description = block.get('description', '').lower()
                text_content = block.get('text_content', '').lower()

                is_irrelevant = (
                    block_type == 'irrelevant_block' or
                    'logo' in description or 'logo' in text_content or
                    '校训' in description or '校训' in text_content or
                    '页脚' in description or '页眉' in description or
                    'copyright' in text_content or '©' in text_content or
                    '页码' in text_content or 'page' in text_content
                )

                if is_irrelevant:
                    irrelevant_count += 1
                    if verbose:
                        print(f"   🗑️  过滤无关内容块: {block_type} | {description[:30]}...")
                    continue

                x, y, w, h = map(int, block.get('bbox', [0, 0, 0, 0]))
                x = max(0, x)
                y = max(0, y)
                w = min(img_width - x, w)
                h = min(img_height - y, h)
                area = w * h

                is_edge_block = (
                    (x < img_width * 0.05 or x + w > img_width * 0.95 or
                     y < img_height * 0.05 or y + h > img_height * 0.95) and
                    area < min_area * 3
                )
                if is_edge_block:
                    irrelevant_count += 1
                    if verbose:
                        print(f"   🗑️  过滤边缘无关小块: 面积{area}px，位于页面边缘")
                    continue

                if area < min_area * 2:
                    if verbose:
                        print(f"   🗑️  过滤块：面积过小 {area}px < {min_area*2}px")
                    continue
                if area > img_width * img_height * 0.9:
                    if verbose:
                        print(f"   🗑️  过滤块：面积过大 {area}px > 90%页面")
                    continue
                if w <= 0 or h <= 0:
                    if verbose:
                        print(f"   🗑️  过滤块：尺寸无效 {w}x{h}")
                    continue

                block['bbox'] = [x, y, w, h]
                valid_blocks.append(block)
            except Exception as e:
                if verbose:
                    print(f"   🗑️  过滤无效块：{e}")
                continue

        if verbose and irrelevant_count > 0:
            print(f"   🔍 共过滤掉 {irrelevant_count} 个无关内容块（logo、校训、页脚等）")

        if verbose:
            print(f"   🔍 基础过滤后：{len(valid_blocks)}个有效块")

        # 第二步：使用CV优化每个块的边界框
        if len(valid_blocks) > 0:
            if verbose:
                print(f"   ✂️  开始CV优化边界框...")
            optimized_count = 0
            for i, block in enumerate(valid_blocks):
                try:
                    if image_path is None:
                        continue
                    optimized_bbox = self._refine_bbox_with_cv(image_path, block['bbox'], verbose)
                    if optimized_bbox != block['bbox']:
                        optimized_count += 1
                        block['bbox'] = optimized_bbox
                        if verbose and optimized_count <= 5:
                            x1, y1, w1, h1 = block['bbox']
                            x2, y2, w2, h2 = optimized_bbox
                            print(f"     块#{i}边界优化: 原[{x1},{y1},{w1},{h1}] → 新[{x2},{y2},{w2},{h2}]")
                except Exception as e:
                    if verbose:
                        print(f"     块#{i}边界优化失败: {e}")
                    continue
            if verbose and optimized_count > 0:
                print(f"   ✅ 共优化了 {optimized_count} 个块的边界框")

        # 第三步：按位置排序
        valid_blocks.sort(key=lambda b: (b['bbox'][1], b['bbox'][0]))

        # 合并语义相关的相邻块
        merged_blocks = []
        i = 0
        merge_count = 0

        while i < len(valid_blocks):
            current = valid_blocks[i]
            merged = False
            if i + 1 < len(valid_blocks):
                next_block = valid_blocks[i+1]
                if self._can_merge_blocks(current, next_block):
                    merged_block = self._merge_two_blocks(current, next_block)
                    merged_blocks.append(merged_block)
                    merge_count += 1
                    i += 2
                    merged = True
            if not merged:
                merged_blocks.append(current)
                i += 1

        if verbose and merge_count > 0:
            print(f"   🔗 自动合并了 {merge_count} 对相邻相关块")

        # 第四步：二次检查，确保块数不要太多（最多10个）
        if len(merged_blocks) > 10:
            if verbose:
                print(f"   ⚠️  块数过多({len(merged_blocks)})，进行二次合并")
            while len(merged_blocks) > 10:
                min_dist = float('inf')
                merge_idx = 0
                for j in range(len(merged_blocks)-1):
                    b1 = merged_blocks[j]
                    b2 = merged_blocks[j+1]
                    y1_end = b1['bbox'][1] + b1['bbox'][3]
                    y2_start = b2['bbox'][1]
                    dist = y2_start - y1_end
                    if dist < min_dist:
                        min_dist = dist
                        merge_idx = j
                merged_item = self._merge_two_blocks(merged_blocks[merge_idx], merged_blocks[merge_idx+1])
                merged_blocks[merge_idx:merge_idx+2] = [merged_item]

        # 第五步：重叠消解（VLM输出的边界框常有重叠，需要裁剪）
        merged_blocks = self._resolve_overlapping_blocks(merged_blocks, verbose)

        # 第六步：适配原来的元素类型系统
        final_blocks = []
        type_mapping = {
            'title_block': 'text',
            'content_block': 'text',
            'list_block': 'text',
            'chart_block': 'chart',
            'image_block': 'image',
            'table_block': 'table',
            'mixed_block': 'mixed',
            'irrelevant_block': 'decoration'
        }

        for block in merged_blocks:
            block_type = block.get('type', 'mixed_block')
            block['type'] = type_mapping.get(block_type, 'mixed')
            block['is_title'] = block.get('is_title', False) or (block_type == 'title_block')
            final_blocks.append(block)

        if verbose:
            print(f"   ✅ 语义块处理完成：最终得到 {len(final_blocks)} 个完整的讲解单元")
            type_counts = {}
            for b in final_blocks:
                t = b['type']
                type_counts[t] = type_counts.get(t, 0) + 1
            print(f"   📊 块类型统计：{type_counts}")

        return final_blocks

    def _can_merge_blocks(self, block1: Dict, block2: Dict) -> bool:
        """判断两个语义块是否可以合并为一个更大的语义块"""
        x1, y1, w1, h1 = block1['bbox']
        x2, y2, w2, h2 = block2['bbox']

        vertical_dist = max(0, y2 - (y1 + h1))
        if vertical_dist > min(h1, h2) * 0.3:
            return False

        overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        if overlap_x < min(w1, w2) * 0.6:
            return False

        type1 = block1.get('type', '')
        type2 = block2.get('type', '')
        type_pair = {type1, type2}

        allowed_pairs = [
            {'title_block', 'content_block'},
            {'content_block', 'list_block'},
            {'content_block', 'content_block'},
            {'chart_block', 'content_block'},
            {'image_block', 'content_block'},
            {'table_block', 'content_block'},
            {'list_block', 'list_block'}
        ]

        return type_pair in allowed_pairs

    def _merge_two_blocks(self, block1: Dict, block2: Dict) -> Dict:
        """合并两个语义块为一个新的语义块"""
        x1, y1, w1, h1 = block1['bbox']
        x2, y2, w2, h2 = block2['bbox']

        new_x = min(x1, x2)
        new_y = min(y1, y2)
        new_w = max(x1 + w1, x2 + w2) - new_x
        new_h = max(y1 + h1, y2 + h2) - new_y

        text1 = block1.get('text_content', '').strip()
        text2 = block2.get('text_content', '').strip()
        merged_text = f"{text1}\n{text2}" if text1 and text2 else text1 + text2

        desc1 = block1.get('description', '').strip()
        desc2 = block2.get('description', '').strip()
        merged_desc = f"{desc1} + {desc2}" if desc1 and desc2 else desc1 + desc2

        type1 = block1.get('type', 'mixed_block')
        type2 = block2.get('type', 'mixed_block')

        type_priority = {
            'title_block': 5, 'chart_block': 4, 'image_block': 4,
            'table_block': 4, 'content_block': 3, 'list_block': 2, 'mixed_block': 1
        }

        new_type = type1 if type_priority.get(type1, 0) >= type_priority.get(type2, 0) else type2

        return {
            'bbox': [new_x, new_y, new_w, new_h],
            'type': new_type,
            'text_content': merged_text,
            'description': merged_desc,
            'is_title': block1.get('is_title', False) or block2.get('is_title', False),
            'is_key_block': block1.get('is_key_block', False) or block2.get('is_key_block', False),
            'confidence': (block1.get('confidence', 0.7) + block2.get('confidence', 0.7)) / 2
        }

    def _resolve_overlapping_blocks(self, blocks: List[Dict], verbose: bool = False) -> List[Dict]:
        """
        消解语义块之间的重叠
        
        策略：
        - 面积较小的块（更精确的检测）保持不变
        - 面积较大的块（通常是VLM给了过宽的边界）被裁剪
        - 裁剪方向根据两个块的相对位置自动判断（水平/垂直）
        """
        if len(blocks) <= 1:
            return blocks

        # 按面积从小到大排序，小块优先保留
        blocks_with_area = [(i, b, b['bbox'][2] * b['bbox'][3]) for i, b in enumerate(blocks)]
        blocks_with_area.sort(key=lambda x: x[2])

        resolved = [b.copy() for b in blocks]
        trim_count = 0

        # 每对块检查重叠，小块不动，裁剪大块
        for i in range(len(blocks_with_area)):
            idx_small, _, _ = blocks_with_area[i]
            sb = resolved[idx_small]['bbox']
            sx, sy, sw, sh = sb

            for j in range(i + 1, len(blocks_with_area)):
                idx_large, _, _ = blocks_with_area[j]
                lb = resolved[idx_large]['bbox']
                lx, ly, lw, lh = lb

                # 计算重叠区域
                overlap_x1 = max(sx, lx)
                overlap_y1 = max(sy, ly)
                overlap_x2 = min(sx + sw, lx + lw)
                overlap_y2 = min(sy + sh, ly + lh)

                if overlap_x2 <= overlap_x1 or overlap_y2 <= overlap_y1:
                    continue  # 无重叠

                overlap_w = overlap_x2 - overlap_x1
                overlap_h = overlap_y2 - overlap_y1
                overlap_area = overlap_w * overlap_h
                small_area = sw * sh
                large_area = lw * lh

                # 重叠面积占小块不到10%，忽略
                if small_area > 0 and overlap_area / small_area < 0.1:
                    continue

                # 判断裁剪方向：根据两块中心点的相对位置
                sc_x = sx + sw / 2
                sc_y = sy + sh / 2
                lc_x = lx + lw / 2
                lc_y = ly + lh / 2

                dx = abs(sc_x - lc_x)
                dy = abs(sc_y - lc_y)

                old_bbox = list(resolved[idx_large]['bbox'])

                if dx >= dy:
                    # 水平方向分离：裁剪大块的左边或右边
                    if lc_x < sc_x:
                        # 大块在左，裁剪右边界
                        new_right = sx  # 大块右边界 = 小块左边界
                        new_w = new_right - lx
                        if new_w > 0:
                            resolved[idx_large]['bbox'] = [lx, ly, new_w, lh]
                    else:
                        # 大块在右，裁剪左边界
                        new_left = sx + sw  # 大块左边界 = 小块右边界
                        new_w = (lx + lw) - new_left
                        if new_w > 0:
                            resolved[idx_large]['bbox'] = [new_left, ly, new_w, lh]
                else:
                    # 垂直方向分离：裁剪大块的上边或下边
                    if lc_y < sc_y:
                        # 大块在上，裁剪下边界
                        new_bottom = sy
                        new_h = new_bottom - ly
                        if new_h > 0:
                            resolved[idx_large]['bbox'] = [lx, ly, lw, new_h]
                    else:
                        # 大块在下，裁剪上边界
                        new_top = sy + sh
                        new_h = (ly + lh) - new_top
                        if new_h > 0:
                            resolved[idx_large]['bbox'] = [lx, new_top, lw, new_h]

                new_bbox = resolved[idx_large]['bbox']
                if new_bbox != old_bbox:
                    trim_count += 1
                    if verbose:
                        print(f"   ✂️  裁剪重叠: 块[{idx_large}] {old_bbox} → {new_bbox}")

        if verbose and trim_count > 0:
            print(f"   🔧 共裁剪了 {trim_count} 个重叠边界")

        # 过滤掉裁剪后面积过小的块
        result = []
        for b in resolved:
            bw, bh = b['bbox'][2], b['bbox'][3]
            if bw > 0 and bh > 0 and bw * bh > 100:
                result.append(b)

        return result

    def _refine_bbox_with_cv(self, image_path: str, original_bbox: List[int], verbose: bool = False) -> List[int]:
        """
        使用CV技术优化VLM给出的边界框，修正边界不准确的问题
        """
        x, y, w, h = original_bbox

        image = cv2.imread(image_path)
        if image is None:
            return original_bbox

        img_height, img_width = image.shape[:2]

        # 自适应扩展量
        expand_pixels = max(10, min(30, int(min(w, h) * 0.08)))
        x_expanded = max(0, x - expand_pixels)
        y_expanded = max(0, y - expand_pixels)
        w_expanded = min(img_width - x_expanded, w + 2 * expand_pixels)
        h_expanded = min(img_height - y_expanded, h + 2 * expand_pixels)

        roi = image[y_expanded:y_expanded+h_expanded, x_expanded:x_expanded+w_expanded]
        if roi.size == 0:
            return original_bbox

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        block_size = max(11, min(31, int(min(w_expanded, h_expanded) * 0.05) | 1))
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block_size, 3
        )

        edges = cv2.Canny(gray, 30, 120)
        combined = cv2.bitwise_or(binary, edges)

        kernel_w = max(5, min(15, int(w_expanded * 0.03)))
        kernel_h = max(3, min(8, int(h_expanded * 0.02)))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, kernel_h))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return original_bbox

        roi_area = w_expanded * h_expanded
        noise_threshold = max(30, int(roi_area * 0.002))
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = -float('inf'), -float('inf')

        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if cw * ch < noise_threshold:
                continue
            min_x = min(min_x, cx)
            min_y = min(min_y, cy)
            max_x = max(max_x, cx + cw)
            max_y = max(max_y, cy + ch)

        if min_x == float('inf'):
            return original_bbox

        new_x = x_expanded + min_x
        new_y = y_expanded + min_y
        new_w = max_x - min_x
        new_h = max_y - min_y

        padding = max(3, int(min(new_w, new_h) * 0.02))
        new_x = max(0, new_x - padding)
        new_y = max(0, new_y - padding)
        new_w = min(img_width - new_x, new_w + 2 * padding)
        new_h = min(img_height - new_y, new_h + 2 * padding)

        original_area = w * h
        new_area = new_w * new_h
        if original_area > 0 and abs(new_area - original_area) / original_area > 0.7:
            if verbose:
                print(f"     边界优化跳过: 面积变化过大 ({original_area} → {new_area})")
            return original_bbox

        return [new_x, new_y, new_w, new_h]

    def batch_analyze_regions(self, image_path: str, regions_info: List[Dict], img_width: int, img_height: int) -> Dict:
        """批量分析CV检测到的多个区域，进行语义理解和合并"""
        if not self.enabled:
            return {}

        base64_image = self._encode_resized_image(image_path)

        regions_desc = []
        for region in regions_info:
            idx = region['idx']
            x, y, w, h = region['bbox']
            cv_type = region['cv_type']
            cv_text = region['cv_text'].replace('\n', ' ')[:50] if region['cv_text'] else ''
            regions_desc.append(
                f"区域{idx}: 位置({x},{y}), 尺寸{w}x{h}, CV识别类型:{cv_type}, OCR文本:\"{cv_text}\""
            )

        regions_str = '\n'.join(regions_desc)

        prompt = f"""
你是幻灯片语义分析专家，现在有一张幻灯片图像，以及CV算法检测到的{len(regions_info)}个候选区域。

请分析这些区域，把语义相关、属于同一个讲解单元的区域合并为一个语义块。

图像尺寸: {img_width}x{img_height}
所有候选区域信息:
{regions_str}

### 分析要求:
1. 合并规则:
   - 标题 + 副标题 → 合并为一个标题块
   - 小标题 + 下面的正文段落 → 合并为一个内容块
   - 列表的所有项 → 合并为一个列表块
   - 图表 + 图表标题/说明文字 → 合并为一个图表块
   - 图片 + 图片说明 → 合并为一个图片块
   - 表格 + 表格标题 → 合并为一个表格块
   - 无关内容(logo、校训、页脚、页眉、装饰线等) → 标记为无关块，会被过滤

2. 语义块类型只能使用以下类型:
   - title_block / content_block / list_block / chart_block
   - image_block / table_block / mixed_block / decoration_block

3. 每个语义块需要包含:
   - region_indices: 组成这个语义块的所有区域的idx列表
   - type: 语义块类型
   - text_content: 完整文本内容
   - description: 核心内容摘要（10-30字）
   - is_title: 是否是标题类块
   - is_key_block: 是否是页面核心内容块
   - confidence: 分析置信度（0-1）

4. 输出要求:
   - 严格返回JSON格式，不要任何其他内容，不要markdown标记
   - 语义块数量控制在3-10个之间

返回JSON结构示例:
{{
    "semantic_blocks": [
        {{
            "region_indices": [0, 1],
            "type": "title_block",
            "text_content": "幻灯片标题\\n副标题",
            "description": "页面主标题和副标题",
            "is_title": true,
            "is_key_block": true,
            "confidence": 0.95
        }}
    ]
}}
"""

        try:
            spinner = _VLMSpinner(f"VLM语义增强 ({len(regions_info)}个区域)").start()
            resp = self.client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": "你是专业的幻灯片语义分析专家，只返回严格的JSON格式数据。"},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            spinner.stop(f"✅ VLM语义增强完成")

            result_text = resp.choices[0].message.content.strip()
            return self._parse_json_result(result_text)
        except Exception as e:
            if 'spinner' in locals():
                spinner.stop(f"❌ 语义增强失败: {e}")
            else:
                print(f"批量分析区域失败: {e}")
            return {}

    def _parse_json_result(self, text: str) -> Any:
        """解析大模型返回的JSON结果，处理可能的markdown包裹"""
        try:
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            return json.loads(text)
        except Exception as e:
            print(f"JSON解析失败: {e}, 原始内容: {text[:200]}...")
            return None
