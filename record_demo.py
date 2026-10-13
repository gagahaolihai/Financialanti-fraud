"""
反诈系统演示视频录制脚本 V2
使用 Playwright 录制交互式聊天演示，输出高质量 MP4 视频
"""
import os
import sys
import time
import subprocess
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(os.path.abspath(__file__)).parent
DEMO_HTML = BASE_DIR / "demo_chat.html"
OUTPUT_DIR = BASE_DIR
MP4_PATH = OUTPUT_DIR / "反诈卫士系统演示视频.mp4"

# ffmpeg路径
TMP_DIR = Path(os.environ.get("TMP", "/tmp"))
FULL_FFMPEG = TMP_DIR / "ffmpeg_full" / "ffmpeg-8.1.1-essentials_build" / "bin" / "ffmpeg.exe"
PLAYWRIGHT_FFMPEG = Path(r"C:\Users\39214\AppData\Local\ms-playwright\ffmpeg-1011\ffmpeg-win64.exe")
FFMPEG_BIN = str(FULL_FFMPEG if FULL_FFMPEG.exists() else PLAYWRIGHT_FFMPEG)

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
DEMO_TIMEOUT = 150  # 最长等待秒数（18场景）


async def record_demo():
    print("=" * 60)
    print("反诈卫士 演示视频录制 V2")
    print(f"  分辨率: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
    print(f"  演示页面: {DEMO_HTML}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT},
            record_video_dir=str(OUTPUT_DIR),
            record_video_size={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT},
        )
        page = await context.new_page()

        demo_url = DEMO_HTML.as_uri()
        print(f"\n正在加载演示页面...")
        await page.goto(demo_url, wait_until="networkidle")

        # 等待演示脚本执行完毕（页面会设置 window.__demoDone = true）
        print("演示进行中，等待自动播放完成...")
        start_time = time.time()
        last_log = 0
        while True:
            elapsed = time.time() - start_time
            done = await page.evaluate("window.__demoDone || false")
            if done:
                print(f"  [{elapsed:.0f}s] 演示脚本执行完毕")
                break
            if elapsed > DEMO_TIMEOUT:
                print(f"  [{elapsed:.0f}s] 超时，结束录制")
                break
            if elapsed - last_log >= 5:
                msg_count = await page.evaluate("document.querySelectorAll('.msg-row').length || 0")
                print(f"  [{elapsed:.0f}s] 已显示 {msg_count} 条消息...")
                last_log = elapsed
            await asyncio.sleep(0.5)

        # 多停留2秒让最后的消息完全渲染
        await asyncio.sleep(2)

        await context.close()
        await browser.close()

    print(f"\n[OK] 原始视频已录制完成")


def find_recorded_video():
    """查找 Playwright 录制的 webm 文件"""
    candidates = sorted(OUTPUT_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in candidates:
        if f.stat().st_size > 5000:
            return f
    return None


def convert_to_mp4(input_path, output_path):
    """使用 ffmpeg 将 webm 转为高质量 mp4"""
    print(f"\n正在转换为MP4（高质量编码）...")
    print(f"  输入: {input_path.name} ({input_path.stat().st_size / 1024:.0f} KB)")

    cmd = [
        FFMPEG_BIN,
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "128k",
        "-y",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode == 0:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"[OK] MP4视频已生成")
            print(f"     大小: {size_mb:.1f} MB")
            return True
        else:
            print(f"[ERROR] ffmpeg转换失败:")
            print(result.stderr[-600:])
            return False
    except subprocess.TimeoutExpired:
        print("[ERROR] ffmpeg转换超时")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def verify_video(path):
    """校验输出视频"""
    if not path.exists():
        return False
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"[VIDEO] {path.name}")
    print(f"   Size: {size_mb:.1f} MB")

    # 用 ffmpeg 获取详细信息
    try:
        r = subprocess.run([FFMPEG_BIN, "-i", str(path)], capture_output=True, text=True)
        stderr = r.stderr
        for line in stderr.split('\n'):
            if 'Duration' in line:
                print(f"   {line.strip()}")
            if 'Video:' in line and 'Stream' in line:
                print(f"   {line.strip()}")
    except Exception:
        pass

    checks = [
        ("格式: MP4", path.suffix.lower() == '.mp4'),
        ("大小: ≤100 MB", size_mb <= 100),
    ]
    for label, ok in checks:
        print(f"   {'[OK]' if ok else '[FAIL]'} {label}")
    print(f"{'='*60}")
    return True


def main():
    # 1. 录制视频
    asyncio.run(record_demo())

    # 2. 查找录制的webm
    webm_file = find_recorded_video()
    if not webm_file:
        print("[ERROR] 未找到录制的视频文件")
        return 1

    # 3. 删除旧MP4
    if MP4_PATH.exists():
        MP4_PATH.unlink()

    # 4. 转换为MP4
    success = convert_to_mp4(webm_file, MP4_PATH)

    # 5. 清理临时webm
    if success and webm_file.exists():
        try:
            webm_file.unlink()
        except Exception:
            pass

    # 6. 验证
    if success:
        verify_video(MP4_PATH)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
