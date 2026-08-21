#!/usr/bin/env python3
"""
美股日报 → GitHub Pages 博客生成器

用法:
  .venv/bin/python publish.py report-2026-08-01.md "2026.08.01"

作用:
  1. 把单日 markdown 日报渲染成 reports/YYYY-MM-DD.html (深色博客风格)
  2. 更新 index.html 目录, 列出所有日报
  3. (可选) git add/commit/push
"""
import re
import sys
import os
import html
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
REPORTS_DIR = ROOT / "reports"
INDEX_PATH = ROOT / "index.html"
TEMPLATE_PATH = ROOT / "template.html"

STYLE = """
:root {
  --bg: #0a0e17; --surface: #111726; --surface-2: #1a2233; --border: #232d42;
  --text: #e6eaf2; --muted: #8a94ab; --accent: #f7931a; --green: #38d996;
  --red: #ff5c6c; --amber: #ffb84d; --purple: #a78bfa;
  --radius: 14px;
  --mono: "SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; line-height:1.7; -webkit-font-smoothing:antialiased; }
.wrap { max-width:860px; margin:0 auto; padding:0 24px; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }

header { padding:56px 0 32px; border-bottom:1px solid var(--border); background:radial-gradient(1200px 400px at 20% -10%,rgba(79,140,255,.15),transparent 60%),radial-gradient(800px 300px at 90% -20%,rgba(56,217,150,.08),transparent 60%); }
.kicker { display:inline-flex; align-items:center; gap:8px; font-family:var(--mono); font-size:12px; letter-spacing:2px; color:var(--green); text-transform:uppercase; margin-bottom:16px; }
.kicker::before { content:""; width:28px; height:1px; background:var(--green); }
h1 { font-size:clamp(26px,4.5vw,38px); font-weight:700; letter-spacing:-0.02em; line-height:1.2; margin-bottom:10px; }
h1 a { color:var(--text); }
.date { font-family:var(--mono); color:var(--muted); font-size:14px; }
h2 { font-size:20px; font-weight:700; margin:28px 0 14px; letter-spacing:-0.01em; color:var(--text); }
h3 { font-size:17px; font-weight:600; margin:20px 0 10px; color:var(--text); }
p { margin-bottom:12px; }
strong { color:var(--text); font-weight:600; }
em { color:var(--amber); font-style:normal; }
blockquote { border-left:3px solid var(--green); padding:8px 18px; margin:14px 0; background:rgba(56,217,150,.05); border-radius:0 8px 8px 0; }
blockquote p { margin:0; }
code { font-family:var(--mono); color:var(--purple); font-size:13px; background:rgba(167,139,250,.1); padding:1px 7px; border-radius:5px; }
ul,ol { padding-left:24px; margin:12px 0; }
li { margin-bottom:8px; }
table { width:100%; border-collapse:collapse; margin:16px 0; font-size:14px; }
th { text-align:left; font-family:var(--mono); font-size:11px; letter-spacing:1px; text-transform:uppercase; color:var(--muted); padding:10px 12px; border-bottom:1px solid var(--border); }
td { padding:12px; border-bottom:1px solid var(--border); vertical-align:top; }
tr:last-child td { border-bottom:none; }
td:first-child { font-weight:600; color:var(--accent); white-space:nowrap; }
hr { border:none; border-top:1px solid var(--border); margin:28px 0; }
img { max-width:100%; height:auto; border-radius:10px; margin:12px 0; display:block; }
footer { padding:40px 0 64px; text-align:center; color:var(--muted); font-size:13px; }
.back { display:inline-block; margin-top:12px; font-family:var(--mono); font-size:13px; }
.section { padding:12px 0; }
@media (max-width:600px){
  .wrap{padding:0 16px;}
  header{padding:36px 0 20px;}
  body{font-size:15px; line-height:1.75;}
  h1{font-size:24px;}
  h2{font-size:18px; margin:22px 0 12px;}
  h3{font-size:16px;}
  blockquote{padding:6px 14px; margin:12px 0;}
  ul,ol{padding-left:20px;}
  td:first-child{white-space:normal;}
  table{font-size:13px;}
  td{padding:10px 8px;}
  img{border-radius:8px; margin:10px 0;}
}
.lightbox { display:none; position:fixed; inset:0; background:rgba(0,0,0,.95); z-index:9999; overflow:hidden; }
.lightbox.active { display:block; }
.lb-stage { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; overflow:hidden; touch-action:none; }
.lightbox img { max-width:92%; max-height:92%; border-radius:6px; transform-origin:center center; will-change:transform; }
.lightbox .hint { position:fixed; bottom:14px; left:0; right:0; text-align:center; color:#8a94ab; font-size:12px; pointer-events:none; z-index:10001; }
.lb-close { position:fixed; top:12px; right:18px; color:#fff; font-size:30px; line-height:1; cursor:pointer; z-index:10001; padding:6px; }
"""

# markdown 里可能含 HTML 表格/列表, 用 markdown 库渲染最稳
import markdown


def render_report_md_to_html(md_text: str) -> str:
    """把 markdown 日报正文渲染成 HTML body 片段."""
    return markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )


LIGHTBOX_HTML = """<div class="lightbox" id="lightbox">
  <div class="lb-close" id="lb-close">✕</div>
  <div class="lb-stage" id="lb-stage"><img id="lightbox-img" src="" alt=""></div>
  <div class="hint">双指缩放 · 拖动查看 · 双击复位</div>
</div>
<script>
(function(){
  var lb = document.getElementById('lightbox');
  var stage = document.getElementById('lb-stage');
  var img = document.getElementById('lightbox-img');
  var close = document.getElementById('lb-close');
  var scale = 1, tx = 0, ty = 0;
  var startDist = 0, startScale = 1;
  var lastX = 0, lastY = 0, startTx = 0, startTy = 0;

  function apply(){ img.style.transform = 'translate(' + tx + 'px,' + ty + 'px) scale(' + scale + ')'; }
  function reset(){ scale = 1; tx = 0; ty = 0; apply(); }
  function open(src){ img.src = src; reset(); lb.classList.add('active'); }
  function closeLb(){ lb.classList.remove('active'); }

  function clamp(){
    if (scale <= 1){ tx = 0; ty = 0; return; }
    var vw = stage.clientWidth, vh = stage.clientHeight;
    var dispW = img.offsetWidth * scale;
    var dispH = img.offsetHeight * scale;
    var maxTx = Math.max(0, (dispW - vw) / 2);
    var maxTy = Math.max(0, (dispH - vh) / 2);
    tx = Math.max(-maxTx, Math.min(maxTx, tx));
    ty = Math.max(-maxTy, Math.min(maxTy, ty));
  }

  document.addEventListener('click', function(e){
    var t = e.target;
    if (t.tagName === 'IMG' && t.id !== 'lightbox-img'){ open(t.src); }
  });
  close.addEventListener('click', closeLb);
  lb.addEventListener('click', function(e){ if (e.target === lb) closeLb(); });

  stage.addEventListener('touchstart', function(e){
    if (e.touches.length === 2){
      startDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      startScale = scale;
    } else if (e.touches.length === 1 && scale > 1){
      lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
      startTx = tx; startTy = ty;
    }
  }, {passive:false});

  stage.addEventListener('touchmove', function(e){
    e.preventDefault();
    if (e.touches.length === 2){
      var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      scale = Math.max(1, Math.min(6, startScale * d / startDist));
      apply();
    } else if (e.touches.length === 1 && scale > 1){
      tx = startTx + (e.touches[0].clientX - lastX);
      ty = startTy + (e.touches[0].clientY - lastY);
      clamp();
      apply();
    }
  }, {passive:false});

  stage.addEventListener('dblclick', function(){ if (scale > 1) reset(); else { scale = 2.5; apply(); } });
  stage.addEventListener('wheel', function(e){ e.preventDefault(); scale = Math.max(1, Math.min(6, scale * (e.deltaY < 0 ? 1.12 : 0.9))); apply(); }, {passive:false});
})();
</script>"""


def build_report_page(date_label: str, body_html: str, prev_link: str = "") -> str:
    """生成单期完整 HTML 页面."""
    title = f"Crypto 交易员观点日报 · {date_label}"
    back = f'<a class="back" href="../">← 返回目录</a>' if prev_link else '<a class="back" href="../">← 返回目录</a>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>{title}</title>
<style>{STYLE}</style>
</head>
<body>
<header><div class="wrap">
  <div class="kicker">Crypto Traders Daily · ktzwei.github.io/crypto-traders-blog</div>
  <h1><a href="../">{title}</a></h1>
  <div class="date">{date_label}</div>
</div></header>
<div class="wrap">
{body_html}
{back}
</div>
<footer><div>仅供学习参考，不构成投资建议</div></footer>
{LIGHTBOX_HTML}
</body></html>
"""


def build_index_page(entries: list[tuple[str, str]]) -> str:
    """生成主页目录, entries = [(date_label, href), ...] 最新在前."""
    rows = ""
    for label, href in entries:
        rows += f'<li><a href="{href}"><span class="d">{label}</span></a></li>\n'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>Crypto 交易员观点日报 · 归档</title>
<style>{STYLE}
.list {{ list-style:none; padding:0; }}
.list li {{ padding:14px 0; border-bottom:1px dashed var(--border); }}
.list a {{ font-size:17px; font-weight:600; }}
.list .d {{ font-family:var(--mono); color:var(--muted); font-size:14px; margin-right:10px; }}
.count {{ color:var(--muted); font-size:14px; }}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="kicker">Crypto Traders Daily</div>
  <h1>Crypto 交易员观点日报</h1>
  <div class="date">共 {len(entries)} 期 · 每日 09:00 更新</div>
</div></header>
<div class="wrap">
  <div class="section">
    <h2>📚 历史日报</h2>
    <p class="count">点击任意日期查看当天完整报告</p>
    <ul class="list">
{rows}    </ul>
  </div>
</div>
<footer><div>仅供学习参考，不构成投资建议 · 由 @kongruite 生成</div></footer>
</body></html>
"""


def normalize_date(label: str) -> str:
    """把 '2026.08.01' → '2026-08-01'"""
    m = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", label)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return label.replace(".", "-")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: publish.py <report.md> <date_label> [--push]")
        return 1
    md_path = Path(sys.argv[1])
    date_label = sys.argv[2] if len(sys.argv) > 2 else ""
    do_push = "--push" in sys.argv

    if not md_path.exists():
        print(f"找不到报告文件: {md_path}")
        return 1

    md_text = md_path.read_text(encoding="utf-8")
    body_html = render_report_md_to_html(md_text)
    REPORTS_DIR.mkdir(exist_ok=True)

    date_slug = normalize_date(date_label) if date_label else datetime.now().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"{date_slug}.html"
    report_path.write_text(build_report_page(date_label or date_slug, body_html), encoding="utf-8")
    print(f"生成报告页: {report_path}")

    # 重建 index
    entries = []
    for p in sorted(REPORTS_DIR.glob("*.html"), reverse=True):
        label = p.stem.replace("-", ".")
        entries.append((label, f"reports/{p.name}"))
    INDEX_PATH.write_text(build_index_page(entries), encoding="utf-8")
    print(f"更新目录: {INDEX_PATH} ({len(entries)} 期)")

    if do_push:
        os.chdir(ROOT)
        os.system("git add -A && git commit -q -m '新增Crypto交易员日报' || true")
        os.system("git push -q origin main")
        print("已 push 到 GitHub Pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
