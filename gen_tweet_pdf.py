#!/usr/bin/env python3
"""
推文PDF生成器 GitHub Actions 专用版
优化点：
1. 修复大范围Unicode正则导致正文内容丢失问题
2. 精准过滤Emoji，完整保留所有正常文字、符号、外文
3. 目录预览可配置是否截断，默认放宽长度
4. 统一正文/引用的表情处理逻辑
5. 【重点修复】支持多行正文读取，完整加载txt内所有正文内容
6. 保留原有字体、排版、去重、图片渲染全部功能
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
# 本地TTF字体路径（已适配wqy-microhei.ttf）
FONT_FILE = os.path.join(BASE_DIR, "fonts", "wqy-microhei.ttf")
TWEET_DATA_DIR = os.path.join(BASE_DIR, "tweet_data")
REPORTS_DIR = os.path.join(BASE_DIR, "pdf_output")
os.makedirs(REPORTS_DIR, exist_ok=True)

# 输出文件（固定，覆盖旧文件）
DEFAULT_OUTPUT = os.path.join(REPORTS_DIR, "推文合集.pdf")

# ===================== 加载仓库本地字体 =====================
FONT_NAME = "LocalWqyFont"
use_font = "Helvetica"

def load_local_font():
    """加载仓库内本地中文字体"""
    global use_font
    print("\n[调试] 字体路径:", FONT_FILE)
    if os.path.exists(FONT_FILE):
        print("[调试] 字体文件存在，尝试注册...")
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))
            use_font = FONT_NAME
            print(f"✅ 成功加载仓库本地字体: {FONT_FILE}")
            return True
        except Exception as e:
            print(f"⚠️ 字体注册失败: {e}")
    else:
        print("[调试] 字体文件不存在！")
    print("⚠️ 未找到本地字体，将使用默认英文字体")
    return False

# 初始化字体
load_local_font()

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

# ===================== 全局表情配置 & 精准Emoji正则 =====================
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

# 精准匹配Emoji区间，不误伤正常文字/符号/字母
emoji_pattern = re.compile(
    "["
    u"\U0001F600-\U0001F64F"
    u"\U0001F300-\U0001F5FF"
    u"\U0001F680-\U0001F6FF"
    u"\U0001F1E0-\U0001F1FF"
    u"\U00002500-\U00002BEF"
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE
)

# 目录预览最大字符数，调大=展示更多内容，设0=完全不截断
TOC_PREVIEW_MAX = 200

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
    print(f"[调试] 解析文件: {txt_path}")
    if not os.path.exists(txt_path):
        print(f"[调试] 文件不存在: {txt_path}")
        return None
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"[调试] 文件读取成功，内容长度: {len(content)}")
    except UnicodeDecodeError:
        print("[调试] UTF-8解码失败，尝试GBK...")
        try:
            with open(txt_path, "r", encoding="gbk") as f:
                content = f.read()
            print(f"[调试] GBK解码成功，内容长度: {len(content)}")
        except Exception as e:
            print(f"[调试] 文件读取失败: {e}")
            return None
    except Exception as e:
        print(f"[调试] 文件读取异常: {e}")
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

    lines = content.split("\n")
    text_buffer = []
    in_content = False

    for line in lines:
        raw_line = line
        line_strip = line.strip()
        if not line_strip:
            if in_content:
                text_buffer.append(raw_line)
            continue

        # 发布时间
        if line_strip.startswith(("发布时间：", "发布时间:")):
            raw_date = line_strip.split("：", 1)[-1].split(":", 1)[-1].strip()
            data["date"] = convert_relative_date(raw_date, dir_name)
            in_content = False
        # 引用内容
        elif line_strip.startswith(("引用：", "引用:")):
            quote_text = line_strip.split("：", 1)[-1].split(":", 1)[-1].strip()
            data["quote"] = quote_text
            in_content = False
        # 互动统计行
        elif any(k in line_strip for k in ("评论", "转发", "点赞", "浏览")):
            eng = parse_engagement_line(line_strip)
            data["comments"] = eng["comments"]
            data["retweets"] = eng["retweets"]
            data["likes"] = eng["likes"]
            data["views"] = eng["views"]
            in_content = False
        # 正文起始行
        elif line_strip.startswith(("正文：", "正文:")):
            content_part = line_strip.split("：", 1)[-1].split(":", 1)[-1]
            text_buffer.append(content_part)
            in_content = True
        # 正文后续多行
        elif in_content:
            text_buffer.append(raw_line)

    # 拼接完整多行正文，保留原始换行
    data["text"] = "\n".join(text_buffer).rstrip()

    print(f"[调试] 解析结果: date={data['date']}, text长度={len(data['text'])}, quote长度={len(data['quote'])}")
    return data


def scan_tweet_dirs():
    print("\n" + "="*60)
    print("[调试] 开始扫描推文目录...")
    print(f"[调试] 目录路径: {TWEET_DATA_DIR}")
    if not os.path.exists(TWEET_DATA_DIR):
        print("[调试] 目录不存在！")
        return []
    
    # 1. 列出所有文件夹（排除_开头）
    all_dirs = sorted([
        d for d in os.listdir(TWEET_DATA_DIR)
        if os.path.isdir(os.path.join(TWEET_DATA_DIR, d)) and not d.startswith("_")
    ], reverse=True)
    print(f"[调试] 扫描到的所有文件夹（共{len(all_dirs)}个）:")
    for idx, d in enumerate(all_dirs, 1):
        print(f"  {idx:2d}. {d}")

    # 2. 去重逻辑（按tweet_id保留最新日期）
    seen = {}
    for d in all_dirs:
        parts = d.split("_")
        if len(parts) >= 2:
            date_str = parts[0]
            tweet_id = parts[1]
        else:
            date_str = ""
            tweet_id = d
        
        print(f"[调试] 处理文件夹: {d} | ID: {tweet_id} | 日期: {date_str}")
        if tweet_id in seen:
            old_date = seen[tweet_id]["dir_name"].split("_")[0]
            if date_str > old_date:
                print(f"[调试] 发现更新版本，替换旧记录（旧日期: {old_date} → 新日期: {date_str}）")
                seen[tweet_id] = {"dir_name": d, "date": date_str, "id": tweet_id}
            else:
                print(f"[调试] 已存在更新版本，跳过（旧日期: {old_date} ≥ 新日期: {date_str}）")
        else:
            print(f"[调试] 新ID，添加记录")
            seen[tweet_id] = {"dir_name": d, "date": date_str, "id": tweet_id}

    # 3. 打印去重结果
    print(f"\n[调试] 去重后保留的文件夹（共{len(seen)}个）:")
    sorted_seen = sorted(seen.values(), key=lambda x: x["date"], reverse=True)
    for idx, item in enumerate(sorted_seen, 1):
        print(f"  {idx:2d}. {item['dir_name']} | ID: {item['id']} | 日期: {item['date']}")

    # 4. 解析有效推文
    tweets = []
    print("\n[调试] 开始解析有效推文...")
    for item in sorted_seen:
        dir_path = os.path.join(TWEET_DATA_DIR, item["dir_name"])
        txt_path = os.path.join(dir_path, "推文内容.txt")
        images = sorted([
            os.path.join(dir_path, f)
            for f in os.listdir(dir_path)
            if f.endswith((".jpg", ".jpeg", ".png", ".gif")) and f.startswith("图片_")
        ])
        print(f"[调试] 文件夹内图片数量: {len(images)}")
        
        tweet_data = parse_tweet_text(txt_path, dir_name=item["dir_name"])
        if tweet_data:
            tweet_data["id"] = item["id"]
            tweet_data["dir_name"] = item["dir_name"]
            tweet_data["images"] = images
            tweet_data["dir_path"] = dir_path
            tweets.append(tweet_data)
            print(f"[调试] 推文添加成功，当前总数: {len(tweets)}")
        else:
            print(f"[调试] 推文解析失败，跳过")

    print(f"\n✅ 最终有效推文总数: {len(tweets)}")
    print("="*60 + "\n")
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
        self.color = color

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
        text_raw = tweet.get("text", "")
        
        # 目录预览处理
        if TOC_PREVIEW_MAX > 0 and len(text_raw) > TOC_PREVIEW_MAX:
            text_preview = text_raw[:TOC_PREVIEW_MAX] + "..."
        else:
            text_preview = text_raw

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

    for i, tweet in enumerate(tweets, 1):
        date_str = tweet.get("date", "")
        title_text = f"#{i}  {date_str}"
        story.append(Paragraph(title_text, section_title))
        story.append(ColorBar(40 * mm, 1.5 * mm, COLOR_ACCENT))
        story.append(Spacer(1, 3 * mm))

        raw_text = tweet.get("text", "")
        # 正文清洗：转义标签 + 替换表情 + 精准过滤Emoji
        safe_text = raw_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for emoji, text in emoji_map.items():
            safe_text = safe_text.replace(emoji, text)
        safe_text = emoji_pattern.sub("", safe_text)

        # 话题、币种着色 + 换行转换
        safe_text = re.sub(r"#([a-zA-Z]\w*)", r'<font color="#0984e3"><b>#\1</b></font>', safe_text)
        safe_text = re.sub(r"\$([A-Z]{1,6}(?:\.[A-Z])?)", r'<font color="#e94560"><b>\$\1</b></font>', safe_text)
        safe_text = safe_text.replace("\n", "<br/>")

        if safe_text.strip():
            story.append(Paragraph(safe_text, text_style))
            story.append(Spacer(1, 2 * mm))

        # 引用内容清洗（同正文逻辑）
        quote_text = tweet.get("quote", "")
        if quote_text.strip():
            safe_quote = quote_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for emoji, text in emoji_map.items():
                safe_quote = safe_quote.replace(emoji, text)
            safe_quote = emoji_pattern.sub("", safe_quote)

            safe_quote = re.sub(r"#([a-zA-Z]\w*)", r'<font color="#0984e3"><b>#\1</b></font>', safe_quote)
            safe_quote = re.sub(r"\$([A-Z]{1,6}(?:\.[A-Z])?)", r'<font color="#e94560"><b>\$\1</b></font>', safe_quote)
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

        # 图片渲染
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
                story.append(Spacer(1, 2 * mm))

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
    print("  推文PDF生成器 (GitHub Actions 优化版)")
    print("=" * 60)

    tweets = scan_tweet_dirs()
    if not tweets:
        print("[提示] 未找到任何推文数据，程序退出")
        sys.exit(0)

    if args.limit > 0:
        tweets = tweets[:args.limit]
        print(f"[调试] 限制处理前 {args.limit} 条")

    total_imgs = sum(len(t.get("images", [])) for t in tweets)
    print(f"[调试] 最终处理推文数: {len(tweets)}, 配图总数: {total_imgs}")

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
