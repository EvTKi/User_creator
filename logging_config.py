# logging_config.py
"""
Модуль для настройки логирования приложения.
"""
import logging
import logging.config
import os
import json
import sys # Убедитесь, что sys импортирован
from datetime import datetime
from typing import Optional

# --- ЛОГИКА ОПРЕДЕЛЕНИЯ ПУТИ К КОНФИГУРАЦИОННЫМ ФАЙЛАМ ---
def get_resource_path(filename: str) -> str:
    """
    Определяет путь к ресурсу (конфигурационному файлу).
    Если приложение запущено из .exe ( frozen ), ищет рядом с .exe.
    Иначе ищет в текущей директории скрипта.
    """
    try:
        # PyInstaller создает временную папку и хранит путь в _MEIPASS
        base_path = sys._MEIPASS
        print(f"DEBUG (get_resource_path): Запущено из .exe, base_path (MEIPASS) = {base_path}")
    except Exception:
        # При обычном запуске скрипта
        base_path = os.path.abspath(".")
        print(f"DEBUG (get_resource_path): Запущено как скрипт, base_path (abspath) = {base_path}")
    
    # Путь к директории, где находится исполняемый файл (.exe) или основной скрипт
    if getattr(sys, 'frozen', False):
        # frozen
        exe_dir = os.path.dirname(sys.executable)
        print(f"DEBUG (get_resource_path): Frozen, exe_dir = {exe_dir}")
    else:
        # unfrozen
        # Для скрипта лучше искать рядом с logging_config.py
        exe_dir = os.path.dirname(os.path.abspath(__file__)) 
        print(f"DEBUG (get_resource_path): Unfrozen, exe_dir (logging_config dir) = {exe_dir}")

    # Формируем путь к конфигурационному файлу рядом с exe/скриптом
    config_path_near_exe = os.path.join(exe_dir, filename)
    print(f"DEBUG (get_resource_path): Путь к ресурсу ищем по: {config_path_near_exe}")
    
    # Также проверим путь относительно текущей рабочей директории (cwd) при запуске
    config_path_in_cwd = os.path.join(os.getcwd(), filename)
    print(f"DEBUG (get_resource_path): Путь к ресурсу в CWD: {config_path_in_cwd}")

    # Приоритет: 1. Рядом с exe/скриптом, 2. В текущей рабочей директории
    if os.path.exists(config_path_near_exe):
        print(f"DEBUG (get_resource_path): Найден по пути рядом с exe/скриптом")
        return config_path_near_exe
    elif os.path.exists(config_path_in_cwd):
        print(f"DEBUG (get_resource_path): Найден по пути в текущей рабочей директории")
        return config_path_in_cwd
    else:
        # Если не найден ни там, ни там, возвращаем путь рядом с exe/скриптом (для вывода ошибки)
        print(f"DEBUG (get_resource_path): Не найден, возвращаем путь рядом с exe/скриптом для ошибки")
        return config_path_near_exe
# --- КОНЕЦ ЛОГИКИ ОПРЕДЕЛЕНИЯ ПУТИ ---

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ПРИЛОЖЕНИЯ ДЛЯ ПОЛУЧЕНИЯ log_dir ---
# Сначала попробуем загрузить config.json для получения log_dir
# Используем новую функцию get_resource_path
try:
    config_json_path = get_resource_path('config.json')
    print(f"DEBUG (logging_config, module load): Ищу config.json по пути: {config_json_path}")
    if os.path.exists(config_json_path):
        with open(config_json_path, 'r', encoding='utf-8') as f:
            app_config = json.load(f)
        log_dir = app_config['output']['log_dir']
        print(f"DEBUG (logging_config, module load): Директория логов из config.json: {log_dir}")
    else:
        raise FileNotFoundError(f"config.json not found at {config_json_path}")
except Exception as e:
    print(f"WARNING (logging_config, module load): Не удалось загрузить config.json для определения log_dir: {e}")
    print("WARNING (logging_config, module load): Используется директория по умолчанию: 'logs'")
    log_dir = 'logs' # Значение по умолчанию, если config.json не найден или ошибка

os.makedirs(log_dir, exist_ok=True)
print(f"DEBUG (logging_config, module load): Убедились, что директория логов '{log_dir}' существует.")
# --- КОНЕЦ ЛОГИКИ ЗАГРУЗКИ CONFIG.JSON ---


def setup_logging():
    """
    Загружает базовую конфигурацию логгера из logging_config.json
    и добавляет/заменяет файловые обработчики с именами, содержащими текущую дату.
    """
    # Определяем путь к logging_config.json
    config_path = get_resource_path('logging_config.json')
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"DEBUG (logging_config): Ищу logging_config.json по пути: {config_path}")

    # Загружаем базовую конфигурацию (форматтеры, консоль)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Имена файловых обработчиков, которые мы хотим заменить/удалить
            file_handler_names_to_remove = ["file_app", "file_errors"]

            # 1. Удаляем определения этих обработчиков из config["handlers"]
            handlers_config = config.get("handlers", {})
            for handler_name in file_handler_names_to_remove:
                handlers_config.pop(handler_name, None) # Безопасно удаляем, если есть

            # 2. Удаляем ссылки на эти обработчики из корневого логгера
            # Проверяем оба возможных способа определения корневого логгера в JSON
            root_logger_config = config.get("root") # Стиль "root"
            if not root_logger_config:
                root_logger_config = config.get("loggers", {}).get("") # Стиль "loggers": { "": ... }
            
            if root_logger_config and "handlers" in root_logger_config:
                 # Создаем новый список обработчиков, исключая те, что удалили
                updated_handlers = [
                    h for h in root_logger_config["handlers"] 
                    if h not in file_handler_names_to_remove
                ]
                root_logger_config["handlers"] = updated_handlers

            # Применяем модифицированную конфигурацию
            logging.config.dictConfig(config)
            print(f"✅ Базовая конфигурация логгирования загружена из {config_path}")
        except ValueError as e: # Перехватываем конкретную ошибку конфигурации
            print(f"❌ Ошибка применения конфигурации из {config_path}: {e}")
            print("Используется резервная настройка.")
            logging.basicConfig(level=logging.INFO)
        except Exception as e:
            print(f"❌ Неизвестная ошибка при загрузке {config_path}: {e}")
            print("Используется резервная настройка.")
            logging.basicConfig(level=logging.INFO)
            
    else:
        # Резервная настройка, если JSON не найден
        print(f"⚠️ Файл конфигурации {config_path} не найден. Используется резервная настройка.")
        logging.basicConfig(level=logging.INFO)

    # --- Создание и настройка файлового обработчика для app.log с датой ---
    app_filename = f"app_{today}.log"
    app_log_path = os.path.join(log_dir, app_filename)
    
    # Получаем форматтер 'detailed' из уже загруженной конфигурации, если он есть
    try:
        # Попробуем получить форматтер из конфигурации
        detailed_format = None
        if "formatters" in config and "detailed" in config["formatters"]:
             detailed_format = config["formatters"]["detailed"]["format"]
             
        if detailed_format:
            app_formatter = logging.Formatter(detailed_format)
        else:
            raise KeyError("detailed formatter not found in config")
    except (KeyError, NameError, UnboundLocalError):
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
    
    print(f"📁 Файловые обработчики настроены. Логи будут сохранены в '{log_dir}'")
    print(f"  📄 Основной лог: {app_filename}")
    print(f"  ⚠️  Лог ошибок:   {errors_filename}")

# Инициализируем логгирование при импорте модуля
setup_logging()

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
        # --- Гарантируем существование директории для логов ---
        # log_dir определен на уровне модуля в logging_config.py
        os.makedirs(log_dir, exist_ok=True) 
        # --- Конец добавления ---
        self.log_file = self._setup_logging()
        print(f"DEBUG (LogManager): LogManager инициализирован для файла '{csv_filename}'. Лог будет в '{self.log_file}'")

    def _setup_logging(self) -> str:
        """
        Настраивает логирование для текущего CSV-файла.
        Определяет имя файла как {имя_csv}_{дата}.log и создает для него логгер.

        Returns:
            str: Путь к созданному лог-файлу.
        """
        # Определение имени файла лога
        base = os.path.splitext(os.path.basename(self.csv_filename))[0]
        date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"{base}_{date}.log") # Используем log_dir из config

        # Определяем имя логгера (обычно совпадает с именем файла без расширения)
        logger_name = base
        
        # --- Получаем или создаем логгер ---
        logger = logging.getLogger(logger_name)
        # Устанавливаем уровень логирования
        logger.setLevel(self.log_level)
        
        # Очищаем старые обработчики, чтобы избежать дублирования
        # Это важно, если LogManager для этого файла уже создавался
        if logger.hasHandlers():
            logger.handlers.clear()
            print(f"DEBUG (LogManager._setup_logging): Старые обработчики для логгера '{logger_name}' очищены.")

        # --- Настройка форматтера ---
        formatter = None
        try:
            # Пытаемся загрузить формат из logging_config.json
            config_path = get_resource_path('logging_config.json') # Используем нашу функцию
            print(f"DEBUG (LogManager._setup_logging): Загрузка форматтера из '{config_path}' для логгера '{logger_name}'")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if 'formatters' in config and 'standard' in config['formatters']:
                    standard_format = config['formatters']['standard']['format']
                    formatter = logging.Formatter(standard_format)
                    print(f"DEBUG (LogManager._setup_logging): Используется форматтер 'standard' для логгера '{logger_name}'")
                elif 'formatters' in config and 'detailed' in config['formatters']:
                     # fallback на 'detailed' если 'standard' нет
                     detailed_format = config['formatters']['detailed']['format']
                     formatter = logging.Formatter(detailed_format)
                     print(f"DEBUG (LogManager._setup_logging): Используется форматтер 'detailed' (fallback) для логгера '{logger_name}'")
        except Exception as e:
             print(f"WARNING (LogManager._setup_logging): Ошибка загрузки форматтера из конфига для '{logger_name}': {e}")

        # Если форматтер не загружен, используем стандартный
        if formatter is None:
             formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s') 
             print(f"DEBUG (LogManager._setup_logging): Используется форматтер по умолчанию для логгера '{logger_name}'")

        # --- Создание и настройка обработчика файла ---
        try:
            print(f"DEBUG (LogManager._setup_logging): Создание FileHandler для '{log_file}' для логгера '{logger_name}'")
            # Убедимся, что директория существует (дублируем для надежности)
            log_file_dir = os.path.dirname(log_file)
            if log_file_dir:
                os.makedirs(log_file_dir, exist_ok=True)
            
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setFormatter(formatter)
            handler.setLevel(self.log_level) # Устанавливаем уровень и для обработчика
            print(f"DEBUG (LogManager._setup_logging): FileHandler для '{log_file}' успешно создан для логгера '{logger_name}'")
        except Exception as e:
             print(f"ERROR (LogManager._setup_logging): Не удалось создать FileHandler для '{log_file}' для логгера '{logger_name}': {e}")
             # В случае ошибки создания файлового обработчика, можно добавить StreamHandler как fallback
             # handler = logging.StreamHandler(sys.stdout)
             # handler.setFormatter(formatter)
             raise # Пока просто пробрасываем исключение

        # --- Добавление обработчика к логгеру ---
        logger.addHandler(handler)
        print(f"DEBUG (LogManager._setup_logging): FileHandler добавлен к логгеру '{logger_name}'. Логгер готов.")
        
        # --- Отключаем propagate ---
        # Это предотвращает дублирование сообщений в родительские логгеры (например, корневой)
        # Если вы хотите, чтобы сообщения из CSV-логгера также попадали в app_*.log и errors_*.log,
        # установите logger.propagate = True. Пока отключим для изоляции.
        logger.propagate = False 
        print(f"DEBUG (LogManager._setup_logging): propagate для логгера '{logger_name}' установлен в {logger.propagate}.")

        return log_file

    def get_logger(self) -> logging.Logger:
        """
        Возвращает настроенный логгер для текущего CSV-файла.

        Returns:
            logging.Logger: Логгер для текущего CSV-файла.
        """
        # Получение логгера по имени файла (без расширения)
        base = os.path.splitext(os.path.basename(self.csv_filename))[0]
        logger = logging.getLogger(base)
        print(f"DEBUG (LogManager.get_logger): Возвращен логгер '{base}'")
        return logger

# Примечание: Убедитесь, что в config.json output.log_dir указывает на существующую директорию,
# например, "logs". Эта директория будет создана автоматически, если её нет.