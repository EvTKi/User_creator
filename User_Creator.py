# main.py

import os
import sys
import csv
import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import getpass
import ldap3
from ldap3 import Server, Connection, ALL, AUTO_BIND_NO_TLS

# --- Загрузка конфигурации ---
CONFIG_PATH = 'config.json'

if not os.path.exists(CONFIG_PATH):
    print(f"❌ Файл конфигурации не найден: {CONFIG_PATH}")
    sys.exit(1)

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# --- Настройка логирования ---
log_dir = config['output']['log_dir']
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y-%m-%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Константы ---
AD_ENABLED = config['ad']['enabled']
DOMAIN_CONTROLLER = config['ad']['domain_controller']
DOMAIN_DN = config['ad']['domain_dn']
AD_USER = config['ad']['user']
INPUT_ENCODING = config['input']['encoding']  # должно быть "windows-1251"
DELIMITER = config['input']['delimiter']
ENERGY_SUFFIX = config['output']['energy_xml_suffix']
SYSCONFIG_SUFFIX = config['output']['sysconfig_xml_suffix']
NOT_IN_AD_CSV = config['output']['not_in_ad_csv']
MODEL_VERSION_SYS = config['xml']['model_version_sysconfig']
MODEL_VERSION_ENERGY = config['xml']['model_version_energy']

# --- Определение кодировки (как в PowerShell) ---
def get_file_encoding(file_path: str) -> str:
    """Определяет кодировку файла, как в PowerShell-функции Get-FileEncoding"""
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
        return INPUT_ENCODING  # По умолчанию windows-1251

# --- Подключение к AD ---
def connect_to_ad(password: str) -> Optional[Connection]:
    server = Server(DOMAIN_CONTROLLER, get_info=ALL)
    try:
        conn = Connection(server, user=AD_USER, password=password, auto_bind=True)
        logger.info("✅ Подключение к AD успешно.")
        return conn
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к AD: {e}")
        return None

def get_user_guid(conn: Connection, sAMAccountName: str) -> Optional[str]:
    """Получает ObjectGUID по логину"""
    try:
        conn.search(
            search_base=DOMAIN_DN,
            search_filter=f'(sAMAccountName={sAMAccountName})',
            attributes=['objectGUID']
        )
        if conn.entries:
            guid_bytes = conn.entries[0].objectGUID.raw_values[0]
            guid = uuid.UUID(bytes_le=guid_bytes)
            return str(guid).upper()
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при поиске GUID для {sAMAccountName}: {e}")
    return None

# --- Генерация XML ---
def generate_sysconfig_xml(ad_guid: str, users: List[Dict]) -> str:
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_sysconfig">
      <md:Model.created>{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")}Z</md:Model.created>
      <md:Model.version>{MODEL_VERSION_SYS}</md:Model.version>
      <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
  </md:FullModel>
'''
    for user in users:
        person_guid = user['person_guid']
        name = user['name']
        login = user.get('login', '') or ''
        parent_sysconfig = user.get('parent_sysconfig', '') or ''
        roles = user.get('roles', '') or ''
        groups = user.get('groups', '') or ''

        roles_blocks = ''.join(
            f'<cim:Principal.Roles rdf:resource="#_{r.strip()}" />'
            for r in roles.split('!') if r.strip()
        )
        groups_blocks = ''.join(
            f'<cim:Principal.Groups rdf:resource="#_{g.strip()}" />'
            for g in groups.split('!') if g.strip()
        )

        xml += f'''

  <cim:User rdf:about="#_{person_guid}">
      <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>
      <cim:Principal.Domain rdf:resource="#_{ad_guid}" />
      <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
      <cim:User.login>{login}</cim:User.login>
      <cim:IdentifiedObject.ParentObject rdf:resource="#_{parent_sysconfig}" />
      {roles_blocks}
      {groups_blocks}
  </cim:User>
'''
    xml += '</rdf:RDF>'
    return xml

def generate_energy_xml(users: List[Dict]) -> str:
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_energy">
      <md:Model.created>{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")}Z</md:Model.created>
      <md:Model.version>{MODEL_VERSION_ENERGY}</md:Model.version>
      <me:Model.name>CIM16</me:Model.name>
  </md:FullModel>
'''
    for user in users:
        person_guid = user['person_guid']
        name = user['name']
        email = user.get('email', '') or ''
        mobile = user.get('mobilePhone', '') or ''
        position = user.get('position', '') or ''
        operational = user.get('OperationalAuthorities', '') or ''
        electrical = user.get('electrical_safety_level', '') or ''
        parent_energy = user.get('parent_energy', '') or ''

        email_block = f'''
<cim:Person.electronicAddress>
    <cim:ElectronicAddress>
      <cim:ElectronicAddress.email1>{email}</cim:ElectronicAddress.email1>
    </cim:ElectronicAddress>
</cim:Person.electronicAddress>''' if email else ''

        phone_block = f'''
<cim:Person.mobilePhone>
    <cim:TelephoneNumber>
      <cim:TelephoneNumber.localNumber>{mobile}</cim:TelephoneNumber.localNumber>
    </cim:TelephoneNumber>
</cim:Person.mobilePhone>''' if mobile else ''

        position_block = f'<me:Person.Position rdf:resource="#_{position}"/>' if position else ''

        operational_blocks = ''.join(
            f'    <me:Person.OperationalAuthorities rdf:resource="#_{u.strip()}" />\n'
            for u in operational.split('!') if u.strip()
        )

        electrical_block = f'<me:Person.ElectricalSafetyLevel rdf:resource="#_{electrical}"/>' if electrical else ''

        fio = name.strip().split()
        fio_last = fio[0] if len(fio) >= 1 else ''
        fio_first = fio[1] if len(fio) >= 2 else ''
        fio_middle = fio[2] if len(fio) >= 3 else ''

        abbreviation = fio_last
        if fio_first:
            abbreviation += ' ' + fio_first[0] + '.'
        if fio_middle:
            abbreviation += fio_middle[0] + '.'

        name_abbreviation_guid = str(uuid.uuid4()).upper()

        xml += f'''

  <cim:Person rdf:about="#_{person_guid}">
      <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>
      <cim:IdentifiedObject.Names rdf:resource="#_{name_abbreviation_guid}" />
      <me:IdentifiedObject.ParentObject rdf:resource="#_{parent_energy}" />
      {email_block}
      <cim:Person.firstName>{fio_first}</cim:Person.firstName>
      <cim:Person.lastName>{fio_last}</cim:Person.lastName>
      <cim:Person.mName>{fio_middle}</cim:Person.mName>
      {phone_block}
      {position_block}
      {electrical_block}
{operational_blocks}
  </cim:Person>

  <cim:Name rdf:about="#_{name_abbreviation_guid}">
      <cim:Name.name>{abbreviation}</cim:Name.name>
      <cim:Name.IdentifiedObject rdf:resource="#_{person_guid}" />
      <cim:Name.NameType rdf:resource="#_00000002-0000-0000-c000-0000006d746c" />
  </cim:Name>
'''
    xml += '</rdf:RDF>'
    return xml

# --- Основной процесс ---
def main():
    logger.info("🚀 Запуск скрипта преобразования CSV → CIM XML")

    print("\n" + "="*60)
    print("РЕЖИМ ОБРАБОТКИ")
    print("Y — использовать AD для получения GUID по логину")
    print("N — использовать GUID из CSV (или ввести вручную)")
    print("="*60)

    mode = input("Выберите режим (y/n): ").strip().lower()
    while mode not in ('y', 'n'):
        mode = input("Введите 'y' или 'n': ").strip().lower()

    ad_guid = None
    ad_conn = None
    not_found_in_ad = []

    if mode == 'y' and AD_ENABLED:
        password = getpass.getpass("🔐 Введите пароль AD: ")
        ad_conn = connect_to_ad(password)
        if not ad_conn:
            logger.error("❌ Не удалось подключиться к AD. Работа завершена.")
            return

        try:
            ad_conn.search(
                search_base=DOMAIN_DN,
                search_filter='(objectClass=domainDNS)',
                attributes=['objectGUID']
            )
            if ad_conn.entries:
                guid_bytes = ad_conn.entries[0].objectGUID.raw_values[0]
                ad_guid = str(uuid.UUID(bytes_le=guid_bytes)).upper()
                logger.info(f"✅ GUID домена из AD: {ad_guid}")
            else:
                logger.error("❌ Не удалось получить GUID домена.")
                return
        except Exception as e:
            logger.error(f"❌ Ошибка получения GUID домена: {e}")
            return
    else:
        ad_guid_input = input("Введите GUID домена (adGuid): ").strip()
        ad_guid = ad_guid_input.upper()
        logger.info(f"✅ Используется вручную введённый GUID домена: {ad_guid}")

    # --- Поиск CSV-файлов ---
    csv_files = [
        f for f in os.listdir('.')
        if f.lower().endswith('.csv') and f != 'Sample.csv' and f != NOT_IN_AD_CSV
    ]

    if not csv_files:
        logger.warning("⚠️ Нет подходящих CSV-файлов для обработки.")
        return

    # --- Обработка каждого файла ---
    for csv_file in csv_files:
        file_path = os.path.join('.', csv_file)
        logger.info(f"🔄 Обработка файла: {csv_file}")

        encoding = get_file_encoding(file_path)
        logger.debug(f"Определена кодировка: {encoding}")

        try:
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline()
                f.seek(0)
                delimiter = DELIMITER if DELIMITER in first_line else (',' if ',' in first_line else ';')
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
        except Exception as e:
            logger.error(f"❌ Ошибка чтения {csv_file}: {e}")
            continue

        updated_rows = []
        users_data = []

        for row in rows:
            name = (row.get('name') or '').strip()
            if not name:
                continue

            person_guid = (row.get('person_guid') or '').strip()
            login = (row.get('login') or '').strip()
            mark_not_found = False

            if mode == 'y' and ad_conn:
                ad_person_guid = None
                if login:
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

            updated_row = {
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
                'parent_energy': row.get('parent_energy', ''),
                'parent_sysconfig': row.get('parent_sysconfig', '')
            }
            updated_rows.append(updated_row)
            users_data.append(updated_row)

        # --- Генерация XML ---
        try:
            base_name = os.path.splitext(csv_file)[0]
            sys_xml = generate_sysconfig_xml(ad_guid, users_data)
            energy_xml = generate_energy_xml(users_data)

            with open(f"{base_name}{SYSCONFIG_SUFFIX}", 'w', encoding='utf-8') as f:
                f.write(sys_xml)
            with open(f"{base_name}{ENERGY_SUFFIX}", 'w', encoding='utf-8') as f:
                f.write(energy_xml)

            logger.info(f"✅ Созданы XML: {base_name}{SYSCONFIG_SUFFIX}, {base_name}{ENERGY_SUFFIX}")
        except Exception as e:
            logger.error(f"❌ Ошибка генерации XML: {e}")
            continue

        # --- Перезапись CSV ---
        try:
            with open(file_path, 'w', newline='', encoding=INPUT_ENCODING) as f:
                writer = csv.DictWriter(f, fieldnames=updated_rows[0].keys(), delimiter=DELIMITER)
                writer.writeheader()
                writer.writerows(updated_rows)
            logger.info(f"✅ Обновлён CSV: {csv_file}")
        except Exception as e:
            logger.error(f"❌ Ошибка записи CSV: {e}")

    # --- Сохранение not_in_AD.csv ---
    if mode == 'y' and not_found_in_ad:
        try:
            not_found_in_ad.sort(key=lambda x: x['login'])
            with open(NOT_IN_AD_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['login', 'name', 'person_guid'], delimiter=';')
                writer.writeheader()
                writer.writerows(not_found_in_ad)
            logger.warning(f"🟡 Логины не из AD сохранены в: {NOT_IN_AD_CSV}")
        except Exception as e:
            logger.error(f"❌ Ошибка записи not_in_AD.csv: {e}")

    logger.info("✅ Обработка завершена.")

if __name__ == "__main__":
    main()# main.py
