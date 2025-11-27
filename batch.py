#!/usr/bin/env python3
"""
批量处理模块和高级配置
支持多页幻灯片处理、配置管理、后续TTS扩展
"""

import os
import json
import glob
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from pipeline_old import SlideSegmenter, SlideReconstructor, SlideMetadata

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """流水线配置"""
    # 分割参数
    min_area: int = 500
    merge_threshold: int = 20
    ocr_lang: str = "chi_sim+eng"
    
    # PPTX参数
    slide_width_inches: float = 13.333
    slide_height_inches: float = 7.5
    
    # 处理参数
    max_workers: int = 4
    save_intermediate: bool = True
    
    # 输出控制
    generate_description: bool = True  # 生成描述（为TTS准备）
    extract_keywords: bool = True
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PipelineConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_file(cls, path: str) -> 'PipelineConfig':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))
    
    def save(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)


@dataclass
class BatchResult:
    """批量处理结果"""
    total: int
    success: int
    failed: int
    results: List[Dict]
    errors: List[Dict]


class SlidePipeline:
    """
    幻灯片处理流水线
    支持单页和批量处理
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.segmenter = SlideSegmenter(
            min_area=self.config.min_area,
            merge_threshold=self.config.merge_threshold,
            ocr_lang=self.config.ocr_lang
        )
        self.reconstructor = SlideReconstructor(
            slide_width_inches=self.config.slide_width_inches,
            slide_height_inches=self.config.slide_height_inches
        )
    
    def process_single(self, image_path: str, output_dir: str) -> Dict:
        """
        处理单张幻灯片
        
        Returns:
            包含处理结果的字典
        """
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        slide_output_dir = os.path.join(output_dir, image_name)
        
        try:
            # 分割
            metadata = self.segmenter.segment(image_path, slide_output_dir)
            
            # 获取JSON路径
            json_path = os.path.join(slide_output_dir, f"{metadata.slide_id}.json")
            
            # 重建
            pptx_path = os.path.join(slide_output_dir, f"{image_name}_reconstructed.pptx")
            self.reconstructor.reconstruct(json_path, pptx_path)
            
            return {
                "status": "success",
                "image_path": image_path,
                "output_dir": slide_output_dir,
                "json_path": json_path,
                "pptx_path": pptx_path,
                "slide_id": metadata.slide_id,
                "element_count": metadata.element_count,
                "title": metadata.title
            }
            
        except Exception as e:
            logger.error(f"处理失败 {image_path}: {e}")
            return {
                "status": "error",
                "image_path": image_path,
                "error": str(e)
            }
    
    def process_batch(self, image_paths: List[str], output_dir: str,
                      progress_callback: Optional[Callable] = None) -> BatchResult:
        """
        批量处理多张幻灯片
        
        Args:
            image_paths: 图像路径列表
            output_dir: 输出目录
            progress_callback: 进度回调函数 (current, total, result)
        """
        results = []
        errors = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self.process_single, path, output_dir): path
                for path in image_paths
            }
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                
                if result["status"] == "success":
                    results.append(result)
                else:
                    errors.append(result)
                
                if progress_callback:
                    progress_callback(i + 1, len(image_paths), result)
        
        return BatchResult(
            total=len(image_paths),
            success=len(results),
            failed=len(errors),
            results=results,
            errors=errors
        )
    
    def process_directory(self, input_dir: str, output_dir: str,
                          patterns: List[str] = None) -> BatchResult:
        """
        处理目录中的所有图像
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            patterns: 文件模式列表，默认为 ['*.png', '*.jpg', '*.jpeg']
        """
        if patterns is None:
            patterns = ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']
        
        image_paths = []
        for pattern in patterns:
            image_paths.extend(glob.glob(os.path.join(input_dir, pattern)))
        
        image_paths = sorted(set(image_paths))
        
        if not image_paths:
            logger.warning(f"在 {input_dir} 中未找到图像文件")
            return BatchResult(0, 0, 0, [], [])
        
        logger.info(f"找到 {len(image_paths)} 个图像文件")
        
        def progress(current, total, result):
            status = "✓" if result["status"] == "success" else "✗"
            logger.info(f"[{current}/{total}] {status} {os.path.basename(result['image_path'])}")
        
        return self.process_batch(image_paths, output_dir, progress)


class PresentationBuilder:
    """
    演示文稿构建器
    从多个页面JSON创建多页PPTX
    """
    
    def __init__(self, slide_width_inches: float = 13.333, 
                 slide_height_inches: float = 7.5):
        from pptx import Presentation
        from pptx.util import Inches
        
        self.prs = Presentation()
        self.prs.slide_width = Inches(slide_width_inches)
        self.prs.slide_height = Inches(slide_height_inches)
        self.slide_width = Inches(slide_width_inches)
        self.slide_height = Inches(slide_height_inches)
    
    def add_slide_from_json(self, json_path: str) -> int:
        """
        从JSON元数据添加幻灯片
        
        Returns:
            幻灯片索引
        """
        from pptx.dml.color import RGBColor
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        metadata_dir = os.path.dirname(json_path)
        
        # 添加空白幻灯片
        blank_layout = self.prs.slide_layouts[6]
        slide = self.prs.slides.add_slide(blank_layout)
        
        # 设置背景色
        bg_color = data.get('background_color', '#ffffff').lstrip('#')
        r, g, b = int(bg_color[0:2], 16), int(bg_color[2:4], 16), int(bg_color[4:6], 16)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor(r, g, b)
        
        # 计算缩放比例
        from pptx.util import Emu
        original_width = data['width']
        original_height = data['height']
        scale_x = self.slide_width / original_width
        scale_y = self.slide_height / original_height
        
        # 添加元素
        for elem_data in sorted(data['elements'], key=lambda e: e.get('z_order', 0)):
            bbox = elem_data['bbox']
            left = int(bbox['x'] * scale_x)
            top = int(bbox['y'] * scale_y)
            width = int(bbox['width'] * scale_x)
            height = int(bbox['height'] * scale_y)
            
            image_path = os.path.join(metadata_dir, elem_data['image_path'])
            if os.path.exists(image_path):
                shape = slide.shapes.add_picture(image_path, left, top, width, height)
                shape.name = elem_data['name']
        
        return len(self.prs.slides) - 1
    
    def add_slides_from_directory(self, directory: str) -> List[int]:
        """
        从目录中的所有JSON文件添加幻灯片
        按文件名排序
        """
        json_files = sorted(glob.glob(os.path.join(directory, "**/*.json"), recursive=True))
        indices = []
        
        for json_path in json_files:
            try:
                idx = self.add_slide_from_json(json_path)
                indices.append(idx)
                logger.info(f"添加幻灯片: {os.path.basename(json_path)}")
            except Exception as e:
                logger.error(f"添加幻灯片失败 {json_path}: {e}")
        
        return indices
    
    def save(self, output_path: str):
        """保存演示文稿"""
        self.prs.save(output_path)
        logger.info(f"演示文稿已保存: {output_path}")


# ============ 为后续TTS扩展准备的工具 ============

class SlideNarrator:
    """
    幻灯片旁白生成器
    从元数据生成分段描述，为TTS做准备
    """
    
    def __init__(self):
        self.templates = {
            "title": "这张幻灯片的标题是「{title}」。",
            "text": "{content}",
            "chart": "这里有一个图表，展示了相关数据。",
            "table": "这里有一个表格，包含详细信息。",
            "image": "这里有一张图片。",
            "diagram": "这里有一个示意图。"
        }
    
    def generate_narration(self, metadata: Dict) -> Dict:
        """
        生成幻灯片旁白
        
        Returns:
            {
                "full_narration": str,  # 完整旁白
                "segments": List[Dict]  # 分段旁白，每段对应一个元素
            }
        """
        segments = []
        
        for elem in sorted(metadata['elements'], key=lambda e: e.get('z_order', 0)):
            segment = self._generate_segment(elem)
            if segment:
                segments.append({
                    "element_id": elem['id'],
                    "element_name": elem['name'],
                    "element_type": elem['type'],
                    "narration": segment,
                    "bbox": elem['bbox']
                })
        
        full_narration = " ".join([s['narration'] for s in segments])
        
        return {
            "slide_id": metadata['slide_id'],
            "title": metadata.get('title', ''),
            "full_narration": full_narration,
            "segments": segments,
            "word_count": len(full_narration),
            "estimated_duration_seconds": len(full_narration) / 5  # 粗略估计：每秒5个字
        }
    
    def _generate_segment(self, element: Dict) -> str:
        """生成单个元素的旁白"""
        elem_type = element['type']
        text_content = element.get('text_content', '').strip()
        
        if element.get('is_title') and text_content:
            return self.templates['title'].format(title=text_content.split('\n')[0])
        
        if elem_type == 'text' and text_content:
            # 清理文本
            cleaned = ' '.join(text_content.split())
            return self.templates['text'].format(content=cleaned)
        
        if elem_type in self.templates:
            return self.templates[elem_type]
        
        return ""
    
    def generate_batch(self, json_dir: str, output_path: str):
        """
        批量生成旁白并保存
        """
        json_files = sorted(glob.glob(os.path.join(json_dir, "**/*.json"), recursive=True))
        all_narrations = []
        
        for json_path in json_files:
            with open(json_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            narration = self.generate_narration(metadata)
            all_narrations.append(narration)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_narrations, f, ensure_ascii=False, indent=2)
        
        return all_narrations


# ============ 命令行接口 ============

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='幻灯片截图分割与PPTX还原流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 处理单张图片
  python batch.py process slide.png -o ./output
  
  # 批量处理目录
  python batch.py batch ./slides -o ./output
  
  # 合并多个处理结果为单个PPTX
  python batch.py merge ./output -o presentation.pptx
  
  # 生成旁白（为TTS准备）
  python batch.py narrate ./output -o narration.json
'''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 单张处理
    process_parser = subparsers.add_parser('process', help='处理单张幻灯片')
    process_parser.add_argument('image', help='输入图像路径')
    process_parser.add_argument('-o', '--output', default='./output', help='输出目录')
    process_parser.add_argument('--config', help='配置文件路径')
    
    # 批量处理
    batch_parser = subparsers.add_parser('batch', help='批量处理目录')
    batch_parser.add_argument('input_dir', help='输入目录')
    batch_parser.add_argument('-o', '--output', default='./output', help='输出目录')
    batch_parser.add_argument('--config', help='配置文件路径')
    batch_parser.add_argument('--workers', type=int, default=4, help='并行工作数')
    
    # 合并PPTX
    merge_parser = subparsers.add_parser('merge', help='合并多个页面为单个PPTX')
    merge_parser.add_argument('input_dir', help='包含JSON文件的目录')
    merge_parser.add_argument('-o', '--output', default='merged.pptx', help='输出PPTX路径')
    
    # 生成旁白
    narrate_parser = subparsers.add_parser('narrate', help='生成旁白（为TTS准备）')
    narrate_parser.add_argument('input_dir', help='包含JSON文件的目录')
    narrate_parser.add_argument('-o', '--output', default='narration.json', help='输出JSON路径')
    
    args = parser.parse_args()
    
    if args.command == 'process':
        config = PipelineConfig.from_file(args.config) if args.config else PipelineConfig()
        pipeline = SlidePipeline(config)
        result = pipeline.process_single(args.image, args.output)
        
        if result['status'] == 'success':
            print(f"✓ 处理成功")
            print(f"  JSON: {result['json_path']}")
            print(f"  PPTX: {result['pptx_path']}")
        else:
            print(f"✗ 处理失败: {result['error']}")
    
    elif args.command == 'batch':
        config = PipelineConfig.from_file(args.config) if args.config else PipelineConfig()
        config.max_workers = args.workers
        pipeline = SlidePipeline(config)
        result = pipeline.process_directory(args.input_dir, args.output)
        
        print(f"\n处理完成:")
        print(f"  总计: {result.total}")
        print(f"  成功: {result.success}")
        print(f"  失败: {result.failed}")
    
    elif args.command == 'merge':
        builder = PresentationBuilder()
        builder.add_slides_from_directory(args.input_dir)
        builder.save(args.output)
        print(f"✓ 合并完成: {args.output}")
    
    elif args.command == 'narrate':
        narrator = SlideNarrator()
        narrations = narrator.generate_batch(args.input_dir, args.output)
        print(f"✓ 旁白生成完成: {args.output}")
        print(f"  共 {len(narrations)} 页")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
