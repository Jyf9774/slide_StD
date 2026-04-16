#!/usr/bin/env python3
"""
API连通性与可用性测试脚本
测试对象：
1. 阿里云Qwen3-TTS API
2. Azure OpenAI GPT API
"""
import os
import sys
import time
import json
import tempfile
import base64
import threading
import dashscope
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat
from openai_client import get_gpt_client, DEFAULT_MODEL
from key_manage import Ali_Cloud_LLM_Key

def test_qwen3_tts_api() -> bool:
    """测试阿里云Qwen3-TTS API可用性"""
    print("\n" + "="*60)
    print(f"测试阿里云Qwen3-TTS API (qwen3-tts-instruct-flash-realtime)")
    print("="*60)

    class TestCallback(QwenTtsRealtimeCallback):
        def __init__(self):
            self.complete_event = threading.Event()
            self.audio_received = 0
            self.error = None
            self.session_id = None
            self.first_audio_delay = None

        def on_open(self) -> None:
            pass

        def on_close(self, close_status_code, close_msg) -> None:
            if close_status_code != 1000 and close_status_code != 1005:
                self.error = f"连接关闭异常，代码: {close_status_code}, 信息: {close_msg}"
            self.complete_event.set()

        def on_event(self, response: str) -> None:
            try:
                type = response['type']
                if 'session.created' == type:
                    self.session_id = response['session']['id']
                if 'response.audio.delta' == type:
                    recv_audio_b64 = response['delta']
                    self.audio_received += len(base64.b64decode(recv_audio_b64))
                if 'session.finished' == type:
                    self.complete_event.set()
            except Exception as e:
                self.error = f"处理响应出错: {str(e)}"
                self.complete_event.set()
                return

        def wait_for_finished(self, timeout=10):
            return self.complete_event.wait(timeout=timeout)

    start_time = time.time()

    try:
        # 初始化API Key
        dashscope.api_key = Ali_Cloud_LLM_Key

        # 初始化回调和客户端
        callback = TestCallback()
        qwen_tts_realtime = QwenTtsRealtime(
            model='qwen3-tts-instruct-flash-realtime',
            callback=callback,
        )
        print(f"✅ TTS客户端初始化成功，响应时间: {(time.time() - start_time)*1000:.2f}ms")

        # 连接服务
        start_time = time.time()
        qwen_tts_realtime.connect()

        # 配置会话
        qwen_tts_realtime.update_session(
            voice = 'Cherry',
            response_format = AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode = 'server_commit'
        )

        # 发送测试文本
        test_text = "测试语音生成，阿里云Qwen3-TTS服务正常"
        qwen_tts_realtime.append_text(test_text)
        qwen_tts_realtime.finish()

        # 等待完成
        if not callback.wait_for_finished():
            print(f"❌ 测试超时，10秒内未收到完成响应")
            return False

        # 检查结果
        if callback.error:
            print(f"❌ {callback.error}")
            return False

        if callback.audio_received > 1000:
            first_audio_delay = qwen_tts_realtime.get_first_audio_delay()
            print(f"✅ 实时语音生成功能正常，总耗时: {time.time() - start_time:.2f}s")
            print(f"   首包延迟: {first_audio_delay:.2f}ms")
            print(f"   音频大小: {callback.audio_received/1024:.2f}KB")
            print(f"   Session ID: {callback.session_id}")
            return True
        else:
            print(f"❌ 语音生成失败，未收到有效音频数据")
            return False

    except Exception as e:
        print(f"❌ TTS测试出错: {str(e)}")
        return False

def test_gpt_api() -> bool:
    """测试GPT API可用性（现在使用阿里云Qwen3.6-plus，原Azure GPT已注释）"""
    print("\n" + "="*60)
    # print("测试Azure OpenAI GPT API")
    print("测试阿里云Qwen3.6-plus API")
    print("="*60)
    
    start_time = time.time()
    
    try:
        client = get_gpt_client()
        if not client:
            print(f"❌ GPT客户端初始化失败，请检查key_manage.py配置")
            return False
        
        print(f"✅ GPT客户端初始化成功")
        
        # 测试简单聊天请求（原Azure模型gpt-4o-mini已注释，现在使用阿里云Qwen模型）
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            # model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "你好，只需要回复'测试成功'这四个字就行"}
            ],
            temperature=0,
            max_tokens=10
        )
        
        result = response.choices[0].message.content.strip()
        if "测试成功" in result:
            print(f"✅ GPT API调用正常，响应时间: {time.time() - start_time:.2f}s")
            print(f"   响应内容: {result}")
            return True
        else:
            print(f"⚠️ GPT API调用成功但返回内容不符合预期: {result}")
            return True  # 只要能返回就算连通
            
    except Exception as e:
        print(f"❌ GPT API测试失败: {str(e)}")
        return False

def main():
    print("API 连通性测试工具")
    print("="*60)
    
    results = []
    
    # 测试TTS API
    tts_ok = test_qwen3_tts_api()
    results.append(("阿里云Qwen3-TTS API", tts_ok))
    
    # 测试GPT API
    gpt_ok = test_gpt_api()
    results.append(("GPT API", gpt_ok))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    all_ok = True
    for name, ok in results:
        status = "✅ 正常" if ok else "❌ 异常"
        print(f"{name}: {status}")
        if not ok:
            all_ok = False
    
    print("\n" + "="*60)
    if all_ok:
        print("🎉 所有API测试通过，可以正常使用！")
    else:
        print("⚠️ 部分API存在异常，请检查配置和服务状态。")
    print("="*60)

if __name__ == "__main__":
    main()
