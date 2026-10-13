"""
录制真实反诈卫士 Flask 项目运行演示视频
完整展示：聊天对话、反诈知识库(深入)、情景模拟(深入)、举报中心、排行榜、历史对话、隐私保护
"""
import os, sys, time, subprocess, asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(os.path.abspath(__file__)).parent
MP4_PATH = BASE_DIR / "反诈卫士系统演示视频.mp4"
APP_URL = "http://localhost:5000"
TMP_DIR = Path(os.environ.get("TMP", "/tmp"))
FFMPEG_BIN = str(TMP_DIR / "ffmpeg_full" / "ffmpeg-8.1.1-essentials_build" / "bin" / "ffmpeg.exe")


async def close_all_modals(page):
    """使用JS强制关闭所有模态框"""
    await page.evaluate("""() => {
        document.querySelectorAll('.modal-overlay').forEach(m => {
            m.classList.remove('active');
        });
    }""")


async def wait_modal(page, modal_id, timeout=8):
    """等待指定模态框激活"""
    try:
        await page.wait_for_selector(f'#{modal_id}.active', timeout=timeout * 1000)
    except:
        pass


async def click_nav(page, action):
    """点击侧边栏按钮"""
    btn = page.locator(f'.nav-item[data-action="{action}"]')
    if await btn.count() > 0:
        await btn.first.click()
        await asyncio.sleep(0.6)


async def send_message(page, text, wait_response=True):
    """发送聊天消息并等待回复"""
    await page.fill('#user-input', '')
    await asyncio.sleep(0.2)
    await page.type('#user-input', text, delay=25)
    await asyncio.sleep(0.3)
    await page.click('#send-btn')
    if wait_response:
        await asyncio.sleep(2.5)


async def record():
    print("=" * 60)
    print("反诈卫士 完整功能演示录制 (增强版)")
    print(f"  应用: {APP_URL}  |  分辨率: 1280x720")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(BASE_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        await page.goto(APP_URL, wait_until="networkidle")
        await asyncio.sleep(2.5)

        # ============================================================
        # PART 1: 聊天对话核心功能 (约70秒)
        # ============================================================

        print("[1] 系统首页 - 反诈卫士欢迎界面")
        await asyncio.sleep(2)

        print("[2] 诈骗类型知识查询")
        await send_message(page, "常见的电信诈骗类型有哪些？")
        await asyncio.sleep(3)

        print("[3] 刷单诈骗风险识别")
        await send_message(page, "有个人加我微信说刷单做任务返利，一单返30，靠谱吗？")
        await asyncio.sleep(3.5)

        print("[4] 杀猪盘自检诊断")
        await send_message(page, "网上认识的朋友推荐我投资虚拟币，投了2000赚了500，现在让我再加5万，我是不是被骗了？")
        await asyncio.sleep(3.5)

        print("[5] 老年人模式 + 大白话劝阻")
        await send_message(page, "我今年70了不太懂这些，刚才有人打电话说是派出所的让我去银行转钱")
        await asyncio.sleep(4)

        print("[6] 紧急场景 - 冒充公检法转账后劝阻")
        await send_message(page, "不好了！接到自称警察的电话说我涉嫌洗钱，我已经转了5000块到安全账户了...")
        await asyncio.sleep(4)

        print("[7] URL钓鱼链接分析")
        await send_message(page, "帮我分析一下这个链接 http://xn--tiq75w2w.com/login")
        await asyncio.sleep(3.5)

        print("[8] 隐私保护PII检测")
        await send_message(page, "我叫张三，身份证320102199003071234，手机13812345678，帮我查下有没有被诈骗")
        await asyncio.sleep(4)

        print("[9] 法律咨询")
        await send_message(page, "诈骗罪的量刑标准是什么？被骗的钱能追回来吗？")
        await asyncio.sleep(4)

        print("[10] 知识图谱关联查询")
        await send_message(page, "刷单诈骗和杀猪盘之间有什么关联？")
        await asyncio.sleep(3.5)

        print("[11] 感谢回应 + 防骗提醒")
        await send_message(page, "谢谢你的帮助！我会提醒家人注意的")
        await asyncio.sleep(3)

        # ============================================================
        # PART 2: 反诈知识库 - 深入演示 (约30秒)
        # ============================================================

        print("[12] 反诈知识库 - 浏览诈骗类型列表")
        await click_nav(page, "knowledge")
        await wait_modal(page, "knowledge-modal")
        await asyncio.sleep(3)

        # 点击第一个诈骗类型：刷单返利
        print("[12a] 知识库 - 查询「刷单返利诈骗」详情")
        kb_btn = page.locator('#kb-list .choice-btn').first
        if await kb_btn.count() > 0:
            await kb_btn.click()
            await asyncio.sleep(3.5)  # 等待聊天回复

        # 重新打开知识库，查询第二个类型
        await click_nav(page, "knowledge")
        await wait_modal(page, "knowledge-modal")
        await asyncio.sleep(2)

        print("[12b] 知识库 - 查询「冒充公检法诈骗」详情")
        kb_btns = page.locator('#kb-list .choice-btn')
        if await kb_btns.count() >= 3:
            await kb_btns.nth(2).click()  # 第三个按钮：冒充公检法
            await asyncio.sleep(3.5)

        # 再打开一次，查询第三个类型
        await click_nav(page, "knowledge")
        await wait_modal(page, "knowledge-modal")
        await asyncio.sleep(2)

        print("[12c] 知识库 - 查询「虚假投资诈骗」详情")
        kb_btns = page.locator('#kb-list .choice-btn')
        if await kb_btns.count() >= 4:
            await kb_btns.nth(3).click()  # 第四个按钮：虚假投资
            await asyncio.sleep(3.5)

        await asyncio.sleep(0.5)

        # ============================================================
        # PART 3: 情景模拟训练 - 完整多步演示 (约50秒)
        # ============================================================

        print("[13] 情景模拟 - 打开情景列表")
        await click_nav(page, "scenario")
        await wait_modal(page, "scenario-modal")
        await asyncio.sleep(3)

        # 点击第一个情景：「刷单陷阱」
        print("[13a] 情景模拟 - 开始「刷单陷阱」")
        first_card = page.locator('#scenario-list .scenario-card').first
        if await first_card.count() > 0:
            await first_card.click()
            await asyncio.sleep(2.5)

        # Step 1: 做出选择（选最安全的那个）
        print("[13b] 情景模拟 - Step 1 做出选择")
        choices = page.locator('#scenario-scene .choice-btn')
        if await choices.count() >= 3:
            await choices.nth(2).click()  # "我不做违法的事，刷单本身就不对"
            await asyncio.sleep(2.5)

        # 点击「下一步」进入 Step 2
        print("[13c] 情景模拟 - 进入 Step 2")
        next_btn = page.locator('#scene-next button')
        if await next_btn.count() > 0:
            await next_btn.click()
            await asyncio.sleep(2.5)

        # Step 2: 做出选择
        print("[13d] 情景模拟 - Step 2 做出选择")
        choices = page.locator('#scenario-scene .choice-btn')
        if await choices.count() >= 3:
            await choices.nth(2).click()  # "越赚越多？这不对劲，我要收手了"
            await asyncio.sleep(2.5)

        # 点击「下一步」进入 Step 3
        next_btn = page.locator('#scene-next button')
        if await next_btn.count() > 0:
            await next_btn.click()
            await asyncio.sleep(2.5)

        # Step 3: 做出选择
        print("[13e] 情景模拟 - Step 3 做出选择")
        choices = page.locator('#scenario-scene .choice-btn')
        if await choices.count() >= 3:
            await choices.nth(2).click()  # "这是诈骗！立即报警并举报该账号"
            await asyncio.sleep(3)

        # 查看完成结果
        print("[13f] 情景模拟 - 查看评估结果")
        await asyncio.sleep(4)

        # 关闭情景
        done_btn = page.locator('#scene-next button')
        if await done_btn.count() > 0:
            await done_btn.click()
            await asyncio.sleep(0.5)

        await close_all_modals(page)
        await asyncio.sleep(0.5)

        # ============================================================
        # PART 4: 举报中心 (约15秒)
        # ============================================================

        print("[14] 举报中心 - 填写举报")
        await click_nav(page, "report")
        await wait_modal(page, "report-modal")
        await asyncio.sleep(1.5)
        try:
            url_inp = page.locator('#report-url')
            await url_inp.wait_for(state='visible', timeout=5000)
            await url_inp.fill('http://fake-bank-login.com/verify')
            await asyncio.sleep(0.3)
            await page.locator('#report-desc').fill('冒充中国银行的钓鱼网站，诱导输入密码')
            await asyncio.sleep(0.3)
            await page.locator('#report-btn').click()
            await asyncio.sleep(2.5)
        except Exception as e:
            print(f"  [warn] 举报表单: {e}")
        await close_all_modals(page)
        await asyncio.sleep(0.5)

        # ============================================================
        # PART 5: 排行榜 (约8秒)
        # ============================================================

        print("[15] 排行榜")
        await click_nav(page, "leaderboard")
        await wait_modal(page, "leaderboard-modal")
        await asyncio.sleep(3.5)
        await close_all_modals(page)
        await asyncio.sleep(0.5)

        # ============================================================
        # PART 6: 历史对话 + 隐私保护 (约15秒)
        # ============================================================

        print("[16] 历史对话")
        await click_nav(page, "history")
        await wait_modal(page, "history-modal")
        await asyncio.sleep(3.5)
        await close_all_modals(page)
        await asyncio.sleep(0.5)

        print("[17] 隐私保护状态")
        await click_nav(page, "privacy")
        await asyncio.sleep(3)
        await close_all_modals(page)
        await asyncio.sleep(0.5)

        # ============================================================
        # PART 7: 结束总结 (约10秒)
        # ============================================================
        await click_nav(page, "help")
        await asyncio.sleep(0.5)
        await send_message(page, "总结一下反诈卫士都有哪些功能")
        await asyncio.sleep(5)

        print("\n录制完成，保存视频...")
        await asyncio.sleep(1)
        await context.close()
        await browser.close()

    print("[OK] 原始视频已录制")


def convert_mp4(webm, mp4):
    print(f"转换MP4 (CRF 18, preset slow)...")
    cmd = [FFMPEG_BIN, "-i", str(webm), "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k",
           "-y", str(mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode == 0:
        print(f"[OK] {mp4.name} ({mp4.stat().st_size/1024/1024:.1f} MB)")
        return True
    print(f"[ERROR] {r.stderr[-400:]}")
    return False


def main():
    asyncio.run(record())

    webms = sorted(BASE_DIR.glob("*.webm"), key=lambda f: f.stat().st_mtime, reverse=True)
    webm = webms[0] if webms else None
    if not webm:
        print("[ERROR] 未找到录制文件"); return 1

    # 输出到新文件名（避免旧文件被锁）
    out_mp4 = BASE_DIR / "反诈卫士系统演示视频_v2.mp4"
    if out_mp4.exists():
        try:
            out_mp4.unlink()
        except:
            pass

    if convert_mp4(webm, out_mp4):
        webm.unlink()
        r = subprocess.run([FFMPEG_BIN, "-i", str(out_mp4)], capture_output=True, text=True)
        for line in r.stderr.split('\n'):
            if 'Duration' in line or ('Video:' in line and 'Stream' in line):
                print(f"  {line.strip()}")
        print(f"  最终文件: {out_mp4}")
        print(f"  大小: {out_mp4.stat().st_size/1024/1024:.1f} MB")
        # 尝试覆盖旧文件
        try:
            old = BASE_DIR / "反诈卫士系统演示视频.mp4"
            if old.exists():
                old.unlink()
            import shutil
            shutil.move(str(out_mp4), str(old))
            print(f"  已覆盖: {old}")
        except Exception as e:
            print(f"  [info] 旧文件被锁定，新视频保存为 {out_mp4.name}: {e}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
