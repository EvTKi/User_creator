# logging_config.py
"""
Модуль для настройки логирования приложения.
Создаёт отдельный лог-файл для каждого обрабатываемого CSV.
"""

import logging
import os
import json
from datetime import datetime
from typing import Optional


class LogManager:
    """
    Класс для управления логированием.
    Настройка логгера для каждого CSV-файла отдельно.
    """

    def __init__(self, csv_filename: str, config_path: str = 'config.json'):
        """
        Инициализирует LogManager.

        Args:
            csv_filename (str): Имя обрабатываемого CSV-файла.
            config_path (str): Путь к config.json.
        """
        self.csv_filename = csv_filename
        self.config_path = config_path
        self.log_dir = self._load_log_dir()
        self.logger = self._setup_logger()

    def _load_log_dir(self) -> str:
        """Загружает log_dir из config.json."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Конфигурационный файл не найден: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        log_dir = config['output']['log_dir']
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def _setup_logger(self) -> logging.Logger:
        """Настраивает и возвращает логгер для текущего CSV-файла."""
        base_name = os.path.splitext(os.path.basename(self.csv_filename))[0]
        log_file = os.path.join(
            self.log_dir,
            f"{base_name}_{datetime.now().strftime('%Y-%m-%d')}.log"
        )

        # Создаём логгер с уникальным именем
        logger = logging.getLogger(f"csv.{base_name}")
        logger.setLevel(logging.INFO)

        # Очищаем предыдущие обработчики, чтобы избежать дублирования
        if logger.hasHandlers():
            logger.handlers.clear()

        # Формат лога
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s')

        # Обработчик для записи в файл
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def get_logger(self) -> logging.Logger:
        """
        Возвращает настроенный логгер.

        Returns:
            logging.Logger: Логгер для текущего CSV-файла.
        """
        return self.logger