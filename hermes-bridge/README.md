# Linky ↔ Hermes: пилот голосовой постановки задач

Вы звоните Linky (ваш dot в ChatGPT) и голосом ставите задачу. Linky передаёт её
координатору Hermes, команда Hermes выполняет и проверяет работу, а Linky сообщает
статус и итог в чате, в том числе после звонка.

```
 Вы ──голос──▶ Linky (dot, ChatGPT)
                  │  MCP (HTTPS, токен/OAuth)            ← custom MCP server в ChatGPT
                  ▼
        linky-hermes-bridge  (этот каталог; на том же хосте, что Hermes, слушает 127.0.0.1)
          • SQLite: проект ↔ задача Linky (LT-…) ↔ карточка Hermes (t_…) ↔ ключ идемпотентности
          • фоновая синхронизация, последний подтверждённый статус + время
                  │  официальный CLI: hermes kanban create/show --json
                  ▼
        Hermes Kanban: координатор → исполнители → проверяющий (reviewer)
```

## 1. Официальные способы связи (что проверено)

### Сторона Hermes (документация `hermes-agent`, последняя версия на PyPI — **0.19.0**)

| Что нужно | Официальный интерфейс | Где описано |
|---|---|---|
| Версия сервера | `GET /api/status` дашборда (`:9119`) возвращает версию агента и состояние шлюза; `hermes --version` | web-dashboard → REST API |
| Какие операции есть | `GET /v1/capabilities` API-сервера (`:8642`, Bearer `API_SERVER_KEY`): `run_submission`, `run_status`, `run_events_sse`, `run_stop`, `run_approval` | api-server |
| Запуск | `POST /v1/runs` с `Idempotency-Key` (повтор отдаёт тот же `run_id`, хранится 24 ч, переживает рестарт) | api-server → Runs API |
| Статус | `GET /v1/runs/{id}` (опрос), `GET /v1/runs/{id}/events` (SSE), `stop`, `approval`, `clarify` | api-server → Runs API |
| **Команда: координатор, исполнители, проверка** | **Hermes Kanban**: `hermes kanban create … --assignee <координатор> --goal --idempotency-key K --json`, `hermes kanban show <id> --json`; статусы `triage/todo/ready/running/blocked/review/done`, проверка через `request-review`/`--reviewer` | kanban |
| Доставка событий наружу | webhooks и `kanban notify-subscribe` (в Telegram, Slack и т. п.) | messaging/webhooks, kanban |

**Выбор:** основной путь — Kanban, потому что только у него есть координатор, исполнители,
проверка и блокировки «нужна помощь». Runs API реализован в `bridge/hermes.py` как запасной
путь. Он подходит, если мост будет стоять не на хосте Hermes, но тогда статус будет без
разбивки «кто выполняет / кто проверяет».

Важно по безопасности (из документации): REST-маршруты Kanban `/api/plugins/kanban/*`
**не аутентифицируются** и рассчитаны на localhost. Наружу их выставлять нельзя.
Поэтому мост работает с Kanban через CLI на том же хосте, а наружу открывает только
свой MCP-эндпоинт с токеном.

### Сторона Dot (Linky)

Из этой среды сайты OpenAI недоступны (прокси), поэтому сторона Dot проверена только
по справке OpenAI в поисковой выдаче. Перепроверить в вашем аккаунте:

- **Вызов внешнего сервиса:** custom MCP server, раздел ChatGPT **Plugins → + → Add custom
  MCP server** (help.openai.com «Connecting custom MCP servers in ChatGPT»). Нужен
  публичный HTTPS-URL. Для закрытых серверов OpenAI упоминает Secure MCP Tunnel.
  Основной вариант аутентификации — OAuth.
- **Доставка обновлений:** dot присылает проактивные обновления и результаты
  запланированных задач в свой чат («Getting started with your dot»). Проактивные
  проверки используют инструменты только на чтение. Поэтому статус-инструменты моста
  помечены `readOnlyHint`.
- **Прямой push от внешней системы в чат dot** (webhook в Linky) в документации
  не найден. Итог после звонка приходит через запланированную проверку Linky
  (`hermes_pending_updates`), см. `linky/instructions.md`.

**Прямого подключения Linky → Hermes нет.** Hermes не говорит по MCP как сервер для
ChatGPT, а его Kanban нельзя открывать наружу. Поэтому нужен закрытый промежуточный
сервис — этот мост.

## 2. Как устроен мост

| Требование ТЗ | Реализация |
|---|---|
| Связь проект ↔ задача Linky ↔ ID Hermes | таблица `tasks`: `project_slug`, `linky_task_id` (LT-…), `hermes_card_id` (t_…), `hermes_run_id`, `idempotency_key` |
| Передавать Hermes только нужное | `build_brief`: проект, краткий контекст проекта, задача, критерии, правила пилота. Переписка не передаётся, email/телефоны/номера карт/ключи вырезаются. В БД сохраняется ровно то, что ушло (`brief_sent`) |
| Статус, время, кто выполняет/проверяет, итог, помощь | `hermes_project_status` / `hermes_task_status`: `status_ru`, `updated_at`, `executor`, `reviewer`, `result`, `needs_help`, дерево карточек `team`, готовая фраза `say` |
| Нет обновлений → последний подтверждённый статус | `confirmed_at` + `stale=true` + «последний подтверждённый статус на ДД.ММ ЧЧ:ММ» |
| Hermes работает после звонка | работа идёт в Kanban, звонок на неё не влияет; мост опрашивает Hermes в фоне (`SYNC_INTERVAL`) |
| Повтор после обрыва без дубля | 3 уровня: `client_request_id` от Linky → отпечаток «проект+текст» за 24 ч → `--idempotency-key` в Hermes (тот же ключ при повторной отправке) |
| Итог в чате | `hermes_pending_updates` + `hermes_ack_update` (итог сообщается один раз) |

Инструменты MCP: `hermes_submit_task`, `hermes_project_status`, `hermes_task_status`,
`hermes_pending_updates`, `hermes_ack_update`, `hermes_list_projects`.

## 3. Приёмка на тестовых данных: что реально прошло

Запуск: `python3 demo/acceptance.py`. Результат: `demo/acceptance_result.json`. **14/14 PASS.**

Честно о том, что было настоящим:

- **Настоящее:** мост целиком — MCP по HTTP, проверка токена, SQLite, защита от дублей,
  фоновая синхронизация, расчёт статуса, вырезание личных данных, устаревший статус.
- **Имитация Linky:** скриптовый MCP-клиент, который шлёт те же вызовы, что сделает dot.
  Реального голосового звонка не было.
- **Имитация Hermes:** макет `mock/hermes_mock.py` по документированному контракту
  (`kanban create/show --json`, idempotency-key, `/api/status`, `/v1/capabilities`).
  Команда (координатор → executor → reviewer) имитируется по времени. **Настоящий Hermes
  не запускался:** установку `hermes-agent` в песочнице запретили правила безопасности,
  а адреса и ключа вашего сервера у меня нет.

| Шаг сценария | Итог |
|---|---|
| 0. Версия Hermes и операции запуска/статуса | PASS (на макете) |
| 0b. Без токена доступа к мосту нет (401) | PASS |
| 1. «Звонок 1»: задача поставлена, Hermes принял, ID сохранён | PASS |
| 1c. В Hermes ушёл только нужный контекст, email/телефон скрыты | PASS |
| 2. Повтор после обрыва (с тем же ID и без ID) — одна задача, одна карточка | PASS |
| 3. После «звонка» работа идёт: видно исполнителя, потом проверяющего | PASS |
| 4. Итог готов для сообщения в чате и не повторяется после отметки | PASS |
| 5. «Звонок 2»: статус по проекту без повторного объяснения | PASS |
| 6. «Нужна помощь» (запрос на внешнюю отправку) видна и озвучивается | PASS |
| 7. Hermes недоступен → последний подтверждённый статус и время | PASS |

## 4. Запуск на сервере Hermes (после согласования)

```bash
cd hermes-bridge
cat > .env <<'EOF'            # chmod 600 .env, в git не коммитить
BRIDGE_TOKEN=<openssl rand -hex 32>
BRIDGE_PATH_SECRET=<openssl rand -hex 12>
API_SERVER_KEY=<ключ API-сервера Hermes>
COORDINATOR_PROFILE=coordinator
REVIEWER_PROFILE=reviewer
EOF
set -a; . ./.env; set +a
python3 -m bridge check        # версия Hermes, features, доступ к kanban CLI
python3 -m bridge serve        # 127.0.0.1:8765, наружу — только через туннель
```

Профили `coordinator` и `reviewer` (и исполнители) должны существовать в Hermes.
Координатор — профиль с toolsets `kanban, memory`, как рекомендует документация.

### Что проверить на сервере (не удалось проверить отсюда)
1. Фактическая версия: `hermes --version`, `curl 127.0.0.1:9119/api/status`.
2. Поля JSON `hermes kanban show <id> --json`: как называются дети, проверяющий
   и итог. Под них подстраивается `normalize_card` в `bridge/hermes.py`.
3. Что `kanban create --idempotency-key` на повторе возвращает ту же карточку в `--json`.
4. Тариф ChatGPT: доступны ли dot'у custom MCP servers с инструментами записи
   (`hermes_submit_task`). По сторонним источникам на Plus/Pro запись бывает ограничена.
   Если так, нужен Business или режим разработчика.

## 5. Риски и границы пилота
- Боевые данные, внешние отправки и платные прогоны в пилот не входят. Эти правила
  добавляются в каждую задачу для Hermes, а координатор должен блокировать карточку
  с запросом согласования (шаг 6).
- Прямой push в чат Linky не подтверждён, поэтому итог после звонка приходит с задержкой
  до интервала запланированной проверки (например, 15 минут).
- Мост — единая точка доступа к команде с терминалом. Нужен только туннель с токеном
  или OAuth, сам мост слушает только localhost, токены хранятся в `.env` с правами 600.
