#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多模态检测验证脚本
1. 生成一张"模拟诈骗截图"（假通缉令 / 假客服界面文字）
2. 调用 ImageFraudDetector 进行 OCR + 诈骗特征检测
3. 输出检测结果

用法:
    python tools/demo_multimodal.py
"""
import io
import os
import sys
import json

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

SAMPLE = os.path.join(BASE_DIR, "tools", "sample_fraud_screenshot.png")

# 模拟诈骗截图文字（含多个已知诈骗特征）
SAMPLE_TEXT = [
    "中华人民共和国最高人民检察院",
    "通 缉 令",
    "案件编号：2024A0089",
    "涉嫌洗钱、非法入境",
    "请将资金转入安全账户接受核查",
    "此案涉密，不得告知任何人，否则追责",
    "联系人：王警官  电话：96110-8888",
]


def make_sample():
    """生成一张模拟诈骗截图"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (720, 520), (255, 255, 255))
    d = ImageDraw.Draw(img)

    font_path = "C:/Windows/Fonts/msyh.ttc"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/simhei.ttf"
    try:
        f_title = ImageFont.truetype(font_path, 30)
        f_body = ImageFont.truetype(font_path, 22)
    except Exception:
        f_title = ImageFont.load_default()
        f_body = ImageFont.load_default()

    y = 30
    for i, line in enumerate(SAMPLE_TEXT):
        d.text((30, y), line, fill=(0, 0, 0), font=f_title if i == 1 else f_body)
        y += 58 if i == 1 else 42

    img.save(SAMPLE)
    print(f"[OK] 已生成模拟诈骗截图: {SAMPLE}")
    return SAMPLE


def main():
    path = make_sample()

    print("\n=== 加载检测引擎 ===")
    from engine.multimodal_detector import get_image_detector
    det = get_image_detector()
    ok = det.load()
    print(f"OCR 引擎就绪: {ok}")

    if not ok:
        print("\n[降级] OCR 引擎不可用。请安装 easyocr 或 pytesseract。")
        print("系统将走「文本多维度分析」路径：/api/analyze/text")
        return

    print("\n=== 检测结果 ===")
    res = det.analyze(path)
    print(json.dumps(res, ensure_ascii=False, indent=2))

    print("\n=== 结论 ===")
    if res.get("has_fraud_indicators"):
        print(f"✅ 成功检测到 {len(res.get('detections', []))} 个诈骗特征，"
              f"风险等级：{res.get('risk_level')}")
    else:
        print("未检测到诈骗特征（可能 OCR 未正确识别中文）")


if __name__ == "__main__":
    main()
