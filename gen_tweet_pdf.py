from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph
import os
import requests

# ---------------------- 1. 自动下载中文字体（GitHub Actions 可用） ----------------------
FONT_DIR = "fonts"
FONT_PATH = os.path.join(FONT_DIR, "NotoSansCJKsc-Regular.ttf")
if not os.path.exists(FONT_DIR):
    os.makedirs(FONT_DIR)

# 不存在就下载（Google 开源中文字体）
if not os.path.exists(FONT_PATH):
    url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
    r = requests.get(url, allow_redirects=True)
    with open(FONT_PATH, "wb") as f:
        f.write(r.content)

# ---------------------- 2. 注册中文字体 ----------------------
pdfmetrics.registerFont(TTFont("NotoSans", FONT_PATH))

# ---------------------- 3. 生成 PDF（示例，你按自己逻辑改） ----------------------
OUTPUT_PDF = "pdf_output/推文合集.pdf"
if not os.path.exists("pdf_output"):
    os.makedirs("pdf_output")

# 建文档+样式，强制用中文字体
doc = SimpleDocTemplate(OUTPUT_PDF, pagesize=A4)
styles = getSampleStyleSheet()

# 覆盖默认样式，全部用 NotoSans
for name in styles.byName:
    styles[name].fontName = "NotoSans"
    styles[name].wordWrap = "CJK"  # 中文自动换行

# 示例内容（你替换成自己的推文内容）
story = []
story.append(Paragraph("推文合集", styles["Title"]))
story.append(Paragraph("测试中文：你好，这是中文推文", styles["Normal"]))
story.append(Paragraph("English + 中文混合：Hello 世界", styles["Normal"]))

doc.build(story)
print(f"✅ PDF 生成完成：{OUTPUT_PDF}")
