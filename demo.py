#!/usr/bin/env python3
"""
幻灯片处理流水线演示

使用方法:
1. python demo.py <图片路径>
2. python demo.py <图片路径> --lang=en  # 英文讲解
3. python demo.py <图片路径> --no-gpt   # 不使用GPT
"""

import os
import sys
import json


def main():
    """主函数"""
    
    # 解析参数
    image_path = "test_slide.png"  # 默认使用test_slide.png
    language = "zh"
    use_gpt = True
    
    for arg in sys.argv[1:]:
        if arg.startswith("--lang="):
            language = arg.split("=")[1]
        elif arg == "--no-gpt":
            use_gpt = False
        elif not arg.startswith("-"):
            image_path = arg
    
    # 显示帮助信息（如果使用-h或--help）
    if "-h" in sys.argv or "--help" in sys.argv:
        print("""
幻灯片处理流水线演示
====================
用法: python demo.py [图片路径] [选项]

参数:
  [图片路径]       幻灯片截图路径（默认: test_slide.png）

选项:
  --lang=zh/en    讲解语言（默认: zh）
  --no-gpt        不使用GPT-4.1（使用传统CV/OCR）
  -h, --help      显示此帮助信息

示例:
  python demo.py              # 使用默认的test_slide.png
  python demo.py slide.png    # 使用指定的图片
  python demo.py --lang=en    # 使用默认图片并生成英文讲解
""")
        sys.exit(0)
    
    if not os.path.exists(image_path):
        print(f"错误: 找不到图片文件 '{image_path}'")
        sys.exit(1)
    
    print(f"\n📷 输入图片: {image_path}")
    print(f"🌐 讲解语言: {'中文' if language == 'zh' else '英文'}")
    print(f"🤖 使用GPT: {'是' if use_gpt else '否'}")
    
    # ========== 第一步: 分割与重建 ==========
    print("\n" + "=" * 60)
    print("第一步: 分割幻灯片并重建PPTX")
    print("=" * 60)
    
    from pipeline import process_slide
    
    output_dir = "./output"
    json_path, pptx_path = process_slide(
        image_path, 
        output_dir,
        use_gpt=use_gpt
    )
    
    print(f"\n✅ 分割完成!")
    print(f"   📄 JSON: {json_path}")
    print(f"   📊 PPTX: {pptx_path}")
    
    # 读取JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    print(f"\n📋 元数据摘要:")
    print(f"   - 幻灯片ID: {metadata['slide_id']}")
    print(f"   - 尺寸: {metadata['width']}x{metadata['height']}")
    print(f"   - 背景色: {metadata['background_color']}")
    print(f"   - 元素数量: {metadata['element_count']}")
    
    print("\n📦 检测到的元素:")
    for elem in metadata['elements']:
        text_preview = ""
        if elem.get('text_content'):
            text_preview = f" | {elem['text_content'][:40].replace(chr(10), ' ')}..."
        print(f"   [{elem['name']}] {elem['type']}{text_preview}")
    
    # ========== 第二步: 生成讲解 ==========
    print("\n" + "=" * 60)
    print("第二步: 生成讲解脚本")
    print("=" * 60)
    
    try:
        from narration_generator import generate_narration
        
        narration = generate_narration(
            json_path,
            language=language,
            style="formal"
        )
        
        print(f"\n✅ 讲解生成完成!")
        print(f"   - 讲解段落: {len(narration.segments)}个")
        print(f"   - 预估时长: {narration.total_duration:.1f}秒")
        
        # 输出文件路径
        slide_dir = os.path.dirname(json_path)
        slide_id = metadata['slide_id']
        
        print(f"\n📝 输出文件:")
        print(f"   - {slide_id}_narration.json      (完整数据)")
        print(f"   - {slide_id}_narration_script.txt (带元素标记)")
        print(f"   - {slide_id}_narration.txt       (纯文本)")
        
        # 显示讲解预览
        print("\n" + "-" * 60)
        print("📖 讲解预览:")
        print("-" * 60)
        
        plain_text = narration.to_plain_text()
        if len(plain_text) > 600:
            print(plain_text[:600])
            print("\n... (更多内容请查看输出文件)")
        else:
            print(plain_text)
        
    except ImportError as e:
        print(f"\n⚠️ 无法生成讲解: {e}")
        print("   请确保已创建 key_manage.py 并配置 Azure_GPT_4_1_Key")
    except Exception as e:
        print(f"\n⚠️ 讲解生成失败: {e}")
        import traceback
        traceback.print_exc()
    
    # ========== 完成 ==========
    print("\n" + "=" * 60)
    print("🎉 全部处理完成!")
    print("=" * 60)
    print(f"\n📁 输出目录: {os.path.dirname(json_path)}")
    print(f"   可以用PowerPoint打开 {os.path.basename(pptx_path)} 查看效果")


if __name__ == "__main__":
    main()