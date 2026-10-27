"""Generate a sample deals export (Bitrix24-like) for testing the puls skill.

The data is synthetic and deterministic (fixed seed). Column names imitate a
typical CRM deal-list export in Russian.
"""

from __future__ import annotations

import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

logger = logging.getLogger(__name__)

STAGES: list[str] = ["Новая", "Переговоры", "Счёт выставлен", "Успешно", "Провал"]
MANAGERS: list[str] = ["Иванова А.", "Петров С.", "Сидорова Е.", "Кузнецов Д."]
HEADERS: list[str] = [
    "ID", "Название", "Стадия сделки", "Сумма", "Ответственный",
    "Дата создания", "Дата закрытия", "Дата изменения",
]


def build(path: Path, today: date, n_deals: int = 160, seed: int = 42) -> Path:
    """Write a synthetic deals workbook.

    Args:
        path: Output .xlsx path.
        today: Reference date ("now" for the export).
        n_deals: Number of deal rows.
        seed: Random seed for reproducibility.

    Returns:
        The written path.
    """
    rnd = random.Random(seed)
    wb = Workbook()
    ws = wb.active
    ws.title = "Сделки"
    ws.append(HEADERS)
    for i in range(1, n_deals + 1):
        created = today - timedelta(days=rnd.randint(0, 60))
        stage = rnd.choices(STAGES, weights=[2, 3, 2, 4, 2])[0]
        amount = rnd.randrange(20_000, 400_000, 5_000)
        closed = None
        if stage in ("Успешно", "Провал"):
            closed = min(today, created + timedelta(days=rnd.randint(1, 20)))
        changed = closed or min(today, created + timedelta(days=rnd.randint(0, 30)))
        ws.append([
            i, f"Сделка №{i}", stage, amount, rnd.choice(MANAGERS),
            created, closed, changed,
        ])
    for col in ("F", "G", "H"):
        for cell in ws[col][1:]:
            cell.number_format = "DD.MM.YYYY"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    logger.info("Saved %s (%d deals)", path, n_deals)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/out/sample-deals.xlsx")
    build(out, today=date(2026, 10, 27))
