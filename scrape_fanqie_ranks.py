# -*- coding: utf-8 -*-
import os
import json
import time
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

START_CODE = 58344  # 0xE3E8
CHAR_SEQUENCE = [
    "D", "在", "主", "特", "家", "军", "然", "表", "场", "4", "要", "只", "v", "和", "?", "6", "别", "还", "g", "现", "儿", "岁", "?", "?", "此", "象", "月", "3", "出", "战", "工", "相", "o", "男", "直", "失", "世", "F", "都", "平", "文", "什", "V", "O", "将", "真", "T", "那", "当", "?", "会", "立", "些", "u", "是", "十", "张", "学", "气", "大", "爱", "两", "命", "全", "后", "东", "性", "通", "被", "1", "它", "乐", "接", "而", "感", "车", "山", "公", "了", "常", "以", "何", "可", "话", "先", "p", "i", "叫", "轻", "M", "士", "w", "着", "变", "尔", "快", "l", "个", "说", "少", "色", "里", "安", "花", "远", "7", "难", "师", "放", "t", "报", "认", "面", "道", "S", "?", "克", "地", "度", "I", "好", "机", "U", "民", "写", "把", "万", "同", "水", "新", "没", "书", "电", "吃", "像", "斯", "5", "为", "y", "白", "几", "日", "教", "看", "但", "第", "加", "候", "作", "上", "拉", "住", "有", "法", "r", "事", "应", "位", "利", "你", "声", "身", "国", "问", "马", "女", "他", "Y", "比", "父", "x", "A", "H", "N", "s", "X", "边", "美", "对", "所", "金", "活", "回", "意", "到", "z", "从", "j", "知", "又", "内", "因", "点", "Q", "三", "定", "8", "R", "b", "正", "或", "夫", "向", "德", "听", "更", "?", "得", "告", "并", "本", "q", "过", "记", "L", "让", "打", "f", "人", "就", "者", "去", "原", "满", "体", "做", "经", "K", "走", "如", "孩", "c", "G", "给", "使", "物", "?", "最", "笑", "部", "?", "员", "等", "受", "k", "行", "一", "条", "果", "动", "光", "门", "头", "见", "往", "自", "解", "成", "处", "天", "能", "于", "名", "其", "发", "总", "母", "的", "死", "手", "入", "路", "进", "心", "来", "h", "时", "力", "多", "开", "已", "许", "d", "至", "由", "很", "界", "n", "小", "与", "Z", "想", "代", "么", "分", "生", "口", "再", "妈", "望", "次", "西", "风", "种", "带", "J", "?", "实", "情", "才", "这", "?", "E", "我", "神", "格", "长", "觉", "间", "年", "眼", "无", "不", "亲", "关", "结", "0", "友", "信", "下", "却", "重", "己", "老", "2", "音", "字", "m", "呢", "明", "之", "前", "高", "P", "B", "目", "太", "e", "9", "起", "稜", "她", "也", "W", "用", "方", "子", "英", "每", "理", "便", "四", "数", "期", "中", "C", "外", "样", "a", "海", "们", "任"
]

def decode_text(text: str) -> str:
    if not text:
        return ""
    result = []
    for char in text:
        code = ord(char)
        idx = code - START_CODE
        if 0 <= idx < len(CHAR_SEQUENCE):
            result.append(CHAR_SEQUENCE[idx])
        else:
            result.append(char)
    return "".join(result)

# 我们将直接从页面解析所有新书榜类别目录，实现动态抓取

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def run_scraper(channel="0", rank_type="1", limit=30, sleep_sec=5, output_dir=None, min_category_books=15):
    os.makedirs(output_dir or OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    gender = "female" if channel == "0" else "male"
    rank_name = "new" if rank_type == "1" else "read"
    output_root = output_dir or OUTPUT_DIR
    output_file = os.path.join(output_root, f"fanqie_{gender}_{rank_name}_ranks_{date_str}.json")
    state_file = os.path.join(output_root, f"task_state_{gender}_{rank_name}_{date_str}.json")
    category_id = "1139" if channel == "0" else "1141"
    rank_prefix = f"/rank/{channel}_{rank_type}_"
    
    # ------------- 状态恢复逻辑 -------------
    completed_cats = []
    all_categories = []  # 收集所有分类数据
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            try:
                state = json.load(f)
                completed_cats = state.get("completed", [])
            except:
                pass
    # 如果有中断恢复的数据，先加载已有的 JSON
    if os.path.exists(output_file) and len(completed_cats) > 0:
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
                all_categories = existing.get("categories", [])
                valid_names = {
                    cat.get("name")
                    for cat in all_categories
                    if len(cat.get("books", [])) >= min_category_books
                }
                completed_cats = [name for name in completed_cats if name in valid_names]
                all_categories = [cat for cat in all_categories if cat.get("name") in valid_names]
            except:
                pass
    # ----------------------------------------
    
    with sync_playwright() as p:
        launch_kwargs = {"headless": True}
        executable_path = os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH")
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        elif os.environ.get("GITHUB_ACTIONS"):
            # GitHub Actions installs Playwright's bundled Chromium.
            pass
        elif os.name == "nt":
            launch_kwargs["channel"] = "chrome"
        else:
            # Oracle's ARM64 images commonly ship Chromium at one of these
            # paths, while Playwright's "chrome" channel only checks the
            # x64 Google Chrome location.
            for candidate in (
                "/usr/bin/google-chrome",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ):
                if os.path.exists(candidate):
                    launch_kwargs["executable_path"] = candidate
                    break
            else:
                raise RuntimeError(
                    "No Chromium executable found; set PLAYWRIGHT_EXECUTABLE_PATH"
                )
        browser = p.chromium.launch(**launch_kwargs)
        # Create a new context with a normal user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 先访问新书榜的基准前缀页面，以此为入口模拟人工作业
        init_url = f"https://fanqienovel.com/rank/{channel}_{rank_type}_{category_id}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在初始化并访问基础榜单页：{init_url}")
        initialized = False
        for attempt in range(3):
            try:
                page.goto(init_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector('a[href^="/page/"]', timeout=15000)
                initialized = True
                break
            except Exception as e:
                print(f"官方入口第 {attempt + 1} 次加载失败: {e}")
                if attempt < 2:
                    page.wait_for_timeout(2000)
        if not initialized:
            raise RuntimeError("官方榜单入口连续三次加载失败，拒绝发布本次数据")
        
        # 动态解析页面左侧拥有的所有类别目录 (通过匹配对应的榜单路由规律)
        categories_js = """
        (rankPrefix) => {
            return Array.from(document.querySelectorAll('a'))
                .filter(a => a.href.includes(rankPrefix))
                .map(a => ({
                    name: a.innerText.trim(),
                    href: a.getAttribute('href')
                }));
        }
        """
        categories = page.evaluate(categories_js, rank_prefix)
        print(f"✅ 成功自适应提取到 {len(categories)} 个分类标签。开始全量模拟点击抓取下级数据...")
        
        for cat in categories:
            cat_name = cat["name"]
            cat_href = cat["href"]
            
            if cat_name in completed_cats:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️ 跳过今日已经完成抓取的类别：{cat_name}")
                continue
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 模拟点击执行类别切换 -> {cat_name}")
            category_url = cat_href if cat_href.startswith("http") else "https://fanqienovel.com" + cat_href
            category_ready = False
            for attempt in range(3):
                try:
                    # Direct navigation avoids extracting the previous category while the SPA route changes.
                    page.goto(category_url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        page.wait_for_function(
                            "expected => document.title.includes(expected)",
                            cat_name,
                            timeout=10000,
                        )
                    except Exception:
                        pass
                    page.wait_for_timeout(1800)

                    previous_count = 0
                    stable_rounds = 0
                    for _ in range(8):
                        current_count = page.locator('a[href^="/page/"]').count()
                        if current_count == previous_count:
                            stable_rounds += 1
                        else:
                            stable_rounds = 0
                        previous_count = current_count
                        if current_count >= min(limit, min_category_books) and stable_rounds >= 1:
                            break
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1200)

                    if previous_count >= min(limit, min_category_books):
                        category_ready = True
                        break
                    print(f"分类 {cat_name} 第 {attempt + 1} 次仅加载 {previous_count} 个作品，准备重试")
                except Exception as e:
                    print(f"分类 {cat_name} 第 {attempt + 1} 次加载失败: {e}")

            if not category_ready:
                raise RuntimeError(
                    f"分类 {cat_name} 未加载到至少 {min_category_books} 本书，拒绝发布不完整榜单"
                )
                
            # Extract cards. Based on helper.js: books usually are inside links a[href^="/page/"]
            # Let's use playwright evaluate to reliably traverse DOM the same way script did.
            extract_js = """
            () => {
                const bookMap = new Map();
                const links = document.querySelectorAll('a[href^="/page/"]');
                links.forEach(link => {
                    let container = link.parentElement;
                    let depth = 0;
                    while (container && depth < 6) {
                        if (container.querySelector('img') && container.innerText.includes('在读')) {
                            const href = link.getAttribute('href');
                            if (!bookMap.has(href)) {
                                bookMap.set(href, container);
                            }
                            break;
                        }
                        container = container.parentElement;
                        depth++;
                    }
                });
                
                const cards = Array.from(bookMap.values());
                const results = [];
                for (const item of cards) {
                    let imgNode = item.querySelector('img');
                    let cover = imgNode ? imgNode.getAttribute('src') : "";
                    
                    let title = "";
                    if (imgNode && imgNode.getAttribute('alt')) {
                        title = imgNode.getAttribute('alt').trim();
                    }
                    if (!title) {
                        let textTitleNode = item.querySelector('h4, .title, h1') || item.querySelector('a[href^="/page/"]');
                        if (textTitleNode) {
                            let text = textTitleNode.innerText.trim();
                            if (text && !/^\\d+$/.test(text)) {
                                title = text;
                            }
                        }
                    }
                    if (!title) title = "未知";
                    if (title.includes("榜单说明")) continue;
                    
                    let authorNode = item.querySelector('.author, .author-name') || item.querySelector('a[href^="/author-page/"]');
                    let author = authorNode ? authorNode.innerText.trim() : "未知";
                    
                    let reads = "未知";
                    const lines = item.innerText.split('\\n');
                    for (let line of lines) {
                        if (line.includes('在读')) {
                            reads = line;  // We'll decode in Python
                            break;
                        }
                    }
                    
                    let introNode = item.querySelector('.intro, .abstract, .desc');
                    let intro = introNode ? introNode.innerText.trim() : "暂无简介";
                    
                    results.push({
                        title: title,
                        author: author,
                        reads: reads,
                        intro: intro,
                        cover: cover,
                        url: item.querySelector('a[href^="/page/"]').getAttribute('href')
                    });
                }
                return results;
            }
            """
            
            try:
                books_data = page.evaluate(extract_js)
            except Exception as e:
                print(f"执行JS抽取失败 {cat_name}: {e}")
                books_data = []
            
            category_books = []
            for b in books_data[:limit]:
                # Apply decoding logic!
                t = decode_text(b.get("title", ""))
                a = decode_text(b.get("author", ""))
                r_raw = decode_text(b.get("reads", ""))
                i = decode_text(b.get("intro", "")).replace("\\n", " ")
                c = b.get("cover", "")
                
                # Cleanup "Reads" string (e.g. "已完结 在读：34.8万" -> "34.8万")
                if "在读" in r_raw:
                    parts = r_raw.split("在读")
                    if len(parts) > 1:
                        # removes colons
                        cleaned_r = parts[1].replace(":", "").replace("：", "").strip()
                    else:
                        cleaned_r = r_raw
                else:
                    cleaned_r = r_raw
                    
                category_books.append({
                    "title": t,
                    "author": a,
                    "reads": cleaned_r,
                    "intro": i,
                    "cover": c,
                    "url": "https://fanqienovel.com" + b.get("url", "")
                })
            
            # 收集分类数据到内存，并增量写入 JSON
            if len(category_books) < min_category_books:
                raise RuntimeError(
                    f"分类 {cat_name} 最终只解析到 {len(category_books)} 本书，拒绝发布不完整榜单"
                )

            all_categories.append({
                "name": cat_name,
                "books": category_books
            })
            
            # 每完成一个分类就写入 JSON（防止中断丢数据）
            snapshot = {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "categories": all_categories
            }
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
            # 更新状态记录
            completed_cats.append(cat_name)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"completed": completed_cats}, f, ensure_ascii=False)
                
            print(f"成功抓取 {cat_name} 类别的前 {len(category_books)} 本书，且进度已存档。等待 {sleep_sec} 秒防拦截...")
            
            # 保护防封禁机制
            time.sleep(sleep_sec)
        
        browser.close()
        
    print(f"\n✅ 当日选定类目任务已完毕或刷新！数据源：{output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="番茄榜单采集（基于 FanqieRankTracker 原版 Playwright + 字体解码）")
    parser.add_argument("--channel", choices=["0", "1"], default="0", help="0=女频，1=男频")
    parser.add_argument("--type", dest="rank_type", choices=["1", "2"], default="1", help="1=新书榜，2=阅读榜")
    parser.add_argument("--limit", type=int, default=30, help="每个分类最多抓取数量")
    parser.add_argument("--sleep", type=float, default=5, help="分类之间等待秒数")
    parser.add_argument("--output-dir", default=None, help="数据输出目录")
    parser.add_argument("--min-category-books", type=int, default=15, help="每个分类至少解析的作品数")
    args = parser.parse_args()
    print(f"开始执行番茄榜单：channel={args.channel} type={args.rank_type}")
    run_scraper(
        channel=args.channel,
        rank_type=args.rank_type,
        limit=args.limit,
        sleep_sec=args.sleep,
        output_dir=args.output_dir,
        min_category_books=args.min_category_books,
    )
