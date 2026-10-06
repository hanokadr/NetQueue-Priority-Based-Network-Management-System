"""Graph drawing for NetQueue (matplotlib). The backend draws the graphs and the
frontend only displays the picture.

Uses matplotlib's Figure class directly (no pyplot), so no window is opened and it
is safe to use inside a web server."""

import io

import matplotlib
from matplotlib.figure import Figure

# Same font as the page (style.css uses system-ui). matplotlib cannot read "system-ui",
# so list the usual system fonts: the first one installed on this computer is used.
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = [
    "Segoe UI", "SF Pro Text", "Helvetica Neue", "Roboto", "Ubuntu",
    "Cantarell", "Noto Sans", "Arial", "DejaVu Sans",
]

# Colors taken from style.css so the graph matches the page theme.
THEMES = {
    "light": {"bg": "#ffffff", "fg": "#1d2733", "mut": "#6b7785", "line": "#d5dbe1",
              "queue": "#1f77b4", "cap": "red", "tx": "#1f77b4", "drop": "#ff7f0e",
              "grid": "#b0b0b0"},
    "dark":  {"bg": "#1a222b", "fg": "#e6ebf0", "mut": "#93a0ad", "line": "#2d3945",
              "queue": "#5dade2", "cap": "#ef6a5b", "tx": "#5dade2", "drop": "#f0b13a",
              "grid": "#2d3945"},
}


def style_axes(ax, c):
    ax.set_facecolor(c["bg"])
    ax.tick_params(colors=c["fg"])
    for spine in ax.spines.values():
        spine.set_color(c["mut"])
    ax.title.set_color(c["fg"])
    ax.xaxis.label.set_color(c["fg"])
    ax.yaxis.label.set_color(c["fg"])
    ax.grid(True, color=c["grid"])


def style_legend(legend, c):
    frame = legend.get_frame()
    frame.set_facecolor(c["bg"])
    frame.set_edgecolor(c["line"])
    for text in legend.get_texts():
        text.set_color(c["fg"])


def draw_graphs(history, capacity, theme="light"):
    """Two graphs in one image:
       1) Queue size over time (with the capacity line)
       2) Packets transmitted and dropped over time"""
    c = THEMES.get(theme, THEMES["light"])
    fig = Figure(figsize=(8, 7), facecolor=c["bg"])
    ax1, ax2 = fig.subplots(2, 1)

    if history:
        start = history[0]["time"]                      # time axis starts at the first sample
        t = [p["time"] - start for p in history]

        # ---- Graph 1 - Queue size over time ----
        ax1.plot(t, [p["queue"] for p in history], marker="o", color=c["queue"], label="Queue size")
        ax1.axhline(capacity, color=c["cap"], linestyle="--", label="Capacity")
        style_legend(ax1.legend(loc="upper left"), c)

        # ---- Graph 2 - Transmitted and dropped packets ----
        ax2.plot(t, [p["transmitted"] for p in history], marker="o", color=c["tx"], label="Transmitted")
        ax2.plot(t, [p["dropped"] for p in history], marker="x", color=c["drop"], label="Dropped")
        style_legend(ax2.legend(loc="upper left"), c)
    else:
        for ax in (ax1, ax2):
            ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                    transform=ax.transAxes, color=c["mut"])

    ax1.set_xlabel("Time (seconds)")
    ax1.set_ylabel("Queue Size")
    ax1.set_title("NetQueue - Queue Size Over Time")

    ax2.set_xlabel("Time (seconds)")
    ax2.set_ylabel("Number of Packets")
    ax2.set_title("Packet Transmission and Dropping")

    style_axes(ax1, c)
    style_axes(ax2, c)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=c["bg"])
    return buf.getvalue()
