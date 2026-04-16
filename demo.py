#!/usr/bin/env python3
"""
幻灯片一键全流程演示脚本

完整流程: 幻灯片截图 → 元素分割+PPTX重建 → 旁白生成 → TTS语音+动画方案

使用方法:
  python demo.py                          # 默认处理 test_slide.png
  python demo.py slide.png                # 处理指定图片
  python demo.py slide.png --lang=en      # 英文讲解
  python demo.py slide.png --voice=Alvin  # 指定发音人
  python demo.py slide.png --no-tts       # 跳过TTS语音生成
  python demo.py slide.png --no-vlm       # 不使用VLM（纯CV模式）
"""

import os
import sys
import json
import time


def main():
    """一键全流程处理"""

    # === 参数解析 ===
    image_path = "test_slide.png"
    language = "zh"
    use_vlm = True
    do_tts = True
    voice = "Cherry"
    output_dir = "./output"

    for arg in sys.argv[1:]:
        if arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif arg.startswith("--lang="):
            language = arg.split("=", 1)[1]
        elif arg.startswith("--voice="):
            voice = arg.split("=", 1)[1]
        elif arg.startswith("--output="):
            output_dir = arg.split("=", 1)[1]
        elif arg == "--no-vlm":
            use_vlm = False
        elif arg == "--no-tts":
            do_tts = False
        elif not arg.startswith("-"):
            image_path = arg

    if not os.path.exists(image_path):
        print(f"错误: 找不到图片文件 '{image_path}'")
        sys.exit(1)

    print(f"""
{'='*60}
  幻灯片一键全流程演示
{'='*60}
📷  输入图片: {image_path}
🌐  讲解语言: {'中文' if language == 'zh' else 'English'}
🎙️  发音人:   {voice}
🤖  VLM模式:  {'启用' if use_vlm else '关闭'}
🔊  TTS生成:  {'启用' if do_tts else '跳过'}
📁  输出目录: {output_dir}
{'='*60}
""")

    total_start = time.time()

    # ================================================================
    # 第一步: 幻灯片分割 + PPTX重建
    # ================================================================
    print("📌 第一步: 分割幻灯片 + 重建PPTX")
    print("-" * 40)

    from pipeline import process_slide

    step_start = time.time()
    json_path, pptx_path = process_slide(
        image_path,
        output_dir,
        use_vlm=use_vlm,
        hybrid_mode=use_vlm,  # VLM启用时自动使用混合模式
    )
    step_time = time.time() - step_start

    # 读取元数据
    with open(json_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"\n✅ 分割完成 ({step_time:.1f}s)")
    print(f"   幻灯片ID: {metadata['slide_id']}")
    print(f"   尺寸: {metadata['width']}x{metadata['height']}")
    print(f"   背景色: {metadata['background_color']}")
    print(f"   元素数量: {metadata['element_count']}")
    print(f"   JSON: {json_path}")
    print(f"   PPTX: {pptx_path}")

    print(f"\n   检测到的元素:")
    for elem in metadata['elements']:
        flag = "🏆" if elem.get('is_title') else "  "
        text = elem.get('text_content', '')
        preview = f" | {text[:40].replace(chr(10), ' ')}..." if text else ""
        print(f"   {flag} [{elem['type']}] {elem['name']}{preview}")

    # ================================================================
    # 第二步: 生成讲解旁白
    # ================================================================
    print(f"\n📌 第二步: 生成讲解旁白")
    print("-" * 40)

    narration_data = None
    narration_json_path = None

    try:
        from narration_generator import generate_narration

        step_start = time.time()
        narration = generate_narration(
            json_path,
            language=language,
            style="formal"
        )
        step_time = time.time() - step_start

        print(f"\n✅ 旁白生成完成 ({step_time:.1f}s)")
        print(f"   讲解段落: {len(narration.segments)}个")
        print(f"   预估时长: {narration.total_duration:.1f}秒")

        # 找到输出的 narration json 文件
        slide_dir = os.path.dirname(json_path)
        slide_id = metadata['slide_id']
        narration_json_path = os.path.join(slide_dir, f"{slide_id}_narration.json")

        if os.path.exists(narration_json_path):
            with open(narration_json_path, 'r', encoding='utf-8') as f:
                narration_data = json.load(f)

        # 讲解预览
        plain_text = narration.to_plain_text()
        print(f"\n   📖 讲解预览:")
        preview = plain_text[:300].replace('\n', '\n   ')
        print(f"   {preview}")
        if len(plain_text) > 300:
            print(f"   ... (共{len(plain_text)}字)")

    except Exception as e:
        print(f"\n⚠️  旁白生成失败: {e}")
        import traceback
        traceback.print_exc()

    # ================================================================
    # 第三步: TTS语音合成 + 动画方案
    # ================================================================
    if do_tts and narration_json_path and os.path.exists(narration_json_path):
        print(f"\n📌 第三步: TTS语音合成 + 动画方案生成")
        print("-" * 40)

        try:
            from media import generate_tts_and_animations

            slide_dir = os.path.dirname(json_path)

            step_start = time.time()
            tts_result = generate_tts_and_animations(
                narration_json_path=narration_json_path,
                output_dir=slide_dir,
                voice=voice,
                use_llm_animation=True
            )
            step_time = time.time() - step_start

            print(f"\n✅ TTS + 动画生成完成 ({step_time:.1f}s)")
            print(f"   发音人: {voice}")

            if tts_result.get("type") == "batch":
                total_dur = sum(r["audio_info"]["total_duration"] for r in tts_result["results"])
                total_anim = sum(len(r["animation_scheme"]["animations"]) for r in tts_result["results"])
                print(f"   总时长: {total_dur:.1f}秒")
                print(f"   动画数: {total_anim}个")
            else:
                audio = tts_result.get("audio_info", {})
                anim = tts_result.get("animation_scheme", {})
                print(f"   音频时长: {audio.get('total_duration', 0):.1f}秒")
                print(f"   动画数量: {len(anim.get('animations', []))}个")
                print(f"   元素段时长: {anim.get('element_duration', 0):.1f}秒")

            print(f"   音频目录: {os.path.join(slide_dir, 'tts')}")
            print(f"   动画目录: {os.path.join(slide_dir, 'animation')}")

        except Exception as e:
            print(f"\n⚠️  TTS生成失败: {e}")
            import traceback
            traceback.print_exc()

    elif do_tts and not narration_json_path:
        print(f"\n⏭️  跳过TTS: 旁白生成失败，无法合成语音")
    elif not do_tts:
        print(f"\n⏭️  跳过TTS (--no-tts)")

    # ================================================================
    # 完成汇总
    # ================================================================
    total_time = time.time() - total_start
    slide_dir = os.path.dirname(json_path)

    print(f"""
{'='*60}
  🎉 全流程处理完成！总耗时: {total_time:.1f}s
{'='*60}
📁 输出目录: {slide_dir}
   📊 {os.path.basename(pptx_path)}  (重建的PPTX)
   📄 {os.path.basename(json_path)}  (元数据)""")

    # 列出 elements 目录
    elements_dir = os.path.join(slide_dir, "elements")
    if os.path.isdir(elements_dir):
        elems = sorted(os.listdir(elements_dir))
        print(f"   📂 elements/  ({len(elems)}个元素)")
        for e in elems[:5]:
            print(f"      {e}")
        if len(elems) > 5:
            print(f"      ... 还有{len(elems)-5}个")

    if narration_json_path and os.path.exists(narration_json_path):
        print(f"   📝 {os.path.basename(narration_json_path)}  (旁白)")

    tts_dir = os.path.join(slide_dir, "tts")
    if os.path.isdir(tts_dir):
        wav_files = [f for f in os.listdir(tts_dir) if f.endswith('.wav')]
        print(f"   🔊 tts/  ({len(wav_files)}个音频)")

    anim_dir = os.path.join(slide_dir, "animation")
    if os.path.isdir(anim_dir):
        anim_files = os.listdir(anim_dir)
        print(f"   🎬 animation/  ({len(anim_files)}个文件)")

    print()


if __name__ == "__main__":
    main()
