"""
Модуль для работы с CSV-файлами.
"""
import csv
import os
import uuid
from typing import List, Dict, Optional
import traceback
import logging

# Импортируем конфигурацию
from .config_loader import CONFIG

INPUT_ENCODING = CONFIG['input']['encoding']  # должно быть "windows-1251"
DELIMITER = CONFIG['input']['delimiter']
NOT_IN_AD_CSV = CONFIG['output']['not_in_ad_csv']


def get_file_encoding(file_path: str) -> str:
    """
    Определяет кодировку файла по его первым байтам.

    Args:
        file_path (str): Путь к файлу.

    Returns:
        str: Определенная кодировка файла.
    """
    try:
        with open(file_path, 'rb') as f:
            raw = f.read(4)
        if raw.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        elif raw.startswith(b'\xff\xfe\x00\x00'):
            return 'utf-32'
        elif raw.startswith(b'\xff\xfe'):
            return 'utf-16'
        elif raw.startswith(b'\xfe\xff'):
            return 'big-endian-unicode'
        else:
            return INPUT_ENCODING
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Ошибка определения кодировки файла {file_path}: {e}")
        # Возвращаем кодировку по умолчанию
        return INPUT_ENCODING


def find_csv_files(exclude_files: List[str] = ['Sample.csv', NOT_IN_AD_CSV]) -> List[str]:
    """
    Находит все CSV-файлы в текущей директории, исключая указанные.

    Args:
        exclude_files (List[str]): Список имен файлов для исключения.

    Returns:
        List[str]: Список имен найденных CSV-файлов.
    """
    try:
        return [
            f for f in os.listdir('.')
            if f.lower().endswith('.csv') and f not in exclude_files
        ]
    except Exception as e:
        logging.getLogger(__name__).error(f"Ошибка поиска CSV-файлов: {e}")
        return []


def read_csv_file(file_path: str, encoding: str) -> List[Dict]:
    """
    Читает CSV-файл и возвращает список словарей.

    Args:
        file_path (str): Путь к CSV-файлу.
        encoding (str): Кодировка файла.

    Returns:
        List[Dict]: Список словарей с данными из CSV.

    Raises:
        Exception: В случае ошибок при чтении файла.
    """
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            first_line = f.readline()
            f.seek(0)
            delimiter = DELIMITER if DELIMITER in first_line else (
                ',' if ',' in first_line else ';')
            reader = csv.DictReader(f, delimiter=delimiter)
            return list(reader)
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Ошибка чтения CSV-файла {file_path}: {e}")
        logging.getLogger(__name__).debug(
            f"Детали ошибки: {traceback.format_exc()}")
        raise  # Передаем исключение дальше


def write_csv_file(file_path: str, rows: List[Dict], delimiter: str = DELIMITER):
    """
    Записывает данные в CSV-файл.

    Args:
        file_path (str): Путь к CSV-файлу для записи.
        rows (List[Dict]): Список словарей с данными для записи.
        delimiter (str): Разделитель полей (по умолчанию из конфигурации).

    Raises:
        Exception: В случае ошибок при записи файла.
    """
    if not rows:
        return

    try:
        with open(file_path, 'w', newline='', encoding=INPUT_ENCODING) as f:
            writer = csv.DictWriter(
                f, fieldnames=rows[0].keys(), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Ошибка записи CSV-файла {file_path}: {e}")
        logging.getLogger(__name__).debug(
            f"Детали ошибки: {traceback.format_exc()}")
        raise  # Передаем исключение дальше


def process_user_row(row: Dict, row_index: int, csv_file: str, mode: str, ad_conn, ad_guid: str, not_found_in_ad: List[Dict], logger: logging.Logger) -> Optional[Dict]:
    """
    Обрабатывает одну строку данных пользователя из CSV.

    Args:
        row (Dict): Словарь с данными строки из CSV.
        row_index (int): Индекс строки в CSV (для логирования).
        csv_file (str): Имя обрабатываемого CSV-файла.
        mode (str): Режим работы ('y' - с AD, 'n' - без AD).
        ad_conn: Подключение к AD (если используется).
        ad_guid (str): GUID домена AD.
        not_found_in_ad (List[Dict]): Список для накопления пользователей, не найденных в AD.
        logger (logging.Logger): Логгер для текущего файла.

    Returns:
        Optional[Dict]: Словарь с обработанными данными пользователя или None, если строку нужно пропустить.
    """
    try:
        name = (row.get('name') or '').strip()

        # Проверка на пустое имя
        if not name:
            logger.debug(
                f"Файл: {csv_file}, Строка: {row_index + 1}: пропущена (пустое имя)")
            return None

        person_guid = (row.get('person_guid') or '').strip()
        login = (row.get('login') or '').strip()

        mark_not_found = False

        if mode == 'y' and ad_conn:
            ad_person_guid = None
            if login:
                # Импортируем функцию из ad_operations
                from ad_operations import get_user_guid
                ad_person_guid = get_user_guid(ad_conn, login)
            if ad_person_guid:
                person_guid = ad_person_guid
            elif person_guid:
                mark_not_found = True
            else:
                person_guid = str(uuid.uuid4()).upper()
                mark_not_found = True
            if mark_not_found:
                not_found_in_ad.append({
                    'login': login,
                    'name': name,
                    'person_guid': person_guid
                })
        else:
            if not person_guid:
                person_guid = str(uuid.uuid4()).upper()

        return {
            'person_guid': person_guid,
            'name': name,
            'login': login,
            'email': row.get('email', ''),
            'mobilePhone': row.get('mobilePhone', ''),
            'position': row.get('position', ''),
            'OperationalAuthorities': row.get('OperationalAuthorities', ''),
            'electrical_safety_level': row.get('electrical_safety_level', ''),
            'roles': row.get('roles', ''),
            'groups': row.get('groups', ''),
            'department': row.get('department', ''),
            'organisation': row.get('organisation', ''),
            'parent_energy': row.get('parent_energy', ''),
            'parent_access': row.get('parent_access', '')
        }
    except Exception as e:
        logger.error(
            f"❌ Ошибка обработки строки {row_index + 1} в файле {csv_file}: {e}")
        logger.debug(f"Детали ошибки: {traceback.format_exc()}")
        return None
