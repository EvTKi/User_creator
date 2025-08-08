# config_loader.py
"""
Модуль для загрузки и валидации конфигурации приложения.
"""
import json
import os
import sys
from typing import Dict, Any

def get_config_path(filename: str) -> str:
    """
    Определяет путь к конфигурационному файлу.
    Если приложение запущено из .exe ( frozen ), ищет рядом с .exe.
    Иначе ищет в текущей директории скрипта.
    """
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
        print(f"DEBUG (get_config_path): Запущено из .exe, base_path (MEIPASS) = {base_path}")
    except Exception:
        # При обычном запуске скрипта
        base_path = os.path.abspath(".")
        print(f"DEBUG (get_config_path): Запущено как скрипт, base_path (abspath) = {base_path}")
    
    # Путь к директории, где находится исполняемый файл (.exe) или основной скрипт
    if getattr(sys, 'frozen', False):
        # frozen
        exe_dir = os.path.dirname(sys.executable)
        print(f"DEBUG (get_config_path): Frozen, exe_dir = {exe_dir}")
    else:
        # unfrozen
        # Для скрипта лучше искать рядом с config_loader.py
        exe_dir = os.path.dirname(os.path.abspath(__file__)) 
        print(f"DEBUG (get_config_path): Unfrozen, exe_dir (config_loader dir) = {exe_dir}")

    # Формируем путь к конфигурационному файлу рядом с exe/скриптом
    config_path_near_exe = os.path.join(exe_dir, filename)
    print(f"DEBUG (get_config_path): Путь к конфигу ищем по: {config_path_near_exe}")
    
    # Также проверим путь относительно текущей рабочей директории (cwd) при запуске
    config_path_in_cwd = os.path.join(os.getcwd(), filename)
    print(f"DEBUG (get_config_path): Путь к конфигу в CWD: {config_path_in_cwd}")

    # Приоритет: 1. Рядом с exe/скриптом, 2. В текущей рабочей директории
    if os.path.exists(config_path_near_exe):
        print(f"DEBUG (get_config_path): Найден по пути рядом с exe/скриптом")
        return config_path_near_exe
    elif os.path.exists(config_path_in_cwd):
        print(f"DEBUG (get_config_path): Найден по пути в текущей рабочей директории")
        return config_path_in_cwd
    else:
        # Если не найден ни там, ни там, возвращаем путь рядом с exe/скриптом (для вывода ошибки)
        print(f"DEBUG (get_config_path): Не найден, возвращаем путь рядом с exe/скриптом для ошибки")
        return config_path_near_exe

# Определяем путь к config.json ДО определения функции load_config
CONFIG_PATH = get_config_path('config.json')
print(f"DEBUG (module level): CONFIG_PATH = {CONFIG_PATH}")

def load_config() -> Dict[str, Any]:
    """
    Загружает конфигурацию из файла config.json.
    
    Returns:
        Dict[str, Any]: Словарь с параметрами конфигурации.
        
    Raises:
        SystemExit: Если файл конфигурации не найден или содержит некорректные данные.
    """
    # CONFIG_PATH уже определен на уровне модуля
    print(f"DEBUG (load_config): Попытка загрузить config из: {CONFIG_PATH}")
    
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Файл конфигурации не найден: {CONFIG_PATH}")
        # Сообщение об альтернативном пути уже выведено в get_config_path
        sys.exit(1)
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ Конфигурация успешно загружена из: {CONFIG_PATH}")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка декодирования JSON в конфигурационном файле '{CONFIG_PATH}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неизвестная ошибка при загрузке конфигурации из '{CONFIG_PATH}': {e}")
        sys.exit(1)

# Загрузка конфигурации при импорте модуля
print("DEBUG (module level): Начало загрузки CONFIG...")
CONFIG = load_config()
print("DEBUG (module level): CONFIG загружен.")