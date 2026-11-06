# Документация для устной защиты: Control_1C_version и консоль «Норд»

Этот текст написан так, чтобы его можно было проговаривать на защите. Отдельного файла с техническим заданием в репозитории нет: номера требований (1.1, 2.1, 5.2 и так далее) взяты из `summary` маршрутов FastAPI и из таблицы в корневом `README.md`. Ниже описан только тот код, который лежит в дереве на ветке `main`. Если функция есть, но её никто не вызывает, это сказано прямо.

Консоль называется «Норд». Это имя пакета в `frontend/package.json` (`"name": "nord"`) и заголовок страницы в `frontend/index.html`.

---

## 1. Введение

### Зачем система

Система ведёт учёт конфигураций 1С у клиентов фирмы сопровождения. Специалист видит, какая информационная база отстала от актуального релиза, сообщает клиенту, клиент выбирает дату, специалист проводит работу по статусам, а руководитель отдела смотрит отчёт: кого уже обновили и что ещё в плане.

Пользователи системы — четыре роли:

- администратор заводит людей и назначает роли;
- специалист по сопровождению ведёт клиентов, каталог, проверки, окна записи и статусы работ;
- руководитель отдела сопровождения читает реестр и отчёты, но не меняет данные;
- клиент видит только свою организацию, свои уведомления и свои заявки и может выбрать дату обновления.

### Стек и почему он такой

Бэкенд — **FastAPI**. Это HTTP-фреймворк на Python: маршрут объявляется функцией, тело запроса проверяет Pydantic, интерактивная схема сама поднимается на `/docs`. Для учебного MVP этого достаточно, и `scripts/smoke.py` как раз ходит в `/openapi.json` и `/docs`.

Доступ к PostgreSQL — **SQLAlchemy 2 в асинхронном режиме** и драйвер **asyncpg**. Обработчик запроса не блокирует процесс, пока база отвечает: сессия запроса — `AsyncSession`. Точка входа — `uvicorn main:app`.

Схему базы не создаёт `Base.metadata.create_all`. Её накатывает **Alembic** (`alembic upgrade head` в `docker/entrypoint.sh`). Миграции можно прочитать, откатить и повторить; `create_all` этого не умеет и не хранит историю.

База — **PostgreSQL 16** (образ `postgres:16-alpine`). Нужны частичный уникальный индекс `uq_configuration_versions_current`, `SELECT … FOR UPDATE` на слоте и обычные внешние ключи. Всё это есть в PostgreSQL и описано в миграциях.

Пароль хранится как bcrypt-хеш (`hash_password`). Сессия после входа — **JWT** (библиотека PyJWT, алгоритм `HS256`): клиент присылает заголовок `Authorization: Bearer …`, сервер не хранит таблицу сессий.

Всё поднимается **Docker Compose**: три сервиса `db`, `api`, `web`.

Фронтенд — **Vite + React 19 + TypeScript**. Vite в разработке проксирует `/api` и `/health` на порт 8000, в Compose тот же прокси делает nginx. TypeScript включён со `strict` и `noUnusedLocals`, поэтому неиспользуемый импорт просто не соберётся.

### Как запустить для демо

Полный стенд из корня репозитория:

```bash
docker compose up --build
```

Контейнер API ждёт Postgres, выполняет `alembic upgrade head` и запускает uvicorn. Демо-данные создаёт уже само приложение в `lifespan`, не скрипт входа. После старта:

- консоль «Норд»: http://127.0.0.1:8080
- API: http://127.0.0.1:8000
- схема: http://127.0.0.1:8000/docs
- Postgres с хоста: `localhost:5433`, пользователь `postgres`, пароль `postgres`, база `control_1c_version`

Если порт 8080 на машине занят, консоль можно поднять отдельно, когда API уже слушает 8000:

```bash
cd frontend
npm install
npm run dev
```

Открывается http://127.0.0.1:5173 . Vite проксирует `/api` и `/health` на `http://127.0.0.1:8000`.

Проверка без браузера: `curl -sS http://127.0.0.1:8000/health`, затем `curl -sS http://127.0.0.1:8000/health/ready`, затем `python scripts/smoke.py`.

Учётные записи демо перечислены в разделе 10. На экране входа те же четыре пары почта/пароль показаны как подсказка учебного стенда.

---

## 2. Доменная модель

Связи такие. Организация-клиент имеет установки. Установка — это пара «клиент + конфигурация 1С» плюс конкретный установленный релиз и необязательное имя информационной базы. У конфигурации в каталоге много релизов, но текущий (`is_current`) один. Проверка сравнивает установленный релиз с текущим и сохраняет снимок. Уведомление адресовано одному портальному пользователю. Слот — окно специалиста на дату и время. Заявка на обновление ссылается на установку, запоминает исходный и целевой релиз и необязательно занимает слот. Смена статуса пишется в историю и не переписывается.

### Клиент

Таблица `clients`, модель `Client` в `src/data/models/clients.py`. Поля: `company_name`, `phone`, `email` (все уникальны), `responsible_employee_id` — сотрудник, который ведёт организацию. Удаление сотрудника не удаляет клиента: внешний ключ `ON DELETE SET NULL`.

Портальный пользователь связан с клиентом полем `users.client_id`. Это другая связь: ответственный — сотрудник фирмы, портальный пользователь — человек со стороны клиента.

### Конфигурация 1С и версия

`Configuration` — строка каталога, например «Бухгалтерия предприятия». Имя уникально.

`ConfigurationVersion` — релиз: строка `version` (до 64 символов), необязательная дата `released_at`, флаг `is_current`, заметка `notes`. Пара `(configuration_id, version)` уникальна ограничением `uq_configuration_version`.

### Одна текущая версия: `uq_configuration_versions_current`

В модели и в первой миграции объявлен частичный уникальный индекс:

```text
Index(
    "uq_configuration_versions_current",
    "configuration_id",
    unique=True,
    postgresql_where=text("is_current IS TRUE"),
)
```

Индекс смотрит только строки, где `is_current` истинно. Сколько угодно старых релизов с `is_current = false` допустимо. Вторая строка с `is_current = true` на ту же конфигурацию нарушает индекс. `flush_session` и `commit_session` превращают такой `IntegrityError` в ответ **409** с текстом `Data conflict`.

Код старается не доходить до конфликта: перед тем как пометить новый релиз текущим, `clear_current` снимает флаг с остальных. Снять флаг с единственного текущего релиза, пока есть другие, `touch_current_flag` не даёт: ответ **422**, «сначала назначьте другую версию текущей».

Если в базе каким-то образом окажутся две текущие (ручной SQL в обход API), индекс это запретит на записи. Чтение `map_current_versions` складывает результат в словарь по `configuration_id`: при двух строках в словаре осталась бы одна, последняя. До записи двух строк индекс не пускает, так что этот крайний случай — про обход ограничений, а не про штатный путь.

### Установка у клиента

`ClientConfiguration`, таблица `client_configurations`. Уникальность пары клиент+конфигурация — `uq_client_configuration`. Одна организация не может иметь две установки одной и той же конфигурации; имя базы различает базы внутри одной установки, а не две строки. Повторная привязка даёт **409** `This client already has that configuration`.

`installed_version_id` обязан принадлежать той же конфигурации. Это проверяет `ensure_version_of_configuration`, иначе **422**.

Удалить установку можно, только если нет заявок (`ScheduledUpdate`). Проверки версий при удалении установки удаляются вместе с ней: у связи `checks` стоит `cascade="all, delete-orphan"`, а внешний ключ `ON DELETE CASCADE`.

### Проверка актуальности

`VersionCheck` — снимок, его не переписывают. Новый запуск добавляет строку. Поля: какой релиз был установлен, какой был актуальным, флаг `is_outdated`, кто проверил и когда.

`is_outdated` считается сравнением идентификаторов, не текста номера: `installed_version_id != current.id`. Две разные строки с одинаковым текстом версии система считает разными релизами, но уникальный индекс `uq_configuration_version` такой пары и не пустит.

Если у конфигурации нет текущего релиза, проверка этой установки не создаётся: она попадает в `skipped` с причиной `Configuration has no current version`.

Список «кому пора обновляться» (`outdated_report`) считается заново по каталогу, а не по архиву проверок. Архив — это `GET /api/version-checks`. Живой список — `GET /api/version-checks/outdated` и отчёт руководителя.

В ответе карточки установки `is_outdated` может быть `null`: это не «ложь», а «сравнивать не с чем», потому что текущий релиз в каталоге не отмечен. На экране это плашка «Нет текущего релиза» (`CurrencyPill`).

### Уведомление

`Notification` — одно сообщение одному получателю. Тип — перечисление `NotificationType`:

- `update_available` — пора обновиться (создаёт специалист или администратор);
- `update_scheduled` — дата назначена;
- `update_completed` — работа выполнена;
- `update_cancelled` — заявка отменена.

Переход в `in_progress` письма не создаёт. Это прямо в `_notify_status`: для неизвестного типа функция просто выходит.

Получатели — активные пользователи с ролью `client` и этим `client_id`. Если таких нет, явная рассылка (`strict=True`) отвечает **422**. Служебные письма о статусе (`strict=False`) молча не создаются: заявку это не ломает. У «АО Василёк» портального пользователя в сиде нет, поэтому писем ему не будет, хотя выполненное обновление в истории есть.

Клиент в ленте видит только строки, где `recipient_id` — он сам, а не все письма организации.

### Слот

`UpdateSlot`: дата, начало, конец, `capacity` (по умолчанию 1, в API от 1 до 20), `is_active`, специалист. Уникальность `uq_specialist_slot` — один специалист не может иметь два окна с тем же началом в тот же день. Конец должен быть позже начала: это проверяет `SlotCreate.check_times`, иначе **422**.

Занятость считается по заявкам на этот `slot_id`, кроме статуса `cancelled`. Место, которое держит сама редактируемая заявка, при смене слота не считается (`ignore_update_id`). Перед записью строка слота блокируется `SELECT … FOR UPDATE` (`lock_slot`), чтобы два параллельных запроса не заняли последнее место.

Клиенту прошедшее, неактивное или заполненное окно в `GET /api/update-slots/{id}` выглядит как **404**, а не как 403. Список окон клиенту принудительно сужается до свободных будущих.

### Запланированное обновление

`ScheduledUpdate`. Статусы `UpdateStatus`:

| Код | Смысл |
| --- | --- |
| `requested` | заявка без даты |
| `scheduled` | дата выбрана, место занято |
| `in_progress` | специалист взял работу |
| `completed` | релиз установлен, в `completed_at` записано время |
| `cancelled` | заявка снята, место в слоте освобождается, потому что отменённые в `booked_count` не входят |

Допустимые переходы лежат в `ALLOWED_TRANSITIONS` в `src/services/planning.py`:

- `requested` → `scheduled` или `cancelled`;
- `scheduled` → `in_progress`, `cancelled` или обратно в `requested`;
- `in_progress` → `completed` или `cancelled`;
- `completed` и `cancelled` дальше никуда.

Любой другой переход — **409** с текстом `Transition <старый> -> <новый> is not allowed`. Тот же статус ещё раз — **422** `Status is unchanged`. Перевод в `scheduled` без слота — **422** `Choose a slot before scheduling`. Возврат в `requested` обнуляет `slot_id`, иначе место осталось бы занятым.

Пока заявка в `requested`, `scheduled` или `in_progress` (`OPEN_STATUSES`), вторую открытую заявку на ту же установку создать нельзя — **409**.

При создании цель фиксируется сразу: `target_version_id` — это текущий релиз каталога на момент заявки, а не «какой станет текущим потом». `source_version_id` — установленный на этот момент релиз. Когда статус становится `completed`, `_apply_completion` подменяет `installed_version_id` установки на цель и ставит `completed_at`. Отчёт 5.1 после этого всё ещё показывает «с какой на какую», потому что номера лежат на заявке, а не вычисляются из текущего состояния установки.

История — таблица `update_status_history`, модель `UpdateStatusHistory`. Старые строки не редактируются. Первая запись создаётся с `old_status = None`.

Назначение специалиста при создании: специалист слота, если дата выбрана; иначе ответственный сотрудник клиента, если он указан; иначе сам автор, если это администратор или специалист.

### Роли

Справочник `roles`, код — `RoleCode`:

| Код | Название в сиде |
| --- | --- |
| `admin` | Администратор |
| `specialist` | Специалист по сопровождению |
| `manager` | Руководитель отдела сопровождения |
| `client` | Клиент |

Пользователь хранит `role_id`, а не строку кода. Роль `client` обязана иметь `client_id`. Сотрудник с `client_id` не проходит: **422** `Only client users can be linked to a client company`. Это проверяет `_validate_role_link`.

Кто что может, в коде собрано в зависимости `src/api/deps.py`:

| Зависимость | Кто проходит |
| --- | --- |
| `CurrentUser` | любой активный пользователь с годным токеном |
| `AdminUser` | только `admin` |
| `WriterUser` | `admin` и `specialist` |
| `StaffUser` | `admin`, `specialist`, `manager` |
| `ReportUser` | `admin` и `manager` |

Клиент не вынесен в отдельную зависимость: его ограничение — `ensure_client_scope` на конкретных маршрутах. Руководитель читает, но `ensure_can_book` и `change_status` его не пускают.

Скрытие пунктов меню в «Норде» — только интерфейс. Защита — эти зависимости и проверки в сервисах. Если клиент откроет адрес `/users`, `RequireRole` нарисует заглушку, а прямой вызов `POST /api/users` всё равно получит **403**.

---

## 3. Архитектура и жизненный цикл запроса

Цепочка такая.

1. Браузер открывает «Норд». В разработке это Vite на порту 5173, в Compose — nginx сервиса `web` на хостовом порту 8080 (внутри контейнера nginx слушает 80).
2. Страница ходит относительными путями: `/api/...` и `/health`. Браузер считает это тем же источником, что и страница.
3. Vite (`server.proxy` в `frontend/vite.config.ts`) или nginx (`frontend/nginx.conf`) пересылает эти пути контейнеру `api:8000`.
4. FastAPI принимает запрос. CORS-middleware стоит на приложении, но при прокси браузер на API напрямую не ходит, поэтому запрос same-origin и CORS не участвует. CORS нужен, если кто-то открыл страницу и дергает порт 8000 сам. Оба механизма описаны в разделе 7 и в ответах.
5. Зависимости: `get_db` открывает `AsyncSession`; `HTTPBearer` достаёт токен; `get_current_user` проверяет подпись и загружает пользователя; `require(...)` сверяет роль.
6. Функция роутера разбирает тело схемой Pydantic, вызывает сервис или запрос, сериализатор собирает ответ без пароля.
7. Запись фиксирует `commit_session`. Если уникальный индекс нарушен, наружу уходит **409**, а не трасса PostgreSQL.

Слоя репозиториев нет. Пакет `src/data/repositories` — пустая заготовка. Запросы живут в `src/services` и частично прямо в роутерах.

`get_db` сам транзакцию не коммитит. Он только откатывает сессию, если из обработчика вылетело исключение, и пробрасывает его дальше. Кто забыл `commit_session`, тот ничего не записал: при закрытии сессии незакоммиченное откатывается.

### Как JWT доходит от login до `/auth/me`

1. Экран входа вызывает `POST /api/auth/login` с почтой и паролем. Токен в этот запрос не кладётся (`auth: false` в `api.login`).
2. `login` ищет пользователя по почте (она приводится к нижнему регистру валидатором `LoginRequest.normalize_email`), вызывает `verify_password`. Неверная пара — **401** `Invalid email or password`. Верный пароль, но `is_active = false` — **403** `User is deactivated`. Специально не говорят, чего именно не хватило, пока пароль неверен: отключённый пользователь с неверным паролем тоже получает 401, потому что проверка активности стоит после проверки пароля.
3. `create_access_token` кладёт в полезную нагрузку `sub` (строка UUID пользователя), `role` (код роли) и `exp` (сейчас UTC плюс `access_token_expire_minutes`, по умолчанию 720 минут). Подпись — HMAC на `jwt_secret`, алгоритм `HS256`.
4. Ответ `TokenResponse`: `access_token`, `token_type = "bearer"`, `expires_in` в секундах (минуты умножить на 60), `role` и карточка `user` без хеша.
5. `AuthProvider.login` пишет в `localStorage` ключ `nord.session`: токен, `expiresAt = Date.now() + expires_in * 1000` и карточку пользователя.
6. Дальше `request` в `frontend/src/api/client.ts` читает токен через `readToken` и ставит заголовок `Authorization: Bearer <token>`.
7. `GET /api/auth/me` зависит от `CurrentUser`, то есть от `get_current_user`. Нет заголовка или схема не `Bearer` — **401** `Not authenticated` и заголовок `WWW-Authenticate: Bearer`. Подпись битая, срок вышел или `sub` не UUID — **401** `Invalid or expired token`. Пользователя нет или он неактивен — **401** `Inactive or unknown user`.
8. Роль для допуска берётся не из поля `role` токена, а из базы: `select(User).options(selectinload(User.role), selectinload(User.client))`. Поле `role` в JWT нужно клиенту в момент входа и лежит в ответе логина. Если администратор сменил роль или отключил человека, следующий запрос это уже увидит, старый токен «старую роль» не продлевает. Подделать чужой `sub` можно только зная `jwt_secret`.

`remember_actor` сразу копирует код роли и `client_id` в `__dict__` пользователя. Иначе позже повторная загрузка того же `User` (например автора заявки) может сбросить связь `role`, и ленивое чтение в async упрётся в ошибку greenlet. `actor_role` и `actor_client_id` читают этот кэш.

При **401** на запросе с авторизацией фронтенд вызывает `clearSession` и `onUnauthorized`: статус становится `anon`, `RequireAuth` уводит на `/login`.

---

## 4. Соответствие требований, эндпоинтов и кода

Номера — из `summary` роутеров и из `README.md`. «Кто вызывает» — серверная функция и место во фронтенде, если экран его использует. Часть `GET` по одному идентификатору фронтенд не оборачивает: они есть для API, `/docs` и точечного чтения, экран обходится списками.

| Требование | Метод и путь | Роль на входе | Функция | Сервис и сериализация | Экран «Норд» |
| --- | --- | --- | --- | --- | --- |
| Живость | `GET /health`, дубль `GET /api/health` | без токена | `health` | `database_reachable` | `api.health` на экране входа |
| Готовность | `GET /health/ready`, дубль `GET /api/health/ready` | без токена | `ready` | роли и `DEMO_EMAILS` | экран не вызывает; вызывает `scripts/smoke.py` |
| Указатель | `GET /` | без токена | `root` | — | не используется UI |
| Вход | `POST /api/auth/login` | без токена | `login` | `verify_password`, `create_access_token`, `user_read` | `LoginPage` → `AuthProvider.login` |
| Кто я | `GET /api/auth/me` | любой активный | `me` | `user_read` | `AuthProvider` при старте |
| 1.1 список ролей | `GET /api/roles` | `StaffUser` | `list_roles` | таблица `roles` | `UserDialog` через `api.listRoles` |
| 1.1 регистрация | `POST /api/users` | `AdminUser` | `create_user` | `hash_password`, `get_role`, `_validate_role_link` | `UsersPage` |
| 1.1 список | `GET /api/users` | `StaffUser` | `list_users` | `like_pattern`, `count_rows`, `user_read` | `UsersPage`, `ClientForm`, `SpecialistSelect` |
| 1.1 карточка | `GET /api/users/{user_id}` | сам клиент или сотрудник | `get_user` | `_load_user`, `user_read` | обёртки во фронтенде нет |
| 1.1 правка роли и доступа | `PATCH /api/users/{user_id}` | `AdminUser` | `update_user` | `_guard_last_admin`, `hash_password` | `UsersPage` |
| 1.2 создать клиента | `POST /api/clients` | `WriterUser` | `create_client` | `ensure_staff_user`, `client_read` | `ClientForm` |
| 1.2 список | `GET /api/clients` | любой, клиент видит только себя | `list_clients` | `_scoped_client_filter` | `ClientsPage`, `ClientSelect`, `ChecksPage` |
| 1.2 карточка | `GET /api/clients/{client_id}` | область клиента | `read_client` | `ensure_client_scope`, `get_client` | `ClientPage` |
| 1.2 правка | `PATCH /api/clients/{client_id}` | `WriterUser` | `update_client` | `get_client` | `ClientForm` |
| 1.2 удаление без истории заявок | `DELETE /api/clients/{client_id}` | `WriterUser` | `delete_client` | счётчик `ScheduledUpdate` | `ClientPage.remove` |
| 1.3 создать конфигурацию | `POST /api/configurations` | `WriterUser` | `create_configuration` | `configuration_read` | `ConfigurationDialog` |
| 1.3 список | `GET /api/configurations` | любой активный | `list_configurations` | `map_current_versions` | каталог, `ConfigurationSelect`, `AddInstallation` |
| 1.3 карточка с версиями | `GET /api/configurations/{id}` | любой | `read_configuration` | `configuration_detail`, `list_versions` | `ConfigurationPage`, `EditInstallation` |
| 1.3 правка | `PATCH /api/configurations/{id}` | `WriterUser` | `update_configuration` | `get_configuration` | `ConfigurationDialog` |
| 1.3 удалить неиспользуемую | `DELETE /api/configurations/{id}` | `WriterUser` | `delete_configuration` | счётчик установок | `ConfigurationPage.removeConfiguration` |
| 1.3 добавить релиз | `POST /api/configurations/{id}/versions` | `WriterUser` | `create_version` | `clear_current` | `VersionDialog` |
| 1.3 правка релиза / сделать текущим | `PATCH .../versions/{version_id}` | `WriterUser` | `update_version` | `touch_current_flag` | кнопка «Сделать текущей» |
| 1.3 удалить релиз | `DELETE .../versions/{version_id}` | `WriterUser` | `delete_version` | `version_reference_count` | `removeVersion` |
| 1.3 поставить клиенту | `POST /api/clients/{id}/configurations` | `WriterUser` | `create_installation` | `ensure_version_of_configuration` | `AddInstallation` |
| 1.3 сменить установленный релиз вручную | `PATCH /api/client-configurations/{id}` | `WriterUser` | `update_installation` | `get_installation` | `EditInstallation` |
| 1.3 удалить установку без заявок | `DELETE /api/client-configurations/{id}` | `WriterUser` | `delete_installation` | счётчик заявок | `InstallationCard.remove` |
| 1.4 установки клиента | `GET /api/clients/{id}/configurations` | область клиента | `list_client_configurations` | `list_installations` | `ClientPage` |
| 1.4 поиск установок | `GET /api/client-configurations` | клиенту подставляется его id | `search_installations` | `list_installations` | `InstallationsPage`, обзор, форма заявки |
| 1.4 одна установка | `GET /api/client-configurations/{id}` | область клиента | `read_installation` | `_to_reads` | обёртки во фронтенде нет |
| 2.1 сравнить | `POST /api/version-checks/run` | `WriterUser` | `run_checks` | `run_version_checks`, `load_checks` | `ChecksPage.run`, кнопка «Проверить» |
| 2.2 кому нужно обновление | `GET /api/version-checks/outdated` | `StaffUser` | `list_outdated` | `outdated_report` | `ChecksPage` |
| 2.3 архив | `GET /api/version-checks` | `StaffUser` | `list_checks` | `check_load_options` | история на `ChecksPage` |
| 2.3 одна проверка | `GET /api/version-checks/{check_id}` | сотрудник; клиент — только своя | `read_check` | `version_check_read` | обёртки нет |
| 3.1–3.2 сообщить | `POST /api/notifications` | `WriterUser` | `create_notification` | `create_update_notification`, `notify_client_users` | `NotifyDialog`, `Compose` |
| 3.3 лента | `GET /api/notifications` | клиент видит только свои | `list_notifications` | `_visible` | `NotificationsPage`, бейдж в `Shell` |
| 3.3 одно письмо | `GET /api/notifications/{id}` | получатель или сотрудник | `read_notification` | `notification_read` | обёртки нет |
| 3.3 прочитано | `POST /api/notifications/{id}/read` | только получатель | `mark_read` | ставит `is_read` | кнопка «Прочитано» |
| 4.1 открыть окно | `POST /api/update-slots` | `WriterUser` | `create_slot` | `_owner_for_create` | `CreateSlot` |
| 4.1 свободные даты | `GET /api/update-slots/dates` | клиенту только свободные | `available_dates` | `_list_slots` | `SlotPicker` |
| 4.1 список окон | `GET /api/update-slots` | клиенту принудительно `available_only` | `list_slots` | `_list_slots`, `slot_read` | `SlotsPage` |
| 4.1 одно окно | `GET /api/update-slots/{slot_id}` | клиенту плохое окно как 404 | `read_slot` | `booked_count`, `slot_is_past` | обёртки нет |
| 4.1 вместимость и активность | `PATCH /api/update-slots/{slot_id}` | специалист — только своё окно | `update_slot` | `booked_count` | `toggle`, `CapacityDialog` |
| 4.2 заявка / выбор даты | `POST /api/scheduled-updates` | клиент на своё, писатели; руководитель нет | `create_update` | `create_scheduled_update` | `RequestForm` |
| 4.3 список | `GET /api/scheduled-updates` | клиент видит только свои | `list_updates` | `_update_filters` | `UpdatesPage`, обзор |
| 4.3–4.4 карточка и история | `GET /api/scheduled-updates/{id}` | `ensure_can_view` | `read_update` | `get_scheduled_update`, `scheduled_update_detail` | `UpdatePage` |
| 4.2 сменить дату или комментарий | `PATCH /api/scheduled-updates/{id}` | пока `requested` или `scheduled` | `patch_update` | `assign_slot` | `saveSlot`, `saveComment` |
| 4.4 сменить статус | `PATCH /api/scheduled-updates/{id}/status` | `WriterUser` | `patch_status` | `change_status` | кнопки на `UpdatePage` |
| 5.1 кого обновили | `GET /api/reports/updated-clients` | `ReportUser` | `updated_clients` | `updated_clients_report` | `ReportsPage`, обзор руководителя |
| 5.2 план и факт | `GET /api/reports/updates` | `ReportUser` | `updates` | `updates_summary` | `ReportsPage`, обзор руководителя |
| Отчёт отстающих для руководителя | `GET /api/reports/outdated-clients` | `ReportUser` | `outdated_clients` | тот же `outdated_report` | `ReportsPage` |

Списки почти везде отдают `Page`: `items`, `total`, `limit`, `offset`. Параметры страницы — `get_page`: `limit` от 1 до 200, по умолчанию 50; `offset` от 0. Поиск `q` режется `like_pattern`: символы `%`, `_` и `\` экранируются, чтобы пользовательский ввод был буквальной подстрокой `ILIKE`, а не шаблоном.

Коды, которые всплывают часто и не расписаны у каждой функции ещё раз:

- **401** — нет токена, токен плохой, пользователь неизвестен или выключен;
- **403** — роль не из списка `require`, клиент лезет в чужое, руководитель пытается писать;
- **404** — нет строки;
- **409** — уникальность, занятый слот, запрещённый переход, удаление того, на что есть история;
- **422** — схема Pydantic, бизнес-правило «так нельзя», в том числе `extra="forbid"` на лишнее поле JSON;
- **500** — роль из справочника не найдена (`get_role`), то есть миграция или сид ролей не отработали;
- **503** — `/health` или `/health/ready`, когда база недоступна или не хватает ролей.

---

## 5. Бэкенд по файлам

### `requirements.txt`

Зависимости без жёстких версий, кроме `sqlalchemy>=2.0`: `fastapi`, `uvicorn[standard]`, `asyncpg`, `alembic`, `pydantic-settings`, `greenlet` (его требует async SQLAlchemy), `bcrypt`, `PyJWT`, `email-validator` (его требует тип `EmailStr`). Отдельного lock-файла Python в репозитории нет: в образ ставится то, что `pip` возьмёт на момент сборки.

### `main.py`

Точка входа HTTP. Объект приложения называется `app`. Uvicorn запускает `main:app`.

#### `lifespan(_app)`

Асинхронный контекст. До приёма запросов вызывает `init_db` (проверка базы, роли, демо). После остановки — `dispose_engine`. Если `init_db` бросит `RuntimeError`, процесс не начнёт слушать порт.

#### `app`

`FastAPI` с именем из настроек, версией `0.1.0` (она зашита здесь, не в `Settings`), кратким английским `summary` и `description`. К приложению подключены `health_router` и `api_router`.

#### CORS

Список `_LOCAL_UI_ORIGINS`: localhost и 127.0.0.1 на портах 5173, 4173 и 8080. Плюс регулярное выражение `https?://(localhost|127\.0\.0\.1)(:\d+)?$` — любой порт на localhost. Методы и заголовки разрешены все (`allow_methods=["*"]`, `allow_headers=["*"]`). `allow_credentials` не включён: куки сессии нет, токен едет заголовком. Это не замена прокси. Штатный путь — same-origin через Vite или nginx. CORS закрывает случай, когда браузер сам обращается на порт 8000.

#### `root()`

`GET /`. В OpenAPI не входит (`include_in_schema=False`). Возвращает словарь `app`, `health`, `docs`. Нужен как короткий указатель, если открыли корень API. «Норд» его не вызывает.

### `src/__init__.py`

Одна строка документации пакета. Исполняемого кода нет.

### `src/core/__init__.py`

Документация пакета настроек, базы и JWT. Кода нет.

### `src/core/config.py`

#### Класс `Settings`

Наследник `BaseSettings`. Читает окружение и файл `.env` (регистр имён не важен, лишние переменные игнорируются).

Поля и значения по умолчанию:

- `app_name` — `Control_1C_version`;
- `environment` — только `dev`, `development`, `prod`, `production`, по умолчанию `dev`;
- `debug` — `False`, при `True` SQLAlchemy печатает SQL (`echo`);
- `database_url` — `postgresql+asyncpg://postgres:postgres@localhost:5433/control_1c_version`;
- `database_pool_size` — 20;
- `jwt_secret` — `dev-only-change-me`;
- `jwt_algorithm` — `HS256`;
- `access_token_expire_minutes` — 720;
- `seed_demo` — `None`.

#### `Settings.is_production`

Истина для `prod` и `production`.

#### `Settings.should_seed_demo`

Если `SEED_DEMO` задан, берётся он. Если нет — демо наполняется везде, кроме production. В Compose переменная задана явно: `SEED_DEMO=true`.

#### `get_settings()`

Обёрнута в `lru_cache`: на процесс один объект. Модуль сразу делает `settings = get_settings()`. Пока процесс жив, смена `.env` не подхватится без перезапуска. Это нормально для настроек старта.

### `src/core/database.py`

#### Класс `Base`

`DeclarativeBase`. У всех моделей общий `metadata`. Его забирает Alembic как `target_metadata`.

#### `engine`

`create_async_engine` на `settings.database_url`, пул `database_pool_size`, `echo=settings.debug`, `connect_args={"ssl": False}`. Для локального Postgres без TLS. В боевой контур с обязательным SSL этот аргумент пришлось бы менять: сейчас его нет в настройках.

#### `async_session`

Фабрика `async_sessionmaker`, `expire_on_commit=False`: после `commit` поля объекта ещё читаются без повторного запроса. Это нужно сериализаторам.

#### `get_db()`

Генератор сессии одного запроса. `yield session`. При любом исключении — `rollback` и проброс. Коммита здесь нет.

#### `init_db()`

`SELECT 1`. Не вышло — `RuntimeError` «Database is unreachable…». Затем в отдельной сессии `seed_initial_data` и, если `should_seed_demo`, `seed_demo_data`. Ошибка сида логируется и заворачивается в `RuntimeError` с текстом «Apply migrations first». Вызывается из `lifespan`. Повторный старт безопасен: сид идемпотентный, см. `seed.py`.

#### `dispose_engine()`

`engine.dispose()`, закрывает пул. Вызывает `lifespan` при остановке.

### `src/core/security.py`

#### Класс `TokenError`

Пустое исключение-маркер. Его поднимает `decode_access_token` и ловит `get_current_user`, чтобы отдать 401, а не 500.

#### `hash_password(password)`

`bcrypt.hashpw` с `bcrypt.gensalt()` (соль и стоимость — по умолчанию библиотеки) и `decode()` в строку. Эту строку пишут в `users.hashed_password`. Вызывают `create_user`, `update_user` и сид. В ответах API хеш не сериализуется: в `UserRead` такого поля нет, `user_read` его не копирует.

#### `verify_password(password, hashed)`

`bcrypt.checkpw`. Битый хеш даёт `ValueError`, функция возвращает `False`, а не падает. Вызывают `login` и сид (чтобы не переписывать пароль, если он уже совпал).

#### `create_access_token(*, user_id, role)`

Собирает payload `sub`, `role`, `exp` и подписывает `jwt.encode`. Возвращает строку. Вызывает только `login`.

#### `decode_access_token(token)`

`jwt.decode` с тем же секретом и списком алгоритмов из настроек (алгоритм из самого токена не доверяется: список задаёт сервер). Любой `jwt.PyJWTError` становится `TokenError`. Вызывает `get_current_user`.

### `src/api/__init__.py` и `src/api/routers/__init__.py`

Только строки документации пакетов. Реэкспорта маршрутов нет: `router.py` импортирует модули сам.

### `src/api/deps.py`

#### Класс `PageParams`

Хранит `limit` и `offset`.

#### `get_page(limit=50, offset=0)`

Query-параметры. `limit` от 1 до 200, `offset` от 0. Вне диапазона FastAPI сам ответит **422**.

#### `PageDep`, `Db`

Аннотации `Annotated[..., Depends(...)]`. `Db` — сессия запроса.

#### `bearer`

`HTTPBearer(auto_error=False)`. Если заголовка нет, зависимость получит `None` и сама решит, какой 401 отдать, а не стандартный ответ Starlette.

#### `get_current_user(creds, session)`

Описан в разделе 3. Успех: живой активный `User` после `remember_actor`. Коды 401 перечислены там же.

#### `require(*roles)`

Возвращает зависимость `checker`. Та сравнивает `actor_role(user)` со списком. Чужая роль — **403** `Insufficient permissions`. Администратор не зашит как «бог»: если маршрут требует только `ReportUser`, специалист получит 403, даже если он администратор? Нет: `ReportUser` включает `ADMIN` и `MANAGER`. А вот маршрут только для `AdminUser` специалиста не пустит. Отдельного обхода «admin может всё» внутри `require` нет: админ указан в тех кортежах, где ему можно.

Готовые аннотации: `CurrentUser`, `AdminUser`, `StaffUser`, `WriterUser`, `ReportUser`. Их ставят в сигнатуры эндпоинтов. FastAPI вызывает их до тела функции.

### `src/api/router.py`

Собирает `api_router` с префиксом `/api` и подключает роутеры auth, users, clients, configurations, вложенный и плоский роутеры установок, checks, notifications, slots, updates, reports. Health сюда не входит: он подключён к приложению отдельно и сам объявляет пути `/health` и `/api/health`.

### `src/api/schemas.py`

Схемы Pydantic. `from_attributes=True` стоит только там, где объект ORM можно отдать через `model_validate`: `RoleRead` и `VersionRead`. Остальные ответы собирает `serializers.py`, потому что в них есть вычисляемые поля (имена, признак устаревания, остаток мест).

Почти у всех тел запроса `extra="forbid"`: лишнее поле — **422**, а не тихое игнорирование. Строки обрезают пробелы валидаторами. Пустая строка после обрезки у необязательных текстов становится `None`.

#### `Page[T]`

`items`, `total`, `limit`, `offset`. Общая обёртка списков.

#### `RoleRead`

`id`, `code: RoleCode`, `name`.

#### `UserRead`

Карточка без пароля: `id`, `full_name`, `email`, `phone`, `is_active`, `role`, `client_id`, `client_name`, `created_at`, `updated_at`.

#### `UserCreate` и валидаторы `normalize_email`, `strip_text`

Имя 1–255, почта, пароль 6–128, необязательный телефон до 32, роль, необязательный `client_id`. Почта в нижний регистр.

#### `UserUpdate` и `strip_text`

Все поля необязательны. Поля, которых нет в JSON, колонку не меняют. Это важно для `phone` и `client_id`: роутер смотрит `model_fields_set`, чтобы отличить «не прислали» от «прислали null».

#### `TokenResponse`

`access_token`, `token_type` по умолчанию `bearer`, `expires_in`, `role`, `user`.

#### `LoginRequest` и `normalize_email`

Почта и пароль 1–128. Пароль входа короче шести символов схема пускает: ограничение шести символов — на создание, не на проверку старого пароля.

#### `ClientRead`, `ClientCreate`, `ClientUpdate`

Карточка, создание (название, телефон, почта, необязательный ответственный) и частичная правка. У `ClientUpdate` валидаторы `strip_text` и `normalize_email`. `responsible_employee_id: null` снимает ответственного, если поле присутствует в JSON.

#### `VersionRead`

Релиз как в таблице, через `from_attributes`.

#### `ConfigurationRead`, `ConfigurationDetail`

Каталог плюс строка `current_version`. Детальная схема добавляет `versions`.

#### `ConfigurationCreate`, `ConfigurationUpdate`

Имя и описание. Валидатор `strip_name`.

#### `VersionCreate`, `VersionUpdate`

Новый релиз: номер, дата, `is_current` по умолчанию `False`, заметка. Правка даты, заметки и флага. Номер версии через PATCH не меняется: такого поля в `VersionUpdate` нет.

#### `ClientConfigurationRead`

Установка для экрана: организация, конфигурация, установленный и текущий номера, `is_outdated` (bool или null), имя базы, `last_checked_at`.

#### `ClientConfigurationCreate`, `ClientConfigurationUpdate`

Привязка (`configuration_id`, `installed_version_id`, имя базы) и правка версии или имени базы. Валидатор `strip_infobase`.

#### `VersionCheckRead`

Снимок человекочитаемыми именами, не только UUID.

#### `RunChecksRequest`

Оба поля необязательны. Пустой объект — все установки. Иначе один клиент или одна установка. Одновременно оба идентификатора код не запрещает: если передан `client_configuration_id`, ветка в `run_version_checks` смотрит только его и `client_id` игнорирует.

#### `SkippedCheck`, `RunChecksResponse`

Пропуск (`client_configuration_id`, `reason`) и пара списков `created` и `skipped`.

#### `OutdatedConfiguration`, `OutdatedClient`, `OutdatedReport`

Живой список: клиент и его отстающие установки, плюс два счётчика.

#### `NotificationRead`, `NotificationList`, `NotificationCreate`

Письмо, лента с `unread` и тело рассылки. `message` можно не передавать, если указана установка: текст соберёт сервис.

#### `SlotRead`, `SlotCreate`, `SlotUpdate`, `AvailableDate`

Окно с `booked` и `remaining`. Создание проверяет `check_times`: `end_time` позже `start_time`, иначе `ValueError`, которое Pydantic отдаёт как **422**. Вместимость 1–20. Правка — только `is_active` и `capacity`, время слота поменять нельзя.

#### `StatusEventRead`, `ScheduledUpdateRead`, `ScheduledUpdateDetail`

Факт смены статуса, заявка без истории и заявка с `status_history`.

#### `ScheduledUpdateCreate`, `ScheduledUpdatePatch`, `StatusChange`

Создание (установка, необязательный слот, комментарий до 4000), правка слота или комментария, целевой статус.

#### `UpdatedConfigurationReport`, `UpdatedClientReport`, `UpdatedClientsReport`

Отчёт 5.1: клиент и выполненные обновления «с версии на версию».

#### `UpdateBrief`, `UpdatesReport`

Короткая строка заявки и сводка 5.2. `planned_count` не включает `completed` и `cancelled`. `by_status` содержит все пять статусов.

### `src/api/serializers.py`

Связи ORM должны быть уже загружены. Сериализатор запросов не делает. Если связь не подгружена, обращение к ней в async даст ошибку ленивой загрузки, а не аккуратный JSON.

#### `user_read(user)`

Собирает `UserRead`. `client_name` берётся из `user.client.company_name`, если связь есть. Хеш пароля не копируется. Вызывают auth и users.

#### `client_read(client)`

`ClientRead` и имя ответственного, если `responsible_employee` загружен.

#### `configuration_read(row, current)`

`ConfigurationRead`. Строку актуального релиза передают снаружи, потому что у модели нет колонки «текущий номер», есть флаг на версии.

#### `configuration_detail(row, versions)`

Ищет первый `is_current` в переданном списке и добавляет `versions` через `VersionRead.model_validate`.

#### `installation_read(row, current, last_checked_at)`

`ClientConfigurationRead`. `is_outdated` — `None`, если `current` нет, иначе сравнение id. Нужны загруженные `client`, `configuration`, `installed_version`.

#### `version_check_read(row)`

Имена клиента, конфигурации, обеих версий и автора проверки.

#### `notification_read(row)`

Имя конфигурации достаёт только если загружены и установка, и её конфигурация. Иначе `configuration_name = None`, падения нет.

#### `slot_read(row, booked)`

`remaining = max(capacity - booked, 0)`. Отрицательный остаток наружу не отдаётся, даже если вместимость когда-то опустили бы ниже занятых мест. API так опустить не даёт (`update_slot` отвечает 422), формула страхует ответ.

#### `status_event_read(row)`

Строка истории и имя того, кто сменил статус.

#### `scheduled_update_read(row)`

Заявка без истории: версии, слот, кто запросил, кто назначен. Если связи версии или слота нет, соответствующие поля `None`.

#### `scheduled_update_detail(row)`

То же плюс `status_history` через `status_event_read`.

#### `update_brief(row)`

Короткая строка для отчёта 5.2. Вызывает `updates_summary`.

#### `ids(values)`

Делает `set` из списка UUID. **Никто её не импортирует.** Это оставшаяся мелочь, на поведение системы не влияет.

### `src/api/routers/health.py`

Константа `REQUIRED_ROLES` — четыре кода. Роутер без префикса.

#### `database_reachable()`

Своя короткая сессия, `SELECT 1`. Любое исключение логируется и превращается в `False`. Текст ошибки клиенту не отдаётся.

#### `health()`

`GET /health` и скрытый из схемы `GET /api/health`. База жива — `{"status":"ok","app":...,"database":"ok"}` и **200**. База недоступна — **503** `status=unavailable`, `database=down`. Это живость процесса и базы, не проверка сида.

#### `ready()`

`GET /health/ready` и скрытый `GET /api/health/ready`. База недоступна или запрос ролей упал — **503** `not_ready`, `demo_seeded: false`. Иначе собирает коды ролей. Если какого-то из четырёх нет — **503** и список `missing_roles`. Если роли на месте — **200** и `status: ok`, даже когда `demo_seeded` ложь. Флаг `demo_seeded` истинен, только если в `users` есть все четыре адреса из `DEMO_EMAILS`. Выключенный `SEED_DEMO` не роняет готовность, он только оставляет `demo_seeded: false`. `smoke.py` как раз требует и `status == ok`, и `demo_seeded`.

### `src/api/routers/auth.py`

Префикс `/auth`, в итоге `/api/auth`.

#### `login(payload, session)`

`POST /api/auth/login`. Логика в разделе 3. Возвращает `TokenResponse`. Коды: **401**, **403**, **422**. Вызывает `verify_password`, `create_access_token`, `user_read`. Вызывают экран входа и `scripts/smoke.py`.

#### `me(user)`

`GET /api/auth/me`. Аргумент уже `CurrentUser`. Возвращает `user_read(user)`. **401**, если токен не подошёл. Вызывает `AuthProvider` при загрузке страницы, чтобы подменить карточку из `localStorage` свежей из базы.

### `src/api/routers/users.py`

Тег `users`, префикса нет: пути `/api/roles` и `/api/users`.

#### `_user_options()`

`selectinload` роли и клиента. Нужен каждому ответу `user_read`.

#### `_load_user(session, user_id)`

Пользователь с этими связями или **404** `User not found`.

#### `_validate_role_link(session, role, client_id)`

Роль клиента без `client_id` — **422**. Не-клиент с `client_id` — **422**. Если `client_id` есть, `get_client`: нет организации — **404**. Вызывают `create_user` и `update_user`.

#### `_guard_last_admin(session, target, actor, payload)`

Нельзя выключить самого себя (**422**). Нельзя снять с себя роль администратора (**422**). Нельзя снять роль или выключить последнего активного администратора (**422** `Cannot remove or deactivate the last active administrator`). Считаются другие активные пользователи с кодом `admin`. Вызывает только `update_user`.

#### `list_roles(_user, session)`

`GET /api/roles`. `StaffUser`. Все роли по коду. Клиент получит **403**: форма назначения ролей ему не нужна. Возвращает список `Role`, схема ответа `list[RoleRead]`.

#### `create_user(payload, _actor, session)`

`POST /api/users`, **201**, только админ. Проверяет связь роли, уникальность почты (**409**, если такая уже есть), берёт роль через `get_role` (**500**, если справочник пуст), хеширует пароль, пишет пользователя, `flush_session`, `commit_session`, возвращает `user_read`. Почта к этому моменту уже в нижнем регистре.

#### `list_users(...)`

`GET /api/users`. `StaffUser`. Фильтры `q` (имя или почта), `role`, `is_active`, страница. Возвращает `Page[UserRead]`. Клиент этот список не видит.

#### `get_user(user_id, actor, session)`

`GET /api/users/{user_id}`. Клиент может открыть только свой id, иначе **403**. Сотрудник любой из трёх ролей открывает любого. Неизвестная роль (в перечислении таких нет) тоже **403**. Фронтенд метод не вызывает: карточка пользователя редактируется из списка, отдельной страницы пользователя нет.

#### `update_user(user_id, payload, actor, session)`

`PATCH /api/users/{user_id}`, только админ. Грузит цель, вызывает `_guard_last_admin`, применяет присланные поля. Пароль, если прислан, снова хешируется. Роль меняется и в объекте, и в `role_id`. `client_id` обновляется, только если ключ был в JSON. Затем снова `_validate_role_link` уже по итоговым значениям. **404**, **422**, **409** на конфликт уникальности почты через `flush_session`. Почту этот метод не меняет: в `UserUpdate` нет поля `email`. Экран так и написан: «Почту после создания изменить нельзя».

### `src/api/routers/clients.py`

Префикс `/clients`.

#### `_scoped_client_filter(user, stmt, client_id)`

Для роли `client`: если `client_id` пользователя пуст, возвращает `None` (список будет пустым, не ошибкой). Иначе сужает запрос до его организации и дополнительно вызывает `ensure_client_scope`. Для остальных ролей необязательный `client_id` добавляет фильтр. Сейчас `list_clients` всегда передаёт сюда `client_id=None`; фильтр по конкретному id для сотрудника идёт отдельным параметром только у ответственного.

#### `create_client(payload, _actor, session)`

`POST /api/clients`, **201**, `WriterUser`. Ответственный, если указан, проверяется `ensure_staff_user` (**422**, если это клиент, неактивный или неизвестный). Дубль названия, почты или телефона — **409**. Иначе вставка и `client_read`.

#### `list_clients(...)`

`GET /api/clients`. Поиск по названию, почте, телефону. Сотрудник может сузить `responsible_employee_id`; клиенту этот фильтр игнорируется. Пустая привязка клиента — пустая страница, не 403.

#### `read_client(client_id, actor, session)`

`GET /api/clients/{client_id}`. `ensure_client_scope` (**403** на чужое), затем `get_client` (**404**).

#### `update_client(...)`

`PATCH /api/clients/{client_id}`, `WriterUser`. Частичное обновление. Ответственного с null можно снять, потому что смотрят `model_fields_set`. Конфликт уникальности — **409** через flush.

#### `delete_client(...)`

`DELETE /api/clients/{client_id}`, **204**. Если есть хотя бы одна заявка — **409** `Cannot delete a client that has update history`. Историю отчёта не стирают. Если заявок нет, роутер делает `session.delete(client)`. Установки клиент удаляет связью с `cascade="all, delete-orphan"`, а проверки уходят вместе с установкой (такой же каскад на `checks` и `ON DELETE CASCADE` в базе). Уведомления в модели без ORM-каскада, но в миграции у `notifications.client_id` стоит `ON DELETE CASCADE`. У портальных пользователей `users.client_id` при удалении организации становится `NULL` (`ON DELETE SET NULL`): роль `client` в базе при этом не проверяется заново, ограничение «у клиента обязана быть организация» живёт в `_validate_role_link`, а не в таблице. Вызывает `ClientPage.remove`.

### `src/api/routers/configurations.py`

Префикс `/configurations`.

#### `_reads(session, rows)`

Одним запросом `map_current_versions` подставляет номер актуального релиза в список карточек.

#### `create_configuration`

`POST /api/configurations`, **201**, писатель. Дубль имени — **409**. У новой записи `current_version` в ответе `None`: релизов ещё нет.

#### `list_configurations`

`GET /api/configurations`. Любой вошедший, включая клиента: каталог ему можно читать. Поиск по имени.

#### `read_configuration`

`GET /api/configurations/{configuration_id}`. Конфигурация и все релизы. **404** через `get_configuration`.

#### `update_configuration`

`PATCH`, писатель. Имя и описание. Описание можно затереть в `null`, если ключ прислан. Возвращает детальную карточку.

#### `delete_configuration`

`DELETE`, **204**. Если есть хоть одна установка — **409** `Configuration is installed for a client`. Иначе удаление. Версии уйдут каскадом модели (`cascade="all, delete-orphan"` и `ON DELETE CASCADE` у версии).

#### `create_version`

`POST /api/configurations/{id}/versions`, **201**. Дубль номера — **409**. Релиз становится текущим, если так просят или если текущего ещё нет (`make_current = payload.is_current or not any(...)`). Перед этим `clear_current`. Первый релиз станет текущим, даже если клиент прислал `is_current: false`. Экран `VersionDialog` об этом пишет отдельно. Ответ — `VersionRead`.

#### `update_version`

`PATCH .../versions/{version_id}`. Конфигурация должна существовать. Версия должна принадлежать ей, иначе **404**. Дата и заметка применяются, если ключ есть. `is_current`, если не `None`, уходит в `touch_current_flag`.

#### `delete_version`

`DELETE`, **204**. **404**, если версия чужая или её нет. Если на релиз ссылаются установка, проверка или заявка — **409** (`version_reference_count`). Если это текущий релиз и есть другие версии — **422**: сначала назначьте другой текущим. Последний релиз конфигурации, даже текущий, удалить можно, если ссылок нет: условие требует «есть другие».

### `src/api/routers/installations.py`

Два роутера. `router` — `/client-configurations`. `nested` — `/clients`, чтобы получить пути `/api/clients/{id}/configurations` рядом с карточкой клиента. Оба подключены в `router.py`.

#### `_to_reads(session, rows)`

Текущие релизы и время последней проверки (`map_last_checks`) для пачки установок, затем `installation_read`.

#### `list_installations(session, *, actor, page_limit, page_offset, client_id, configuration_id, outdated, q)`

Общая выборка. Клиенту без организации — пустая страница. Если клиент передал чужой `client_id` — **403** из `ensure_client_scope`, затем id всё равно подменяется на его собственный. Фильтр `outdated` делает `JOIN` на версию с `is_current`. Установки без текущего релиза в фильтр «устарело/актуально» не попадают: им не с чем соединиться. Поиск по организации, имени конфигурации и имени базы. Это не эндпоинт, её вызывают два GET ниже.

#### `list_client_configurations`

`GET /api/clients/{client_id}/configurations`. Сначала область видимости и `get_client`, потом `list_installations`.

#### `create_installation`

`POST /api/clients/{client_id}/configurations`, **201**, писатель. Проверяет клиента, конфигурацию и что версия от этой конфигурации. Дубль пары — **409**. Имя базы необязательно.

#### `search_installations`

`GET /api/client-configurations`. Тонкая обёртка над `list_installations`.

#### `read_installation`

`GET /api/client-configurations/{installation_id}`. **404** или **403**. Фронтенд отдельный метод не делает.

#### `update_installation`

`PATCH /api/client-configurations/{installation_id}`. Ручная смена установленного релиза или имени базы. Это не выполнение заявки: `source/target` и история статусов здесь не пишутся. Комментарий в коде роутера прямо так и говорит.

#### `delete_installation`

`DELETE`, **204**. Есть заявки — **409**. Нет — удаление вместе с проверками. Уведомления, которые ссылались на установку, не удаляются: у них `ON DELETE SET NULL` на `client_configuration_id`.

### `src/api/routers/checks.py`

Префикс `/version-checks`.

#### `_day_start(value)`

Полночь UTC для фильтра истории. `date_to` включается целиком: сравнение строго меньше полуночи следующего дня.

#### `run_checks(payload, actor, session)`

`POST /api/version-checks/run`, **201**, `WriterUser`. Внутри есть ветка «если роль клиент — 403». При текущей зависимости `WriterUser` клиент сюда не доходит: 403 отдаст `require` раньше. Ветка недостижима, пока сигнатура не сменится. Дальше `run_version_checks`, `commit_session`, `load_checks`. Ответ: созданные карточки и пропуски. **404**, если просили одну установку или клиента, а их нет. Пустой список установок у существующего клиента — пустой `created`, не ошибка.

#### `list_outdated`

`GET /api/version-checks/outdated`, `StaffUser`. Если передан `client_id`, сначала `get_client` (**404**). Иначе `outdated_report`. Руководитель этот путь тоже может вызвать. Отдельный отчёт `/api/reports/outdated-clients` считает то же самое, но пускает только `ReportUser` (админ и руководитель, без специалиста). Специалист ходит сюда, руководитель — в отчёты. Админ может в оба.

#### `list_checks`

`GET /api/version-checks`, `StaffUser`. Фильтры: клиент, установка, `is_outdated`, даты. Сортировка по `checked_at` вниз.

#### `read_check`

`GET /api/version-checks/{check_id}`. **404**, если нет. Клиент — только если установка его (`ensure_client_scope`). Сотрудник трёх ролей — да. Иная роль — **403**. Фронтенд не вызывает.

### `src/api/routers/notifications.py`

Префикс `/notifications`.

#### `_visible(actor, stmt, client_id, recipient_id)`

Клиент: только `recipient_id == actor.id`. Параметры клиента и получателя ему не расширяют ленту. Сотрудник может сузить по организации и по получателю.

#### `create_notification`

`POST /api/notifications`, **201**, писатель. `create_update_notification` (там **422**, если нет получателей, чужая установка или нет текста без установки), затем `commit_session` и повторное чтение со связями. Возвращает список: по письму на каждого активного портального пользователя. Вызывают `NotifyDialog` и `Compose`.

#### `list_notifications`

`GET /api/notifications`. Клиент, который передал чужой `client_id`, получает **403** до выборки. `unread` считается по аудитории без фильтра `is_read`, но с фильтром типа, если тип задан? Смотрите код: `audience` уже с клиентом и получателем, `unread_stmt` добавляет только `is_read = false`, а фильтр `type` добавляется к `stmt` после. Значит счётчик непрочитанных не сужается типом. Комментарий функции говорит: unread не зависит от фильтра `is_read`. От фильтра типа он тоже не зависит. Экран показывает этот счётчик над лентой.

#### `read_notification`

`GET /api/notifications/{id}`. **404**. Клиенту чужое письмо — **403**. Сотрудник видит. Фронтенд не вызывает: лента и так содержит текст.

#### `mark_read`

`POST /api/notifications/{id}/read`. **404**. Если `recipient_id` не текущий пользователь — **403** `Only the recipient can mark this notification as read`, в том числе для администратора. Ставит `is_read = True`, коммитит, перечитывает. Повторный вызов остаётся успешным: флаг и так истинен.

### `src/api/routers/planning.py`

Два роутера: `slots` (`/update-slots`) и `updates` (`/scheduled-updates`).

#### `_slot_query()`

Подзапрос: число неотменённых заявок на слот. Внешнее соединение со слотом, чтобы окно без заявок тоже попало в список, а `booked` стал 0 через `coalesce`.

#### `_owner_for_create(session, actor, specialist_id)`

Специалист создаёт окно себе, чужой `specialist_id` игнорируется. Администратор обязан передать `specialist_id`, иначе **422**. Владелец должен быть активным пользователем с ролью `specialist`, иначе **422** `Slot must belong to an active support specialist`. Руководитель до функции не доходит: маршрут на `WriterUser`.

#### `create_slot`

`POST /api/update-slots`, **201**. Дубль начала у того же специалиста в тот же день — **409**. Окно создаётся активным. В ответе `booked = 0`.

#### `available_dates`

`GET /api/update-slots/dates`. Берёт до 500 свободных активных окон начиная с `date_from` или с сегодня, группирует по дате: `open_slots` и `remaining_capacity`. Окна с `remaining <= 0` в группу не кладёт (после `available_only` таких и не должно остаться). Клиент этот путь видит. Экран — `SlotPicker`.

#### `list_slots` и `_list_slots`

`GET /api/update-slots`. Клиенту насильно `available_only=True` и `is_active=True`, даже если он попросил все. `available_only` оставляет активные, не закончившиеся (сегодня сравнивается `end_time` с локальным `datetime.now().time()`), с `booked < capacity`. Если `date_from` не задан, дата не раньше сегодня. Специалист и админ без флага видят и прошлое, и закрытые, и полные — так устроен экран «Окна записи».

Сравнение «сегодня» идёт через `date.today()` и `datetime.now()` без явной таймзоны процесса. В контейнере это время образа, обычно UTC. Для демо на одной машине расхождение незаметно; на границе суток окно может ещё считаться доступным или уже прошлым в зависимости от часов сервера, а не браузера.

#### `read_slot`

`GET /api/update-slots/{slot_id}`. Нет строки — **404**. Клиенту неактивное, прошлое или полное — тоже **404**. Фронтенд не вызывает.

#### `update_slot`

`PATCH /api/update-slots/{slot_id}`, писатель. Специалист, чьё окно чужое, — **403** `You can only change your own slots`. Администратор может менять любое. Вместимость ниже уже занятых мест — **422**. Время и специалиста этим методом не меняют.

#### `_update_filters`

К списку заявок присоединяет клиента и по необходимости слот. Фильтры: статус, клиент, назначенный специалист, подстрока названия организации, диапазон даты слота. Заявка без слота при фильтре по датам выпадает: условие смотрит `UpdateSlot.slot_date`, а соединение внешнее, у пустой даты сравнение не проходит.

#### `create_update`

`POST /api/scheduled-updates`, **201**, `CurrentUser`. Всю политику делает `create_scheduled_update`. Руководитель получит **403** из `ensure_can_book`. Успех — детальная карточка с историей. Вызывает `RequestForm`.

#### `list_updates`

`GET /api/scheduled-updates`. Клиенту подставляется его `client_id`. Чужой id — **403**. Нет привязки — пустая страница. Сортировка по `created_at` вниз.

#### `read_update`

`GET /api/scheduled-updates/{update_id}`. **404** или **403** для чужой заявки клиента. История включена.

#### `patch_update`

`PATCH /api/scheduled-updates/{update_id}`. Сначала `ensure_can_view`. Пустое тело (оба поля пусты) — **422** `Nothing to update`. Новый `slot_id` идёт в `assign_slot` (там свои 403/409). Только комментарий: руководитель — **403**, остальные, кто уже прошёл просмотр, комментарий пишут. Клиент тоже может сохранить комментарий, пока видит заявку. Смена даты разрешена сервисом только в `requested` и `scheduled`.

#### `patch_status`

`PATCH /api/scheduled-updates/{update_id}/status`, `WriterUser`. `change_status`. Клиент и руководитель сюда не входят. Вызывают кнопки на `UpdatePage`.

### `src/api/routers/reports.py`

Префикс `/reports`. Все три маршрута — `ReportUser`. Специалист получит **403**, хотя живой список отстающих ему доступен другим путём.

#### `updated_clients`

`GET /api/reports/updated-clients`. Аргументы `date_from`, `date_to`, `q`. Делегирует `updated_clients_report`.

#### `updates`

`GET /api/reports/updates`. Делегирует `updates_summary`.

#### `outdated_clients`

`GET /api/reports/outdated-clients`. Необязательный `client_id` проверяется `get_client`. Дальше тот же `outdated_report`, что у специалиста. Период дат этот отчёт не принимает: отставание — это текущее состояние каталога, не событие за интервал. Экран отчётов так и пишет в подзаголовке.

### `src/services/__init__.py`

Документация пакета. Кода нет.

### `src/services/common.py`

#### `like_pattern(value)`

Экранирует `\`, `%` и `_`, оборачивает в `%...%`. Так `ILIKE` ищет подстроку, а не шаблон. Почти все поиски `q` идут через неё.

#### `count_rows(session, stmt)`

`COUNT(*)` по подзапросу без `ORDER BY`. Иначе сортировка мешала бы агрегату. Возвращает int.

#### `commit_session(session)`

`commit`. `IntegrityError` — откат и **409** `Data conflict`. Сюда попадает в том числе нарушение `uq_configuration_versions_current`.

#### `flush_session(session)`

`flush` без коммита. Тот же **409** на конфликт. Нужен, чтобы узнать id новой строки до коммита и поймать уникальность раньше ответа.

#### `remember_actor(user)`

Кладёт `_role_code` и `_client_id` в `__dict__`. Возвращает того же пользователя. Вызывает только `get_current_user`.

#### `actor_role(user)`

Кэш или `user.role.code`.

#### `actor_client_id(user)`

Кэш, если ключ есть (в том числе значение `None` у сотрудника), иначе колонка.

#### `ensure_client_scope(user, client_id)`

Клиент с другим `client_id` — **403** `You can only access your own client data`. Остальные роли проходят. Не проверяет, существует ли организация.

#### `get_role(session, code)`

Строка справочника или **500** `Role {code} is not configured`. Это сигнал, что миграция не вставила роли и сид ролей тоже не отработал.

### `src/services/catalog.py`

#### `get_client(session, client_id)`

Клиент с ответственным или **404**.

#### `ensure_staff_user(session, user_id)`

Активный пользователь, роль не `client`. Иначе **422**.

#### `get_configuration(session, configuration_id)`

`session.get` или **404**.

#### `list_versions(session, configuration_id)`

Релизы: дата выпуска по убыванию, пустые даты в конце (`nullslast`), затем номер по убыванию.

#### `clear_current(session, configuration_id, except_id=None)`

`UPDATE` сбрасывает `is_current` у текущих релизов конфигурации, кроме `except_id`. Делает `flush`. Это подготовка к новому текущему, чтобы частичный индекс не увидел две истины в одной транзакции.

#### `get_current_version(session, configuration_id)`

Одна строка с `is_current` или `None`.

#### `map_current_versions(session, configuration_ids)`

То же пачкой. Пустой набор id — пустой словарь, запрос не выполняется.

#### `map_last_checks(session, installation_ids)`

`max(checked_at)` по установкам.

#### `installation_options()`

Тройка `selectinload`: клиент, конфигурация, установленная версия.

#### `get_installation(session, installation_id)`

Установка с этими связями или **404** `Client configuration not found`.

#### `ensure_version_of_configuration(session, version_id, configuration_id)`

Релиз есть и его `configuration_id` совпал. Иначе **422**.

#### `version_reference_count(session, version_id)`

Сумма ссылок из установок (`installed_version_id`), проверок (обе колонки версий) и заявок (`source_version_id` или `target_version_id`). Больше нуля — удалять нельзя.

#### `touch_current_flag(session, version, is_current)`

Если делают текущим: `clear_current` с `except_id=version.id`, затем флаг в истину. Если снимают флаг с того, кто и так не текущий, просто пишут ложь. Если снимают с текущего — **422**, другой текущий надо назначить раньше. Иначе конфигурация осталась бы без актуального релиза при живых старых версиях, и проверки начали бы пропускать установки.

### `src/services/checks.py`

#### `run_version_checks(session, actor, *, client_id, client_configuration_id)`

Выбирает установки (одну, клиента или все). Нет такой установки — **404**. Нет такого клиента — **404**. Клиент без установок — пустой результат. Для каждой берёт текущий релиз. Нет текущего — запись в `skipped`, строка проверки не создаётся. Иначе `VersionCheck` с автором `actor.id` и `is_outdated` по сравнению id. Если что-то создано — `flush_session`. Коммитит роутер, не эта функция. Возвращает пару списков.

#### `check_load_options()`

Жадная загрузка установки, её клиента и конфигурации, обеих версий и автора. Нужна карточке `version_check_read`.

#### `load_checks(session, checks)`

Перечитывает только что созданные id с этими связями, новые сверху. Пустой вход — пустой список.

#### `outdated_report(session, *, q, client_id)`

Живое сравнение. Соединение с версией `is_current` внутреннее: установка без текущего релиза в отчёт не попадает (её и сравнивать нельзя). Условие — установленный id не равен текущему. Группирует по клиенту в `OutdatedClient`. Порядок — название организации, затем конфигурации. Возвращает `OutdatedReport`. Эту же функцию вызывают и список специалиста, и отчёт руководителя.

### `src/services/notifications.py`

#### `notification_options()`

Загрузка клиента и конфигурации установки.

#### `notify_client_users(...)`

Ищет активных пользователей роли `client` с этим `client_id`. Никого нет: при `strict=True` — **422** с текстом про регистрацию портального пользователя; при `strict=False` — пустой список. Иначе каждому одинаковые `title` и `message`, `is_read=False`, общий `created_by_id` и ссылки на установку и заявку. `flush_session`. Вызывают явная рассылка (`strict=True`) и `_notify_status` (`strict=False`).

#### `create_update_notification(...)`

Грузит клиента. Если передана установка и она чужая — **422**. Если установки нет и текст пустой — **422**. Если установка есть, а текст не передали, собирает русский заголовок и абзац: имя конфигурации, имя базы или слова «информационная база», установленный номер и актуальный (или «не задана»). Тип всегда `UPDATE_AVAILABLE`. Дальше `notify_client_users` со `strict=True`.

### `src/services/planning.py`

Константы `OPEN_STATUSES`, `ALLOWED_TRANSITIONS`, `WRITERS` (админ и специалист). Таблица переходов — в разделе 2.

#### `update_options(*, with_history=False)`

Набор `selectinload` для карточки заявки. С историей добавляется цепочка и автор каждого события.

#### `get_scheduled_update(session, update_id, *, with_history=False)`

Заявка или **404**. `populate_existing=True`: если объект уже в сессии, SQLAlchemy обновит его, а не отдаст устаревший кэш. Это нужно после `expire` связей.

#### `ensure_can_view(user, row)`

Тонкая обёртка `ensure_client_scope` на `row.client_id`.

#### `ensure_can_book(user, installation)`

Клиент — только своя установка. Админ и специалист — да. Руководитель и любая прочая роль — **403**.

#### `booked_count(session, slot_id, *, ignore_update_id=None)`

Число заявок на слот со статусом не `cancelled`. Саму заявку можно исключить, когда она меняет слот или подтверждает свой.

#### `slot_is_past(slot, today=None, now=None)`

Дата раньше сегодня или сегодня, но `end_time` уже не позже текущего времени.

#### `lock_slot(session, slot_id)`

`SELECT … FOR UPDATE`. Нет строки — **404**. Блокировка держится до конца транзакции, то есть до `commit_session` роутера.

#### `ensure_slot_available(session, slot, *, ignore_update_id=None)`

Неактивен — **409** `Slot is not active`. В прошлом — **409** `Slot is in the past`. Мест нет — **409** `Slot is full`.

#### `add_history(...)`

Добавляет `UpdateStatusHistory` через `session.add`, не через коллекцию `update.status_history`. Комментарий в коде объясняет зачем: дописывание в уже загруженную коллекцию в async может вызвать ленивую подгрузку. Старые строки не трогает.

#### `_notify_status(session, update, kind, actor_id)`

Три текста по-русски: дата и интервал для `UPDATE_SCHEDULED` (если слот загружен), номер версии для `UPDATE_COMPLETED`, отмена для `UPDATE_CANCELLED`. Иной тип — выход. Затем `notify_client_users` со `strict=False`. Переход в работу сюда не приходит.

#### `create_scheduled_update(...)`

Проверяет установку и право бронировать. Открытая заявка на ту же установку — **409**. Нет текущего релиза — **422**. Слот, если передан, блокируется и проверяется. Назначение специалиста — как в разделе 2. Статус сразу `scheduled`, если слот есть, иначе `requested`. Пишет заявку, историю с пустым старым статусом. Если слот был, сбрасывает кэш связей и шлёт письмо о дате. Коммит — снаружи.

#### `assign_slot(...)`

Право бронировать. Клиенту менять дату можно только в `requested` и `scheduled`, иначе **409** `The date can no longer be changed`. То же ограничение статусов для сотрудника, текст чуть другой. Слот блокируется, доступность проверяется без учёта этой заявки. Ставит слот и специалиста слота. Если статус ещё не `scheduled`, переводит и пишет историю. Письмо `UPDATE_SCHEDULED` уходит и при повторном выборе даты.

#### `_apply_completion(session, update)`

Если цель не загружена, читает её по id. Если цели нет совсем, берёт текущий релиз каталога и записывает его в заявку; если и его нет — **422**. Пустой `source_version_id` заполняется установленным релизом до подмены. Затем установка переключается на цель, `completed_at = now(UTC)`, связь `target_version` обновляется в объекте.

#### `change_status(...)`

Не писатель — **403**. Тот же статус — **422**. Нет в `ALLOWED_TRANSITIONS` — **409** с текстом перехода. В `scheduled` без слота — **422**; со слотом слот снова блокируется и проверяется, специалист берётся со слота. В `requested` слот обнуляется. В `completed` вызывается `_apply_completion`. Комментарий, если прислан, заменяет `comment` заявки (не дописывает). История пишется всегда. Письмо — для `scheduled`, `completed`, `cancelled`. Для `in_progress` письма нет. Перед письмом связи сбрасываются, чтобы в текст не попал старый слот из кэша сессии.

### `src/services/reports.py`

Константа `PLANNED` — `requested`, `scheduled`, `in_progress`. `in_progress` ещё «в плане»: факт в отчёте — только `completed`.

#### `_completed_bounds(date_from, date_to)`

Границы `completed_at` в UTC: с полуночи `date_from` включительно и до полуночи дня после `date_to` не включая.

#### `updated_clients_report(...)`

Только `status == completed`. Фильтр дат — по `completed_at`. Поиск — по названию организации. Группирует в `UpdatedClientReport`, внутри — `UpdatedConfigurationReport` с именами версий и специалиста. Сортировка завершённых — новые сверху.

#### `updates_summary(...)`

Все заявки (с поиском по организации). Если задан период, выполненные режутся по `completed_at`, остальные — по дате слота или, если слота нет, по календарному дню `created_at` (`func.coalesce(UpdateSlot.slot_date, cast(created_at, Date))`). `by_status` инициализируется нулями по всем пяти статусам. `planned` и `completed` — списки кратких строк. Отменённые в эти два списка не кладутся, они есть только в `cancelled_count` и `by_status`. План сортируется: сначала у кого есть дата слота, по дате, затем по созданию.

### `src/data/__init__.py`

Документация пакета моделей и сида.

### `src/data/repositories/__init__.py`

Текст: зарезервировано под репозитории, в MVP запросы собраны в `src/services`. Классов нет. Это честный пустой пакет, не скрытый слой.

### `src/data/models/__init__.py`

Импортирует все модели и перечисления, перечисляет их в `__all__`. Побочный эффект импорта: таблицы регистрируются в `Base.metadata`. Поэтому `alembic/env.py` делает `import src.data.models`. Если новую модель забыть импортировать здесь, автогенерация Alembic её не увидит. Сейчас автогенерация не используется: обе миграции написаны вручную, но импорт всё равно нужен, чтобы метаданные были полными при `compare_type`.

Удалённый файл `src/data/models/schedual_updates.py` в дереве отсутствует. README объясняет, зачем его убрали: он отображал те же таблицы второй раз и при импорте регистрировал бы `scheduled_updates` дважды. На защите достаточно сказать: дублирующей модели с опечаткой в имени больше нет, живая модель — `scheduled_updates.py`.

### `src/data/models/enums.py`

#### `persisted_enum(enum_cls, name)`

Колонка SQLAlchemy: `native_enum=False`, длина 32, в базу пишется значение (`admin`), не имя константы (`ADMIN`). Имя аргумента — имя типа в метаданных, не тип PostgreSQL. Отдельных типов `ENUM` в базе нет: миграция создаёт `String(32)`. Так проще сравнивать и не плодить тип при каждой смене списка.

#### `RoleCode`

`admin`, `specialist`, `manager`, `client`.

#### `UpdateStatus`

`requested`, `scheduled`, `in_progress`, `completed`, `cancelled`.

#### `NotificationType`

`update_available`, `update_scheduled`, `update_completed`, `update_cancelled`.

### `src/data/models/mixins.py`

#### `TimestampMixin`

`created_at` и `updated_at`, оба `DateTime(timezone=True)`, `server_default=now()`, не null. `updated_at` дополнительно `onupdate=func.now()`: SQLAlchemy подставляет время в `UPDATE`, который сама же генерирует. Это не триггер PostgreSQL. Правка строки сырым SQL мимо ORM `updated_at` не сдвинет. У `VersionCheck` и `UpdateStatusHistory` mixin нет: у проверки своё `checked_at`, у истории своё `changed_at`, и строки этих таблиц по задумке не обновляют.

### `src/data/models/roles.py`

#### Класс `Role`

Таблица `roles`. `id` UUID, `code` уникален, `name` уникален. Связь `users`. Код из API не редактируется: эндпоинта правки роли нет, только чтение справочника.

### `src/data/models/users.py`

#### Класс `User`

Таблица `users`. `email` уникален, индекс на имя. `hashed_password` обязателен. `is_active` по умолчанию истина. `role_id` — `ON DELETE RESTRICT`: роль, на которую кто-то ссылается, не удалить. `client_id` необязателен, `ON DELETE SET NULL`, `use_alter=True`, потому что пользователи и клиенты ссылаются друг на друга (ответственный и портальный пользователь). Миграция создаёт этот ключ вторым шагом, после таблицы `clients`.

Связи: роль, клиент, список организаций, где пользователь ответственный (`assigned_clients`), проверки, созданные и полученные уведомления, слоты, заявки как автор и как назначенный, история статусов.

### `src/data/models/clients.py`

#### Класс `Client`

Таблица `clients`. Уникальные название, телефон, почта. `responsible_employee_id` → `users.id` `ON DELETE SET NULL`. Связи: ответственный, портальные пользователи, установки (каскад delete-orphan), уведомления, заявки.

### `src/data/models/configurations.py`

#### Класс `Configuration`

Таблица `configurations`. Уникальное имя, необязательное описание. Версии каскадом, установки обратной связью без каскада удаления конфигурации.

#### Класс `ConfigurationVersion`

Таблица `configuration_versions`. Ограничения `uq_configuration_version` и частичный индекс `uq_configuration_versions_current` — см. раздел 2. Внешний ключ на конфигурацию `ON DELETE CASCADE`. Обратная связь на установки по `installed_version_id`.

### `src/data/models/client_configurations.py`

#### Класс `ClientConfiguration`

Таблица `client_configurations`, уникальность `uq_client_configuration`. Клиент удаляется каскадом вместе с установками (`ON DELETE CASCADE`). Конфигурацию и установленный релиз так не удалить (`RESTRICT`). Связи: клиент, конфигурация, установленная версия, проверки (каскад), уведомления, заявки.

### `src/data/models/version_checks.py`

#### Класс `VersionCheck`

Таблица `version_checks`. Установка — `CASCADE`. Обе версии и автор — `RESTRICT`: релиз или человека, которые уже в истории сверки, просто так не стереть. `is_outdated` и `checked_at` индексированы. Отдельного `updated_at` нет.

### `src/data/models/notifications.py`

#### Класс `Notification`

Таблица `notifications`. Тип через `persisted_enum`. Получатель — `CASCADE` (удалили пользователя — его письма тоже). Автор — `SET NULL`. Клиент — `CASCADE`. Установка и заявка — `SET NULL`, чтобы удаление установки без заявок не убивало текст письма, а снятие ссылки на заявку не требовалось. На практике заявку из API не удаляют вовсе: эндпоинта удаления заявки нет.

### `src/data/models/update_slots.py`

#### Класс `UpdateSlot`

Таблица `update_slots`, уникальность `uq_specialist_slot`. Специалист — `RESTRICT`. `capacity` по умолчанию 1, `is_active` по умолчанию истина.

### `src/data/models/scheduled_updates.py`

#### Класс `ScheduledUpdate`

Таблица `scheduled_updates`. Статус по умолчанию `requested`. `completed_at` необязателен. Клиент — `CASCADE`. Установка — `RESTRICT` (поэтому установку с заявками не удалить и на уровне базы, не только проверкой в роутере). Обе версии — `RESTRICT`, в первой миграции этих колонок не было, их добавляет вторая. Слот — `SET NULL`. Автор заявки — `RESTRICT`. Назначенный специалист — `SET NULL`. История каскадом delete-orphan, по `changed_at`. Уведомления обратной связью.

#### Класс `UpdateStatusHistory`

Таблица `update_status_history`. `old_status` может быть пустым. Заявка — `CASCADE`. Автор смены — `RESTRICT`. Строки из API не правятся.

### `src/data/seed.py`

Стабильные демо-идентификаторы: пространство имён `NS = uuid c0ffee00-0000-4000-8000-000000000001`, дальше UUID пятой версии от логического ключа.

`DEMO_EMAILS` — четыре адреса. `DEMO_PASSWORD` — пароли из README. `ROLE_TITLES` — русские названия ролей.

#### `demo_id(name)`

`uuid.uuid5(NS, name)`. Повторный запуск получает те же id и не плодит дубликаты, если строка ищется по этому id. Вызывается при создании новых демо-строк.

#### `seed_initial_data(session)`

Читает коды ролей. Добавляет недостающие из `ROLE_TITLES`. Коммитит. Повторно ничего не дублирует. Роли также вставляет первая миграция. Если миграция уже отработала, сид видит четыре кода и пропускает вставку. Если кто-то поднял таблицы без этого куска миграции, сид роли допишет. Оба пути сходятся.

#### `_role(session, code)`

Роль или `RuntimeError` с просьбой выполнить `alembic upgrade head`.

#### `_ensure_user(...)`

Ищет по почте, потом по `demo_id`. Нашёл: при необходимости меняет почту и, если `verify_password` не сошёлся, перехеширует пароль на демо-значение. Это чинит старую базу, где пароль когда-то был другим, иначе вход `admin123` давал бы 401. Роль и `client_id` у уже существующего пользователя сид не переписывает. Не нашёл — создаёт с стабильным id, активным, с заданной ролью.

#### `_ensure_client(...)`

Ищет по точному `company_name`. Есть — возвращает как есть, телефон и ответственного не трогает. Нет — создаёт.

#### `_ensure_configuration(...)`

Ищет по имени. Есть — возвращает. Нет — создаёт. Описание старой строки не обновляет.

#### `_ensure_version(...)`

Ищет пару конфигурация+номер. Есть — возвращает, флаги не переписывает. Нет и релиз должен быть текущим — сначала снимает `is_current` с других, иначе на старых данных сработает `uq_configuration_versions_current`. Затем вставляет.

#### `_ensure_installation(...)`

Ищет пару клиент+конфигурация. Есть — возвращает, установленную версию не меняет. Нет — создаёт.

#### `seed_demo_data(session)`

Собирает учебный стенд. Подробные данные — в разделе 10. Кратко по шагам: четыре пользователя (клиент создаётся после организаций, потому что ему нужен `client_id` Ромашки), две организации, две конфигурации, по два релиза, две установки, слоты на семь следующих дней двумя окнами, выполненная заявка Василька с двумя строками истории, одна проверка Ромашки, одно непрочитанное уведомление Ивану Петрову. Если уведомление уже есть, но получатель другой, получателя поправляют. В конце `commit` и запись в лог. Пароли в лог не пишутся.

Идемпотентность значит: второй запуск не создаёт вторую Ромашку, второй релиз 3.0.175 и второе уведомление с тем же id. Она не значит «привести базу к эталону». Уже существующие версии, установки и клиенты не перезаписываются. Пароль демо-пользователя — исключение, его выравнивают.

История Василька вставлена напрямую и содержит переход `requested → completed`. Живой `change_status` такой переход запретит. Это учебная строка для отчёта, а не пример разрешённого перехода. На защите так и сказать.

#### `_cli()`

Точка `python -m src.data.seed`. Открывает сессию, вызывает `seed_initial_data` и `seed_demo_data`. HTTP не поднимает. Имеет смысл после `alembic upgrade head`. Если таблиц нет, упадёт на запросе к `roles`.

#### `if __name__ == "__main__"`

Настраивает лог и `asyncio.run(_cli())`.

### `alembic.ini`

Обычный каркас. `script_location = alembic`. `sqlalchemy.url` в файле — заглушка `driver://user:pass@localhost/dbname`. Рабочий URL подставляет `alembic/env.py` из `settings.database_url`, то есть из `.env` и окружения. Логи Alembic — INFO, SQLAlchemy — WARN.

### `alembic/README`

Одна строка: миграции для Control_1C_version.

### `alembic/script.py.mako`

Шаблон `alembic revision`. В репозитории им не пользуются для уже лежащих файлов: обе версии написаны вручную. Если спросят «что это», ответ: заготовка новой миграции, на работу стенда не влияет.

### `alembic/env.py`

Импортирует `settings`, `Base` и `src.data.models` (импорт ради регистрации таблиц). Подменяет URL.

#### `run_migrations_offline()`

Печатает SQL без соединения. `literal_binds=True`, `compare_type=True`. Режим `alembic upgrade head --sql`.

#### `do_run_migrations(connection)`

Настраивает контекст на уже открытом синхронном соединении и запускает миграции. Тоже `compare_type=True`.

#### `run_async_migrations()`

Поднимает async-движок с `NullPool` и `ssl=False`, прогоняет `do_run_migrations` через `run_sync`, закрывает движок. Пул приложения здесь не используется: у миграции свой короткий движок.

#### `run_migrations_online()`

`asyncio.run(run_async_migrations())`. Это обычный путь `alembic upgrade head` из entrypoint и с хоста.

В конце файла выбор: offline или online по `context.is_offline_mode()`.

### `alembic/versions/.gitkeep`

Пустой файл, чтобы каталог версий существовал в git, даже если бы миграций не было. Миграции рядом есть, файл просто лежит.

### `alembic/versions/20261102_0001_initial_schema.py`

Ревизия `20261102_0001`, предыдущей нет. Это корень цепочки.

#### `upgrade()`

Создаёт таблицы в порядке зависимостей: `roles`, `users` (ещё без внешнего ключа на клиентов), `clients`, затем `fk_users_client_id_clients`, `configurations`, `configuration_versions` вместе с `uq_configuration_version` и частичным индексом `uq_configuration_versions_current`, `client_configurations` с `uq_client_configuration`, `version_checks`, `update_slots` с `uq_specialist_slot`, `scheduled_updates` (пока без колонок версий), `update_status_history`, `notifications`. Индексы повторяют те, что объявлены на моделях. В конце `bulk_insert` четырёх ролей со случайными UUID (`uuid.uuid4()`, не `demo_id`). Поэтому id ролей в разных базах разные, а коды одинаковые. Пользователи ссылаются на роль по id, найденному по коду, так что это не мешает.

#### `downgrade()`

Удаляет таблицы в обратном порядке и снимает частичный индекс до удаления `configuration_versions`, затем ключ `fk_users_client_id_clients`, затем клиентов, пользователей и роли.

### `alembic/versions/20261105_0002_scheduled_update_versions.py`

Ревизия `20261105_0002`, родитель `20261102_0001`.

#### `_column_names`, `_fk_names`, `_index_names`

Смотрят инспектор SQLAlchemy. Миграция идемпотентна наполовину: если колонка или ключ уже есть (старая локальная база могла получить `target_version_id` вручную), шаг пропускается. На чистой базе после первой ревизии добавляется всё.

#### `upgrade()`

При отсутствии добавляет `source_version_id` и `target_version_id`, внешние ключи на `configuration_versions` с `ON DELETE RESTRICT`, индексы по ним и индекс `ix_scheduled_updates_completed_at`.

#### `downgrade()`

Снимает индекс, ключи и колонки, только если они ещё есть.

### `_ensure_db.py`

Отдельный скрипт, не шаг Compose и не `lifespan`. Compose создаёт базу сам переменной `POSTGRES_DB`. Скрипт нужен, если Postgres уже запущен, а базы `control_1c_version` в нём нет.

#### `main()`

Парсит `settings.database_url` (отрезает `+asyncpg`), подключается к служебной базе `postgres` через asyncpg и `CREATE DATABASE`, если `pg_database` такой базы не знает. Печатает `DATABASE_CREATED` или `DATABASE_EXISTS`. Имя базы подставляется в SQL кавычками. Это локальный помощник администратора стенда, не пользовательский ввод из интернета: URL берётся из настроек.

Запуск как скрипт: `asyncio.run(main())`.

### `scripts/smoke.py`

Повторяемый прогон требований без браузера. Адрес — переменная `BASE_URL`, иначе `http://127.0.0.1:8000`. Метка `STAMP` — `time.time()` целым, чтобы имена созданных строк не сталкивались при повторном запуске.

#### Класс `SmokeError`

Наследник `SystemExit`. В `main` его ловят и печатают в stderr с кодом 1. Если бросить его мимо этого `try`, процесс и так завершится с ненулевым кодом.

#### `request(method, path, token=None, body=None, expected=200)`

Собирает JSON-запрос библиотекой `urllib`. Кладёт Bearer, если токен есть. Считает ответ успешным, только если статус в `expected` (число или кортеж). Иначе `SmokeError` с куском тела. Пустое тело — `None`, иначе JSON.

#### `ok(label)`

Печатает `OK` и подпись шага.

#### `login(email, password)`

`POST /api/auth/login`, возвращает `access_token`. Нет токена или роли — `SmokeError`.

#### `main()`

Ждёт `/health` до 30 секунд. Проверяет `status` и `database`. Проверяет `/health/ready` и `demo_seeded`. Проверяет, что в `/openapi.json` есть ключевые пути, и что `/docs` отвечает 200. Неверный пароль админа должен дать 401. Входит четырьмя демо-ролями. Клиентский `/api/auth/me` должен вернуть роль `client`.

Дальше негативные проверки ролей: клиент и специалист не создают пользователей (403), руководитель не создаёт клиента (403), клиент не читает отчёт (403).

Затем читает демо: поиск пользователя «Мария», четыре роли, клиент «Ромашка», конфигурация «Бухгалтерия» с текущей версией, установка Ромашки с `is_outdated`.

Создаёт свою организацию, пустую организацию, портального пользователя, конфигурацию, версии 1.0.0 и 1.0.1 (вторая текущая), установку на 1.0.0 и убеждается, что она устарела.

Запускает проверку одной установки, читает историю, живой список по новой организации и по Ромашке.

Шлёт уведомление, входит новым клиентом, видит непрочитанное, отмечает прочитанным.

Открывает слот далеко в будущем (день и время зависят от `STAMP`, чтобы не попасть в `uq_specialist_slot` на повторе), убеждается, что дата видна клиенту.

Клиент создаёт заявку со слотом: статус должен стать `scheduled`, история не пустая.

Специалист видит её в списке и в карточке.

Переводит в `in_progress`, затем в `completed`. Обратный переход в `requested` обязан дать 409. Установка после этого на 1.0.1 и не устарела. Повторная проверка это подтверждает. У клиента есть письмо типа `update_completed`.

Руководитель видит организацию в отчёте 5.1 и Василька в истории обновлений. Счётчик плана в 5.2 равен сумме трёх незавершённых статусов. Новая организация из списка отстающих исчезла, Ромашка осталась.

Пустого клиента удаляет (204). Клиента с заявкой удалить нельзя (409).

Печатает, что прогон прошёл. Созданные «ООО Проверка …» скрипт не удаляет: у них есть история. Повторные прогоны копят такие организации. Это стоит сказать, если преподаватель увидит много «ООО Проверка» в реестре.

### `Dockerfile` (корень, образ API)

База `python:3.12-slim`. `PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED`, `PYTHONPATH=/app`. Ставит `requirements.txt` без кэша pip, копирует дерево. `sed` снимает `\r` с `docker/entrypoint.sh` и делает его исполняемым: checkout с Windows мог принести CRLF, и dash тогда падает на `set -eu\r` с «Illegal option». Открывает 8000. `ENTRYPOINT` — этот скрипт.

Корневой `.dockerignore` не пускает в образ `.venv`, `.git`, кэши, `.env` и каталог `frontend`. Образ API не содержит «Норд».

`.gitattributes` помечает `*.sh`, `Dockerfile` и `docker-compose.yml` как текст с LF, чтобы CRLF не возвращался из git. `sed` в Dockerfile — вторая сетка на случай, если файл всё же приехал с CR.

### `docker/entrypoint.sh`

`#!/bin/sh`, `set -eu` (без `pipefail`: это dash, не bash). Комментарий в файле: демо создаёт приложение, не этот скрипт.

Встроенный Python ждёт базу до 30 раз с паузой в секунду: `SELECT 1` через `engine`. Не дождался — сообщение в stderr и код 1. Успех — `engine.dispose()`, чтобы не унести соединение в следующий процесс.

Затем `alembic upgrade head` и `exec uvicorn main:app --host 0.0.0.0 --port 8000`. `exec` заменяет шелл на uvicorn, чтобы сигналы остановки доходили до сервера.

### `docker-compose.yml`

Три сервиса и том `control_1c_pgdata`.

**`db`.** Образ `postgres:16-alpine`, имя контейнера `control_1c_version_db`, перезапуск `unless-stopped`. Пользователь, пароль и база — `postgres` / `postgres` / `control_1c_version`. Порт `5433:5432`: внутри контейнера Postgres слушает обычный 5432, на хост он выведен как 5433, чтобы не столкнуться с локальным Postgres на 5432. Данные в томе. Healthcheck — `pg_isready` каждые 5 секунд, до 10 попыток.

**`api`.** Сборка из корня, имя `control_1c_version_api`. Стартует после здоровой `db`. `DATABASE_URL` указывает на хост `db` и порт `5432` (это сеть Compose, не хостовый 5433). `ENVIRONMENT=dev`, `DEBUG=false`, `SEED_DEMO=true`, `JWT_SECRET=dev-only-change-me`, срок токена 720 минут. Порт `8000:8000`. Healthcheck дергает `http://127.0.0.1:8000/health` из Python, `start_period` 20 секунд, до 20 попыток: за это время entrypoint должен дождаться базы и накатить миграции.

**`web`.** Сборка `./frontend`, имя `control_1c_version_web`. Стартует после здорового API. Порт `8080:80`.

Секрет JWT в файле учебный. Перед любым общим стендом его меняют. README говорит то же.

### `.env.example`

Образец для запуска API на хосте: `ENVIRONMENT=dev`, `DEBUG=false`, URL на `localhost:5433`, учебный секрет, 720 минут, `SEED_DEMO=true`. Файл `.env` в git не входит (`.gitignore`).

### `.gitignore` и `.dockerignore`

Игнорируются `.env`, виртуальное окружение, кэши Python, `.idea`, `node_modules`, `frontend/dist`. Секреты из `.env` в репозиторий не попадают. Учебный секрет в Compose и в примере — отдельная история: он не секрет, он заглушка.

---

## 6. Фронтенд «Норд» по файлам

Каталог `frontend/`. Сборки в репозитории нет: `dist` появляется после `npm run build` и в git не входит.

### `frontend/package.json`

Имя пакета `nord`, версия `0.1.0`, `"type": "module"`, `"private": true`. Скрипты: `dev` — Vite, `build` — `tsc --noEmit` и затем `vite build` (ошибка типов останавливает сборку), `preview` — собранный бандл на `127.0.0.1:4173`. Зависимости: `react` и `react-dom` 19, `react-router-dom` 7. В devDependencies: типы React, `@vitejs/plugin-react`, TypeScript 5.8, Vite 6. Отдельной UI-библиотеки и клиента вроде axios нет: запросы пишет свой `fetch`.

`frontend/package-lock.json` фиксирует дерево npm для `npm ci` в Docker. Построчно его на защите разбирать не нужно: это слепок версий, не логика.

### `frontend/tsconfig.json`

Цель ES2022, `jsx: react-jsx`, `strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `noUncheckedIndexedAccess`, `noEmit`. В сборку входит только `src`. Неиспользуемая переменная не соберётся. Поэтому «мёртвый» код во фронтенде почти не лежит: если символ импортирован, он используется. Исключение — стили: классы `.sr-only` и `.stack-lg` в CSS есть, в компонентах не встречаются.

### `frontend/src/vite-env.d.ts`

Одна строка `/// <reference types="vite/client" />`. Подключает типы Vite для импорта модулей. Логики нет.

### `frontend/index.html`

Язык `ru`, заголовок «Норд — сопровождение 1С», `noindex`, цвет темы `#14241c`. Иконка — встроенный SVG, тот же знак, что рисует компонент `Mark`. Шрифты с Google Fonts: Cormorant Garamond, IBM Plex Mono, Onest. Если шрифты не загрузятся, CSS падает на Liberation и системные. Корень — `<div id="root">`, скрипт `/src/main.tsx`. Фон страницы до загрузки CSS уже `#efe8dc`, чтобы не мигал белый.

### `frontend/vite.config.ts`

Плагин React. Сервер разработки: хост `127.0.0.1`, порт **5173**. Прокси `/api` и `/health` на `http://127.0.0.1:8000`, `changeOrigin: true`. Preview: хост тот же, порт **4173**, тот же прокси. Отдельного `base` нет, пути абсолютные от корня сайта. Переменных `VITE_*` код не читает: адрес API зашит как относительный, а цель прокси — константа `api` в этом файле.

### `frontend/nginx.conf`

Слушает 80, корень `/usr/share/nginx/html`, `index.html`, UTF-8, gzip для css, js, json и svg.

`resolver 127.0.0.11` — встроенный DNS Docker. Имя `api` резолвится в момент запроса, а не при старте nginx. Иначе после пересоздания контейнера API nginx держал бы старый IP. Поэтому `proxy_pass` идёт через переменную `$upstream`, а не через литерал `http://api:8000`: с переменной nginx как раз спрашивает резолвер.

`location /api/` проксирует на `api:8000`, передаёт `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`.

Отдельно `location = /health` и `location = /health/ready`. Префикс `/health/` целиком не проксируется, только эти два точных пути. Другого `/health/...` в API нет.

`location /` — `try_files` на `index.html`. Это нужно React Router: адрес `/clients/…` не файл на диске, его открывает `App`.

### `frontend/Dockerfile`

Две стадии. Сборка: `node:22-alpine`, `npm ci`, `npm run build`. Отдача: `nginx:1.27-alpine`, конфиг поверх `default.conf`, статика из `/app/dist`. Наружу 80. `frontend/.dockerignore` не копирует `node_modules`, `dist`, `.git` и markdown.

### `frontend/src/main.tsx`

Ищет `#root`. Нет элемента — бросает `Error` «Root element is missing», приложение не монтируется. Иначе `createRoot` и `StrictMode`. Порядок провайдеров снаружи внутрь: `AuthProvider`, `ToastProvider`, `ConfirmProvider`, `BrowserRouter`, `App`. Сессия снаружи тостов, потому что тост может понадобиться уже внутри страниц, а обработчик 401 живёт в сессии и не зависит от тоста. `BrowserRouter` внутри, потому что страницы используют `useNavigate` и `Link`, а охрана маршрутов — тоже внутри `App`.

### `frontend/src/App.tsx`

#### `App()`

Только таблица маршрутов, без разметки.

- `/login` обёрнут в `LoginGate`: вошедшего сразу уводит на `/`.
- Всё остальное, что ниже, внутри `RequireAuth`: нет сессии — на `/login`, сессия есть — `Shell` и вложенные маршруты.
- `/` — `HomePage`.
- `/clients`, `/clients/:clientId`.
- `/configurations`, `/configurations/:configurationId`.
- `/installations`.
- `/notifications`.
- `/updates`, `/updates/:updateId`.
- Группа `RequireRole` для `admin`, `specialist`, `manager`: `/checks` и `/slots`.
- Группа для `admin` и `manager`: `/reports`.
- Группа для `admin`: `/users`.
- Внутри оболочки неизвестный путь — `NotFoundPage`.
- Совсем снаружи, если маршрут не попал в `RequireAuth` (практически уже покрыто), `*` ведёт на `/`.

Клиент физически может набрать `/reports`. Оболочка откроется, `RequireRole` покажет пустое состояние «Этот раздел для другой роли» и ссылку на обзор. Запроса к отчётам страница не сделает, потому что `ReportsPage` не смонтируется.

### `frontend/src/api/types.ts`

Зеркало схем ответа и тел запроса. Это не проверка на сервере: сервер всё равно валидирует Pydantic. Типы нужны, чтобы экран не выдумывал поля.

Имеет смысл помнить отличия от «хотелки»:

- `RoleCode`, `UpdateStatus`, `NotificationType` — строковые объединения, те же значения, что в Python-перечислениях.
- `Page<T>` совпадает с серверным `Page`.
- `Health` — три строки `status`, `app`, `database`. Поля `demo_seeded` здесь нет: экран готовность не читает.
- `is_outdated` у установки — `boolean | null`.
- `UserRead` без пароля.
- `UpdatesReport.by_status` — `Record<string, number>`, не жёсткая карта статусов.
- `PageQuery` объявлен и нигде не импортируется. Это единственный неиспользуемый тип файла. На сборку не влияет: `noUnusedLocals` смотрит на локальные символы модулей-потребителей, а не на неимпортированный экспорт. Тип просто лежит.

Остальные типы один к одному повторяют `schemas.py`: пользователи, клиенты, конфигурации, версии, установки, проверки, отчёты устаревания, уведомления, слоты, заявки, отчёты. Перечислять каждое поле второй раз нет смысла: они названы так же, как в разделе про схемы. Если преподаватель ткнёт в `ScheduledUpdateDetail`, ответ: это `ScheduledUpdateRead` плюс `status_history: StatusEventRead[]`, и его отдаёт `GET /api/scheduled-updates/{id}`.

### `frontend/src/api/errors.ts`

Словарь `DETAILS` переводит известные английские `detail` сервера на русский. Сюда входят все строки, которые роутеры и сервисы кладут в `HTTPException`. Если сервер добавит новую фразу и её забудут в словарь, пользователь увидит запасной текст, а не ключ.

`FIELD_LABELS` — русские имена полей форм.

#### `fieldLabel(name)`

Подпись поля или само имя, если подписи нет.

#### `isRole(value)`, `isStatus(value)`

Узкие проверки строк, чтобы перевод перехода статуса и пропущенной роли не подставил мусор в `statusLabel`.

#### `translateDetail(detail)`

Сначала точное совпадение со словарём. Затем шаблон `Transition A -> B is not allowed`: русская фраза с подписями статусов. Затем `Role X is not configured`: про миграции. Иначе «Сервер отклонил запрос: …» плюс исходный текст. Вызывают `parseError` и `ChecksPage` (причины пропуска проверки тоже английские, их прогоняют здесь).

#### `translateValidation(message)`

Сообщения Pydantic: обязательное поле, `end_time must be after start_time`, почта, минимум и максимум символов, границы числа, UUID, время, дата, целое, булево. Префикс `Value error,` снимается. Неизвестное становится «Проверьте введённое значение».

#### Класс `ApiError`

Поля `status`, `detail` (уже по-русски), `fieldErrors` (имя поля → текст). `message` у `Error` равен `detail`, поэтому `caught.message` на экране входа тоже русский.

#### `parseError(status, body)`

Если `detail` строка — `translateDetail`. Если массив (ошибка валидации FastAPI) — собирает `fieldErrors` по последнему элементу `loc`, кроме `body`/`query`/`path`, и общую фразу «Имя: текст». Нет тела: **404** → «Не найдено», **500 и выше** → «Сервис временно недоступен», **0** → нет связи, иначе «Не удалось выполнить запрос».

#### `asApiError(error)`

Уже `ApiError` возвращает как есть. Обычный `Error` заворачивает с кодом 0. Иное — общая фраза.

#### `messageOf(error)`

`asApiError(error).detail`. Её вызывает тост ошибки.

### `frontend/src/api/client.ts`

#### `setUnauthorizedHandler(handler)`

Подменяет функцию `onUnauthorized`. Её один раз ставит `AuthProvider`.

#### `withQuery(path, query)`

Кладёт в query только значения, которые не `undefined`, не `null` и не пустая строка. `false` и `0` проходят: фильтр `outdated=false` и `offset=0` так и должны уехать.

#### `readJson(text)`

`JSON.parse`. Битый JSON — `null`, не исключение.

#### `request(path, options)`

Если `auth` не `false`, читает токен и ставит `Authorization: Bearer`. Тело, если есть, — JSON. `fetch` с `cache: "no-store"`. Сетевой сбой — `ApiError` 0 «Нет связи с сервером. Проверьте, что API запущен на порту 8000.» **204** — `undefined`. Неуспех: `parseError`; если статус 401 и запрос был с авторизацией, сессия чистится и вызывается `onUnauthorized`, затем ошибка всё равно бросается. Успех — разобранный JSON как тип `T`. Ответ сервера клиент дополнительно не проверяет схемой.

#### Объект `api`

Все методы — тонкие вызовы `request`. Имеет смысл знать соответствие, если спросят «кто на экране ходит в этот URL».

- `health` — `GET /health` без токена.
- `login` — `POST /api/auth/login` без токена.
- `me` — `GET /api/auth/me`.
- `listRoles`, `listUsers`, `createUser`, `updateUser`. Отдельного `getUser` нет.
- `listClients`, `getClient`, `createClient`, `updateClient`, `deleteClient`.
- `listConfigurations`, `getConfiguration`, `createConfiguration`, `updateConfiguration`, `deleteConfiguration`, `createVersion`, `updateVersion`, `deleteVersion`.
- `listInstallations`, `listClientInstallations`, `createInstallation`, `updateInstallation`, `deleteInstallation`. Отдельного чтения одной установки нет.
- `runChecks`, `outdated`, `listChecks`. Чтения одной проверки нет.
- `listNotifications`, `createNotification`, `markNotificationRead`. Чтения одного письма нет.
- `listSlots`, `availableDates`, `createSlot`, `updateSlot`. Чтения одного слота нет.
- `listUpdates`, `getUpdate`, `createUpdate`, `patchUpdate`, `changeUpdateStatus`.
- `reportUpdatedClients`, `reportUpdates`, `reportOutdated`.

Параметры методов совпадают с query сервера: пагинация, `q`, роль, статус, даты, `outdated`, `is_read`, тип уведомления.

### `frontend/src/auth/storage.ts`

Ключ `nord.session`. Тип `StoredSession`: `token`, `expiresAt` (миллисекунды `Date.now()`), `user` (`UserRead`).

#### `readSession()`

Нет ключа — `null`. Битый JSON, нет токена, нет пользователя или `expiresAt` не число — ключ удаляется, `null`. Срок уже прошёл — ключ удаляется, `null`. Иначе объект. Это клиентский срок. Сервер всё равно проверит `exp` в JWT. Если часы разъедутся, решающим будет сервер: просроченный по мнению браузера токен просто не отправится, а ещё «живой» по браузеру, но просроченный по серверу, даст 401 и очистку.

#### `readToken()`

`readSession()?.token ?? null`.

#### `writeSession(session)`

`JSON.stringify` в `localStorage`.

#### `clearSession()`

Удаляет ключ.

Токен лежит в `localStorage`, не в cookie. Его прочитает любой скрипт на этом источнике. Для учебного стенда без чужих скриптов это принято. HttpOnly-cookie в проекте нет. Подробнее — в ответах про JWT.

### `frontend/src/auth/session.tsx`

Тип `Status`: `loading`, `anon`, `ready`. Контекст хранит статус, пользователя, `login` и `logout`.

#### `AuthProvider`

При монтировании ставит обработчик 401: пользователь `null`, статус `anon`. Читает сессию. Нет — сразу `anon`. Есть — сначала показывает сохранённого пользователя и параллельно зовёт `api.me`. Успех — перезаписывает карточку (роль могла смениться) и статус `ready`. **401** или **403** от `me` — сессия стирается, `anon`. Иная ошибка (сеть, 500) — статус всё равно `ready`, старая карточка остаётся: иначе обрыв сети на секунду выкидывал бы на логин при ещё годном токене. Следующий рабочий запрос либо пройдёт, либо поймает 401.

`login(email, password)` обрезает почту, зовёт `api.login`, пишет сессию со сроком `expires_in * 1000`, ставит пользователя и `ready`. Ошибку не глотает: её поймает форма.

`logout` чистит хранилище и ставит `anon`. Серверного «выхода» нет: токен остаётся валидным до `exp`, просто браузер его забывает. Это ограничение MVP.

#### `useAuth()`

Контекст или ошибка «AuthProvider is missing», если хук вызвали снаружи провайдера.

#### `useAccess()`

Удобные флаги от роли, не от сервера:

- `isClient` — `client`;
- `canWrite` — админ или специалист (кнопки создания и правки);
- `canAdmin` — админ (на окнах это значит «надо выбрать специалиста»);
- `canReport` — админ или руководитель (во фронтенде флаг объявлен, страницы отчётов режет маршрут, сам флаг нигде больше не читается);
- `canBook` — админ, специалист или клиент, не руководитель;
- `isStaff` — три сотрудникские роли (объявлен, в компонентах не используется).

`canReport` и `isStaff` — запасные флаги. Поведение экранов на них не завязано. Меню режется своим списком ролей в `Shell`, маршруты — `RequireRole`, кнопки — `canWrite`, `canAdmin`, `canBook`, `isClient`.

#### `hasRole(role, roles)`

Истина, если роль не пустая и входит в список. Тоже нигде снаружи не вызывается. Охрана маршрута сравнивает `roles.includes` сама.

### `frontend/src/lib/labels.ts`

Словари подписей. `ROLE_ORDER` и `STATUS_ORDER` задают порядок сегментов на экранах. `NOTE_TYPES` — порядок фильтра писем.

#### `roleLabel`, `roleLabelLong`

Короткие и полные русские имена ролей. Полные совпадают с `ROLE_TITLES` сида.

#### `statusLabel`, `statusAction`, `noteLabel`

«Запрошено / Назначено / В работе / Выполнено / Отменено», подписи кнопок («Взять в работу», «Завершить», …) и типы писем.

#### `NEXT_STATUS`

Та же таблица, что `ALLOWED_TRANSITIONS`, продублированная на клиенте, чтобы нарисовать кнопки. Сервер всё равно проверит переход. Если таблицы разъедутся, кнопка может предлагать то, что API отвергнет, или не предлагать разрешённое. Сейчас они совпадают. У `scheduled` клиент не предлагает кнопку «Назначить», если слота нет: это уже логика `UpdatePage`, не словаря.

#### `statusTone`

Цвет плашки: выполнено — `ok`, отмена — `muted`, в работе — `warn`, остальное — `info`.

### `frontend/src/lib/format.ts`

#### `formatDate`

`YYYY-MM-DD` в «5 ноября 2026». Пустое — тире. Кривая строка возвращается как есть. Месяцы склоняются массивом `MONTHS`, без `Date`, чтобы не сдвинуть календарный день часовым поясом.

#### `formatDateTime`

`Intl.DateTimeFormat('ru-RU')`: день, короткий месяц, часы и минуты в локальной зоне браузера. Сервер хранит UTC. На экране человек видит своё местное время.

#### `formatTime`

Первые пять символов `HH:MM:SS`, то есть `HH:MM`.

#### `formatSlot(date, start, end)`

Нет даты — «Дата не выбрана». Иначе дата и при наличии начала интервал.

#### `todayISO(now?)`

Локальная дата браузера `YYYY-MM-DD`. Ею заполняются поля «с» на экране окон и дата выпуска новой версии.

#### `formatToday`, `greeting`, `firstName`, `initials`

Шапка обзора: «5 ноября», «Доброе утро/день/вечер» по часу браузера, первое слово имени, две буквы для аватара. Пустое имя даёт «Н».

#### `plural(n, one, few, many)`

Русские формы: 1 окно, 2 окна, 5 окон, 11 окон.

#### `cx(...parts)`

Склеивает классы, выбрасывая пустые. Аналог маленького `clsx`, библиотеку не подключали.

### `frontend/src/lib/hooks.ts`

#### `useAsync(fn, deps)`

Хранит функцию в ref, чтобы эффект не перезапускался из-за новой стрелки. Счётчик `seq` отбрасывает устаревший ответ, если зависимости сменились раньше. Пока грузится, старые `data` сохраняются, чтобы список не мигал пустым. Ошибка 401 состояние в `error` не кладёт: сессию уже сбросил клиент, рисовать баннер «войдите» поверх ухода на логин не нужно. Другая ошибка — `status: "error"` и прежние данные. `reload` увеличивает `tick`. Возвращает `status`, `data`, `error`, `reload`.

#### `useDebounced(value, delay=280)`

Отдаёт значение спустя паузу. Поиск по спискам не бьёт API на каждую букву. В выборе организации и конфигурации пауза 250 мс задана явно.

#### `useTitle(title)`

`document.title` = «{title} — Норд». При размонтировании возвращает «Норд — сопровождение 1С».

#### `useSubmit()`

`pending`, `error`, `setError`, `run`. `run` ловит исключение, кладёт `ApiError`, возвращает `false`. Успех — `true`. Формы решают, закрывать ли диалог, по этому флагу. `finally` всегда снимает `pending`.

### `frontend/src/ui/icons.tsx`

#### `Icon({ name })`

Декоративный SVG 24×24, `aria-hidden`. Имена: `home`, `building`, `layers`, `book`, `pulse`, `bell`, `calendar`, `refresh`, `chart`, `users`. Это пункты меню, не данные.

#### `Mark({ size=28 })`

Знак «Норд»: скруглённый квадрат и четырёхконечная фигура цвета `#d7b56a`. Тот же знак, что в favicon. `aria-hidden`.

### `frontend/src/ui/guards.tsx`

#### `RequireAuth()`

`loading` — `BootScreen`. `anon` — `Navigate` на `/login`. Иначе `Shell` и `Outlet` дочерних маршрутов.

#### `RequireRole({ roles })`

Нет пользователя или роль не в списке — `EmptyState` «Этот раздел для другой роли» и ссылка на обзор. Иначе `Outlet`. Не редирект: адрес в строке остаётся, содержимое заменяется заглушкой. Это не проверка безопасности. Её делает API.

#### `LoginGate({ children })`

Пока грузится сессия — `BootScreen`. Уже вошли — на `/`. Иначе дети, то есть `LoginPage`.

### `frontend/src/ui/toast.tsx`

#### `ToastProvider`

Держит до четырёх последних тостов (срез `slice(-3)` перед добавлением). Успех живёт 4.2 с, ошибка 6.4 с. Ошибке в текст идёт `messageOf`. Контейнер `aria-live="polite"`. Кнопка закрывает один тост.

#### `useToast()`

`success(text)` и `error(error)`. Вне провайдера бросает ошибку.

Так английский `detail` становится русской плашкой: сервер → `parseError` / `translateDetail` → `ApiError.detail` → `messageOf` → тост.

### `frontend/src/ui/confirm.tsx`

#### `ConfirmProvider`

`confirm(options)` возвращает `Promise<boolean>`. Пока обещание висит, рисуется `Modal` слоем `confirm` поверх обычного диалога. «Оставить» и крестик — `false`. Кнопка подтверждения — `true`, по умолчанию тон `danger` и подпись «Подтвердить». Вызывают удаления и смену статуса.

#### `useConfirm()`

Функция `confirm` или ошибка, если провайдера нет.

### `frontend/src/ui/shell.tsx`

Константа `GROUPS` — группы меню. У каждого пункта свой список ролей. «Организации» и «Моя организация» ведут на один путь `/clients`, но подпись зависит от роли: в массив попадут только пункты, чья роль совпала, поэтому клиент не видит слово «Организации», а сотрудник не видит «Моя организация». Так же «Установки» и «Мои базы».

Пункты по ролям, если проговорить вслух:

- все четыре: Обзор, Конфигурации, Уведомления, Обновления;
- сотрудник, не клиент: Организации, Установки, Проверки, Окна записи;
- клиент вместо них: Моя организация, Мои базы;
- админ и руководитель: Отчёты;
- только админ: Пользователи.

Руководитель видит «Проверки» и «Окна», но писать там не может. Клиент этих пунктов не видит.

#### `Shell({ children })`

Боковое меню, шапка на узком экране, карточка пользователя. `useAsync` зовёт `api.listNotifications({ limit: 1 })` и берёт `unread` для бейджа. Зависимость — `pathname`: переход по разделам обновляет счётчик. Бейдж на пункте уведомлений, если `unread > 0`; больше 99 показывает `99+`. Смена маршрута закрывает мобильное меню. Кнопка «Выйти» вызывает `logout`. Имя, инициалы, роль и название организации клиента — из `useAuth().user`. Если пользователя нет, компонент возвращает `null` (до этого `RequireAuth` уже не должен был его смонтировать).

#### `BootScreen()`

Знак и текст «Открываем консоль…», пока сессия читается.

### `frontend/src/ui/ui.tsx`

Набор без своих запросов к API, кроме заголовка документа.

- `Banner` — предупреждение. Тон `danger` имеет `role="alert"`, тон `info` — `role="status"`.
- `Field` — подпись, контрол, либо ошибка, либо подсказка.
- `TextInput`, `TextArea`, `Select` — нативные элементы с классом `control`.
- `Button` — тона `primary`, `quiet`, `danger`, `light`, размеры `md` и `sm`. По умолчанию `type="button"`, чтобы случайно не отправить форму.
- `PageHeader` — кикер, заголовок, лид, кнопки справа. Заголовок уходит в `useTitle`.
- `Crumbs` — хлебные крошки. Последний элемент обычно без ссылки.
- `StatusPill` — плашка статуса заявки.
- `CurrencyPill` — «Нет текущего релиза» / «Нужно обновление» / «Актуально». `null` не считается актуальностью.
- `VersionPair` — установленный номер, стрелка, текущий, плашка.
- `EmptyState` — пустой список со знаком.
- `ErrorState` — «Не удалось загрузить» и необязательная кнопка «Повторить».
- `SkeletonList` — серые строки, пока нет данных. `aria-hidden`.
- `Pager` — «с–по из всего», назад/вперёд. Если записей не больше лимита, не рисуется.
- `Segmented` — группа кнопок `aria-pressed`.
- `Modal` — портал в `document.body`. Escape закрывает верхний диалог из стека `dialogStack`, клик по фону тоже, если `locked` ложь. Пока форма сохраняется, `locked` не пускает закрытие. Слой `confirm` выше обычного. Фокус переносится на диалог, прокрутка `body` прячется.
- `LoadBlock` — если ещё нет данных и статус loading, скелет; если ошибка и данных нет, `ErrorState`; если данные есть и пришла ошибка обновления, баннер над старым списком; если `isEmpty`, пустое состояние; иначе дети.

### `frontend/src/ui/pickers.tsx`

#### `ClientSelect`

Поиск с паузой 250 мс, `api.listClients` до 50 строк, выпадающий список. Если выбранный id не попал в выдачу поиска, рисуется запасной пункт с `selectedLabel`, чтобы селект не «потерял» значение. Ошибка загрузки показывается под полем. `allowEmpty` даёт пустой пункт.

#### `SpecialistSelect`

`api.listUsers({ role: "specialist", is_active: true, limit: 100 })`. Подсказка: окно принадлежит специалисту сопровождения. Список ролей здесь не нужен: фильтр уже на сервере.

#### `ConfigurationSelect`

Поиск каталога до 50, в подписи пункта — текущий релиз, если он есть.

### `frontend/src/ui/slot-picker.tsx`

#### `SlotPicker({ value, onChange, allowEmpty })`

Сначала `api.availableDates()`. Пока нет данных — скелет или баннер. Пусто — «Свободных окон нет». Иначе сетка дней. `allowEmpty` добавляет «Без даты» и вызывает `onChange(null)`: заявка уйдёт как `requested`. Выбор дня грузит `api.listSlots({ available_only: true, date_from, date_to })` и даёт выбрать конкретное окно: время, имя специалиста, остаток мест. Клиенту сервер и так отдаст только свободные; флаг `available_only` на клиенте дублирует это для сотрудника, который создаёт заявку и не должен видеть закрытые окна в этой сетке.

### `frontend/src/ui/notify.tsx`

#### `NotifyDialog`

Модалка «Сообщить {организация}». Если установки нет и текст пустой, локально ставит ошибку, на сервер не ходит. Иначе `api.createNotification`. Пустые заголовок и текст уходят как `null`: сервер соберёт текст из версий, если установка передана. Тост «Уведомление отправлено: N». Вызывают карточка установки и список отстающих на странице проверок.

### `frontend/src/ui/installations.tsx`

#### `InstallationCard({ item, onChanged, showClient=true })`

Строка установки: ссылка на клиента или имя конфигурации, имя базы, дата последней проверки, `VersionPair`. Кнопка «Записать» видна при `canBook` и ведёт на `/updates?installation={id}`. Писатель дополнительно видит «Проверить», «Сообщить», «Версия», «Удалить».

`runCheck` вызывает `api.runChecks` по id установки. Тост показывает стрелку версий или «релиз актуален». Пропуск из-за отсутствия текущего релиза — тост-ошибка с уже русским текстом (через `ApiError`, без повторного перевода: строка задана по-русски прямо здесь).

`remove` спрашивает подтверждение и вызывает `api.deleteInstallation`. Отказ сервера (есть история) падает в тост.

#### `EditInstallation` (внутренний)

Грузит `api.getConfiguration`, даёт выбрать релиз и имя базы, `api.updateInstallation`. Это ручная правка, не завершение заявки. Тост «Установка обновлена».

#### `AddInstallation({ clientId, onClose, onCreated })`

Список до 100 конфигураций, затем версии выбранной. Без обоих id форма не отправляется. `api.createInstallation`. Тост «Установка добавлена». Имя базы необязательно, подсказка приводит пример `romashka_bp`.

### `frontend/src/pages/LoginPage.tsx`

#### `LoginPage`

Слева знак, слово «Норд» и три тезиса (сверка, уведомление, окна). Справа форма. Константа `DEMOS` — четыре учебные учётки, те же, что в сиде. Клик по строке подставляет почту и пароль, но сам не входит: нужно нажать «Войти». Подпись прямо говорит, что пароли на карточке только для учебного стенда.

`onSubmit` не пускает пустые поля. Иначе `login` из сессии и `navigate("/")`. Текст ошибки — `caught.message`, то есть русский `detail`.

Индикатор `api.health`: «Проверяем API…», «API на связи» при `database === "ok"`, иначе «API не отвечает на порту 8000». Это живость, не `ready`.

Чекбокс показывает пароль, меняя `type` поля.

### `frontend/src/pages/HomePage.tsx`

#### `HomePage`

Ветвление по роли, одним `useAsync`.

- `manager` — три отчёта: план/факт, отстающие, кого обновили. Обзор руководителя, не операционный.
- `client` — свои установки (до 12), уведомления (до 4), заявки (до 4). Сервер и так сузит до его организации.
- админ и специалист попадают в одну ветку `staff`: число клиентов и конфигураций (запрос с `limit: 1`, берётся `total`), шесть устаревших установок, счётчик непрочитанных, шесть заявок.

Подзаголовок разный. Приветствие — `greeting` и `firstName`.

#### `StaffHome`

Четыре плитки-ссылки: клиенты, «ждут релиза» (на `/installations?outdated=1`), непрочитанные, каталог. Два списка: отстающие со ссылкой на карточку клиента и последние заявки.

#### `ManagerHome`

Плитки ведут на `/reports`: в плане, выполнено, отстающие клиенты, отменено. Списки «кто в плане» (первые шесть) и «нужен релиз».

Админ этот блок на обзоре не видит, хотя страница отчётов ему доступна. Обзор админа совпадает с обзором специалиста. Это сознательное ветвление в коде, не забытый маршрут.

#### `ClientHome`

Если есть устаревшие среди загруженных двенадцати — жёлтый призыв и ссылка «Выбрать дату» на первую такую установку. Если нет — спокойный блок «Релизы на месте». Рядом базы, короткие уведомления (без кнопки «прочитано»: это обзор) и заявки.

#### `UpdateRow`

Ссылка на карточку заявки, организация, слот, плашка статуса.

Ограничение, которое стоит проговорить: клиентский призыв смотрит только на уже загруженные 12 установок. Если устаревшая окажется дальше первой страницы, плашка на обзоре её не покажет. Полный список — страница «Мои базы», серверный фильтр `outdated`.

### `frontend/src/pages/ClientsPage.tsx`

Лимит 20.

#### `ClientsPage`

Заголовок для клиента — «Моя организация», поиск ему не показывают: сервер и так отдаст одну карточку или пусто. Писатель видит «Новый клиент». Смена строки поиска сбрасывает offset через сравнение `seen` и `filterKey` во время рендера, без эффекта. Это чтобы не запросить старую страницу с новым фильтром.

Пустой список клиенту говорит: учётка не привязана, идите к администратору. Сотруднику — зарегистрируйте компанию и затем пользователя с ролью «Клиент».

#### `ClientForm`

Создание и правка. Грузит до 200 активных пользователей и оставляет тех, чья роль не `client`. Если у карточки ответственный не попал в этот список, его имя всё равно есть в селекте. Локальная проверка: название, телефон, грубая проверка почты. Пустой ответственный уходит как `null`. Создание — `api.createClient`, правка — `api.updateClient`. Тосты «Клиент зарегистрирован» и «Карточка сохранена». Ошибки полей рисуются у полей, общая — баннером.

### `frontend/src/pages/ClientPage.tsx`

#### `ClientPage`

`clientId` из адреса. Грузит карточку и установки страницами по 20. Писатель может изменить, удалить, добавить базу. Удаление подтверждается. Успех — тост и переход на `/clients`. Ошибка 409 (есть история) — тост, остаёмся на карточке. Установки рисует `InstallationCard` без повторного имени клиента. Ссылка «Перейти к обновлениям» ведёт на общий список, не на фильтр этого клиента: у списка заявок фильтра по клиенту в интерфейсе нет, хотя API параметр `client_id` принимает.

### `frontend/src/pages/ConfigurationsPage.tsx`

#### `ConfigurationsPage`

Поиск по имени, страница 20. Клиенту написано, что менять каталог может только сопровождение; кнопки создания у него нет (`canWrite`). Плашка «Текущая …» или «Нет текущего релиза».

#### `ConfigurationDialog`

Имя обязано быть непустым. Описание пустое уходит как `null`. Создание или правка. Тосты соответствующие. Эту же форму открывает карточка конфигурации.

### `frontend/src/pages/ConfigurationPage.tsx`

#### `ConfigurationPage`

Крошки, описание, кнопки писателя: изменить, новая версия, удалить. Версии сортируются на клиенте по строке номера `localeCompare(..., "ru")`, не по дате выпуска. Сервер в `list_versions` сортирует по дате. На экране порядок может не совпасть с порядком в ответе. Номера вроде `3.0.9` и `3.0.10` строковая сортировка тоже не выстроит «по величине». Это отображение, на актуальность не влияет: актуальность — флаг `is_current`.

`makeCurrent` шлёт `{ is_current: true }`. `removeVersion` подтверждает и удаляет. Кнопка удаления текущей версии погашена, если версий больше одной (`blocked`), с подсказкой назначить другую. Сервер в этом случае и сам ответит 422. `removeConfiguration` удаляет каталожную запись и уводит на список. 409, если кому-то уже поставлена, станет тостом.

#### `VersionDialog`

Номер, дата выпуска по умолчанию сегодня, заметки, флажок «сделать текущим» (изначально включён). Пустой номер не уходит. Если версия первая, подсказка говорит, что она станет текущей даже при снятом флажке: так делает сервер в `create_version`.

### `frontend/src/pages/InstallationsPage.tsx`

#### `InstallationsPage`

Читает `?outdated=1` и включает сегмент «Устарели». Так сюда попадают с плитки обзора. Поиск и сегмент «все / устарели / актуальны» уходят в `api.listInstallations`. Клиент ищет по конфигурации или базе, сотрудник — ещё и по клиенту. Карточки — `InstallationCard`.

### `frontend/src/pages/ChecksPage.tsx`

#### `ChecksPage`

Маршрут доступен и руководителю. Блок запуска виден только `canWrite`. Руководитель видит информационный баннер и списки.

`run(target)` без id проверяет всех (`{}`), с id — одного клиента. Тост: сколько создано и сколько пропущено. Причины пропуска переводятся `translateDetail`. После успеха перезагружаются отчёт и история.

Живой список — `api.outdated` с поиском. У каждой отстающей установки у писателя кнопка «Сообщить», открывается `NotifyDialog`.

История — `api.listChecks` с сегментом устарела/совпала. Поиск по строке историю не фильтрует: `q` уходит только в живой список. Фильтра по датам на экране нет, хотя API умеет `date_from` и `date_to`.

### `frontend/src/pages/NotificationsPage.tsx`

#### `NotificationsPage`

Сегменты прочтения и типа. Счётчик непрочитанных — поле `unread` ответа. Писатель открывает `Compose`. Кнопка «Прочитано» только если письмо ещё не прочитано и `user.id === recipient_id`. Специалист видит чужие письма, но отметить их не может: сервер тоже откажет. Ссылка «Обновление», если у письма есть `scheduled_update_id`.

#### `Compose`

Организация через `ClientSelect`, заголовок, обязательный текст. Установку эта форма не выбирает, поэтому пустой текст сервер бы отверг; экран не даёт отправить пустой текст раньше. Тост с числом созданных писем. Текст из версий здесь не собирается: для этого есть `NotifyDialog` с карточки установки.

### `frontend/src/pages/SlotsPage.tsx`

#### `SlotsPage`

Доступен трём сотрудникским ролям. Клиент пункта меню не имеет и при прямом заходе увидит заглушку `RequireRole`. Дата «с» по умолчанию — сегодня. Сегмент открытые/закрытые/все, по умолчанию открытые. Писатель открывает окно. Править конкретное окно может админ или специалист-владелец (`mine`). Руководитель список видит, кнопок нет. `toggle` переключает `is_active`.

#### `CreateSlot`

Дата, начало 10:00, конец 12:00, мест 1. Админ обязан выбрать специалиста (`SpecialistSelect`), специалист — нет, сервер запишет окно на него. Локально проверяются пустые поля, конец позже начала, вместимость 1–20. Прошедшая дата не блокирует отправку: баннер предупреждает, что в доступные для записи она не попадёт. Тост «Окно открыто».

#### `CapacityDialog`

Меняет только вместимость. Показывает, сколько уже записано. Сервер не даст опустить ниже занятых.

### `frontend/src/pages/UpdatesPage.tsx`

#### `UpdatesPage`

Клиенту форма записи показана сразу на странице, не в модалке, и если в адресе есть `installation`, форма тоже открывается у сотрудника. Поиск по организации сотруднику; клиенту поиск скрыт. Сегмент статусов — все пять плюс «все». Строка ведёт на карточку, показывает стрелку версий и плашку.

Кнопка «Запросить» у сотрудника с `canBook`. У руководителя её нет.

#### `RequestForm`

Ищет установки (клиенту сервер оставит свои). Выбор карточками `InstallationChoice`. `SlotPicker` с `allowEmpty`. Комментарий до 4000. Кнопка «Записаться», если слот выбран, иначе «Запросить без даты». Успех: тост «Обновление назначено» или «Запрос отправлен». Если по установке уже есть открытая заявка, тост покажет перевод 409.

#### `InstallationChoice`

Кнопка с именем конфигурации, организацией и стрелкой версий.

Ограничение экрана: заранее выбранная установка (`preset`) отмечается, только если она есть в загруженных 30. Подсказка так и говорит. Поиск помогает её найти.

### `frontend/src/pages/UpdatePage.tsx`

#### `UpdatePage`

Карточка заявки. Факты: откуда, куда, специалист, кто запросил. История по времени. Комментарий из заявки.

Менять слот можно при `canBook` и статусе `requested` или `scheduled`. `saveSlot` требует выбранный id и шлёт `patchUpdate`. Пустой выбор — тост «Выберите окно» через `new Error`, это не ответ сервера, `messageOf` покажет текст ошибки как есть.

Писатель видит кнопки `NEXT_STATUS`. «Назначить» (`scheduled`) погашена, если слота нет. Перед сменой — подтверждение с пояснением: завершение подменит версию базы и напишет клиенту, отмена напишет клиенту, возврат в запрос снимет дату, «в работу» просто переведёт статус. Комментарий из поля уходит в `StatusChange`, если он не пустой. `saveComment` шлёт только комментарий.

Клиент с непустым полем тоже может сохранить комментарий (ветка `canBook && comment.trim()`), но кнопок статуса у него нет.

Завершённые показывают `completed_at`.

### `frontend/src/pages/UsersPage.tsx`

Маршрут только админа. Лимит 20.

#### `UsersPage`

Поиск по имени или почте, сегмент роли, сегмент активности. Строка: имя, почта, телефон, организация, плашки активности и роли. «Изменить» открывает диалог. «Новый пользователь» — тот же диалог без карточки. Тост успеха ставит страница, не диалог.

Подзаголовок честно говорит: почту после создания изменить нельзя.

#### `UserDialog`

Грузит `api.listRoles`. Если справочник не пришёл, подставляет локальный `ROLE_ORDER` и длинные подписи, чтобы форма не была пустой; сервер при сохранении всё равно проверит код.

Локальная проверка: имя, почта при создании, пароль не короче 6 (при правке пустой пароль значит «не менять»), для роли клиента обязательна организация.

Создание шлёт `client_id` только для роли `client`, иначе `null`. Правка шлёт имя, телефон, пароль только если введён, активность, роль и организацию по тому же правилу. Почта в `updateUser` не входит, поле на форме disabled.

Чекбокс активности есть только у существующего пользователя. Новый создаётся активным на сервере всегда (`is_active=True` в `create_user`), с формы это не выключается.

### `frontend/src/pages/misc.tsx`

#### `NotFoundPage`

Заголовок «Такой страницы нет» и ссылка на обзор. Попадает сюда неизвестный путь уже после входа. До входа неизвестный путь снаружи `RequireAuth` уводится на `/`, а оттуда на логин.

### `frontend/src/styles/global.css`

Только оформление, запросов нет. На `:root` заведены цвета бумаги и «ели», латунь `#d7b56a`, тень, три семейства шрифтов, радиус. Дальше блоки: экран входа, боковое меню, метрики, панели, плашки, формы, модалки, тосты, лента истории, скелетоны. Анимация появления `.rise`. Класс `.sr-only` описан, в JSX не используется. Класс `.stack-lg` тоже не используется. `.stack` используется формами.

Три порога ширины. До 1100px метрики и факты в две колонки, сплит в одну. До 980px вход становится одной колонкой, меню уезжает за экран и открывается кнопкой из `Shell` (класс `is-open` и затемнение `.scrim`). До 720px формы и плитки в одну колонку. `prefers-reduced-motion: reduce` отключает анимации.

На защите про CSS достаточно сказать: файл задаёт внешний вид консоли и мобильную раскладку меню, бизнес-правил в нём нет.

---

## 7. Инфраструктура

Три сервиса Compose.

| Сервис | Образ | Порт на хосте | Зачем |
| --- | --- | --- | --- |
| `db` | `postgres:16-alpine` | **5433** → 5432 | данные |
| `api` | сборка корневого Dockerfile | **8000** → 8000 | FastAPI |
| `web` | сборка `frontend/Dockerfile` | **8080** → 80 | статика «Норд» и прокси |

Порядок старта задаёт `depends_on` со `condition: service_healthy`. Сначала база проходит `pg_isready`, потом API начинает отвечать на `/health`, потом nginx. Иначе nginx поднялся бы раньше API и первые запросы из браузера получили бы 502, пока идут миграции.

### Почему прокси, а не прямой адрес порта 8000

Браузер открывает один источник: `http://127.0.0.1:8080` или `http://127.0.0.1:5173`. Скрипт вызывает `/api/...` без хоста. Страница и API для браузера — один сайт. Не нужно объяснять CORS предварительным запросом, не нужно класть адрес API в сборку фронтенда, токен не уезжает на другой источник.

Прокси два, они делают одно и то же на разных режимах:

- Vite в `npm run dev` и `npm run preview`;
- nginx в сервисе `web`.

CORS при этом в `main.py` тоже включён. Он не мешает прокси: same-origin запрос CORS-проверку не проходит, ей нечего проверять. Он разрешает другой режим: открыли файлы или страницу на localhost и из неё вызвали `http://127.0.0.1:8000` напрямую. Разрешены localhost и 127.0.0.1 на 5173, 4173, 8080 и на любом порту по регулярному выражению. Чужой сайт в интернете в список не входит. Куки не разрешены, потому что их нет.

Штатная демонстрация — прокси. Прямые вызовы с другого источника — запасной путь для отладки и для `curl`, которому CORS не нужен вовсе.

`/docs` остаётся на порту 8000. Nginx его не проксирует. Это нормально: схема для разработчика, консоль для сценария.

### Почему 8080 может быть занят

Compose публикует `web` как `8080:80` и сам занятость порта не проверяет. Если на хосте порт уже слушает другой процесс, `docker compose up` не поднимет `web` и напишет, что порт занят. На учебных машинах с Windows частый сосед — PostgreSQL от EnterpriseDB: вместе с сервером базы ставится служебный веб-компонент (pgAdmin или стек установщика), и он занимает 8080. Сам код проекта про EDB ничего не знает и порт не переназначает.

Тогда консоль запускают мимо Compose:

```bash
cd frontend
npm install
npm run dev
```

Адрес http://127.0.0.1:5173 . API при этом может остаться в Compose на 8000, база на 5433. Vite проксирует сам.

Порт базы вынесен на **5433** как раз чтобы не пересечься с локальным Postgres, который EDB и обычный установщик сажают на **5432**. Внутри сети Compose API ходит на `db:5432`. С хоста, если запускаете uvicorn у себя, в `.env` остаётся `localhost:5433`.

### Что делает контейнер API при старте

`entrypoint.sh` ждёт `SELECT 1`, затем `alembic upgrade head`, затем uvicorn. Роли из миграции уже в таблицах. `lifespan` ещё раз вызывает сид ролей (он ничего не дублирует) и при `SEED_DEMO=true` — демо. Падение сида роняет процесс: контейнер перезапустится по `restart: unless-stopped`, пока причина не исчезнет (обычно причина — миграции не дошли, но entrypoint их уже гоняет до uvicorn).

### Локальный API без Docker-образа

`docker compose up -d db`, виртуальное окружение, `pip install -r requirements.txt`, `alembic upgrade head`, `uvicorn main:app --host 0.0.0.0 --port 8000`. Если базы нет, можно один раз `python _ensure_db.py`. Повторный сид без рестарта: `python -m src.data.seed`.

---

## 8. Сценарии по ролям

Пароли — в разделе 10. Ниже тот путь, который реально есть в интерфейсе, и функции, которые при этом работают.

### Администратор

Вход: `LoginPage.onSubmit` → `AuthProvider.login` → `POST /api/auth/login` (`login`) → токен в `localStorage`. Обзор — ветка `staff` в `HomePage`, не отчёты.

Пользователи, пункт меню только у него. `UsersPage` → `list_users`. Новый человек: `UserDialog` → `create_user`. Для клиента сначала нужна организация, иначе `_validate_role_link` ответит 422, а `ClientSelect` не из чего будет выбирать. Смена роли, пароля, активности — `update_user` и `_guard_last_admin`. Себя выключить нельзя. Последнего активного админа разжаловать нельзя.

Организации и каталог он может менять так же, как специалист: `canWrite` истинен. Окно записи он открывает только на конкретного специалиста: `CreateSlot` показывает `SpecialistSelect`, сервер это проверяет в `_owner_for_create`.

Отчёты ему доступны маршрутом `RequireRole` и `ReportUser`, хотя плитки обзора ведут не туда, а в операционные списки. Открывает «Отчёты» сам.

Проверки и статусы заявок ему разрешены теми же зависимостями, что специалисту.

### Специалист

Демо — Мария Смирнова, `specialist@example.com`.

Утро. Обзор `StaffHome` показывает, сколько установок ждут релиза. Переход в проверки: `ChecksPage`. «Проверить все» или одного клиента → `run_checks` → `run_version_checks`. В списке «Нужно обновление» Ромашка с бухгалтерией 3.0.150 против 3.0.175. «Сообщить» → `NotifyDialog` → `create_update_notification` → письмо Ивану Петрову. Если портального пользователя нет, тост покажет перевод 422.

Окна. `SlotsPage`. Свои окна на неделю уже есть из сида. Новое окно создаётся на неё саму, без выбора специалиста. Чужое окно она не переключит: `update_slot` ответит 403, и кнопка чужого окна на экране не рисуется (`mine`).

Заявка. Либо клиент запишется сам, либо специалист нажмёт «Запросить» в `UpdatesPage` → `RequestForm` → `create_scheduled_update`. Со слотом статус сразу `scheduled` и уходит письмо.

Карточка `UpdatePage`. «Взять в работу» → `change_status` в `in_progress`, письма нет. «Завершить» → `_apply_completion`: у Ромашки `installed_version_id` станет 3.0.175, на заявке останутся источник и цель, клиент получит `update_completed`. «Отменить» снимет заявку и напишет об отмене. Вернуть в запрос можно из `scheduled`, при этом слот освободится.

Каталог. Новая версия в `ConfigurationPage` → `create_version`. «Сделать текущей» → `touch_current_flag`. Пока старая текущая не снята, вторая истина в индекс не запишется.

Установка вручную. На карточке клиента «Добавить базу» → `AddInstallation`. «Версия» на строке — ручная смена релиза без заявки. Удаление клиента или установки с историей заявок закончится тостом про 409.

Пользователей и отчётов в меню нет. Прямой `GET /api/reports/updates` даст 403. `GET /api/users` специалисту как раз разрешён (`StaffUser`): список нужен, чтобы выбрать ответственного в `ClientForm`. Создать пользователя он не может.

### Руководитель

Демо — Алексей Орлов, `manager@example.com`.

Обзор — `ManagerHome`: план, факт, отстающие, отменённые. Цифры с `updates_summary`, `outdated_report`, `updated_clients_report`.

Страница «Отчёты» — те же три запроса плюс период. Период режет заявки. Список отстающих от периода не зависит, его сужает только поиск по организации. Василёк попадает в «кого уже обновили»: с 3.1.27 на 3.1.32. Ромашка — в отстающие, пока заявку не завершат.

Он открывает карточки клиентов, каталог, проверки, окна и заявки. Кнопок создания нет: `canWrite` ложь, `canBook` ложь. На проверках баннер объясняет, что запуск — специалисту и администратору. История проверок и живой список ему видны. Сменить статус заявки API не даст (`WriterUser`). Выбрать дату тоже не даст (`ensure_can_book`).

Пользователей в меню нет. `GET /api/roles` ему можно: он `StaffUser`. Экран пользователей он не откроет из-за `RequireRole`.

### Клиент

Демо — Иван Петров, `client@example.com`, организация ООО Ромашка.

Меню: Обзор, Моя организация, Мои базы, Конфигурации, Уведомления, Обновления. Нет проверок, окон, отчётов, пользователей, чужих организаций.

Обзор `ClientHome` говорит, что бухгалтерия отстала, и предлагает выбрать дату. «Мои базы» — `list_installations`, сервер подставит `client_id` Ромашки. Чужой id в query даст 403 ещё в `list_installations`.

Уведомления — только письма, где он получатель. Сид кладёт одно непрочитанное про 3.0.150 и 3.0.175. «Прочитано» → `mark_read`. Чужое письмо, даже если бы он угадал UUID, сервер не отдаст и не пометит.

Каталог он читает, кнопки правки скрыты. Запись: страница обновлений сразу показывает `RequestForm`. Выбор базы Ромашки, день из `SlotPicker` (`available_dates` и свободные слоты), «Записаться». `create_scheduled_update` поставит `scheduled`, займёт место Марии и пришлёт письмо о дате. Вторую открытую заявку на ту же базу сервер отвергнет.

Пока статус `requested` или `scheduled`, на карточке можно выбрать другую дату (`assign_slot`). После «в работе» кнопка даты пропадёт, а сервер ответит 409, если вызвать API напрямую. Статусы он не переключает.

Василька он не видит: ни в списке клиентов, ни в заявках. Запрос карточки Василька — 403 из `ensure_client_scope`.

Если бы администратор завёл клиента без `client_id`, списки организаций, установок и заявок были бы пустыми, а не ошибочными. Создать такого пользователя API не позволит: `_validate_role_link` требует организацию.

---

## 9. Готовые ответы

### Зачем JWT, а не сессионная cookie?

Сервер не хранит таблицу сессий. После проверки пароля он отдаёт подписанную строку, браузер возвращает её заголовком `Authorization`. Так `curl`, `smoke.py` и «Норд» ходят в API одинаково. Cookie с `HttpOnly` в проекте нет, CSRF-токена тоже нет: состояние авторизации не прилипает к браузеру само, его явно кладёт заголовок. Для SPA на одном источнике cookie тоже подошла бы; JWT выбран, потому что API сразу задумывался как REST с Bearer, и это видно по `/docs` и смоук-прогону.

Ограничение честно: выход на клиенте только забывает токен в `localStorage`. До `exp` украденная строка ещё действует. Срок по умолчанию 12 часов. Секрет в Compose учебный, алгоритм симметричный: кто знает `jwt_secret`, тот может подписать любой `sub`. Перед общим стендом секрет меняют.

Роль внутри токена на доступ не влияет. Доступ считается по пользователю из базы. Это следующий вопрос часто путает с этим.

### Зачем bcrypt?

Пароль нельзя хранить как есть и нельзя хранить так, чтобы из базы его восстановили. `hash_password` считает bcrypt со случайной солью (`gensalt`). В таблице лежит только строка хеша. Проверка — `verify_password`, она не расшифровывает, а считает заново и сравнивает. Битый хеш даёт `False`, а не падение входа. Стоимость bcrypt замедляет перебор. Это не «шифрование пароля»: обратной операции в коде нет.

### Зачем async SQLAlchemy?

FastAPI отдаёт обработчики в событийный цикл. Пока Postgres думает, синхронный драйвер держал бы поток. `create_async_engine` и `AsyncSession` с драйвером asyncpg отпускают цикл на время запроса. Сессия на запрос — `get_db`. Пул на 20 соединений. `expire_on_commit=False`, чтобы после коммита собрать JSON из уже загруженного объекта.

Асинхронность не делает сама по себе транзакцию. Коммит явный, `commit_session`. Откат при исключении — в `get_db`.

### Зачем Alembic, а не `create_all`?

`create_all` создаёт недостающие таблицы и не умеет изменить уже существующую: добавить `source_version_id` в заполненную базу им нельзя без ручного SQL. Alembic хранит цепочку: первая ревизия — вся схема и роли, вторая — колонки версий у заявки идемпотентно. Entrypoint гоняет `upgrade head` при каждом старте контейнера. Откат описан функциями `downgrade`. Метаданные моделей подключены в `env.py`, чтобы типы можно было сравнивать, но сами файлы миграций написаны вручную, не сгенерированы на лету при старте.

`init_db` таблицы не создаёт. Нет таблиц — сид падает, процесс не стартует, в тексте ошибки прямо сказано выполнить миграции.

### Почему пароль никогда не отдаётся?

Колонка называется `hashed_password` и в `UserRead` её нет. `user_read` перечисляет поля карточки и хеш не копирует. Логин возвращает токен и карточку, не пароль. Список пользователей — те же карточки. В лог сида пароли не пишутся. На экране входа демо-пароли видны только потому, что они зашиты во фронтенд как учебная подсказка (`DEMOS`), это не ответ API.

### Как защищена роль?

Тремя слоями, и только два из них — защита.

Справочник ролей в базе, у пользователя `role_id`. При каждом запросе `get_current_user` загружает пользователя и роль заново. Выключенный пользователь — 401, даже с подписью. `require` сравнивает код из базы со списком маршрута и даёт 403. Дополнительно сервисы режут клиента (`ensure_client_scope`) и руководителя (`ensure_can_book`, `change_status`).

Меню и `RequireRole` во фронтенде только прячут разделы. Их можно обойти, набрав адрес. API от этого не становится добрее.

Поле `role` в JWT — снимок на момент входа для удобства ответа. Авторизация его не читает. Сменили роль в `update_user` — следующий запрос уже с новой.

Отдельного «админ может всё» нет. Админ перечислен там, где ему можно: пользователи, запись, отчёты. Специалист в отчёты не входит. Руководитель в запись не входит.

### Что будет, если у конфигурации две текущие версии?

Штатный API до этого не доводит: `clear_current` снимает старый флаг в той же транзакции, затем ставит новый. Частичный уникальный индекс `uq_configuration_versions_current` запрещает вторую строку с `is_current IS TRUE` на тот же `configuration_id`. Попытка записать вторую через обход сервиса закончится `IntegrityError`, а `flush_session` / `commit_session` превратят её в **409** `Data conflict`. Снять единственный текущий флаг, пока есть другие версии, нельзя: **422**. Удалить текущий, пока есть другие, тоже нельзя, пока не назначат замену.

Чтение `get_current_version` делает `scalar` по флагу. При одном текущем это одна строка. Индекс удерживает этот инвариант на записи.

### Какие переходы статусов допустимы?

`requested` → `scheduled` или `cancelled`. `scheduled` → `in_progress`, `cancelled` или `requested`. `in_progress` → `completed` или `cancelled`. Из `completed` и `cancelled` никуда. Тот же статус ещё раз — 422. Прочий прыжок — 409 с текстом перехода, фронтенд переводит его в «Переход … недопустим».

В `scheduled` нужен слот. В `requested` слот сбрасывается. В `completed` установка переводится на целевой релиз, пишется `completed_at`, клиенту уходит письмо. В `cancelled` тоже письмо, место в слоте освобождается, потому что отменённые не считаются занятыми. В `in_progress` письма нет.

Выбор даты из `requested` сам переводит в `scheduled` через `assign_slot`, это не отдельная кнопка статуса.

Демо-история Василька содержит прямой шаг `requested` → `completed`. Его вставила не машина состояний, а сид. Повторить такой шаг через API нельзя.

### Что делает seed и почему он идемпотентен?

`seed_initial_data` добавляет недостающие роли. `seed_demo_data` заводит учебные строки, если их ещё нет: ищет по естественному ключу (почта, название, имя конфигурации, номер версии, пара клиент-конфигурация) или по стабильному `uuid5`. Повторный старт контейнера не плодит вторую Ромашку и второе письмо с тем же id.

Идемпотентность не выравнивает уже изменённые учебные данные. Существующую версию сид не переписывает. Роль уже созданного пользователя не восстанавливает. Пароль демо-учётки — исключение: если хеш не совпал с учебным паролем, хеш обновляют, чтобы вход из README не сломался на старой базе.

Вызывается из `init_db` при старте API, если `should_seed_demo`, и отдельно командой `python -m src.data.seed`. В production при пустом `SEED_DEMO` демо не создаётся. Роли создаются всё равно.

### Чем `health` отличается от `health/ready`?

`GET /health` — процесс жив и `SELECT 1` проходит. Ответ `database: ok` или **503** `down`. Про роли и учётки он молчит.

`GET /health/ready` — база жива и в справочнике есть все четыре кода ролей. Нет роли — **503** и `missing_roles`. `demo_seeded` показывает, заведены ли четыре учебные почты. Если роли есть, а демо нет, статус всё равно `ok` и код **200**: готовность схемы не равна «учебные люди созданы». Смоук требует оба признака.

Оба пути продублированы под `/api/health` и `/api/health/ready`, дубли скрыты из OpenAPI. Nginx проксирует и короткие, и они же доступны на порту 8000. Экран входа смотрит только `/health`.

### Зачем прокси, если CORS тоже есть?

Прокси делает один источник для браузера. Это основной путь Vite и nginx. CORS разрешает браузеру на localhost обратиться к порту 8000 напрямую, если прокси нет. Списки источников — в `main.py`. Чужие сайты не разрешены. `curl` и `smoke.py` CORS не касается. Подробности портов — в разделе 7.

### Ограничения MVP

Их стоит называть самому, не дожидаясь.

- Нет почты и мессенджеров. «Уведомление» — строка в таблице и лента в консоли.
- Нет выхода на сервере. Забытый токен жив до срока. Чёрного списка токенов нет.
- Секрет JWT и пароли демо учебные. `SEED_DEMO` на общем стенде надо выключать, секрет менять.
- Нет синхронизации с настоящей 1С. Версии и факт установки вносит человек. Завершение заявки меняет учётную запись в этой базе, а не конфигурацию в информационной базе клиента.
- Одна пара клиент+конфигурация. Две базы одной конфигурации у одной организации одной установкой с разными именами не выразить: имя базы — поле строки, а пара уникальна.
- Нет удаления заявки и нет правки номера уже созданной версии.
- Нет регистра смен пароля самим пользователем и нет восстановления пароля.
- Руководитель не бронирует и не меняет статус. Специалист не смотрит отчёты 5.1 и 5.2 (отстающих он видит своим маршрутом).
- Сид не приводит изменённые демо-строки к эталону, кроме паролей учёток.
- `scripts/smoke.py` оставляет за собой организации «ООО Проверка …».
- Сравнение «слот ещё не прошёл» использует время процесса сервера без явной зоны.
- `updated_at` обновляет ORM, не триггер базы.
- Пакет репозиториев пуст. Функция `ids` в сериализаторах не используется. Флаги `canReport` и `isStaff` и функция `hasRole` во фронтенде не используются. Тип `PageQuery` не импортируется. Классы CSS `.sr-only` и `.stack-lg` не используются.
- Ряд GET по одному id API есть, обёрток во фронтенде нет: пользователь, установка, проверка, уведомление, слот.
- Ветка «клиент вызывает проверку» в `run_checks` недостижима: маршрут и так закрыт `WriterUser`.
- История демо-заявки Василька обходит таблицу переходов.
- Обзор клиента судит об устаревании по первым двенадцати установкам.
- Почту пользователя после создания сменить нельзя.
- Python-зависимости без lock-файла.
- CORS и прокси рассчитаны на localhost. Это локальный контур, не публикация в интернет. В `index.html` стоит `noindex`.

---

## 10. Демо-аккаунты и данные Ромашки и Василька

Пароли учебные. На общем стенде `SEED_DEMO=false`.

| Роль | Имя в сиде | Почта | Пароль |
| --- | --- | --- | --- |
| Администратор | Администратор Системы | `admin@example.com` | `admin123` |
| Специалист | Мария Смирнова | `specialist@example.com` | `specialist123` |
| Руководитель | Алексей Орлов | `manager@example.com` | `manager123` |
| Клиент ООО Ромашка | Иван Петров | `client@example.com` | `client123` |

Организации. Обе ведёт Мария Смирнова (`responsible_employee_id`).

**ООО Ромашка.** Телефон `+79000000001`, почта `romashka@example.com`. Установка бухгалтерии, информационная база `romashka_bp`, стоит релиз **3.0.150** (выпущен 1 июня 2025, «Предыдущий релиз»). Актуальный релиз каталога — **3.0.175** от 15 сентября 2026. Установка устарела. Есть снимок проверки: специалист, `is_outdated` истина, `checked_at` примерно сутки назад. Ивану Петрову лежит непрочитанное уведомление типа `update_available` с текстом про 3.0.150 и 3.0.175 и просьбой выбрать дату. Открытой заявки на Ромашку сид не создаёт: её создают на демо, когда записываются.

**АО Василёк.** Телефон `+79000000002`, почта `vasilek@example.com`. Портального пользователя нет. Установка зарплаты, база `vasilek_zup`, стоит уже **3.1.32** (20 августа 2026, актуальный). Предыдущий релиз каталога — **3.1.27** от 1 ноября 2025. Заявка в статусе `completed`, комментарий «Демонстрационное выполненное обновление», завершена двое суток назад, источник 3.1.27, цель 3.1.32, автор и исполнитель — Мария. В истории две строки: пустой старый статус → `requested` («Клиент запросил обновление», за сутки до завершения) и `requested` → `completed`. Второй шаг через API был бы запрещён; строка нужна, чтобы отчёт руководителя был непустым до любых кликов. Писем Васильку нет: получателя с ролью клиента у него нет.

Каталог.

- «Бухгалтерия предприятия» — типовая 1С:Бухгалтерия предприятия. Текущая 3.0.175.
- «Зарплата и управление персоналом» — типовая 1С:ЗУП. Текущая 3.1.32.

Окна. На каждый из семи дней начиная с завтра, не включая сегодня, у Марии два окна: 10:00–12:00 и 14:00–16:00, вместимость 1, активны. Повторный сид в тот же день окна не дублирует: ищет тройку специалист+дата+начало. Завтра состав дней сдвинется, старые прошедшие строки сид не удаляет. Клиент видит только те, что ещё не прошли и не заняты.

Идентификаторы этих строк стабильны (`demo_id`), пока строка создаётся заново. Если строка нашлась по названию, у неё останется тот id, который уже был в базе.

---

## Приложение. Куда смотреть, если назвали имя

Имена в алфавитном порядке по смыслу файла. Ищите по странице через поиск редактора: каждое имя выше оформлено как код.

Бэкенд, вход и каркас: `app`, `lifespan`, `root`, `Settings`, `get_settings`, `should_seed_demo`, `Base`, `engine`, `get_db`, `init_db`, `dispose_engine`, `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `TokenError`, `get_current_user`, `require`, `get_page`, `remember_actor`, `actor_role`, `actor_client_id`, `ensure_client_scope`, `commit_session`, `flush_session`, `like_pattern`, `get_role`.

Предметная область: `clear_current`, `touch_current_flag`, `get_current_version`, `map_current_versions`, `run_version_checks`, `outdated_report`, `notify_client_users`, `create_update_notification`, `create_scheduled_update`, `assign_slot`, `change_status`, `_apply_completion`, `ALLOWED_TRANSITIONS`, `OPEN_STATUSES`, `lock_slot`, `booked_count`, `updated_clients_report`, `updates_summary`, `seed_initial_data`, `seed_demo_data`, `demo_id`.

Инварианты, которые стоит уметь произнести одной фразой: одна текущая версия на конфигурацию (`uq_configuration_versions_current`); одна установка конфигурации на клиента (`uq_client_configuration`); одно окно специалиста на дату и время начала (`uq_specialist_slot`); клиент видит только своё (`ensure_client_scope` и `recipient_id`); открытая заявка на установку одна (`OPEN_STATUSES`); переход статуса только по таблице; завершение двигает установленный релиз и сохраняет «с» и «на»; сид повторяем и не плодит дубликаты; пароль в JSON ответа не входит.

Фронтенд: `request`, `api`, `parseError`, `translateDetail`, `ApiError`, `readSession`, `writeSession`, `AuthProvider`, `useAccess`, `RequireAuth`, `RequireRole`, `LoginGate`, `Shell`, `useToast`, `useConfirm`, `useAsync`, `SlotPicker`, `NotifyDialog`, `InstallationCard`, страницы из `App`. Токен: ключ `nord.session`, заголовок `Bearer`. Меню: массив `GROUPS`. Ошибки: словарь `DETAILS` и тост `error`.
