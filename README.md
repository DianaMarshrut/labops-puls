# Пульс — дашборд руководителя по ссылке

Собирает главные цифры компании на одной HTML-странице: продажи, финансы, склад.
Страницу можно открыть в браузере и переслать ссылкой.

Пишешь «обнови пульс» — готово.

## Как поставить

### Claude Code

```
/plugin marketplace add DianaMarshrut/labops-puls
/plugin install puls@labopsai-puls
```

### Codex

```
codex plugin marketplace add DianaMarshrut/labops-puls
```

Затем `/plugins` → Install → начни новую сессию.

### Claude (claude.ai и приложение)

1. «Customize» → «Plugins» → «Add marketplace» → вставь `DianaMarshrut/labops-puls` → «Install».
2. Создай проект «Пульс» и напиши в нём: «Хочу дашборд по продажам».

Альтернатива — загрузить ZIP вручную:
1. Скачай `dist/puls.zip`. Распаковывать не нужно.
2. «Customize» → «Skills» → «+» → «+ Create skill» → «Upload a skill» → выбери `puls.zip`.

### ChatGPT

Создай проект «Пульс», добавь в файлы проекта `chat-instruction.md`.
Напиши в проекте: «Работай по инструкции из файлов проекта. Собери пульс».

## Откуда данные

1. **Excel / CSV-файл** — загрузи файл в чат (работает везде без настройки).
2. **Google Таблицы** — через коннектор Google Drive.
   Гайд: https://guides.labopsai.pro/google-workspace-claude
3. **Битрикс24** — через MCP.
   Гайд: https://guides.labopsai.pro/bitrix24-claude
4. **amoCRM** — через MCP.
   Гайд: https://guides.labopsai.pro/amocrm-claude
5. **МойСклад** — через MCP.
   Гайд: https://guides.labopsai.pro/moysklad-claude

Если 1С: выгрузи отчёт в Excel и кинь файл в чат.

## Ограничения

- Дашборд не обновляется сам — только по команде.
- При Excel каждое обновление требует свежей выгрузки.

## Команды

- «Обнови пульс»
- «Почему упала конверсия?»
- «Добавь метрику: средний чек»

## Безопасность

- Создай отдельного пользователя или ключ с правом только на чтение.
- Ключи и токены в чат не вставляй.
- Результат по умолчанию — HTML-файл `pulse.html`. Открывается локально без аккаунта.
- Публичная ссылка (Claude → Publish) — отдельный шаг. Любой, у кого есть ссылка, откроет страницу без пароля. Публикуй только если в дашборде нет чувствительных данных.

## Что в репозитории

| Путь | Для чего |
|---|---|
| `plugins/puls/skills/puls/` | Навык: `SKILL.md`, справочники `references/`, шаблон `templates/dashboard.html` |
| `dist/puls.zip` | Навык в архиве — для загрузки в Claude |
| `chat-instruction.md` | Навык одним текстом — для ChatGPT и Codex |
| `scripts/build.py` | Пересобирает `dist/puls.zip` и `chat-instruction.md` после правок |

## Для разработчика

Нужен Python 3.10+.

```
python3 scripts/build.py
```

Пишет `dist/puls.zip` и рядом `dist/puls.zip.txt` — список файлов и контрольную сумму SHA-256.

## Другие капсулы labopsai

- [Радар — утренняя сводка](https://github.com/DianaMarshrut/labops-radar)
- [След — встреча → задачи](https://github.com/DianaMarshrut/labops-sled)
