"""
命令行入口和便捷处理函数
CLI Entry Point and Convenience Functions
"""

import sys
from typing import Tuple

from .processor import SlideProcessor


def process_slide(image_path: str,
                  output_base_dir: str = "./output",
                  use_vlm: bool = True,
                  use_original_bg: bool = True,
                  mask_elements: bool = True,
                  min_area: int = 300,
                  verbose: bool = True,
                  hybrid_mode: bool = True) -> Tuple[str, str]:
    """便捷处理函数，对外API"""
    processor = SlideProcessor(use_vlm=use_vlm, min_area=min_area, verbose=verbose, hybrid_mode=hybrid_mode)
    return processor.process_slide(
        image_path,
        output_base_dir,
        use_original_bg=use_original_bg,
        mask_elements=mask_elements
    )


def main():
    """命令行入口"""
    print("""
幻灯片分割与重建流水线 v4.0
===========================
【核心特性】基于语义块检测，输出逻辑完整、适合直接讲解的内容单元
每个块都是独立的讲解单元，不会出现细碎元素，完美适配PPT讲解场景

用法: python -m pipeline <image_path> [output_dir] [options]

选项:
  --no-vlm        不使用VLM大模型（仅用传统CV/OCR fallback）
  --no-hybrid     不使用混合模式（纯VLM直接检测边界，可能不稳定）
  --no-bg         不使用原图作为背景（使用纯色背景）
  --no-mask       不遮罩元素位置（直接原图背景+元素叠加）
  --min-area N    最小语义块面积（像素，默认300）
  --fine-blocks   精细粒度模式（输出更多、更小的语义块，min_area=200）
  --coarse-blocks 粗略粒度模式（输出更少、更大的语义块，min_area=400，推荐默认）
  --fine          兼容旧参数，同--fine-blocks
  --coarse        兼容旧参数，同--coarse-blocks
  -v, --verbose   输出详细调试信息（默认启用）
  -q, --quiet     静默模式，仅输出关键信息

### 模式说明:
  🎯 默认混合模式(推荐): DocLayout-YOLO版面检测 + VLM语义增强，兼顾边界准确性和语义完整性
  🔍 纯VLM模式(--no-hybrid): VLM直接输出边界框，边界可能不稳定但语义理解能力强
  📷 纯CV模式(--no-vlm): 仅用传统CV/OCR，无VLM语义理解能力

示例:
  python -m pipeline slide.png ./output                    # 默认模式，推荐
  python -m pipeline slide.png ./output --coarse-blocks    # 更大的语义块，更少的数量
  python -m pipeline slide.png ./output --fine-blocks      # 更细的粒度，更多的块
  python -m pipeline slide.png ./output --quiet            # 静默模式
""")

    if len(sys.argv) < 2:
        sys.exit(1)

    image_path = sys.argv[1]
    output_dir = "./output"
    use_vlm = True
    hybrid_mode = True
    use_original_bg = True
    mask_elements = True
    min_area = 300
    verbose = True

    # 解析参数
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--no-vlm":
            use_vlm = False
        elif arg == "--no-hybrid":
            hybrid_mode = False
        elif arg == "--no-bg":
            use_original_bg = False
        elif arg == "--no-mask":
            mask_elements = False
        elif arg == "--fine":
            min_area = 200
        elif arg == "--fine-blocks":
            min_area = 200
        elif arg == "--coarse":
            min_area = 400
        elif arg == "--coarse-blocks":
            min_area = 400
        elif arg in ("-v", "--verbose"):
            verbose = True
        elif arg in ("-q", "--quiet"):
            verbose = False
        elif arg == "--min-area" and i + 1 < len(sys.argv):
            try:
                min_area = int(sys.argv[i+1])
                i += 1
            except ValueError:
                if verbose:
                    print("警告: --min-area参数需要是整数，使用默认值300")
        elif not arg.startswith("-"):
            output_dir = arg
        i += 1

    if verbose:
        print(f"⚙️  运行配置:")
        print(f"   处理图像: {image_path}")
        print(f"   输出目录: {output_dir}")
        print(f"   使用VLM语义检测: {use_vlm}")
        print(f"   DocLayout-YOLO+VLM混合模式: {hybrid_mode if use_vlm else '禁用(VLM未启用)'}")
        print(f"   原图背景: {use_original_bg}")
        print(f"   元素遮罩: {mask_elements}")
        print(f"   最小语义块面积: {min_area}px")
        print(f"   详细输出: {verbose}")
        print()
    else:
        print(f"处理图像: {image_path} -> 输出目录: {output_dir}")

    try:
        json_path, pptx_path = process_slide(
            image_path,
            output_dir,
            use_vlm=use_vlm,
            use_original_bg=use_original_bg,
            mask_elements=mask_elements,
            min_area=min_area,
            verbose=verbose,
            hybrid_mode=hybrid_mode
        )

        print(f"\n✅ 处理完成!")
        print(f"📄 元数据: {json_path}")
        print(f"📊 PPTX: {pptx_path}")
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        sys.exit(1)
