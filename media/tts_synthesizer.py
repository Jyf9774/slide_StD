"""
TTS 语音合成器
使用 Qwen3-TTS 实时API生成分段语音，支持进度显示
"""

import os
import json
import base64
import threading
import struct
import subprocess
from typing import Dict, Optional
from pathlib import Path

import dashscope
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat

from key_manage import Ali_Cloud_LLM_Key
from .progress import print_step_progress


class TTSRealtimeCallback(QwenTtsRealtimeCallback):
    """实时TTS回调类，用于接收音频数据"""
    def __init__(self):
        self.complete_event = threading.Event()
        self.audio_data = bytearray()
        self.error = None

    def on_open(self) -> None:
        pass

    def on_close(self, close_status_code, close_msg) -> None:
        if close_status_code not in (1000, 1005):
            self.error = f"TTS连接异常关闭: {close_status_code}, {close_msg}"
        self.complete_event.set()

    def on_event(self, response: dict) -> None:
        try:
            event_type = response['type']
            if event_type == 'response.audio.delta':
                audio_chunk = base64.b64decode(response['delta'])
                self.audio_data.extend(audio_chunk)
            elif event_type == 'session.finished' or event_type == 'response.done':
                self.complete_event.set()
            elif event_type == 'error':
                self.error = f"TTS API错误: {response['error']['message']}"
                self.complete_event.set()
        except Exception as e:
            self.error = f"处理TTS响应出错: {str(e)}"
            self.complete_event.set()

    def wait_for_completion(self, timeout=30) -> bool:
        """等待合成完成，超时返回False"""
        return self.complete_event.wait(timeout=timeout)


class Qwen3TTSGenerator:
    """Qwen3-TTS 语音生成器（实时API版本，使用qwen3-tts-instruct-flash-realtime模型）"""

    def __init__(self, voice: str = "Cherry", sample_rate: int = 24000):
        """
        初始化TTS生成器
        :param voice: 发音人，可选值：Cherry(甜美女声)、Alvin(成熟男声)、Wanwan(可爱童声)等
        :param sample_rate: 采样率，默认24000Hz
        """
        dashscope.api_key = Ali_Cloud_LLM_Key
        self.voice = voice
        self.sample_rate = sample_rate
        self.format = "wav"

    def generate_audio(self, text: str, output_path: str, voice_description: Optional[str] = None) -> float:
        """
        生成单个文本的语音
        :param text: 要合成的文本
        :param output_path: 输出音频文件路径
        :param voice_description: 语音描述（可选，实时API暂不支持）
        :return: 音频时长（秒）
        """
        try:
            callback = TTSRealtimeCallback()

            tts_client = QwenTtsRealtime(
                model='qwen3-tts-instruct-flash-realtime',
                callback=callback
            )

            tts_client.connect()

            tts_client.update_session(
                voice=self.voice,
                response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode='server_commit'
            )

            tts_client.append_text(text)
            tts_client.finish()

            if not callback.wait_for_completion(timeout=30):
                raise Exception("TTS合成超时，30秒内未完成")

            if callback.error:
                raise Exception(callback.error)

            if len(callback.audio_data) == 0:
                raise Exception("TTS合成失败，未收到音频数据")

            # 生成WAV文件
            wav_header = self._gen_wav_header(
                pcm_data_len=len(callback.audio_data),
                sample_rate=self.sample_rate,
                channels=1,
                bit_depth=16
            )

            with open(output_path, 'wb') as f:
                f.write(wav_header)
                f.write(callback.audio_data)

            # 计算音频时长（秒）：16位单声道，每个采样2字节
            duration = len(callback.audio_data) / (self.sample_rate * 2)
            return duration

        except Exception as e:
            raise Exception(f"TTS API调用失败: {str(e)}")

    @staticmethod
    def _gen_wav_header(pcm_data_len: int, sample_rate: int, channels: int = 1, bit_depth: int = 16) -> bytes:
        """生成WAV文件头"""
        byte_rate = sample_rate * channels * bit_depth // 8
        block_align = channels * bit_depth // 8
        header = struct.pack(
            '<4sI4s4sI2H2I2H4sI',
            b'RIFF',
            36 + pcm_data_len,
            b'WAVE',
            b'fmt ',
            16,
            1,  # PCM格式
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bit_depth,
            b'data',
            pcm_data_len
        )
        return header

    def generate_segmented_audio(self, narration_data: Dict, output_dir: str) -> Dict:
        """
        为分段旁白生成语音，带分段进度显示
        :param narration_data: 旁白生成器输出的JSON数据
        :param output_dir: 输出目录
        :return: 包含每个分段音频信息的字典
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 拼接完整旁白
        full_narration = narration_data.get("opening", "") + "\n"
        for seg in narration_data["segments"]:
            full_narration += seg.get("narration_text", seg.get("narration", "")) + "\n"
        full_narration += narration_data.get("closing", "")

        result = {
            "slide_id": narration_data["slide_id"],
            "title": narration_data["title"],
            "full_narration": full_narration.strip(),
            "total_duration": 0,
            "segments": []
        }

        total_duration = 0
        all_audio_paths = []

        # 计算总分段数（用于进度显示）
        total_segments = len(narration_data["segments"])
        if narration_data.get("opening", "").strip():
            total_segments += 1
        if narration_data.get("closing", "").strip():
            total_segments += 1
        current_step = 0

        # 1. 处理开场白opening
        opening_text = narration_data.get("opening", "").strip()
        if opening_text:
            current_step += 1
            audio_filename = "segment_000_opening.wav"
            audio_path = output_dir / audio_filename
            duration = self.generate_audio(
                text=opening_text,
                output_path=str(audio_path)
            )
            print_step_progress(current_step, total_segments, audio_filename, duration)
            segment_info = {
                "order": 0,
                "element_name": "opening",
                "element_type": "narration",
                "narration_text": opening_text,
                "audio_path": str(audio_path),
                "duration": duration,
                "start_time": total_duration
            }
            result["segments"].append(segment_info)
            all_audio_paths.append(str(audio_path))
            total_duration += duration

        # 2. 处理中间分段内容
        for i, segment in enumerate(narration_data["segments"]):
            narration_text = segment.get("narration_text", segment.get("narration", "")).strip()
            if not narration_text:
                continue
            current_step += 1
            segment_order = i + 1
            audio_filename = f"segment_{segment_order:03d}_{segment.get('element_id', f'elem{i}')}.wav"
            audio_path = output_dir / audio_filename

            duration = self.generate_audio(
                text=narration_text,
                output_path=str(audio_path)
            )
            print_step_progress(current_step, total_segments, audio_filename, duration)

            segment_info = {
                **segment,
                "audio_path": str(audio_path),
                "duration": duration,
                "start_time": total_duration
            }

            result["segments"].append(segment_info)
            all_audio_paths.append(str(audio_path))
            total_duration += duration

        # 3. 处理结束语closing
        closing_text = narration_data.get("closing", "").strip()
        if closing_text:
            current_step += 1
            audio_filename = f"segment_{len(result['segments']):03d}_closing.wav"
            audio_path = output_dir / audio_filename
            duration = self.generate_audio(
                text=closing_text,
                output_path=str(audio_path)
            )
            print_step_progress(current_step, total_segments, audio_filename, duration)
            segment_info = {
                "order": len(result["segments"]),
                "element_name": "closing",
                "element_type": "narration",
                "narration_text": closing_text,
                "audio_path": str(audio_path),
                "duration": duration,
                "start_time": total_duration
            }
            result["segments"].append(segment_info)
            all_audio_paths.append(str(audio_path))
            total_duration += duration

        result["total_duration"] = total_duration

        # 拼接所有音频为完整的旁白文件
        full_audio_path = output_dir / "full_narration.wav"
        if all_audio_paths:
            try:
                concat_config_path = output_dir / "concat.txt"
                with open(concat_config_path, "w", encoding="utf-8") as f:
                    for audio_path in all_audio_paths:
                        abs_path = os.path.abspath(audio_path)
                        f.write(f"file '{abs_path}'\n")

                cmd = [
                    "ffmpeg",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_config_path),
                    "-c", "copy",
                    "-y",
                    str(full_audio_path)
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                os.remove(concat_config_path)

                result["full_audio_path"] = str(full_audio_path)
                print(f"   ✅ 完整旁白音频拼接完成，时长：{total_duration:.2f}秒")

            except Exception as e:
                print(f"   ⚠️ 音频拼接失败：{str(e)}，跳过拼接")
                result["full_audio_path"] = None
        else:
            result["full_audio_path"] = None

        # 保存完整音频信息
        info_path = output_dir / "audio_info.json"
        with open(info_path, "w", encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result
