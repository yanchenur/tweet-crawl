#!/usr/bin/env python3
"""
推文PDF生成器 GitHub Actions 专用版
使用Ubuntu系统预装中文字体，无需网络下载，彻底解决链接失效问题
固定输出：pdf_output/推文合集.pdf，每次覆盖旧文件
"""

import os
import sys
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    PageBreak, Flowable, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ===================== 路径配置 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TWEET_DATA_DIR = os.path.join(BASE_DIR, "tweet_data")
REPORTS_DIR = os.path.join(BASE_DIR, "pdf_output")
os.makedirs(REPORTS_DIR, exist_ok=True)

# 输出文件（固定，覆盖旧文件）
DEFAULT_OUTPUT = os.path.join(REPORTS_DIR, "推文合集.pdf")

# ===================== 注册Ubuntu系统内置中文字体（文泉驿微米黑） =====================
# GitHub Actions Ubuntu 固定字体路径，无需下载
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
FONT_NAME = "WQYMicrohei"
use_font = "Helvetica"

def init_system_font():
    """加载系统预装中文字体"""
    global use_font
    if os.path.exists(FONT_PATH):
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
            use_font = FONT_NAME
            print(f"✅ 成功加载系统中文字体: {FONT_PATH}")
            return True
        except Exception as e:
            print(f"⚠️ 字体注册失败: {e}")
    print("⚠️ 未找到系统中文字体，将使用默认英文字体")
    return False

# 初始化字体
init_system_font()

# ===================== 配色方案 =====================
COLOR_PRIMARY = HexColor("#1a1a2e")
COLOR_ACCENT = HexColor("#e94560")
COLOR_TEXT = HexColor("#2d3436")
COLOR_TEXT_LIGHT = HexColor("#636e72")
COLOR_LINK = HexColor("#0984e3")
COLOR_BORDER = HexColor("#dfe6e9")
COLOR_CARD_BG = HexColor("#ffffff")
COLOR_GOLD = HexColor("#d4a843")

PAGE_W, PAGE_H = A4

# ===================== 工具函数 =====================
def parse_engagement_line(line):
    result = {"comments": 0, "retweets": 0, "likes": 0, "views": ""}
    for field, key in [("评论", "comments"), ("转发", "retweets"), ("点赞", "likes"), ("浏览", "views")]:
        pattern = field + r"[：:]\s*([0-9,]*)"
        m = re.search(pattern, line)
        if m:
            val = m.group(1).strip()
            if key == "views":
                result[key] = val
            else:
                try:
                    result[key] = int(val.replace(",", ""))
                except ValueError:
                    pass
    return result


def convert_relative_date(date_str, dir_name=""):
    m = re.match(r"^(\d+)([hdm])$", date_str.strip())
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        base_date = None
        if dir_name:
            parts = dir_name.split("_")
            if len(parts) >= 1:
                try:
                    from datetime import timedelta
                    base_date = datetime.strptime(parts[0], "%Y-%m-%d")
                except ValueError:
                    pass
        if base_date:
            if unit == "h":
                ref = base_date - timedelta(hours=num)
            elif unit == "m":
                ref = base_date - timedelta(minutes=num)
            elif unit == "d":
                ref = base_date - timedelta(days=num)
            else:
                ref = base_date
            return ref.strftime("%b %d")
    return date_str


def parse_tweet_text(txt_path, dir_name=""):
    if not os.path.exists(txt_path):
        return None
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(txt_path, "r", encoding="gbk") as f:
                content = f.read()
        except Exception:
            return None

    data = {
        "date": "",
        "text": "",
        "quote": "",
        "comments": 0,
        "retweets": 0,
        "likes": 0,
        "views": "",
    }

    lines = content.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("发布时间：") or line.startswith("发布时间:"):
            raw_date = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            data["date"] = convert_relative_date(raw_date, dir_name)
        elif line.startswith("正文：") or line.startswith("正文:"):
            data["text"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
        elif line.startswith("引用：") or line.startswith("引用:"):
            quote_text = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            if quote_text:
                data["quote"] = quote_text
        elif "评论" in line and ("转发" in line or "点赞" in line or "浏览" in line):
            eng = parse_engagement_line(line)
            data["comments"] = eng["comments"]
            data["retweets"] = eng["retweets"]
            data["likes"] = eng["likes"]
            data["views"] = eng["views"]
        elif line.startswith("评论：") or line.startswith("评论:"):
            val = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            try:
                data["comments"] = int(val.replace(",", ""))
            except ValueError:
                pass
        elif line.startswith("转发：") or line.startswith("转发:"):
            val = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            try:
                data["retweets"] = int(val.replace(",", ""))
            except ValueError:
                pass
        elif line.startswith("点赞：") or line.startswith("点赞:"):
            val = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            try:
                data["likes"] = int(val.replace(",", ""))
            except ValueError:
                pass
        elif line.startswith("浏览：") or line.startswith("浏览:"):
            data["views"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
    return data


def scan_tweet_dirs():
    if not os.path.exists(TWEET_DATA_DIR):
        return []
    dirs = sorted([
        d for d in os.listdir(TWEET_DATA_DIR)
        if os.path.isdir(os.path.join(TWEET_DATA_DIR, d)) and not d.startswith("_")
    ])
    seen = {}
    for d in dirs:
        parts = d.split("_")
        if len(parts) >= 2:
            tweet_id = parts[1]
            date_str = parts[0]
        else:
            tweet_id = d
            date_str = ""
        if tweet_id in seen:
            if date_str > seen[tweet_id]["dir_name"].split("_")[0]:
                seen[tweet_id] = {"dir_name": d, "date": date_str, "id": tweet_id}
        else:
            seen[tweet_id] = {"dir_name": d, "date": date_str, "id": tweet_id}
    tweets = []
    for tweet_id, info in sorted(seen.items(), key=lambda x: x[1]["date"], reverse=True):
        dir_path = os.path.join(TWEET_DATA_DIR, info["dir_name"])
        txt_path = os.path.join(dir_path, "推文内容.txt")
        images = sorted([
            os.path.join(dir_path, f)
            for f in os.listdir(dir_path)
            if f.endswith((".jpg", ".jpeg", ".png", ".gif")) and f.startswith("图片_")
        ])
        tweet_data = parse_tweet_text(txt_path, dir_name=info["dir_name"])
        if tweet_data:
            tweet_data["id"] = tweet_id
            tweet_data["dir_name"] = info["dir_name"]
            tweet_data["images"] = images
            tweet_data["dir_path"] = dir_path
            tweets.append(tweet_data)
    return tweets


def format_number(n):
    if isinstance(n, int):
        return "{:,}".format(n)
    return str(n)

# ===================== 自定义组件 =====================
class ColorBar(Flowable):
    def __init__(self, width, height, color=COLOR_ACCENT):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.color
    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)

# ===================== PDF 页面构建 =====================
def build_cover_page(story, tweets):
    story.append(Spacer(1, 60 * mm))
    story.append(ColorBar(PAGE_W - 80 * mm, 2 * mm, COLOR_ACCENT))
    story.append(Spacer(1, 8 * mm))

    title_style = ParagraphStyle(
        "CoverTitle", fontName=use_font, fontSize=32,
        textColor=COLOR_PRIMARY, leading=42, alignment=TA_LEFT
    )
    story.append(Paragraph("Tweet Collection", title_style))
    story.append(Spacer(1, 4 * mm))

    sub_style = ParagraphStyle(
        "CoverSub", fontName=use_font, fontSize=14,
        textColor=COLOR_TEXT_LIGHT, leading=22, alignment=TA_LEFT
    )
    story.append(Paragraph("推文数据合集", sub_style))
    story.append(Spacer(1, 12 * mm))
    story.append(ColorBar(40 * mm, 1 * mm, COLOR_GOLD))
    story.append(Spacer(1, 15 * mm))

    info_style = ParagraphStyle(
        "CoverInfo", fontName=use_font, fontSize=11,
        textColor=COLOR_TEXT, leading=20, alignment=TA_LEFT
    )
    total_imgs = sum(len(t.get("images", [])) for t in tweets)
    date_range = ""
    if tweets:
        dates = [t.get("date", "") for t in tweets if t.get("date")]
        if dates:
            date_range = dates[0] + " ~ " + dates[-1]

    info_lines = [
        f"推文总数: {len(tweets)}",
        f"配图总数: {total_imgs}",
        f"时间范围: {date_range or 'N/A'}",
        f"PDF更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    for line in info_lines:
        story.append(Paragraph(line, info_style))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 20 * mm))
    src_style = ParagraphStyle(
        "CoverSrc", fontName=use_font, fontSize=9,
        textColor=COLOR_TEXT_LIGHT, leading=14, alignment=TA_LEFT
    )
    story.append(Paragraph("数据来源: 自动爬虫采集", src_style))
    story.append(Paragraph("生成工具: 推文PDF生成器", src_style))
    story.append(PageBreak())


def build_toc_page(story, tweets):
    toc_title = ParagraphStyle(
        "TOCTitle", fontName=use_font, fontSize=20,
        textColor=COLOR_PRIMARY, leading=28, spaceAfter=8 * mm
    )
    story.append(Paragraph("目录", toc_title))
    story.append(ColorBar(30 * mm, 1.5 * mm, COLOR_ACCENT))
    story.append(Spacer(1, 8 * mm))

    toc_style = ParagraphStyle(
        "TOCItem", fontName=use_font, fontSize=10,
        textColor=COLOR_TEXT, leading=18, spaceAfter=1 * mm
    )
    for i, tweet in enumerate(tweets, 1):
        date_str = tweet.get("date", "N/A")
        text_preview = tweet.get("text", "")[:60]
        if len(tweet.get("text", "")) > 60:
            text_preview += "..."
        n_imgs = len(tweet.get("images", []))
        img_tag = f" [{n_imgs}图]" if n_imgs > 0 else ""
        line = f"{str(i).rjust(2)}. {date_str} {text_preview}{img_tag}"
        story.append(Paragraph(line, toc_style))
    story.append(PageBreak())


def build_tweet_pages(story, tweets):
    text_style = ParagraphStyle(
        "TweetText", fontName=use_font, fontSize=10,
        textColor=COLOR_TEXT, leading=17, spaceAfter=2 * mm,
        alignment=TA_JUSTIFY, wordWrap="CJK"
    )
    quote_style = ParagraphStyle(
        "QuoteText", fontName=use_font, fontSize=9,
        textColor=COLOR_TEXT_LIGHT, leading=15, spaceAfter=2 * mm,
        leftIndent=8 * mm
    )
    section_title = ParagraphStyle(
        "SectionTitle", fontName=use_font, fontSize=16,
        textColor=COLOR_PRIMARY, leading=24, spaceAfter=3 * mm
    )
    img_caption = ParagraphStyle(
        "ImgCaption", fontName=use_font, fontSize=8,
        textColor=COLOR_TEXT_LIGHT, leading=12, alignment=TA_CENTER
    )

    emoji_map = {
        "\U0001f602": "[笑哭]", "\U0001f923": "[笑哭]", "\U0001f604": "[笑]",
        "\U0001f914": "[思考]", "\U0001f910": "[闭嘴]", "\U0001f60e": "[酷]",
        "\U0001f525": "[火]", "\U0001f680": "[火箭]", "\U0001f4c8": "[涨]",
        "\U0001f4c9": "[跌]", "\U0001f4b0": "[钱]", "\U0001f4a1": "[灯泡]",
        "\U0001f44d": "[赞]", "\U0001f44e": "[踩]", "\U0001f622": "[哭]",
        "\U0001f60a": "[微笑]", "\U0001f60d": "[爱心]", "\U0001f929": "[眼冒星]",
        "\U0001f631": "[惊恐]", "\U0001f92f": "[爆头]", "\U0001f643": "[倒脸]",
        "\U0001f534": "[红圈]", "\U0001f7e2": "[绿圈]", "\U0001f535": "[蓝圈]",
        "\U0001f7e1": "[黄圈]", "\u26a0\ufe0f": "[警告]", "\u2757": "[!]",
        "\u2b50": "[星]", "\u2705": "[OK]", "\u274c": "[X]",
    }

    for i, tweet in enumerate(tweets, 1):
        date_str = tweet.get("date", "")
        title_text = f"#{i}  {date_str}"
        story.append(Paragraph(title_text, section_title))
        story.append(ColorBar(40 * mm, 1.5 * mm, COLOR_ACCENT))
        story.append(Spacer(1, 3 * mm))

        raw_text = tweet.get("text", "")
        safe_text = raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for emoji, text in emoji_map.items():
            safe_text = safe_text.replace(emoji, text)
        safe_text = re.sub(r"[\U0001f000-\U0001ffff]", "", safe_text)
        safe_text = re.sub(r"#([a-zA-Z]\w*)", r'<font color="#0984e3"><b>#\1</b></font>', safe_text)
        safe_text = re.sub(r"\$([A-Z]{1,6}(?:\.[A-Z])?)", r'<font color="#e94560"><b>$\1</b></font>', safe_text)
        safe_text = safe_text.replace("\n", "<br/>")

        if safe_text.strip():
            story.append(Paragraph(safe_text, text_style))
            story.append(Spacer(1, 2 * mm))

        quote_text = tweet.get("quote", "")
        if quote_text.strip():
            safe_quote = quote_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for emoji, text in emoji_map.items():
                safe_quote = safe_quote.replace(emoji, text)
            safe_quote = re.sub(r"[\U0001f000-\U0001ffff]", "", safe_quote)
            safe_quote = safe_quote.replace("\n", "<br/>")
            story.append(Paragraph(f"[引用] {safe_quote}", quote_style))
            story.append(Spacer(1, 3 * mm))

        likes = format_number(tweet.get("likes", 0))
        rts = format_number(tweet.get("retweets", 0))
        cmts = format_number(tweet.get("comments", 0))
        views = tweet.get("views", "")
        stats_text = f"点赞: {likes} | 转发: {rts} | 评论: {cmts}"
        if views:
            stats_text += f" | 浏览: {views}"

        stats_style = ParagraphStyle(
            "Stats", fontName=use_font, fontSize=8,
            textColor=COLOR_TEXT_LIGHT, leading=12, spaceAfter=3 * mm
        )
        story.append(Paragraph(stats_text, stats_style))

        images = tweet.get("images", [])
        content_width = PAGE_W - 60 * mm
        for j, img_path in enumerate(images, 1):
            try:
                pil_img = Image(img_path)
                iw, ih = pil_img.imageWidth, pil_img.imageHeight
                max_w = content_width
                max_h = 180 * mm
                scale = min(max_w / iw, max_h / ih, 1.0)
                draw_w = iw * scale
                draw_h = ih * scale
                img = Image(img_path, width=draw_w, height=draw_h)
                story.append(img)
                if len(images) > 1:
                    story.append(Paragraph(f"图 {j}/{len(images)}", img_caption))
                story.append(Spacer(1, 2 * mm))
            except Exception as e:
                err_style = ParagraphStyle(
                    "ImgErr", fontName=use_font, fontSize=8,
                    textColor=HexColor("#e74c3c"), leading=12
                )
                story.append(Paragraph(f"[图片加载失败] {str(e)}", err_style))
                story.append(Spacer(1, 4 * mm))

        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(
            width="100%", thickness=0.5, color=COLOR_BORDER,
            spaceAfter=6 * mm, spaceBefore=2 * mm
        ))

# ===================== 页码 =====================
def add_page_number(canvas, doc):
    canvas.saveState()
    page_num = canvas.getPageNumber()
    if page_num <= 2:
        canvas.restoreState()
        return
    canvas.setStrokeColor(COLOR_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(30 * mm, 15 * mm, PAGE_W - 30 * mm, 15 * mm)
    canvas.setFont(use_font, 8)
    canvas.setFillColor(COLOR_TEXT_LIGHT)
    canvas.drawCentredString(PAGE_W / 2, 10 * mm, f"- {page_num} -")
    canvas.drawRightString(PAGE_W - 30 * mm, 10 * mm, "Tweet Collection")
    canvas.restoreState()

# ===================== 主入口 =====================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="推文PDF生成器")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help="输出PDF路径")
    parser.add_argument("--limit", "-n", type=int, default=0, help="限制处理推文数量")
    args = parser.parse_args()

    print("=" * 60)
    print("  推文PDF生成器 (GitHub Actions 版)")
    print("=" * 60)

    print("\n[1/3] 扫描本地推文数据...")
    tweets = scan_tweet_dirs()
    print(f"去重后推文总数: {len(tweets)}")
    if not tweets:
        print("[提示] 未找到任何推文数据，程序退出")
        sys.exit(0)

    if args.limit > 0:
        tweets = tweets[:args.limit]
        print(f"限制处理前 {args.limit} 条")

    total_imgs = sum(len(t.get("images", [])) for t in tweets)
    print(f"配图总数: {total_imgs}")

    print("\n[2/3] 开始生成 PDF 文件...")
    output_path = args.output
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=30 * mm,
        rightMargin=30 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm,
        title="推文合集"
    )

    story = []
    build_cover_page(story, tweets)
    build_toc_page(story, tweets)
    build_tweet_pages(story, tweets)

    doc.build(
        story,
        onFirstPage=lambda c, d: None,
        onLaterPages=add_page_number
    )

    file_size = os.path.getsize(output_path)
    print("\n" + "=" * 60)
    print(f"✅ PDF 生成成功: {output_path}")
    print(f"文件大小: {file_size / 1024 / 1024:.2f} MB")
    print(f"推文: {len(tweets)} 条 | 配图: {total_imgs} 张")
    print("=" * 60)

if __name__ == "__main__":
    main()
