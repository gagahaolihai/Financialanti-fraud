"""将配音逐段精准对齐到视频时间轴"""
import subprocess, os, json

BASE = r"F:\anti-fraud-system"
VOICE = os.path.join(BASE, "voice")
FFMPEG = r"C:\Users\39214\AppData\Local\Temp\ffmpeg_full\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"

INPUT_VIDEO = os.path.join(BASE, "反诈卫士系统演示视频.mp4")
OUTPUT_VIDEO = os.path.join(BASE, "反诈卫士系统演示视频_配音版.mp4")

def get_duration(path):
    """用ffmpeg获取时长"""
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    for line in r.stderr.split('\n'):
        if 'Duration' in line:
            # Duration: 00:02:36.40
            parts = line.strip().split()[1].rstrip(',')
            h, m, s = parts.split(':')
            return float(h) * 3600 + float(m) * 60 + float(s)
    return 0.0

video_dur = get_duration(INPUT_VIDEO)
print(f"视频时长: {video_dur:.2f}s")

# 各场景在视频中的时间轴 (基于录制脚本的sleep时间线推算)
# 格式: (文件名, 起始秒, 可用窗口秒数)
timeline = [
    # Part 1: 聊天对话 (~0:00 - ~1:13)
    ("开场.mp3",       0.0,   7.0),   # [1] 首页等待
    ("场景一.mp3",     7.0,   9.0),   # [2] 诈骗类型查询
    ("场景二三.mp3",  16.0,  17.0),   # [3]刷单 + [4]杀猪盘
    ("场景四五.mp3",  33.0,  17.0),   # [5]老年人 + [6]紧急
    ("场景六到九.mp3", 50.0,  23.0),  # [7]URL + [8]PII + [9]法律 + [10]图谱 + [11]感谢

    # Part 2: 反诈知识库 (~1:13 - ~1:43)
    ("反诈知识库.mp3", 73.0,  30.0),  # [12]知识库浏览 + 3次查询

    # Part 3: 情景模拟 (~1:43 - ~2:06)
    ("情景模拟.mp3",  103.0,  23.0),  # [13]情景列表 + 3步通关 + 结果

    # Part 4: 举报中心+排行榜 (~2:06 - ~2:18)
    ("举报中心.mp3",  126.0,  12.0),  # [14]举报 + [15]排行榜

    # Part 5: 历史对话+隐私 (~2:18 - ~2:31)
    ("历史对话.mp3",  138.0,  13.0),  # [16]历史 + [17]隐私

    # Part 6: 结尾 (~2:31 - ~2:36)
    ("结尾.mp3",      151.0,   5.4),  # 总结 + 结束
]

print("\n各段音频分析:")
print(f"{'文件':<20s} {'起始':>6s} {'窗口':>6s} {'原时长':>8s} {'处理方式':>20s} {'结果':>8s}")
print("-" * 80)

filter_chains = []  # 每个音频的 filter chain
all_inputs = ["-i", INPUT_VIDEO]

for i, (fname, start, window) in enumerate(timeline):
    fpath = os.path.join(VOICE, fname)
    orig_dur = get_duration(fpath)
    all_inputs.extend(["-i", fpath])

    # 决定处理策略
    ratio = orig_dur / window if window > 0 else 1.0

    if ratio < 0.85:
        # 音频太短，放慢到0.85倍(极限) + 后面自然间隔
        atempo_val = max(ratio, 0.85)
        atrim_end = orig_dur
        method = f"atempo={atempo_val:.2f}(放慢)"
    elif ratio <= 1.20:
        # 适配套，仅微调速度
        atempo_val = ratio
        atrim_end = orig_dur
        method = f"atempo={atempo_val:.2f}(微调)"
    else:
        # 音频太长：先裁切末尾，再加速(最大1.2x)
        atempo_val = 1.20
        # 计算需要保留的原始音频长度
        keep_dur = window * atempo_val  # 加速1.2x后=window的实际素材长度
        atrim_end = min(orig_dur, keep_dur)
        method = f"atrim=0:{atrim_end:.1f}+atempo=1.20"

    result_dur = atrim_end / atempo_val
    print(f"{fname:<20s} {start:>5.1f}s {window:>5.1f}s {orig_dur:>7.2f}s {method:<20s} {result_dur:>7.2f}s")

    # 构建每个音频的 filter chain
    filters = []
    # 裁切
    if atrim_end < orig_dur - 0.05:
        filters.append(f"atrim=0:{atrim_end:.2f}")
    # 调速
    if abs(atempo_val - 1.0) > 0.01:
        filters.append(f"atempo={atempo_val:.2f}")
    # 延时定位
    delay_ms = int(start * 1000)
    filters.append(f"adelay={delay_ms}|{delay_ms}")

    chain = ",".join(filters)
    filter_chains.append(f"[{i+1}:a]{chain}[a{i}]")

# 混音所有轨道
mix_inputs = "".join(f"[a{i}]" for i in range(len(timeline)))
mix_filter = f"{mix_inputs}amix=inputs={len(timeline)}:duration=longest:dropout_transition=0[audio]"

# 最终：静音填充到视频末尾
final_audio = "[audio]apad=whole_dur=" + f"{video_dur:.3f}" + "[outa]"

filter_complex = ";".join(filter_chains) + ";" + mix_filter + ";" + final_audio

cmd = [FFMPEG,
    *all_inputs,
    "-filter_complex", filter_complex,
    "-map", "0:v",
    "-map", "[outa]",
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    "-y", OUTPUT_VIDEO
]

print(f"\n合成中... (共{len(timeline)}段音频, 精确延时定位)")
r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

if r.returncode == 0:
    r2 = subprocess.run([FFMPEG, "-i", OUTPUT_VIDEO], capture_output=True, text=True)
    for line in r2.stderr.split('\n'):
        if 'Duration' in line or 'Audio:' in line or 'Video:' in line:
            print(f"  {line.strip()}")
    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print(f"\n[OK] 配音版视频: {OUTPUT_VIDEO}")
    print(f"[OK] 大小: {size_mb:.1f} MB")
    print(f"[OK] 10段配音已按时间轴精准定位")
else:
    print(f"[ERROR]:")
    # 找最后10行有用的错误信息
    lines = [l for l in r.stderr.split('\n') if l.strip()]
    for l in lines[-15:]:
        print(f"  {l}")
