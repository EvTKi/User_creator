# logging_config.py
"""
Модуль для настройки логирования приложения.
"""
import logging
import logging.config
import os
import json
from datetime import datetime
from typing import Optional

# Импортируем конфигурацию
from config_loader import CONFIG

# Настройка директории логов из config.json
log_dir = CONFIG['output']['log_dir']
os.makedirs(log_dir, exist_ok=True)

def setup_logging():
    """
    Загружает базовую конфигурацию логгера из logging_config.json
    и добавляет файловые обработчики с именами, содержащими текущую дату.
    """
    config_path = 'logging_config.json'
    today = datetime.now().strftime("%Y-%m-%d")

    # Загружаем базовую конфигурацию (форматтеры, консоль)
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
        print(f"Базовая конфигурация логгирования загружена из {config_path}")
    else:
        # Резервная настройка, если JSON не найден
        print(f"Файл конфигурации {config_path} не найден. Используется резервная настройка.")
        logging.basicConfig(level=logging.INFO)

    # --- Создание и настройка файлового обработчика для app.log с датой ---
    app_filename = f"app_{today}.log"
    app_log_path = os.path.join(log_dir, app_filename)
    
    # Получаем форматтер для app логов из уже загруженной конфигурации
    try:
        # Предполагаем, что форматтер 'detailed' используется для файлов
        app_formatter = logging.getLogger().handlers[0].formatter # Берем форматтер из первого обработчика (обычно консольного)
        # Или можно явно создать, если знаем имя форматтера из JSON
        # app_formatter_config = config['formatters']['detailed'] 
        # app_formatter = logging.Formatter(app_formatter_config['format'])
    except (IndexError, AttributeError):
        # Если не удалось получить, создаем стандартный
        app_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s')

    app_handler = logging.FileHandler(app_log_path, encoding='utf-8')
    app_handler.setLevel(logging.DEBUG) 
    app_handler.setFormatter(app_formatter)

    # --- Создание и настройка файлового обработчика для errors.log с датой ---
    errors_filename = f"errors_{today}.log"
    errors_log_path = os.path.join(log_dir, errors_filename)
    
    # Используем тот же форматтер для ошибок
    errors_handler = logging.FileHandler(errors_log_path, encoding='utf-8')
    errors_handler.setLevel(logging.ERROR)
    errors_handler.setFormatter(app_formatter) # Используем 'detailed' форматтер

    # --- Добавляем обработчики к корневому логгеру ---
    root_logger = logging.getLogger()
    root_logger.addHandler(app_handler)
    root_logger.addHandler(errors_handler)
    
    print(f"Файловые обработчики настроены. Логи будут сохранены в '{log_dir}'")
    print(f"  Основной лог: {app_filename}")
    print(f"  Лог ошибок:   {errors_filename}")

# Инициализируем логгирование при импорте модуля
setup_logging()

class LogManager:
    """
    Менеджер логирования, использующий log_dir из config.json.
    Создаёт отдельный лог-файл для каждого CSV.
    СТАРАЯ ЛОГИКА СОХРАНЕНА.
    """

    def __init__(self, csv_filename: str, log_level: int = logging.INFO):
        """
        Инициализирует LogManager.

        Args:
            csv_filename (str): Имя обрабатываемого CSV-файла.
            log_level (int): Уровень логирования (по умолчанию logging.INFO).
        """
        self.csv_filename = csv_filename
        self.log_level = log_level
        self.log_file = self._setup_logging()

    def _setup_logging(self) -> str:
        """
        Настраивает логирование для текущего CSV-файла.
        СТАРАЯ ЛОГИКА: определяет имя файла как {имя_csv}_{дата}.log
        и создает для него логгер.

        Returns:
            str: Путь к созданному лог-файлу.
        """
        # СТАРАЯ ЛОГИКА: определение имени файла
        base = os.path.splitext(os.path.basename(self.csv_filename))[0]
        date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"{base}_{date}.log")

        # СТАРАЯ ЛОГИКА: создание и настройка логгера для конкретного файла
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s') # Формат как в вашем JSON 'standard'
        logger_name = base  # Имя логгера совпадает с именем файла без расширения
        logger = logging.getLogger(logger_name)
        logger.setLevel(self.log_level)

        # Очищаем старые обработчики, чтобы избежать дублирования
        if logger.hasHandlers():
            logger.handlers.clear()

        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return log_file

    def get_logger(self) -> logging.Logger:
        """
        Возвращает настроенный логгер для текущего CSV-файла.
        СТАРАЯ ЛОГИКА: возвращает логгер по имени файла без расширения.

        Returns:
            logging.Logger: Логгер для текущего CSV-файла.
        """
        # СТАРАЯ ЛОГИКА: получение логгера по имени файла
        base = os.path.splitext(os.path.basename(self.csv_filename))[0]
        return logging.getLogger(base)

# Примечание: Убедитесь, что в config.json output.log_dir указывает на существующую директорию,
# например, "logs". Эта директория будет создана автоматически, если её нет.