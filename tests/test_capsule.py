"""Checks for the puls capsule: manifests, skill frontmatter, zip, chat text, template."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "plugins/puls/skills/puls"
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "scripts"))

import build_sample_dashboard as bsd  # noqa: E402
import make_sample_xlsx as msx  # noqa: E402


def _frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md has no frontmatter"
    return dict(line.split(": ", 1) for line in m.group(1).splitlines())


def test_manifests_are_valid_json() -> None:
    mp = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    pl = json.loads((REPO / "plugins/puls/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert mp["plugins"][0]["source"] == "./plugins/puls"
    assert mp["plugins"][0]["name"] == pl["name"] == "puls"


def test_skill_frontmatter_limits() -> None:
    fm = _frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
    assert fm["name"] == "puls" and len(fm["name"]) <= 64
    assert 0 < len(fm["description"]) <= 200  # claude.ai upload limit


def test_shipped_zip_matches_skill_and_checksum() -> None:
    """Check the committed dist/puls.zip as is, without rebuilding it."""
    zpath = REPO / "dist/puls.zip"
    listing = (REPO / "dist/puls.zip.txt").read_text(encoding="utf-8").split()
    assert listing[0] == "sha256"
    assert hashlib.sha256(zpath.read_bytes()).hexdigest() == listing[1]
    expected = sorted(f"puls/{f.relative_to(SKILL).as_posix()}"
                      for f in SKILL.rglob("*") if f.is_file())
    with zipfile.ZipFile(zpath) as zf:
        assert sorted(zf.namelist()) == expected == sorted(listing[2:])
        names = zf.namelist()
        assert all(n.startswith("puls/") for n in names)
        assert "puls/SKILL.md" in names
        fm = _frontmatter(zf.read("puls/SKILL.md").decode("utf-8"))
        assert fm["name"] == "puls"
        for f in SKILL.rglob("*"):
            if f.is_file():
                assert zf.read(f"puls/{f.relative_to(SKILL).as_posix()}") == f.read_bytes()


def test_build_zip_is_reproducible(tmp_path: Path) -> None:
    """Same content gives the same archive even when file times differ."""
    import os
    import shutil

    import build

    copy = tmp_path / "src" / "puls"
    shutil.copytree(SKILL, copy)
    first = build.build_zip(copy, tmp_path / "a.zip").read_bytes()
    for f in copy.rglob("*"):
        os.utime(f, (1_000_000_000, 1_000_000_000))
    second = build.build_zip(copy, tmp_path / "b.zip").read_bytes()
    assert first == second
    assert first == (REPO / "dist/puls.zip").read_bytes()


def test_build_zip_in_temp_dir(tmp_path: Path) -> None:
    import build  # scripts/build.py

    out = build.build_zip(SKILL, tmp_path / "puls.zip")
    with zipfile.ZipFile(out) as zf:
        assert all(n.startswith("puls/") for n in zf.namelist())


def test_chat_instruction_is_current(tmp_path: Path) -> None:
    import build

    fresh = build.build_chat_instruction(SKILL, tmp_path / "c.md").read_text(encoding="utf-8")
    assert fresh == (REPO / "chat-instruction.md").read_text(encoding="utf-8")


def test_chat_instruction_is_self_contained() -> None:
    text = (REPO / "chat-instruction.md").read_text(encoding="utf-8")
    assert "references/" not in text and "templates/" not in text
    assert 'id="puls-data"' in text
    assert "ПРОВЕРИТЬ" not in text


def test_template_payload_is_valid_json() -> None:
    html = (SKILL / "templates/dashboard.html").read_text(encoding="utf-8")
    a = html.index('<script id="puls-data" type="application/json">')
    a = html.index(">", a) + 1
    data = json.loads(html[a:html.index("</script>", a)])
    assert {"meta", "kpis", "charts", "tables", "attention"} <= data.keys()
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in html


def _deal(stage: str, amount: float, created: date, closed: date | None = None,
          changed: date | None = None) -> bsd.Deal:
    return bsd.Deal(stage, amount, "M", created, closed, changed or closed or created)


def test_metrics_on_known_deals() -> None:
    today = date(2026, 10, 27)  # current period 30.09-27.10, previous 02.09-29.09
    deals = [
        _deal("Новая", 0, date(2026, 9, 1)),  # data starts before the previous period
        _deal("Успешно", 100_000, date(2026, 10, 1), date(2026, 10, 5)),
        _deal("Успешно", 300_000, date(2026, 10, 2), date(2026, 10, 20)),
        _deal("Провал", 50_000, date(2026, 10, 3), date(2026, 10, 10)),
        _deal("Успешно", 200_000, date(2026, 9, 5), date(2026, 9, 10)),
        _deal("Провал", 10_000, date(2026, 9, 6), date(2026, 9, 12)),
        _deal("Переговоры", 70_000, date(2026, 10, 1), changed=date(2026, 10, 2)),
    ]
    k = {x.label: x for x in bsd.compute(deals, today, date(2026, 9, 1)).kpis}
    rev = k["Выручка (успешные сделки)"]
    assert rev.value == bsd.money(400_000) and rev.delta_pct == 100.0
    assert k["Новые сделки"].value == "4" and k["Новые сделки"].delta_pct == 100.0
    assert k["Конверсия в успех"].value == "67%"
    assert k["Конверсия в успех"].delta_pct == round(200 / 3 - 50, 1)
    assert k["Средний чек"].value == bsd.money(200_000) and k["Средний чек"].delta_pct == 0.0
    assert k["Без движения > 14 дней"].value == "2"


def test_no_data_vs_zero() -> None:
    today = date(2026, 10, 27)
    recent = [_deal("Новая", 0, date(2026, 10, 20))]
    # Export starts inside the current period: both periods are "no data", chart too.
    dash = bsd.compute(recent, today, date(2026, 10, 15))
    k = {x.label: x for x in dash.kpis}
    assert k["Выручка (успешные сделки)"].value == bsd.NO_DATA
    weeks = dash.charts[0]["points"]
    assert len(weeks) == 4 and all(p["value"] is None for p in weeks[:3])
    assert all(p["label"] for p in weeks)
    assert dash.tables[0]["rows"] == [] and "нет данных" in dash.tables[0]["empty_note"]
    # Full export with only recent deals: revenue is a real zero, average check is "no data".
    dash = bsd.compute(recent, today, date(2026, 8, 1))
    k = {x.label: x for x in dash.kpis}
    assert k["Выручка (успешные сделки)"].value == bsd.money(0)
    assert k["Средний чек"].value == bsd.NO_DATA
    assert k["Конверсия в успех"].value == bsd.NO_DATA
    # Incomplete export that still contains an old deal: an old row proves nothing.
    old = recent + [_deal("Успешно", 9, date(2026, 8, 1), date(2026, 8, 2))]
    k = {x.label: x for x in bsd.compute(old, today, date(2026, 10, 15)).kpis}
    assert k["Выручка (успешные сделки)"].value == bsd.NO_DATA


def test_bitrix_pages_read_to_the_end() -> None:
    """Old deal closed today and an old open deal sit on the last page: both must count."""
    today = date(2026, 10, 27)
    recent = [{"stage": "Новая", "amount": 0, "created": today - timedelta(days=i % 20),
               "closed": None, "changed": today} for i in range(100)]
    old_won = {"stage": "Успешно", "amount": 900_000, "created": date(2025, 10, 1),
               "closed": today, "changed": today}
    old_open = {"stage": "Переговоры", "amount": 0, "created": date(2025, 9, 1),
                "closed": None, "changed": date(2025, 12, 1)}
    records = recent + [old_won, old_open]  # newest first, like order DATE_CREATE DESC

    def fetch(start: int) -> dict:
        page = {"result": records[start:start + 50]}
        if start + 50 < len(records):
            page["next"] = start + 50
        return page

    rows = bsd.read_all_pages(fetch)
    assert len(rows) == len(records) and fetch(0).get("next") == 50
    deals = [_deal(r["stage"], r["amount"], r["created"], r["closed"], r["changed"]) for r in rows]
    k = {x.label: x for x in bsd.compute(deals, today, date(2025, 1, 1)).kpis}
    assert k["Выручка (успешные сделки)"].value == bsd.money(900_000)
    assert k["Без движения > 14 дней"].value == "1"
    first_page = deals[:50]  # what a chat that cannot change the link would see
    k1 = {x.label: x for x in bsd.compute(first_page, today, date(2025, 1, 1)).kpis}
    assert k1["Выручка (успешные сделки)"].value != k["Выручка (успешные сделки)"].value
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "пока в ответе есть\n    `next`" in skill and "до начала периода" not in skill


def test_fill_escapes_script_close(tmp_path: Path) -> None:
    import build_edge_dashboard as bed

    out = bsd.fill(bsd.TEMPLATE, bed.edge_dashboard(), tmp_path / "e.html").read_text("utf-8")
    a = out.index('<script id="puls-data" type="application/json">')
    a = out.index(">", a) + 1
    block = out[a:out.index("</script>", a)]
    data = json.loads(block)
    assert data["attention"][0].startswith("</script><script>")
    assert "<" not in block


def test_sample_metrics(tmp_path: Path) -> None:
    xlsx = msx.build(tmp_path / "d.xlsx", today=date(2026, 10, 27))
    dash = bsd.compute(bsd.read_deals(xlsx), date(2026, 10, 27), date(2026, 8, 28))
    assert 3 <= len(dash.kpis) <= 7
    out = bsd.fill(bsd.TEMPLATE, dash, tmp_path / "p.html")
    assert "Выручка" in out.read_text(encoding="utf-8")


def test_bitrix_link_path_in_all_chats() -> None:
    """Bitrix24 webhook link is the main path in every chat; old 'Claude Code only' text is gone."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    src = (SKILL / "references/sources.md").read_text(encoding="utf-8")
    chat = (REPO / "chat-instruction.md").read_text(encoding="utf-8")
    for text in (skill, src, chat):
        assert "только Claude Code" not in text
        assert "не подключаем Битрикс24 напрямую" not in text
    assert "Ссылка вебхука — основной путь, в любом чате" in src
    assert "генераторе запросов" in src and "`next`" in src and "50 записей" in src
    assert "URLs you've shared" in src
    assert "каждый раз руками" in skill  # Excel is the honest last fallback


VERSION = "0.3.0"


def test_versions_match() -> None:
    """plugin.json, the marketplace entry and the shipped zip all carry one version."""
    mp = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    pl = json.loads((REPO / "plugins/puls/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    entry = next(p for p in mp["plugins"] if p["name"] == "puls")
    assert pl["version"] == entry["version"] == VERSION
    with zipfile.ZipFile(REPO / "dist/puls.zip") as zf:
        assert zf.read("puls/SKILL.md") == (SKILL / "SKILL.md").read_bytes()


# --- Security -------------------------------------------------------------------------

TEMPLATE_PATH = SKILL / "templates/dashboard.html"
SHIPPED_TEXT = [REPO / "README.md", REPO / "chat-instruction.md",
                *sorted((REPO / "plugins/puls").rglob("*.md")),
                *sorted((REPO / "plugins/puls").rglob("*.json")), TEMPLATE_PATH]


def test_template_loads_nothing_external() -> None:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    low = html.lower()
    for bad in ("src=", "href=", "url(", "@import", "fetch(", "xmlhttprequest", "websocket",
                "eventsource", "import(", "<iframe", "<link", "<img", "sendbeacon", "eval(",
                "new function", "document.write", "outerhtml", "insertadjacenthtml"):
        assert bad not in low, bad
    # innerHTML is only ever cleared, never filled with data
    assert re.findall(r"innerHTML\s*=\s*([^;]+);", html) == ['""']
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
    assert "connect-src 'none'" in html


def test_template_masks_webhook_key() -> None:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "function safe(" in html and "n.textContent = safe(text)" in html


def test_template_in_browser_with_hostile_values(tmp_path: Path) -> None:
    """Render hostile strings in a real browser: no script runs, no request leaves, key masked."""
    from playwright import sync_api as pw  # required: see README, "Для разработчика"

    import build_edge_dashboard as bed

    dash = bed.edge_dashboard()
    hook = "https://demo.bitrix24.ru/rest/1/s3cr3tKEY123/crm.deal.list.json"
    evil = '<img src="https://example.com/x.png" onerror="window.__pwned=1">'
    dash.meta["source"] = hook
    dash.meta["company"] = evil
    dash.kpis[0].label = "</script><script>window.__pwned=2</script>"
    dash.tables[0]["rows"] = [[evil, "1"]]
    dash.attention.append("<svg onload=window.__pwned=3>")
    with __import__("pytest").raises(ValueError):  # the key must never reach the file
        bsd.fill(bsd.TEMPLATE, dash, tmp_path / "evil.html")
    dash.meta["source"] = "Битрикс24, сделки"
    out = bsd.fill(bsd.TEMPLATE, dash, tmp_path / "evil.html")
    assert "s3cr3tKEY123" not in out.read_text(encoding="utf-8")
    # Last guard on screen: a key that slipped into the source is masked when shown.
    leak = out.with_name("leak.html")
    leak.write_text(out.read_text(encoding="utf-8").replace(
        "Битрикс24, сделки", hook.replace("/", "\\/")), encoding="utf-8")
    broken = out.with_name("broken.html")
    src = out.read_text(encoding="utf-8")
    a = src.index('<script id="puls-data" type="application/json">') + 48
    broken.write_text(src[:a] + hook + " {" + src[a:], encoding="utf-8")
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        requests: list[str] = []
        dialogs: list[str] = []
        page.on("request", lambda r: requests.append(r.url))
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        page.goto(out.as_uri())
        page.wait_for_timeout(300)
        assert page.evaluate("window.__pwned") is None
        assert [u for u in requests if not u.startswith("file:")] == []
        assert dialogs == []
        assert page.locator("img").count() == 0
        body = page.inner_text("body")
        assert evil in body  # shown as plain text
        for f in (leak, broken):
            page.goto(f.as_uri())
            page.wait_for_timeout(200)
            body = page.inner_text("body")
            assert "s3cr3tKEY123" not in body, f.name
        assert "Ошибка в данных дашборда" in body  # broken.html shows an error, not the key
        page.goto(leak.as_uri())
        page.wait_for_timeout(200)
        assert "/rest/1/***" in page.inner_text("body")
        assert "s3cr3tKEY123" not in page.title()
        assert [u for u in requests if not u.startswith("file:")] == []
        browser.close()


BITRIX_METHOD = re.compile(
    r"\b(?:crm|tasks|task|user|department|catalog|sale|im|disk|lists|telephony|calendar|"
    r"entity|bizproc|socialnetwork|timeman|voximplant|imopenlines|landing|documentgenerator)"
    r"(?:\.[a-z_]+)+\b")


def test_only_read_only_bitrix_methods() -> None:
    """Every Bitrix24 REST method named anywhere must be a read method (.list/.get/.fields)."""
    found: set[str] = set()
    for f in SHIPPED_TEXT:
        for m in BITRIX_METHOD.finditer(f.read_text(encoding="utf-8")):
            name = re.sub(r"\.(json|html|md|py)$", "", m.group(0))
            if name.endswith((".ru", ".com")):
                continue
            found.add(name)
    assert found, "expected crm.deal.list to be documented"
    # calendar.event.get.nearest (radar section of the shared README) is a read method too
    bad = {n for n in found if n.split(".")[-1] not in {"list", "get", "fields", "nearest"}}
    assert not bad, bad


def test_no_secrets_or_internal_paths() -> None:
    pattern = re.compile(r"/rest/\d+/[A-Za-z0-9]{8,}/|/home/|myaiagent|\.claude-lab|"
                         r"(?:api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_-]{12,}",
                         re.I)
    for f in [*SHIPPED_TEXT, REPO / "scripts/build.py", *sorted((REPO / "tests").glob("*.py"))]:
        if f.name == "test_capsule.py":
            continue
        assert not pattern.search(f.read_text(encoding="utf-8")), f


def test_plugin_has_no_hooks_or_install_scripts() -> None:
    root = REPO / "plugins/puls"
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    assert all(f == ".claude-plugin/plugin.json" or f.startswith("skills/puls/") for f in files)
    assert not any(f.endswith((".sh", ".py", ".js", ".ps1", ".bat")) for f in files)
    pl = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    allowed = {"name", "version", "description", "author", "homepage", "license", "keywords"}
    assert set(pl) <= allowed, set(pl) - allowed
    mp = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in mp["plugins"] if p["name"] == "puls")
    assert not {"hooks", "mcpServers", "commands", "agents", "lspServers"} & set(entry)


def test_security_warnings_present() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    pub = (SKILL / "references/publish.md").read_text(encoding="utf-8")
    for text in (skill, pub):
        assert "может открыть любой, у кого она есть" in text
    assert "Ключ внутри ссылки вебхука — это и есть доступ" in skill
    assert "отдельный сотрудник" in skill and "«Чтение»" in skill
    assert "Ключ внутри ссылки" in readme and "только на чтение" in readme


# --- Main principle -----------------------------------------------------------------------


def test_main_principle_in_skill_and_readme() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    pub = (SKILL / "references/publish.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "### Шаг 0. Постоянное место" in skill
    assert "**этот же** артефакт" in skill and "## Автообновление" in pub
    assert "каждый раз руками" in readme
    assert "| Где | Что делаешь один раз | Что делаешь каждый раз |" in readme
    for who in ("| Claude |", "| ChatGPT |", "| DeepSeek |"):
        assert who in readme
    # every "каждый раз" cell starts with the single phrase
    puls_part = readme.split("# Пульс", 1)[1].split("\n# ", 1)[0]  # README is shared
    rows = [ln for ln in puls_part.splitlines() if ln.startswith(("| Claude |", "| ChatGPT |",
                                                                   "| DeepSeek |"))]
    assert len(rows) == 3
    assert all(r.rstrip("|").split("|")[-1].strip().startswith("Пишешь «обнови пульс»")
               for r in rows)


def test_readme_relative_paths_exist() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for rel in re.findall(r"`((?:plugins|dist|scripts|tests|\.claude-plugin)/[^`\s]*|"
                          r"chat-instruction\.md|LICENSE|requirements-dev\.txt)`", readme):
        assert (REPO / rel).exists(), rel
