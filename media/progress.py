"""
通用进度显示工具
支持 spinner 动画和分段进度打印，自动检测并发环境
"""

import sys
import time
import threading


class Spinner:
    """API 调用时的实时进度指示器，自动检测并发环境"""
    FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    # 全局并发计数器：>1 时说明有多个长任务同时进行，应禁用动画
    _active_count = 0
    _lock = threading.Lock()

    def __init__(self, message: str = "处理中"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None
        self._start_time = 0
        self._interactive = False

    def start(self):
        self._start_time = time.time()
        with Spinner._lock:
            Spinner._active_count += 1
            self._interactive = (Spinner._active_count == 1)

        if self._interactive:
            self._stop.clear()
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            print(f"   ⏳ {self.message}...")
        return self

    def _spin(self):
        idx = 0
        while not self._stop.is_set():
            elapsed = time.time() - self._start_time
            frame = self.FRAMES[idx % len(self.FRAMES)]
            sys.stdout.write(f"\r   {frame} {self.message}... {elapsed:.0f}s")
            sys.stdout.flush()
            idx += 1
            self._stop.wait(0.15)

    def stop(self, final_message: str = None):
        elapsed = time.time() - self._start_time
        with Spinner._lock:
            Spinner._active_count -= 1

        if self._interactive:
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=1)
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            sys.stdout.flush()

        if final_message:
            print(f"   {final_message} ({elapsed:.1f}s)")

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


def print_step_progress(current: int, total: int, filename: str, duration: float):
    """打印分段进度，如 [2/7] segment_001_title.wav (8.6s)"""
    print(f"   [{current}/{total}] {filename} ({duration:.1f}s)")
