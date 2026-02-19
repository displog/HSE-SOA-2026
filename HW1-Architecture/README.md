
# Проектирование архитектуры маркетплейса

## 1. Описание архитектуры и доменов

Система спроектирована на основе микросервисной архитектуры. Бизнес-логика разделена на независимые домены, каждый из которых обслуживается отдельным сервисом со своей базой данных (принцип Database-per-Service).

### Перечень доменов и их ответственность:

*   **User Service**: Управление учетными записями покупателей и продавцов, профилями и правами доступа.
*   **Catalog Service**: Управление товарным каталогом, категориями и актуальными остатками товаров.
*   **Order Service**: Обработка корзины, создание заказов и управление их жизненным циклом.
*   **Payment Service**: Взаимодействие с внешними платежными шлюзами, проведение расчетов и учет транзакций.
*   **Feed & Personalization Service**: Формирование персональной ленты товаров для пользователя на основе его предпочтений и истории.
*   **Notification Service**: Отправка уведомлений (Email, Push) об изменении статусов заказов и акциях.

---

## 2. Границы владения данными и взаимодействия

### Владение данными:
Каждый сервис владеет своими данными. **Разделяемые базы данных (Shared Database) отсутствуют**.
*   `User Service` -> PostgreSQL (данные пользователей).
*   `Catalog Service` -> PostgreSQL + Redis (товары и кэш).
*   `Order Service` -> PostgreSQL (заказы).
*   `Payment Service` -> PostgreSQL (транзакции).
*   `Feed Service` -> MongoDB/Vector DB (профили предпочтений).

### Взаимодействия:
1.  **Синхронные (REST/HTTP)**: Используются API Gateway для взаимодействия фронтенда с сервисами (авторизация, просмотр каталога).
2.  **Асинхронные (Message Broker - Kafka)**: Используются для обмена событиями между сервисами.
    *   *Пример:* `Order Service` публикует событие `OrderCreated`. `Payment Service` подписывается на него для проведения оплаты, а `Notification Service` — для отправки письма.

---

## 3. Альтернативные варианты и Trade-off

### Вариант 1: Модульный монолит
*   **Плюсы**: Простота развертывания, отсутствие сетевых задержек между модулями, единая база данных (ACID транзакции).
*   **Минусы**: Невозможность независимого масштабирования (например, нельзя масштабировать только тяжелую Ленту товаров), риск того, что ошибка в одном модуле обрушит всё приложение.

### Вариант 2: Микросервисная архитектура (Финальный выбор)
*   **Плюсы**:
    *   **Масштабируемость**: Каждый компонент (Каталог, Лента) масштабируется отдельно под нагрузку.
    *   **Отказоустойчивость**: Сбой в системе рекомендаций (Feed) не блокирует возможность оформления заказа.
    *   **Технологическая независимость**: Возможность использовать Python для ML-задач в Ленте и Go/Java для транзакционных сервисов.
*   **Минусы**: Сложность эксплуатации, необходимость управления распределенными данными и транзакциями (Saga pattern).

**Обоснование выбора**: Маркетплейс — это высоконагруженная система с разными типами нагрузки. Микросервисы позволяют обеспечить надежность критических доменов (оплата, заказы) и гибкость в развитии ленты и каталога.

---

## 4. Визуализация архитектуры (C4 Model в LikeC4)

В проекте настроены три уровня визуализации:

1. **Landscape View**: Автоматический обзор всей системы и внешних связей.
2. **Marketplace - System Context**: Верхнеуровневый взгляд на взаимодействие Покупателей, Продавцов и Маркетплейса как единого целого ("черный ящик") с внешней платежной системой.
3. **Marketplace - Containers**: Детальная схема внутренних микросервисов, баз данных и брокера сообщений. Позволяет увидеть внутреннее устройство системы.

    *(Скриншоты диаграмм находятся в папке /screenshots)*.
---

## 5. Техническая реализация (Catalog Service)

В рамках работы поднят и контейнеризирован **Catalog Service** на стеке Python/FastAPI.

### Особенности реализации:
*   Реализован health-check endpoint (`/health`).
*   Сервис отвечает стандартным кодом `200 OK`.
*   Конфигурация описана в `docker-compose.yml`.

---

## 6. Инструкция по запуску

### Запуск сервиса в Docker:
1. Перейдите в корень проекта.
2. Выполните команду:
   ```bash
   docker-compose up --build -d
   ```
3. Проверьте работоспособность:
   *   Главная страница: [http://localhost:8080/](http://localhost:8080/)
   *   Health Check: [http://localhost:8080/health](http://localhost:8080/health)

### Просмотр диаграмм (LikeC4):
1. Убедитесь, что установлен Node.js.
2. В корне проекта выполните:
   ```bash
   npx likec4 start
   ```
3. Диаграммы будут доступны по адресу `http://localhost:5173`.

---

## Приложение: Код архитектуры (LikeC4)

```likec4
specification {
  element person
  element system
  element container
  element infrastructure
}

model {
  customer = person 'Покупатель'
  seller = person 'Продавец'

  payment_gw = system 'Payment Gateway' {
    description 'Внешний эквайринг'
  }

  marketplace = system 'Marketplace System' {
    description 'Цифровая платформа торговли'

    // Внутренние контейнеры
    gw = container 'API Gateway' {
      technology 'Go / NGINX'
    }
    user_srv = container 'User Service' {
      technology 'Python'
    }
    catalog_srv = container 'Catalog Service' {
      technology 'Go'
    }
    order_srv = container 'Order Service' {
      technology 'Java'
    }
    payment_srv = container 'Payment Service' {
      technology 'Go'
    }
    feed_srv = container 'Feed Service' {
      technology 'Python / ML'
    }
    notif_srv = container 'Notification Service' {
      technology 'Node.js'
    }

    db = infrastructure 'Shared Data Infrastructure' {
      description 'Базы данных сервисов'
      db_user = infrastructure 'User DB'
      db_catalog = infrastructure 'Catalog DB'
      kafka = infrastructure 'Kafka Message Broker'
    }
  }

  // Связи
  customer -> gw 'Просмотр и покупка'
  seller -> gw 'Управление товарами'

  gw -> user_srv 'Auth'
  gw -> catalog_srv 'Catalog API'
  gw -> order_srv 'Order API'
  gw -> feed_srv 'Personalized Feed'

  user_srv -> db_user 'Persist'
  catalog_srv -> db_catalog 'Persist'

  order_srv -> kafka 'Publish OrderEvents'
  kafka -> payment_srv 'Consume'
  kafka -> notif_srv 'Consume'

  payment_srv -> payment_gw 'External Call'
}

views {

  // 1. Уровень Системы (System Context)
  view system_context {
    title "Marketplace - System Context"
    include
      customer,
      seller,
      marketplace,
      payment_gw

    navigateTo container_view
  }

  // 2. Уровень Контейнеров (Container Diagram)
  view container_view {
    title "Marketplace - Containers"
    include
      customer,
      seller,
      marketplace.*,
      payment_gw

    autoLayout TopBottom
  }
}
```