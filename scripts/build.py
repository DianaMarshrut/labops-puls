"""Build distributables for the puls capsule.

Produces:
  dist/puls.zip        -- skill folder for upload to claude.ai (puls/ is the zip root).
  chat-instruction.md  -- SKILL.md + references + template merged into one text for
                          ChatGPT / DeepSeek (paste as first message or attach as file).

Usage: python3 scripts/build.py
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "plugins/puls/skills/puls"
DIST = REPO / "dist"
REFERENCES: list[tuple[str, str]] = [
    ("references/sources.md", "Приложение 1. Подключение источников данных"),
    ("references/metrics.md", "Приложение 2. Готовые наборы цифр и правила расчёта"),
    ("references/publish.md", "Приложение 3. Постоянное место, ссылка и автообновление"),
]
TEMPLATE = "templates/dashboard.html"
ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def build_zip(skill_dir: Path, out: Path) -> Path:
    """Zip the skill folder so that the folder itself is the archive root.

    Args:
        skill_dir: Folder containing SKILL.md.
        out: Target .zip path.

    Returns:
        Path to the written archive.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    root = skill_dir.name
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if (path.is_file() and not path.name.startswith(".")
                    and "__pycache__" not in path.parts):
                info = zipfile.ZipInfo(f"{root}/{path.relative_to(skill_dir).as_posix()}",
                                       date_time=ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                info.create_system = 3
                zf.writestr(info, path.read_bytes())
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    listing = out.with_name(out.name + ".txt")
    listing.write_text(f"sha256 {digest}\n" + "\n".join(names) + "\n", encoding="utf-8")
    logger.info("Saved %s (%d files, sha256 %s)", out, len(names), digest[:12])
    return out


def strip_frontmatter(text: str) -> str:
    """Remove the YAML frontmatter block from a markdown file."""
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)


def build_chat_instruction(skill_dir: Path, out: Path) -> Path:
    """Merge SKILL.md, references and the template into one instruction text."""
    body = strip_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8")).strip()
    for rel, title in REFERENCES:
        body = body.replace(f"`{rel}`", f"«{title.split('. ', 1)[0]}» ниже")
    body = body.replace(f"шаблон `{TEMPLATE}`", "шаблон из «Приложения 4» ниже")
    body = body.replace(f"`{TEMPLATE}`", "шаблон из «Приложения 4» ниже")
    body = body.replace("из «Приложение ", "из «Приложения ")
    parts = [
        "# Инструкция для чата: капсула «Пульс» от labopsai",
        "",
        "Один раз: в ChatGPT создай проект «Пульс» и добавь этот файл в файлы проекта; "
        "в DeepSeek вставь этот текст первым сообщением в чат «Пульс» (или приложи файлом "
        "и напиши: «Работай по этой инструкции»). Дальше пиши в том же проекте или чате "
        "одну фразу: «обнови пульс».",
        "",
        "Ты работаешь в обычном чате. Источники данных: встроенный коннектор (если он есть "
        "в этом чате), ссылка, которую прислал пользователь (вебхук Битрикс24, Google Таблица), "
        "или загруженный файл. Других доступов к системам пользователя у тебя нет.",
        "",
        "---",
        "",
        body,
    ]
    for rel, title in REFERENCES:
        ref = (skill_dir / rel).read_text(encoding="utf-8").strip()
        ref = re.sub(r"\A# .*\n", "", ref).strip()
        parts += ["", "---", "", f"# {title}", "", ref]
    tpl = (skill_dir / TEMPLATE).read_text(encoding="utf-8").strip()
    parts += [
        "", "---", "",
        "# Приложение 4. Шаблон дашборда",
        "",
        "Скопируй шаблон целиком и замени только JSON внутри "
        '`<script id="puls-data" type="application/json">`.',
        "",
        "```html",
        tpl,
        "```",
        "",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Saved %s (%d chars)", out, out.stat().st_size)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    build_zip(SKILL_DIR, DIST / "puls.zip")
    build_chat_instruction(SKILL_DIR, REPO / "chat-instruction.md")
