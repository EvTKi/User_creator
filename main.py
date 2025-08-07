# main.py
"""
Основной скрипт для обработки CSV-файлов с данными пользователей,
генерации XML-файлов и работы с Active Directory.

Этот скрипт координирует работу всех модулей проекта:
- Загружает конфигурацию (config_loader)
- Настраивает логирование (logging_config)
- Обрабатывает пользовательский ввод режима работы
- Управляет подключением к AD (ad_operations)
- Находит и обрабатывает CSV-файлы (csv_processing)
- Генерирует XML-файлы (xml_generation)
- Сохраняет результаты и пользователей, не найденных в AD
"""

import os
import sys
import csv
import uuid
import logging
from typing import List, Dict, Optional
import getpass
import traceback

# Импортируем модули проекта
from config_loader import CONFIG
from ad_operations import connect_to_ad, get_domain_guid
from xml_generation import generate_sysconfig_xml, generate_energy_xml
from csv_processing import (
    find_csv_files, read_csv_file, write_csv_file, 
    process_user_row, get_file_encoding
)
from logging_config import LogManager

# Константы из конфигурации
AD_ENABLED = CONFIG['ad']['enabled']
"""bool: Флаг включения/выключения работы с Active Directory."""

NOT_IN_AD_CSV = CONFIG['output']['not_in_ad_csv']
"""str: Имя файла для сохранения пользователей, не найденных в AD."""

SYSCONFIG_SUFFIX = CONFIG['output']['sysconfig_xml_suffix']
"""str: Суффикс для генерируемых XML-файлов SysConfig."""

ENERGY_SUFFIX = CONFIG['output']['energy_xml_suffix']
"""str: Суффикс для генерируемых XML-файлов Energy."""


def get_processing_mode() -> str:
    """
    Запрашивает у пользователя режим обработки.
    
    Returns:
        str: Выбранный режим ('y' или 'n').
    """
    print("\n" + "="*60)
    print("РЕЖИМ ОБРАБОТКИ")
    print("Y — использовать AD для получения GUID по логину")
    print("N — использовать GUID из CSV (или ввести вручную)")
    print("="*60)
    mode = input("Выберите режим (y/n): ").strip().lower()
    while mode not in ('y', 'n'):
        mode = input("Введите 'y' или 'n': ").strip().lower()
    return mode


def initialize_ad_connection(mode: str) -> tuple:
    """
    Инициализирует подключение к AD и получает GUID домена.
    
    Args:
        mode (str): Режим работы ('y' или 'n').
        
    Returns:
        tuple: Кортеж из (ad_conn, ad_guid, not_found_in_ad) или (None, None, []) в случае ошибки.
    """
    ad_guid = None
    ad_conn = None
    not_found_in_ad = []
    
    if mode == 'y' and AD_ENABLED:
        password = getpass.getpass("🔐 Введите пароль AD: ")
        ad_conn = connect_to_ad(password)
        if not ad_conn:
            print("❌ Не удалось подключиться к AD.")
            return None, None, None
        
        ad_guid = get_domain_guid(ad_conn)
        if not ad_guid:
            print("❌ Не удалось получить GUID домена.")
            return None, None, None
    else:
        ad_guid_input = input("Введите GUID домена (adGuid): ").strip()
        ad_guid = ad_guid_input.upper()
    
    return ad_conn, ad_guid, not_found_in_ad


def process_single_csv(
    csv_file: str, 
    mode: str, 
    ad_conn, 
    ad_guid: str, 
    not_found_in_ad: List[Dict]
) -> bool:
    """
    Обрабатывает один CSV-файл.
    
    Args:
        csv_file (str): Имя CSV-файла для обработки.
        mode (str): Режим работы ('y' или 'n').
        ad_conn: Подключение к AD (если используется).
        ad_guid (str): GUID домена AD.
        not_found_in_ad (List[Dict]): Список для накопления пользователей, не найденных в AD.
        
    Returns:
        bool: True, если обработка прошла успешно, False в случае ошибки.
    """
    file_path = os.path.join('.', csv_file)
    base_name = os.path.splitext(csv_file)[0]
    
    # Создаём LogManager и получаем логгер
    log_manager = LogManager(csv_file)
    logger = log_manager.get_logger()
    logger.info(f"🚀 Начата обработка файла: {csv_file}")
    
    if mode == 'y' and AD_ENABLED:
        logger.info(f"✅ Используется GUID домена из AD: {ad_guid}")
    else:
        logger.info(f"✅ Используется вручную введённый GUID домена: {ad_guid}")
    
    # Определение кодировки и чтение CSV
    try:
        encoding = get_file_encoding(file_path)
        logger.info(f"Определена кодировка: {encoding}")
        rows = read_csv_file(file_path, encoding)
        logger.info(f"Прочитано строк: {len(rows)}")
    except FileNotFoundError:
        logger.error(f"❌ Файл {file_path} не найден.")
        return False
    except UnicodeDecodeError as e:
        logger.error(f"❌ Ошибка декодирования файла {file_path}: {e}")
        logger.debug(f"Детали ошибки: {traceback.format_exc()}")
        return False
    except csv.Error as e:
        logger.error(f"❌ Ошибка CSV в файле {file_path}: {e}")
        logger.debug(f"Детали ошибки: {traceback.format_exc()}")
        return False
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка чтения файла {file_path}: {e}")
        logger.debug(f"Детали ошибки: {traceback.format_exc()}")
        return False
    
    updated_rows = []
    users_data = []
    
    for row_idx, row in enumerate(rows):
        try:
            processed_row = process_user_row(row, row_idx, csv_file, mode, ad_conn, ad_guid, not_found_in_ad, logger)
            if processed_row:
                updated_rows.append(processed_row)
                users_data.append(processed_row)
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при обработке строки {row_idx + 1} в файле {csv_file}: {e}")
            logger.debug(f"Детали ошибки: {traceback.format_exc()}")
            continue
    
    # Генерация XML
    try:
        sys_xml = generate_sysconfig_xml(ad_guid, users_data)
        energy_xml = generate_energy_xml(users_data)
        with open(f"{base_name}{SYSCONFIG_SUFFIX}", 'w', encoding='utf-8') as f:
            f.write(sys_xml)
        with open(f"{base_name}{ENERGY_SUFFIX}", 'w', encoding='utf-8') as f:
            f.write(energy_xml)
        logger.info(f"✅ Успешно сгенерированы XML-файлы: "
                   f"{base_name}{SYSCONFIG_SUFFIX}, {base_name}{ENERGY_SUFFIX}")
    except Exception as e:
        logger.error(f"❌ Ошибка генерации XML для файла {csv_file}: {e}")
        logger.debug(f"Детали ошибки: {traceback.format_exc()}")
        return False
    
    # Перезапись CSV
    try:
        write_csv_file(file_path, updated_rows)
        logger.info(f"✅ CSV файл обновлён и сохранён: {csv_file}")
    except Exception as e:
        logger.error(f"❌ Ошибка записи CSV для файла {csv_file}: {e}")
        logger.debug(f"Детали ошибки: {traceback.format_exc()}")
        return False
        
    logger.info(f"✅ Обработка файла '{csv_file}' завершена.")
    return True


def save_not_found_users(not_found_in_ad: List[Dict], csv_files: List[str]):
    """
    Сохраняет список пользователей, не найденных в AD, в отдельный CSV-файл.
    
    Args:
        not_found_in_ad (List[Dict]): Список пользователей, не найденных в AD.
        csv_files (List[str]): Список обработанных CSV-файлов (для получения логгера).
    """
    if not_found_in_ad:
        try:
            not_found_in_ad.sort(key=lambda x: x['login'])
            with open(NOT_IN_AD_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['login', 'name', 'person_guid'], delimiter=';')
                writer.writeheader()
                writer.writerows(not_found_in_ad)
            # Логируем в последний обработанный файл
            if csv_files:
                last_logger = logging.getLogger(os.path.splitext(csv_files[-1])[0])
                last_logger.warning(f"🟡 Логины не из AD сохранены в: {NOT_IN_AD_CSV}")
        except Exception as e:
            if csv_files:
                last_logger = logging.getLogger(os.path.splitext(csv_files[-1])[0])
                last_logger.error(f"❌ Ошибка записи {NOT_IN_AD_CSV}: {e}")
                last_logger.debug(f"Детали ошибки: {traceback.format_exc()}")


def main():
    """
    Основная функция программы.
    
    Координирует весь процесс:
    1. Запрашивает режим работы у пользователя.
    2. Инициализирует подключение к AD (если требуется).
    3. Находит все подходящие CSV-файлы.
    4. Последовательно обрабатывает каждый файл.
    5. Сохраняет список пользователей, не найденных в AD.
    6. Выводит финальное сообщение о завершении.
    """
    mode = get_processing_mode()
    ad_conn, ad_guid, not_found_in_ad = initialize_ad_connection(mode)
    
    if ad_conn is None and ad_guid is None:
        # Это означает ошибку при инициализации AD
        return
    
    # --- Поиск CSV-файлов ---
    csv_files = find_csv_files(['Sample.csv', NOT_IN_AD_CSV])
    if not csv_files:
        print("⚠️ Нет подходящих CSV-файлов для обработки.")
        return
    
    # --- Обработка каждого файла ---
    for csv_file in csv_files:
        success = process_single_csv(csv_file, mode, ad_conn, ad_guid, not_found_in_ad)
        if not success:
            print(f"⚠️ Обработка файла {csv_file} завершена с ошибками.")
    
    # --- Сохранение not_in_AD.csv ---
    if mode == 'y' and not_found_in_ad:
        save_not_found_users(not_found_in_ad, csv_files)
    
    # Финальное сообщение
    if csv_files:
        final_logger = logging.getLogger(os.path.splitext(csv_files[-1])[0])
        final_logger.info("✅ Все файлы успешно обработаны.")


if __name__ == "__main__":
    main()