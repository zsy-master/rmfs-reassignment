"""Four publication charts from freshly recomputed tables (vector PDF / 300 dpi PNG)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pypdfium2 as pdfium
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib.colors import Color, HexColor, black, white

WIDTH = 864
LAMBDAS = (0, 0.25, 0.5, 1, 2)
COLORS = ("#440154", "#3b528b", "#21918c", "#5ec962", "#c7a719")


def text(drawing, x, y, value, size=11, anchor="start", color=black):
    drawing.add(
        String(
            x,
            y,
            str(value),
            fontName="Helvetica",
            fontSize=size,
            textAnchor=anchor,
            fillColor=color,
        )
    )


def export(drawing, directory, name):
    pdf = directory / f"{name}.pdf"
    renderPDF.drawToFile(drawing, str(pdf))
    document = pdfium.PdfDocument(str(pdf))
    page = bitmap = None
    try:
        page = document[0]
        bitmap = page.render(scale=300 / 72)
        image = bitmap.to_pil()
        image.save(directory / f"{name}.png", dpi=(300, 300))
        image.close()
    finally:
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        document.close()
    (directory / f"{name}.metadata.json").write_text(
        json.dumps(
            {
                "n": 100,
                "df": 99,
                "confidence": 0.95,
                "dpi": 300,
                "source": "recomputed complete 100-seed statistics",
                "type": "vector PDF and 300 dpi PNG",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def panels(sensitivity):
    return (
        [(scenario, count) for scenario in ("abrupt", "gradual") for count in (5, 9, 13)]
        if sensitivity
        else [(scenario, None) for scenario in ("no_drift", "abrupt", "gradual")]
    )


def title(scenario, count):
    return scenario.replace("_", " ").capitalize() + (
        f" | {count}/30 ({100 * count / 30:.1f}%)" if count else ""
    )


def budget_plot(summary, directory, name, sensitivity):
    height = 520 if sensitivity else 400
    drawing = Drawing(WIDTH, height)
    text(
        drawing,
        WIDTH / 2,
        height - 22,
        "Budget response of M | 100 paired replications",
        16,
        "middle",
    )
    for index, (scenario, count) in enumerate(panels(sensitivity)):
        x = index % 3 * WIDTH / 3 + 51
        y = 300 - index // 3 * 195 if sensitivity else 65
        w, h = WIDTH / 3 - 74, 125 if sensitivity else 250
        data = summary[summary.strategy.eq("M") & summary.scenario.eq(scenario)]
        if count:
            data = data[data.changed_skus.eq(count)]
        low, high = float(data.tc_ci95_low.min()), float(data.tc_ci95_high.max())
        padding = max(3, (high - low) * 0.12)
        low, high = low - padding, high + padding
        step = max(5, 5 * math.ceil((high - low) / 20))
        low, high = step * math.floor(low / step), step * math.ceil(high / step)

        def px(k):
            return x + (k - 0.6) / 4.8 * w

        def py(value):
            return y + (value - low) / (high - low) * h

        text(drawing, x + w / 2, y + h + 17, title(scenario, count), 13, "middle")
        for tick in range(int(low), int(high) + 1, int(step)):
            yt = py(tick)
            drawing.add(Line(x, yt, x + w, yt, strokeColor=HexColor("#dddddd"), strokeWidth=0.4))
            text(drawing, x - 7, yt - 3, tick, 11, "end")
        for k in (1, 3, 5):
            text(drawing, px(k), y - 17, k, 11, "middle")
        text(drawing, x + w / 2, y - 35, "Budget K", 12, "middle")
        text(drawing, x + 2, y + h + 2, "Mean test TC (95% CI)", 9)
        for lam, hex_color in zip(LAMBDAS, COLORS):
            rows = list(data[data["lambda"].eq(lam)].sort_values("budget_k").itertuples())
            color = HexColor(hex_color)
            coordinates = []
            for row in rows:
                coordinates.extend([px(row.budget_k), py(row.tc_ci95_high)])
            for row in reversed(rows):
                coordinates.extend([px(row.budget_k), py(row.tc_ci95_low)])
            drawing.add(
                Polygon(
                    coordinates,
                    fillColor=Color(color.red, color.green, color.blue, alpha=0.12),
                    strokeColor=None,
                )
            )
            points = [(px(row.budget_k), py(row.tc_mean)) for row in rows]
            for a, b in zip(points, points[1:]):
                drawing.add(Line(*a, *b, strokeColor=color, strokeWidth=1.6))
            for point in points:
                drawing.add(Circle(*point, 2.5, fillColor=color, strokeColor=None))
        drawing.add(Line(x, y, x, y + h, strokeWidth=0.6))
        drawing.add(Line(x, y, x + w, y, strokeWidth=0.6))
    for index, (lam, hex_color) in enumerate(zip(LAMBDAS, COLORS)):
        x = 190 + index * 98
        drawing.add(
            Line(
                x, height - 45, x + 22, height - 45, strokeColor=HexColor(hex_color), strokeWidth=2
            )
        )
        text(drawing, x + 28, height - 49, f"lambda={lam}", 11)
    text(
        drawing,
        WIDTH / 2,
        10,
        "Bands: mean TC intervals. Paired budget-difference intervals are reported separately.",
        10,
        "middle",
    )
    export(drawing, directory, name)


def shade(value, maximum):
    fraction = min(abs(value) / maximum, 1)
    base = (0.15, 0.35, 0.66) if value < 0 else (0.70, 0.15, 0.16)
    return Color(*(1 - (1 - component) * fraction for component in base))


def heatmap(paired, directory, name, sensitivity):
    height = 480 if sensitivity else 310
    drawing = Drawing(WIDTH, height)
    text(
        drawing,
        WIDTH / 2,
        height - 21,
        "M versus B2 | mean paired test TC difference | n=100",
        16,
        "middle",
    )
    text(
        drawing,
        WIDTH / 2,
        height - 40,
        "Hatched cells: 95% CI includes zero. Negative means favor M.",
        12,
        "middle",
    )
    data = paired[paired.metric.eq("TC") & paired.comparator.eq("B2")]
    maximum = max(1, float(data.mean_difference.abs().max()))
    plotted = []
    for index, (scenario, count) in enumerate(panels(sensitivity)):
        x = index % 3 * WIDTH / 3 + 38
        y = 275 - index // 3 * 185 if sensitivity else 120
        cell_w, cell_h = 44, 38
        panel = data[data.scenario.eq(scenario)]
        if count:
            panel = panel[panel.changed_skus.eq(count)]
        text(drawing, x + cell_w * 2.5, y + cell_h * 3 + 16, title(scenario, count), 13, "middle")
        for ri, k in enumerate((1, 3, 5)):
            yy = y + (2 - ri) * cell_h
            text(drawing, x - 10, yy + cell_h / 2 - 4, k, 12, "end")
            for ci, lam in enumerate(LAMBDAS):
                row = panel[panel.budget_k.eq(k) & panel["lambda"].eq(lam)].iloc[0]
                xx = x + ci * cell_w
                uncertain = row.ci95_low <= 0 <= row.ci95_high
                drawing.add(
                    Rect(
                        xx,
                        yy,
                        cell_w,
                        cell_h,
                        fillColor=shade(row.mean_difference, maximum),
                        strokeColor=white,
                        strokeWidth=0.7,
                    )
                )
                if uncertain:
                    for position in range(-cell_h, cell_w, 7):
                        a, b = max(0, position), min(cell_w, position + cell_h)
                        if a <= b:
                            drawing.add(
                                Line(
                                    xx + a,
                                    yy + max(0, -position),
                                    xx + b,
                                    yy + min(cell_h, cell_w - position),
                                    strokeColor=Color(0.4, 0.4, 0.4, alpha=0.32),
                                    strokeWidth=0.6,
                                )
                            )
                    drawing.add(
                        Rect(
                            xx + 8,
                            yy + 11,
                            cell_w - 16,
                            16,
                            fillColor=Color(1, 1, 1, alpha=0.78),
                            strokeColor=None,
                        )
                    )
                color = (
                    white if abs(row.mean_difference) > 0.65 * maximum and not uncertain else black
                )
                text(
                    drawing,
                    xx + cell_w / 2,
                    yy + cell_h / 2 - 4,
                    f"{row.mean_difference:.1f}",
                    12,
                    "middle",
                    color,
                )
                plotted.append(
                    {
                        "scenario": scenario,
                        "changed_skus": count,
                        "budget_k": k,
                        "lambda": lam,
                        "mean": float(row.mean_difference),
                        "CI_low": float(row.ci95_low),
                        "CI_high": float(row.ci95_high),
                        "hatched": bool(uncertain),
                    }
                )
        text(drawing, x - 30, y + cell_h * 1.5, "K", 12, "middle")
        for ci, lam in enumerate(LAMBDAS):
            text(drawing, x + (ci + 0.5) * cell_w, y - 17, lam, 11, "middle")
        text(drawing, x + cell_w * 2.5, y - 34, "Movement cost lambda", 12, "middle")
    x, y = WIDTH / 2 - 150, 22
    for index in range(200):
        value = (index / 199 * 2 - 1) * maximum
        drawing.add(
            Rect(x + index * 1.5, y, 1.6, 9, fillColor=shade(value, maximum), strokeColor=None)
        )
    for offset, label in [
        (0, f"-{maximum:.1f} (M lower)"),
        (150, "0"),
        (300, f"+{maximum:.1f} (B2 lower)"),
    ]:
        text(drawing, x + offset, y - 12, label, 10, "middle")
    pd.DataFrame(plotted).to_csv(
        directory / f"{name}_plotted_cells.csv", index=False, encoding="utf-8-sig"
    )
    export(drawing, directory, name)


def render_figures(output: Path):
    directory = output / "figures"
    directory.mkdir(exist_ok=True)
    for prefix, sensitivity, label in [("", False, "main_"), ("sensitivity_", True, "")]:
        summary = pd.read_csv(output / f"{prefix}strategy_summary_100seeds.csv")
        paired = pd.read_csv(output / f"{prefix}paired_comparisons_100seeds.csv")
        budget_plot(summary, directory, f"figure_{label}budget_response_100seeds", sensitivity)
        heatmap(paired, directory, f"figure_{label}M_vs_B2_100seeds", sensitivity)
    print("Four PDF/PNG figure sets generated from recomputed tables.", flush=True)
