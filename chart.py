"""用 matplotlib 畫血糖趨勢圖，回傳 PNG bytes。"""
import io
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import config  # noqa: E402

log = logging.getLogger(__name__)

# 讓中文標題不會變成豆腐方塊（macOS 內建字型）
plt.rcParams["font.sans-serif"] = [
    "PingFang HK", "PingFang TC", "Heiti TC",
    "Arial Unicode MS", "sans-serif",
]
plt.rcParams["axes.unicode_minus"] = False


def render_chart(history, title="血糖趨勢"):
    """history: [(datetime, sg), ...]；回傳 PNG bytes，沒資料時回 None。"""
    if not history:
        return None

    xs = [h[0] for h in history]
    ys = [h[1] for h in history]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=120)
    ax.plot(xs, ys, "-", linewidth=1.5, color="#1f77b4", zorder=2)
    ax.plot(xs, ys, "o", markersize=3, color="#1f77b4", zorder=3)

    # 目標範圍底色 + 上下限虛線
    ax.axhspan(config.LOW_THRESHOLD, config.HIGH_THRESHOLD, color="#d4f4dd", alpha=0.5, zorder=1)
    ax.axhline(config.LOW_THRESHOLD, color="#e74c3c", linestyle="--", linewidth=1, zorder=1)
    ax.axhline(config.HIGH_THRESHOLD, color="#e67e22", linestyle="--", linewidth=1, zorder=1)

    # 標出超標的點
    for x, y in zip(xs, ys):
        if y < config.LOW_THRESHOLD:
            ax.plot(x, y, "o", color="#e74c3c", markersize=6, zorder=4)
        elif y > config.HIGH_THRESHOLD:
            ax.plot(x, y, "o", color="#e67e22", markersize=6, zorder=4)

    ax.set_ylabel("mg/dL")
    ax.set_title(title)
    lo = min(ys + [config.LOW_THRESHOLD])
    hi = max(ys + [config.HIGH_THRESHOLD])
    ax.set_ylim(max(0, lo - 20), hi + 30)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
