"""CareLink 網頁自動化抓資料（Playwright）＋ 解析。

登入 carelink.minimed.eu 後，Connect 頁面會打即時資料端點：
  https://clcloud.minimed.eu/patient/connect/data
回傳「顯示訊息」：lastSG（目前血糖）、lastSGTrend（官方趨勢）、
sgs（當日每 5 分鐘讀數）、bgUnits 等。我們攔截這個回應來解析。

登入狀態用 Playwright 的 storage_state 存成 carelink_state.json，
之後背景無視窗抓取時注入回去（這樣關掉瀏覽器也不會掉登入）。

CLI：
  login       開瀏覽器手動登入一次（存 carelink_state.json）
  fetch       背景無視窗抓一次並解析
  fetch-show  抓一次但顯示視窗（除錯）
  parse       只解析現有的 raw_dump.json（離線測試）
"""
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "browser-profile")
STATE_FILE = os.path.join(BASE, "carelink_state.json")
RAW_DUMP = os.path.join(BASE, "raw_dump.json")
VIEW_URL = "https://carelink.minimed.eu/app/connect/view"

# 攔截目標：即時顯示資料端點
DATA_URL_MARK = "/connect/data"

TREND_ARROWS = {
    "NONE": "",
    "DOUBLE_UP": "⬆️⬆️", "SINGLE_UP": "⬆️", "UP": "⬆️", "FORTY_FIVE_UP": "↗️",
    "FLAT": "➡️",
    "FORTY_FIVE_DOWN": "↘️", "DOWN": "⬇️", "SINGLE_DOWN": "⬇️", "DOUBLE_DOWN": "⬇️⬇️",
}


@dataclass
class Reading:
    sg: int
    trend: str
    timestamp: datetime
    units: str = "mg/dL"

    @property
    def arrow(self) -> str:
        return TREND_ARROWS.get((self.trend or "").upper(), "")


# ---------- 解析（connect/data 結構）----------
def _parse_dt(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _series(data):
    """回傳 [(datetime, sg), ...]，已排序、已濾掉 sg<=0。"""
    out = []
    for p in (data.get("sgs") if isinstance(data, dict) else None) or []:
        if isinstance(p, dict):
            sg, dt = p.get("sg"), _parse_dt(p.get("datetime"))
            if isinstance(sg, (int, float)) and sg > 0 and dt:
                out.append((dt, int(round(sg))))
    out.sort()
    return out


def _compute_trend(series, ref_dt, ref_sg):
    """官方沒給趨勢時，用約 15 分鐘前的讀數自算箭頭。"""
    if not series or ref_dt is None:
        return "NONE"
    prev = None
    for t, v in reversed(series):
        if (ref_dt - t).total_seconds() >= 15 * 60:
            prev = v
            break
    if prev is None and len(series) >= 4:
        prev = series[-4][1]
    if prev is None:
        return "FLAT"
    d = ref_sg - prev
    return (
        "DOUBLE_UP" if d >= 45 else
        "SINGLE_UP" if d >= 25 else
        "FORTY_FIVE_UP" if d >= 10 else
        "DOUBLE_DOWN" if d <= -45 else
        "SINGLE_DOWN" if d <= -25 else
        "FORTY_FIVE_DOWN" if d <= -10 else
        "FLAT"
    )


def parse_current(data):
    """目前血糖 + 趨勢（官方優先，否則自算）；沒資料回 None。"""
    if not isinstance(data, dict):
        return None
    series = _series(data)
    sg = dt = None
    last = data.get("lastSG")
    if isinstance(last, dict) and isinstance(last.get("sg"), (int, float)) and last["sg"] > 0:
        sg = int(round(last["sg"]))
        dt = _parse_dt(last.get("datetime"))
    if sg is None:
        if not series:
            return None
        dt, sg = series[-1]
    trend = (data.get("lastSGTrend") or "NONE").upper()
    if trend in ("", "NONE"):
        trend = _compute_trend(series, dt, sg)
    return Reading(sg=sg, trend=trend, timestamp=dt or datetime.now())


def history_points(data, hours=12):
    """回傳 [(datetime, sg), ...]，最近 hours 小時。"""
    s = _series(data)
    if not s:
        return []
    cutoff = s[-1][0] - timedelta(hours=hours)
    return [(t, v) for t, v in s if t >= cutoff]


# ---------- 抓資料（Playwright）----------
LAUNCH_ARGS = dict(
    args=["--disable-blink-features=AutomationControlled"],
    ignore_default_args=["--enable-automation"],
)
VIEWPORT = {"width": 1280, "height": 900}


def _capture_page(page, timeout_sec):
    """開血糖頁、攔截 connect/data 的 JSON 回應，回傳 (body_or_None, url)。"""
    store = {}

    def on_response(resp):
        try:
            if DATA_URL_MARK in resp.url and "json" in resp.headers.get("content-type", ""):
                body = resp.text()
                if body and '"sgs"' in body:
                    store["body"] = body
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(VIEW_URL, timeout=60000)
    except Exception:
        pass
    waited = 0
    while "body" not in store and waited < timeout_sec:
        page.wait_for_timeout(1000)
        waited += 1
    return store.get("body"), page.url


def run_login(timeout_sec=600):
    """互動登入一次，成功後把登入狀態存成 carelink_state.json。"""
    print("\n>>> 即將開啟瀏覽器。請在視窗裡登入 CareLink（解 reCAPTCHA），直到看到血糖畫面。")
    print(f">>> 偵測到血糖資料就會自動存檔並關閉（最多等 {timeout_sec} 秒）…\n")
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                PROFILE_DIR, channel="chrome", headless=False, viewport=VIEWPORT, **LAUNCH_ARGS)
            print("（使用系統 Google Chrome）")
        except Exception as e:
            print("（改用內建 Chromium：%s）" % str(e)[:80])
            ctx = p.chromium.launch_persistent_context(
                PROFILE_DIR, headless=False, viewport=VIEWPORT, **LAUNCH_ARGS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        body, url = _capture_page(page, timeout_sec)
        if body:
            ctx.storage_state(path=STATE_FILE)
            with open(RAW_DUMP, "w", encoding="utf-8") as f:
                f.write(body)
            print("\n✅ 登入成功，已存登入狀態到 carelink_state.json、資料到 raw_dump.json")
            _print_parsed(json.loads(body))
        else:
            print("\n❌ 逾時，沒抓到血糖資料。目前網址:", url)
        ctx.close()


def fetch_raw(headless=True, timeout_sec=90):
    """背景抓一次原始資料 dict（給 bot 用）：用存好的登入狀態，抓完滾動更新狀態。失敗回 None。"""
    if not os.path.exists(STATE_FILE):
        print("找不到 carelink_state.json，請先執行：carelink_web.py login")
        return None
    body = None
    url = ""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=headless, **LAUNCH_ARGS)
        except Exception:
            browser = p.chromium.launch(headless=headless, **LAUNCH_ARGS)
        ctx = browser.new_context(storage_state=STATE_FILE, viewport=VIEWPORT)
        page = ctx.new_page()
        body, url = _capture_page(page, timeout_sec)
        if body:
            ctx.storage_state(path=STATE_FILE)
            with open(RAW_DUMP, "w", encoding="utf-8") as f:
                f.write(body)
        ctx.close()
        browser.close()
    if not body:
        print("沒抓到血糖資料，最後網址:", url, "(若是 login 頁代表 session 過期，需重跑 login)")
        return None
    return json.loads(body)


def read_dump():
    """讀取常駐 keep 模式寫好的最新原始資料 dict；讀不到回 None。"""
    try:
        with open(RAW_DUMP, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


DATA_HTTP_URL = "https://carelink.minimed.eu/patient/connect/data"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _http_fetch_with_cookies(cookies):
    """用瀏覽器當前 cookies + auth_tmp_token 當 Bearer，純 HTTP 抓 connect/data。
    回傳 (data_dict_or_None, status_code, token_present)。"""
    import requests
    jar = {c["name"]: c["value"] for c in cookies}
    att = jar.get("auth_tmp_token")
    if not att:
        return None, None, False
    s = requests.Session()
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
        except Exception:
            pass
    hdr = {"accept": "application/json, text/plain, */*", "user-agent": _UA,
           "authorization": "Bearer " + att,
           "referer": "https://carelink.minimed.eu/app/connect/view"}
    try:
        r = s.get(DATA_HTTP_URL, headers=hdr, timeout=20)
    except Exception as e:
        print("[keep] HTTP 例外：", str(e)[:100], flush=True)
        return None, None, True
    if r.status_code == 200 and '"sgs"' in r.text:
        return r.json(), 200, True
    return None, r.status_code, True


def run_keep(poll_sec=240, headless=False):
    """混合常駐：開一個 headed 瀏覽器「不關」保住 Auth0 session（讓 SPA 自己刷新
    auth_tmp_token cookie），但抓資料完全走純 HTTP——每 poll_sec 從瀏覽器讀出當前
    cookie 的 auth_tmp_token 當 Bearer，GET connect/data 寫 raw_dump.json。
    不開新分頁、不 reload，避免掉登入。同時記錄 authorize/token 請求以了解刷新機制。"""
    if not os.path.exists(STATE_FILE):
        print("找不到 carelink_state.json，請先執行：carelink_web.py login", flush=True)
        return
    import time

    def on_request(req):
        u = req.url
        if "/authorize" in u or "/oauth/token" in u or "reauth" in u or "/sso/" in u:
            print(f"[keep][auth] {req.method} {u[:120]}", flush=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=headless, **LAUNCH_ARGS)
        except Exception:
            browser = p.chromium.launch(headless=headless, **LAUNCH_ARGS)
        # 用 storage_state 開 context（含 session cookie auth0/auth_tmp_token → 是登入狀態）
        ctx = browser.new_context(storage_state=STATE_FILE, viewport=VIEWPORT)
        ctx.on("request", on_request)
        keeper = ctx.new_page()
        try:
            keeper.goto(VIEW_URL, timeout=60000)
        except Exception:
            pass
        print(f"[keep] 混合常駐啟動（headless={headless}），每 {poll_sec}s 用 cookie token HTTP 抓", flush=True)
        warned401 = False
        last_token = None
        loops = 0
        while True:
            cookies = ctx.cookies()
            data, status, has_tok = _http_fetch_with_cookies(cookies)
            tok = next((c["value"] for c in cookies if c["name"] == "auth_tmp_token"), None)
            if tok and tok != last_token:
                if last_token is not None:
                    print("[keep] 🔄 auth_tmp_token 已更新（SPA 自動刷新成功）", flush=True)
                last_token = tok
            if data:
                warned401 = False
                with open(RAW_DUMP, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                r = parse_current(data)
                if r and r.sg > 0:
                    print(f"[keep] OK {r.sg} mg/dL @ {r.timestamp:%m/%d %H:%M}", flush=True)
                else:
                    ss = data.get("sensorState")
                    print(f"[keep] OK 但無讀數（sensorState={ss}）", flush=True)
                # 定期把刷新後的 session 存回，restart 後不會掉
                loops += 1
                if loops % 5 == 0:
                    try:
                        ctx.storage_state(path=STATE_FILE)
                    except Exception:
                        pass
            else:
                if not warned401:
                    print(f"[keep] ⚠️ HTTP 抓取失敗 status={status} has_token={has_tok}"
                          f"（token 可能過期、SPA 沒刷新）", flush=True)
                    warned401 = True
            keeper.wait_for_timeout(poll_sec * 1000)


def _print_parsed(data):
    r = parse_current(data)
    print("目前血糖:", f"{r.sg} mg/dL {r.arrow} ({r.trend}) @ {r.timestamp:%m/%d %H:%M}" if r else "無")
    hist = history_points(data, hours=12)
    print(f"近 12h 筆數: {len(hist)}")
    if hist:
        ys = [s for _, s in hist]
        print(f"  範圍: 最低 {min(ys)} / 最高 {max(ys)} / 最新 {ys[-1]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if mode == "login":
        run_login()
    elif mode == "keep":
        # keep [poll_sec] [headless]  ；預設 240 秒、有視窗（headed）
        poll = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 240
        run_keep(poll_sec=poll, headless=("headless" in sys.argv))
    elif mode == "parse":
        with open(RAW_DUMP, encoding="utf-8") as f:
            _print_parsed(json.load(f))
    elif mode == "fetch-show":
        data = fetch_raw(headless=False)
        print("✅ 抓到資料" if data else "❌ 沒抓到")
        if data:
            _print_parsed(data)
    else:
        data = fetch_raw(headless=True)
        print("✅ 抓到資料" if data else "❌ 沒抓到")
        if data:
            _print_parsed(data)
