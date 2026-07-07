# AVA Investment Villas — компонент (чистый код)

Vanilla JS + CSS, без зависимостей и фреймворков. Отдаёт HTML для двух мест:
- **карточка** виллы в каталоге товаров (список),
- **инвест-блок** на странице объекта (вставляется под ваше описание+цену).

Всё под-namespace `.ava-*`, со стилями Tilda не конфликтует.

## Файлы
| Файл | Что это |
|------|---------|
| `ava-villas.css` | Стили карточки, инвест-блока и графиков. |
| `ava-villas.js` | Рендер-функции: `AVAVillas.card(v)`, `AVAVillas.detail(v)`, `AVAVillas.load(url)`. |
| `data.json` | Данные вилл (можно подключить наш авто-обновляемый или свой). |

## Подключение
На страницу (или в футер Tilda через блок «Вставка кода»):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://avaestate.github.io/ava-rental/b2b/component/ava-villas.css">
<script src="https://avaestate.github.io/ava-rental/b2b/component/ava-villas.js"></script>
```
(Файлы можно и просто скопировать к себе — они статичные.)

## Использование

### 1) Карточка в каталог товаров
Каждой карточке-товару соответствует одна вилла (`id` = артикул/ключ). Внутрь карточки:
```js
const villas = await AVAVillas.load('https://avaestate.github.io/ava-rental/b2b/data.json');
const v = villas.find(x => x.id === 'radharani');
container.innerHTML = '<div class="ava-card">' + AVAVillas.card(v) + '</div>';
```
`AVAVillas.card(v)` возвращает фото + название + цену + 3 метрики (в работе / доход в мес / ROI) + мини-график. Кнопку «More Info» ведёте на страницу объекта штатными средствами каталога (фильтры/карточки товаров остаются вашими — виджет только наполняет содержимое).

### 2) Инвест-блок на странице объекта
Под вашим описанием и ценой:
```js
container.innerHTML = '<div class="ava-detail">' + AVAVillas.detail(v) + '</div>';
```
Даёт: 3 KPI + строку occupancy/ADR/since + помесячный график (с цифрами на столбиках) + накопленную доходность + CTA.

> Если удобнее — берите готовую разметку из функций как эталон и вставляйте поля в свои Tilda-карточки. Логика графиков — inline-SVG внутри `ava-villas.js`, копируется как есть.

## Схема данных (объект в `villas[]`)
`id` (string, ключ) · `name` · `bd` (спален) · `city` · `price` (THB) · `desc` · `hero` (url) · `gallery` (url[]) · `built`/`land`/`interior` (м²) · `months` (в работе) · `occ` (%) · `adr` (THB) · `net` (доход/мес THB) · `yld` (ROI %/год) · `cum` (заработано с запуска THB) · `since` (напр. «Dec 2025») · `series` (number[12], помесячно) · `labels` (string[12], буквы месяцев).

## Данные и обновление
- Можно подключить наш `data.json` — он обновляется автоматически раз в день из системы бронирования (Guesty).
- Либо ведите свой файл/выгрузку с теми же полями — вёрстку менять не нужно.

## Замечания
- Шрифт Manrope (можно заменить на шрифт сайта — задаётся в `.ava-card/.ava-detail`).
- Адаптивно; по горизонтали не скроллит.
- Фото сейчас со стабильного CDN (Guesty). Можно подставить свои url в `hero`/`gallery`.

Вопросы — пишите здесь, помогу с интеграцией. — Илон, команда AVA
