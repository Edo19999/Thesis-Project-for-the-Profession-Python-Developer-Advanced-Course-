# Сервис управления заказами (дипломный проект, бекэнд)

Бекэнд‑часть сервиса для автоматизации заказа товаров у поставщиков.
Проект реализован на **Django** и **Django REST Framework**, включает API
для клиентов, партнёров (склад/магазин), Celery‑задачи и конфигурацию docker-compose.

## Стек

- Python 3.10
- Django 5.2
- Django REST Framework
- DRF Token Authentication
- Celery 5 + Redis
- SQLite (по умолчанию) / PostgreSQL (в docker-compose)

---

## Установка и запуск локально (без Docker)

Требования:

- установлен Python 3.10+

Шаги:

```bash
python -m venv venv
venv\Scripts\activate  # Windows

pip install --upgrade pip
pip install django==5.2.11 djangorestframework==3.15.2 djangorestframework-authtoken celery==5.4.0 redis==5.0.7 pyyaml==6.0.2

python manage.py migrate
python manage.py createsuperuser  # при необходимости
python manage.py runserver
```

После запуска сервер доступен по адресу:

http://127.0.0.1:8000/

Интерфейс DRF доступен по:

- `/api/` — основной API
- `/api-auth/login/` — форма логина (session auth)

Почта в режиме разработки выводится в консоль (EMAIL_BACKEND = console).

---

## Запуск через Docker / docker-compose

В корне проекта есть файлы:

- `Dockerfile`
- `docker-compose.yml`

Запуск:

```bash
docker-compose build
docker-compose up
```

Сервисы:

- `web` — Django + Gunicorn (порт 8000)
- `db` — PostgreSQL 15
- `redis` — брокер сообщений для Celery
- `celery` — Celery worker

После старта API доступен по `http://localhost:8000/`.

---

## Основные эндпоинты

Базовый префикс для всех путей: `/api/`

### Публичная часть (каталог)

- `GET /api/products/`  
  Список товаров с предложениями магазинов (offers).  
  Поддерживает фильтры:
  - `name` — поиск по части названия товара
  - `category_id` — фильтр по ID категории
  - `category` — фильтр по названию категории
  - `shop_id` — фильтр по магазину
  - `price_min` / `price_max` — фильтр по цене предложения
  - `ordering=price` или `ordering=-price` — сортировка по цене

- `GET /api/products/<id>/`  
  Детали товара с предложениями магазинов.

- `GET /api/products/export/` (требуется авторизация)  
  Экспорт каталога в структуре, аналогичной `shop.yaml`:

  ```json
  {
    "shop": "Название магазина",
    "categories": [...],
    "goods": [...]
  }
  ```

### Аутентификация и пользователи

- `POST /api/users/register/`  
  Регистрация пользователя с отправкой письма в консоль.

- `POST /api/users/login/`  
  Логин, в ответе — токен:

  ```json
  { "token": "..." }
  ```

Дальше все защищённые эндпоинты требуют заголовок:

```text
Authorization: Token <полученный_токен>
```

или авторизацию через `/api-auth/login/` в DRF UI.

### Контакты (адреса доставки)

- `GET /api/contacts/` — список контактов текущего пользователя
- `POST /api/contacts/` — создание контакта
- `GET /api/contacts/<id>/`
- `PUT/PATCH/DELETE /api/contacts/<id>/`

### Корзина

- `GET /api/basket/`  
  Текущая корзина пользователя:

  ```json
  {
    "items": [...],
    "total_amount": "..."
  }
  ```

- `POST /api/basket/`  
  Добавление/обновление позиции:

  ```json
  {
    "product_info": 5,
    "quantity": 2
  }
  ```

  `product_info` — ID предложения из `offers` товара.

- `DELETE /api/basket/`  
  Удаление позиции корзины:

  ```json
  { "id": 1 }
  ```

### Заказы пользователя

- `GET /api/orders/` — список заказов текущего пользователя
- `POST /api/orders/` — создание заказа по текущей корзине:
  - выбирается контакт (`contact`) пользователя;
  - переносит все позиции из корзины в `OrderItem`;
  - корзина очищается;
  - отправляются письма пользователю и админу (в консоль).

- `GET /api/orders/<id>/` — детали заказа
- `PATCH /api/orders/<id>/` — изменение статуса заказа (`status`):
  - при изменении статуса отправляется письмо пользователю.

---

## API партнёра (склад / магазин)

Для работы партнёра используется привязка `Shop.user`.
После первого импорта прайс‑листа магазин привязывается к текущему пользователю.

- `GET /api/partner/state/`  
  Получить информацию о магазине партнёра:

  ```json
  { "id": 1, "name": "Связной", "is_active": true }
  ```

- `POST /api/partner/state/`  
  Включение/выключение магазина:

  ```json
  { "is_active": false }
  ```

- `GET /api/partner/orders/`  
  Заказы, в которых присутствуют товары данного магазина.

- `POST /api/partner/import/`  
  Импорт прайс‑листа магазина из YAML‑файла:

  ```json
  { "file_path": "data/shop.yaml" }
  ```

  Внутри используется функция `import_shop_from_yaml`, которая:

  - создаёт/обновляет магазин и категории;
  - очищает старые `ProductInfo`/`ProductParameter` для магазина;
  - создаёт новые записи по содержимому YAML.

---

## Celery‑задачи

Celery настраивается в `config/celery.py` и `config/settings.py`
(используется Redis как брокер и backend).

Задачи определены в `shop/tasks.py`:

- `send_email_task(subject, message, recipient_list)` — отправка письма.
- `do_import(file_path)` — импорт магазина из YAML (та же логика, что и при обычном импорте).

### Запуск Celery worker локально

При запущенном Redis (например, из docker-compose):

```bash
celery -A config worker -l info
```

---

## Запуск импорта через Celery из админской части API

Эндпоинт (только для админа — `IsAdminUser`):

- `POST /api/admin/do-import/`

Тело запроса:

```json
{ "file_path": "data/shop.yaml" }
```

В ответе:

```json
{
  "task_id": "...",
  "status": "PENDING"
}
```

Задача выполняется воркером Celery (`do_import.delay(...)`).

---

## Соответствие этапам диплома

- **Этапы 1–4**: модели, импорт YAML, каталог товаров, регистрация/логин, контакты, корзина, заказы,
  письма пользователю и админу — реализованы.
- **Этап 5**: сценарий пользователя (регистрация → логин → корзина → ввод адреса → заказ → письма → просмотр заказа) —
  полностью закрыт.
- **Этап 6**: API админки склада — реализованы эндпоинты партнёра для состояния магазина, заказов и импорта.
- **Этап 7**: Celery‑приложение с задачами `send_email_task` и `do_import`, плюс вид для запуска `do_import` из админки —
  реализовано.
- **Этап 8**: docker-compose для web, db, redis и celery — реализован.

