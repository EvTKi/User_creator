"""
Модуль для настройки логирования приложения.
"""
import logging
import os
from datetime import datetime
from typing import Optional

# Импортируем конфигурацию
from config_loader import CONFIG

# Настройка директории логов из config.json
log_dir = CONFIG['output']['log_dir']
os.makedirs(log_dir, exist_ok=True)

class LogManager:
    """
    Менеджер логирования, использующий log_dir из config.json.
    Создаёт отдельный лог-файл для каждого CSV.
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
        
        Returns:
            str: Путь к созданному лог-файлу.
        """
        base = os.path.splitext(os.path.basename(self.csv_filename))[0]
        date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"{base}_{date}.log")
        # Формат как в оригинальном коде
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')
        # Создаём новый логгер для файла
        logger = logging.getLogger(base)
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
        
        Returns:
            logging.Logger: Логгер для текущего CSV-файла.
        """
        base = os.path.splitext(os.path.basename(self.csv_filename))[0]
        return logging.getLogger(base)