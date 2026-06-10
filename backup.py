
import requests
from bs4 import BeautifulSoup
import re
import urllib3
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===================== 全局配置 =====================
PROXY = ""  # GitHub Actions 内部不需要代理
USERNAME = "aleabitoreddit"
BASE_DOMAIN = "https://nitter.net"
NITTER_URL = f"{BASE_DOMAIN}/{USERNAME}"

proxies = {"http": PROXY, "https": PROXY} if PROXY else None
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://nitter.net/",
}

BASE_DIR = "tweet_data"
MIN_CONTENT_LENGTH = 5
LOOP_MODE = False
MAX_WORKERS = 5
MAX_RETRY = 3
RETRY_DELAY = 3
MAX_EMPTY_PAGE = 3

# ===================== 日志函数 =====================
def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{now}] {msg}"
    print(log_msg)

# ===================== 工具函数 =====================
def save_text(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def download_img(url, save_path):
    try:
        r = requests.get(url, proxies=proxies, headers=headers, timeout=15, verify=False)
        with open(save_path, "wb") as f:
            f.write(r.content)
    except Exception:
        pass

# ===================== 带重试的请求函数 =====================
def fetch_url(url):
    retry = 0
    while retry < MAX_RETRY:
        try:
            resp = requests.get(
                url,
                proxies=proxies,
                headers=headers,
                timeout=20,
                verify=False
            )
            return resp
        except Exception as e:
            retry += 1
            log(f"⚠️ 请求失败，{RETRY_DELAY}秒后重试 {retry}/{MAX_RETRY}")
            time.sleep(RETRY_DELAY)
    return None

# ===================== 解析推文 =====================
def parse_tweet(tweet_div):
    data = {
        "time_raw": "",
        "content": "",
        "quote": "",
        "comment": "0",
        "retweet": "0",
        "like": "0",
        "view": "0",
        "imgs": []
    }
    time_elem = tweet_div.find("span", class_="tweet-date")
    if time_elem:
        data["time_raw"] = time_elem.get_text(strip=True)

    content_elem = tweet_div.find("div", class_="tweet-content")
    if content_elem:
        data["content"] = content_elem.get_text(strip=True, separator=" ")

    quote_elem = tweet_div.find("div", class_="quote-text")
    if quote_elem:
        data["quote"] = quote_elem.get_text(strip=True)

    stat_spans = tweet_div.find_all("span", class_="tweet-stat")
    if len(stat_spans) >= 4:
        data["comment"] = stat_spans[0].text.strip()
        data["retweet"] = stat_spans[1].text.strip()
        data["like"] = stat_spans[2].text.strip()
        data["view"] = stat_spans[3].text.strip()

    for a in tweet_div.find_all("a", class_="still-image"):
        href = a.get("href")
        if href:
            data["imgs"].append(BASE_DOMAIN + href)
    return data

# ===================== 目录命名：仅日期 =====================
def make_folder_name(tweet_time_str, tweet_id):
    now = datetime.now()
    target_dt = now

    if "·" in tweet_time_str and "," in tweet_time_str:
        try:
            dt_str = tweet_time_str.replace("· ", "")
            target_dt = datetime.strptime(dt_str, "%b %d, %Y %I:%M %p")
        except:
            pass
    elif "," not in tweet_time_str and len(tweet_time_str) <= 8:
        try:
            target_dt = datetime.strptime(tweet_time_str, "%b %d")
            target_dt = target_dt.replace(year=now.year)
        except:
            pass

    date_only = target_dt.strftime("%Y-%m-%d")
    folder_name = f"{date_only}_{tweet_id}"
    return folder_name

# ===================== 单条处理 =====================
def process_single_item(item):
    tw = parse_tweet(item)
    if len(tw["content"]) < MIN_CONTENT_LENGTH:
        return "empty"

    id_a = item.find("a", href=re.compile(r"/status/\d+"))
    if not id_a:
        return "empty"
    match = re.search(r"(\d+)", id_a["href"])
    if not match:
        return "empty"
    tid = match.group(1)

    folder_name = make_folder_name(tw["time_raw"], tid)
    folder_path = os.path.join(BASE_DIR, folder_name)

    if os.path.exists(folder_path):
        return "exists"

    os.makedirs(folder_path, exist_ok=True)
    txt_path = os.path.join(folder_path, "推文内容.txt")
    txt_content = f"""发布时间：{tw['time_raw']}
正文：{tw['content']}
引用：{tw['quote']}
评论：{tw['comment']} 转发：{tw['retweet']} 点赞：{tw['like']} 浏览：{tw['view']}
"""
    save_text(txt_path, txt_content)

    for idx, img_url in enumerate(tw["imgs"]):
        img_path = os.path.join(folder_path, f"图片_{idx+1}.jpg")
        download_img(img_url, img_path)

    return "success"

# ===================== 主抓取逻辑 =====================
def get_all_tweets():
    log(f"🚀 开始抓取: {NITTER_URL}")
    current_url = NITTER_URL
    total_new = 0
    total_skip = 0
    empty_skip = 0
    consecutive_empty_page = 0

    while True:
        log(f"\n📄 访问页面: {current_url}")
        resp = fetch_url(current_url)
        if not resp:
            log("❌ 页面失败")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.find_all("div", class_="timeline-item")
        if not items:
            log("ℹ️ 无更多推文")
            break

        page_new = 0
        page_skip = 0
        page_empty = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_single_item, item) for item in items]
            for future in as_completed(futures):
                res = future.result()
                if res == "success":
                    total_new += 1
                    page_new += 1
                elif res == "exists":
                    total_skip += 1
                    page_skip += 1
                elif res == "empty":
                    empty_skip += 1
                    page_empty += 1

        log(f"本页：新增 {page_new} | 重复 {page_skip} | 空 {page_empty}")
        if page_new == 0:
            consecutive_empty_page += 1
            if consecutive_empty_page >= MAX_EMPTY_PAGE:
                log("🛑 全部抓取完毕")
                break
        else:
            consecutive_empty_page = 0

        show_more = soup.find("div", class_="show-more")
        if not show_more:
            break
        next_a = show_more.find("a")
        if not next_a:
            break
        href = next_a["href"]
        if "?cursor=" in href:
            current_url = f"{BASE_DOMAIN}/{USERNAME}{href}"
        else:
            current_url = BASE_DOMAIN + href
        time.sleep(1)

    log(f"\n🎉 本轮结束：新增 {total_new} 条")

# ===================== 主入口 =====================
if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)
    get_all_tweets() 
