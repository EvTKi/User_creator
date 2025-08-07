"""
Модуль для загрузки и валидации конфигурации приложения.
"""
import json
import os
import sys
from typing import Dict, Any

CONFIG_PATH = 'config.json'

def load_config() -> Dict[str, Any]:
    """
    Загружает конфигурацию из файла config.json.
    
    Returns:
        Dict[str, Any]: Словарь с параметрами конфигурации.
        
    Raises:
        SystemExit: Если файл конфигурации не найден или содержит некорректные данные.
    """
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Файл конфигурации не найден: {CONFIG_PATH}")
        sys.exit(1)
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка декодирования JSON в конфигурационном файле: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неизвестная ошибка при загрузке конфигурации: {e}")
        sys.exit(1)

# Загрузка конфигурации при импорте модуля
CONFIG = load_config()