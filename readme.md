# User Creator

Приложение для обработки CSV-файлов с данными пользователей, генерации XML-файлов в форматах SysConfig и Energy, и (опционально) интеграции с Active Directory для получения уникальных идентификаторов пользователей (GUID).

## Возможности

*   **Обработка CSV-файлов**: Чтение данных пользователей из CSV-файлов в заданной директории.
*   **Генерация XML**:
    *   Создание XML-файлов формата **SysConfig**.
    *   Создание XML-файлов формата **Energy**.
*   **Интеграция с Active Directory (AD)**:
    *   Получение GUID домена.
    *   Получение GUID пользователей по их логину (`sAMAccountName`).
*   **Работа без AD**: Возможность вручную указать GUID домена и использовать GUID из CSV-файлов или генерировать их автоматически.
*   **Гибкая настройка**: Конфигурация через `config.json` и `logging_config.json`.
*   **Логирование**: Подробное логирование процесса обработки в файлы и в консоль/интерфейс.
*   **Два интерфейса**:
    *   **Консольное приложение** (`main.py`): Традиционный интерфейс командной строки.
    *   **Графическое приложение** (`ui.py`): Удобный GUI на основе PyQt5 с прогресс-баром и реальными логами.

## Требования

*   Python 3.6 или выше
*   Библиотеки, перечисленные в `requirements.txt`:
    *   `PyQt5` (для GUI)
    *   `ldap3` (для работы с AD)
    *   `pyinstaller` (для создания .exe, опционально)

## Установка

1.  **Клонируйте репозиторий или скачайте исходный код.**
2.  **(Рекомендуется) Создайте виртуальное окружение:**
    ```bash
    # Создание виртуального окружения с именем 'venv'
    python -m venv venv

    # Активация виртуального окружения
    # На Windows (в командной строке cmd):
    venv\Scripts\activate
    # На Windows (в PowerShell):
    # venv\Scripts\Activate.ps1
    # (Может потребоваться Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser)
    # На macOS/Linux:
    # source venv/bin/activate
    ```
3.  **Установите зависимости:**
    Убедитесь, что виртуальное окружение активировано.
    ```bash
    pip install -r requirements.txt
    ```

## Конфигурация

### `config.json`

Основной файл конфигурации приложения. Должен находиться в корневой директории проекта (рядом с `main.py` или `ui.py`).

Пример структуры:
```json
{
  "ad": {
    "enabled": true,
    "domain_controller": "your.domain.controller.com",
    "domain_dn": "DC=your,DC=domain,DC=com",
    "user": "CN=service_account,OU=Service Accounts,DC=your,DC=domain,DC=com"
  },
  "input": {
    "encoding": "windows-1251",
    "delimiter": ";"
  },
  "output": {
    "log_dir": "log",
    "not_in_ad_csv": "not_in_AD.csv",
    "sysconfig_xml_suffix": "_SysConfig.xml",
    "energy_xml_suffix": "_Energy.xml"
  },
  "xml": {
    "model_version_sysconfig": "2025-03-04(11.7.1.7)",
    "model_version_energy": "1.0"
  }
}
```
- `ad.enabled` Включить/выключить интеграцию с Active Directory.
- `ad.domain_controller` Адрес контроллера домена.
- `ad.domain_dn` отличительное имя корня домена.
- `ad.user` DN учетной записи службы для подключения к AD.
- `input.encoding` Кодировка входных CSV-файлов (по умолчанию `windows-1251`).
- `input.delimiter` Разделитель в CSV-файлах (по умолчанию `;`).
- `output.log_dir` Директория для сохранения лог-файлов.
- `output.not_in_ad_csv`: Имя файла для сохранения списка пользователей, не найденных в AD.
- `output.sysconfig_xml_suffix` Суффикс для создаваемых XML-файлов SysConfig.
- `output.energy_xml_suffix` Суффикс для генерируемых XML-файлов Energy.
- `xml.model_version_sysconfig` Версия модели для XML SysConfig.
- `xml.model_version_energy` Версия модели для XML Energy.

### `logging_config.json`

Файл конфигурации стандартной библиотеки логирования Python (`logging`). Определяет форматтеры и обработчики для основных логов (`app_*.log`, `errors_*.log`)

Пример структуры:
```
{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] - %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console"]
    }
}
```
*Обратите внимание: Файловые обработчики `app_*.log``errors_*.log` добавляются программно в `logging_config.py` поэтому их не нужно указывать в этом файле.

## Использование

### Подготовка

1. Убедитесь, что файлы `config.json` и `logging_config.json` находятся в корневой директории проекта.
2. Подготовьте CSV-файлы с данными пользователей. Ожидаемые столбцы (многие из них необязательны):
    - `name` (обязательно): полное имя пользователя.
    - `login` Логин пользователя (для поиска в AD).
    - `person_guid` идентификатор GUID пользователя (если не используется AD или пользователь не найден).
    - `email` Электронная почта.
    - `mobilePhone` Мобильный телефон.
    - `position` Должность.
    - `OperationalAuthorities` Оперативные полномочия (разделитель `!`)
    - `electrical_safety_level` Уровень электробезопасности.
    - `roles` Роли (разделитель).
    - `groups` Группы (разделитель)
    - `parent_energy` Родительский объект для Energy.
    - `parent_sysconfig` Родительский объект для SysConfig.
   
  Запуск консольного приложения
  ```
   Активируйте виртуальное окружение, если оно используется
    venv\Scripts\activate (Windows cmd)
    python main.py
```
1. Выберите режим работы (с AD или без).
2. Введите пароль AD (если выбран режим «с AD») или идентификатор GUID домена (если выбран режим «без AD»).
3. Укажите папку с CSV-файлами.
4. Нажмите кнопку «▶ Запустить обработку».

## Логирование

Приложение создаёт несколько типов лог-файлов в директории, указанной в `config.json` (`output.log_dir`):

- `app_YYYY-MM-DD.log`: Основной журнал приложения.
- `errors_YYYY-MM-DD.log`: Журнал ошибок приложения.
- `{имя_csv}_YYYY-MM-DD.log`Отдельный журнал для каждого обрабатываемого CSV-файла.
- `user_creator_ui_YYYY-MM-DD.log`: Журнал работы графического интерфейса (только при запуске `ui.py`).

Формат сообщений в логах определяется в `logging_config.json`.

## Создание исполняемого файла (.exe)

Для создания автономного `.exe` файла можно использовать `PyInstaller`.

1. Убедитесь, что `pyinstaller` установлен (`pip install pyinstaller`).
2. (Необязательно) Создайте файл спецификации: `pyi-makespec --onedir --name=UserCreator ui.py`
3. Соберите проект:
    - Если есть `.spec` файл: `pyinstaller UserCreator.spec`
    - Если нет: `pyinstaller --onedir ui.py`
4. Исполняемый файл и зависимости будут находиться в папке `dist/UserCreator`. 5. **ВАЖНО**: Скопируйте файлы `config.json` и `logging_config.json` в папку `dist/UserCreator` рядом с `UserCreator.exe`.

## Структура проекта

- `main.py`: Основной скрипт консольного приложения.
- `ui.py`Скрипт графического приложения (PyQt5).
- `config_loader.py`: Модуль для загрузки `config.json`.
- `logging_config.py`: Модуль для настройки логирования.
- `csv_processing.py`Модуль для работы с CSV-файлами.
- `ad_operations.py`: Модуль для работы с Active Directory.
- `xml_generation.py`: Модуль для создания XML-файлов.
- `config.json`: Файл конфигурации приложения.
- `logging_config.json`: Файл конфигурации логирования.
- `requirements.txt`Список зависимостей Python.
- `README.md`: Этот файл.

## Разработка

- Код структурирован по модулям для удобства поддержки и повторного использования.
- Используется стандартная библиотека логирования Python.
- Для графического интерфейса используется PyQt5.
- Для работы с AD используется библиотека `ldap3`.