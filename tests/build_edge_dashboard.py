"""Fill the template with edge cases: no data, bad-growth metric, zero delta,
a 27-point line chart, an empty chart and a string containing </script>."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sample_dashboard import REPO, TEMPLATE, Dashboard, Kpi, fill  # noqa: E402

logger = logging.getLogger(__name__)
VALUES: list[int] = [5, 8, 3, 9, 12, 7, 6, 11, 15, 9, 4, 8, 13, 10, 7, 9, 14, 16, 6, 5, 12,
                     18, 11, 9, 7, 13, 17]


def edge_dashboard() -> Dashboard:
    """Build the edge-case payload."""
    return Dashboard(
        meta={"company": "Склад — проверка крайних случаев", "period": "Октябрь 2026",
              "built_at": "27.10.2026", "source": "тест"},
        kpis=[
            Kpi("Остаток денег", "нет данных", None),
            Kpi("Просроченные поставки", "12", 50, better="down", compare_to="сентябрю"),
            Kpi("Выпуск", "1 000 шт", 0, compare_to="плану"),
        ],
        charts=[
            {"title": "Продажи по дням", "type": "line", "unit": "₽",
             "points": [{"label": f"{i:02d}.10", "value": v} for i, v in enumerate(VALUES, 1)]},
            {"title": "Пустой график", "type": "bar", "points": []},
            {"title": "Выручка по неделям, выгрузка неполная", "type": "bar", "unit": "₽",
             "points": [{"label": "30.09–06.10", "value": None},
                        {"label": "07.10–13.10", "value": None},
                        {"label": "14.10–20.10", "value": 420000},
                        {"label": "21.10–27.10", "value": 510000}]},
        ],
        tables=[{"title": "Выручка по менеджерам", "columns": ["Менеджер", "Выручка"],
                 "num_cols": [1], "rows": [],
                 "empty_note": "нет данных: выгрузка не охватывает весь период"}],
        attention=["</script><script>alert(1)</script> проверка экранирования"],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fill(TEMPLATE, edge_dashboard(), REPO / "tests/out/pulse-edge.html")
