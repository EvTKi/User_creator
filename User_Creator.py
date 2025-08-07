# main.py

import os
import csv
import uuid
import chardet
from datetime import datetime
from typing import List, Dict, Optional
import getpass
import ldap3
from ldap3 import Server, Connection, ALL, AUTO_BIND_NO_TLS

# --- Конфигурация ---
DOMAIN_SERVER = 'your-domain-controller.your-domain.local'  # Заменить
DOMAIN_DN = 'DC=your-domain,DC=local'                     # Заменить
AD_USER = 'your_ad_user@your-domain.local'                # Заменить
AD_PASSWORD = getpass.getpass("Введите пароль AD: ")       # Безопасный ввод

# --- Вспомогательные функции ---

def detect_encoding(file_path: str) -> str:
    """Определяет кодировку файла (с приоритетом BOM)"""
    with open(file_path, 'rb') as f:
        raw = f.read(4)
    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    elif raw.startswith(b'\xff\xfe'):
        return 'utf-16-le'
    elif raw.startswith(b'\xfe\xff'):
        return 'utf-16-be'
    else:
        result = chardet.detect(raw)
        return result['encoding'] or 'windows-1251'

def detect_delimiter(first_line: str) -> str:
    """Определяет разделитель: ; или ,"""
    if ';' in first_line:
        return ';'
    elif ',' in first_line:
        return ','
    return ';'

def connect_to_ad() -> Optional[Connection]:
    """Подключается к Active Directory"""
    server = Server(DOMAIN_SERVER, get_info=ALL)
    try:
        conn = Connection(
            server,
            user=AD_USER,
            password=AD_PASSWORD,
            auto_bind=True
        )
        print("✅ Подключение к AD успешно.")
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к AD: {e}")
        return None

def get_user_guid(conn: Connection, sAMAccountName: str) -> Optional[str]:
    """Получает ObjectGUID пользователя по логину"""
    conn.search(
        search_base=DOMAIN_DN,
        search_filter=f'(sAMAccountName={sAMAccountName})',
        attributes=['objectGUID']
    )
    if len(conn.entries) > 0:
        # objectGUID возвращается как байты, конвертируем в строку GUID
        guid_bytes = conn.entries[0].objectGUID.raw_values[0]
        # Переворачиваем первые 4 байта (little-endian)
        guid = uuid.UUID(bytes_le=guid_bytes)
        return str(guid).upper()
    return None

# --- Генерация XML ---

def generate_sysconfig_xml(ad_guid: str, users_data: List[Dict]) -> str:
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_sysconfig">
      <md:Model.created>{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")}Z</md:Model.created>
      <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
      <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
  </md:FullModel>
'''
    for user in users_data:
        person_guid = user['person_guid']
        name = user['name']
        login = user['login'] or ''
        parent_sysconfig = user['parent_sysconfig'] or ''
        roles = user['roles'] or ''
        groups = user['groups'] or ''

        roles_blocks = ''
        if roles:
            for role in filter(None, [r.strip() for r in roles.split('!')]):
                roles_blocks += f'<cim:Principal.Roles rdf:resource="#_{role}" />'

        groups_blocks = ''
        if groups:
            for group in filter(None, [g.strip() for g in groups.split('!')]):
                groups_blocks += f'<cim:Principal.Groups rdf:resource="#_{group}" />'

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

def generate_energy_xml(users_data: List[Dict]) -> str:
    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_energy">
      <md:Model.created>{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")}Z</md:Model.created>
      <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
      <me:Model.name>CIM16</me:Model.name>
  </md:FullModel>
'''
    for user in users_data:
        person_guid = user['person_guid']
        name = user['name']
        email = user['email'] or ''
        mobile = user['mobilePhone'] or ''
        position = user['position'] or ''
        operational = user['OperationalAuthorities'] or ''
        electrical = user['electrical_safety_level'] or ''
        parent_energy = user['parent_energy'] or ''

        # Email
        email_block = f'''
<cim:Person.electronicAddress>
    <cim:ElectronicAddress>
      <cim:ElectronicAddress.email1>{email}</cim:ElectronicAddress.email1>
    </cim:ElectronicAddress>
</cim:Person.electronicAddress>''' if email else ''

        # Phone
        phone_block = f'''
<cim:Person.mobilePhone>
    <cim:TelephoneNumber>
      <cim:TelephoneNumber.localNumber>{mobile}</cim:TelephoneNumber.localNumber>
    </cim:TelephoneNumber>
</cim:Person.mobilePhone>''' if mobile else ''

        # Position
        position_block = f'<me:Person.Position rdf:resource="#_{position}"/>' if position else ''

        # Operational Authorities
        operational_blocks = ''
        if operational:
            for uid in filter(None, [u.strip() for u in operational.split('!')]):
                operational_blocks += f'    <me:Person.OperationalAuthorities rdf:resource="#_{uid}" />\n'

        # Electrical Safety
        electrical_block = f'<me:Person.ElectricalSafetyLevel rdf:resource="#_{electrical}"/>' if electrical else ''

        # ФИО
        fio = name.strip().split()
        fio_last = fio[0] if len(fio) >= 1 else ''
        fio_first = fio[1] if len(fio) >= 2 else ''
        fio_middle = fio[2] if len(fio) >= 3 else ''

        # Аббревиатура: Иванов И.П.
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
    print("Выберите режим:")
    print("Y — использовать AD для получения GUID по логину")
    print("N — использовать GUID из CSV (или генерировать)")
    mode = input("Выбор (y/n): ").strip().lower()

    ad_guid = None
    ad_conn = None
    not_found_in_ad = []

    if mode == 'y':
        # Подключаемся к AD, получаем доменный GUID
        ad_conn = connect_to_ad()
        if not ad_conn:
            print("❌ Не удалось подключиться к AD. Завершаем.")
            return

        # Получаем GUID домена
        ad_conn.search(
            search_base=DOMAIN_DN,
            search_filter='(objectClass=domainDNS)',
            attributes=['objectGUID']
        )
        if len(ad_conn.entries) > 0:
            guid_bytes = ad_conn.entries[0].objectGUID.raw_values[0]
            ad_guid = str(uuid.UUID(bytes_le=guid_bytes)).upper()
        else:
            print("❌ Не удалось получить GUID домена.")
            return
        print(f"GUID домена (adGuid) из AD: {ad_guid}")
    else:
        ad_guid = input("Введите GUID домена (adGuid): ").strip()

    # Обработка CSV-файлов
    current_dir = os.getcwd()
    csv_files = [
        f for f in os.listdir(current_dir)
        if f.lower().endswith('.csv') and f != 'Sample.csv'
    ]

    if not csv_files:
        print("❌ Нет подходящих CSV-файлов для обработки.")
        return

    for csv_file in csv_files:
        file_path = os.path.join(current_dir, csv_file)
        print(f"\n🔄 Обработка файла: {csv_file}")

        # Определяем кодировку и читаем
        encoding = detect_encoding(file_path)
        print(f"Кодировка: {encoding}")

        with open(file_path, 'r', encoding=encoding) as f:
            first_line = f.readline()
            f.seek(0)
            delimiter = detect_delimiter(first_line)
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)

        updated_rows = []
        users_data = []

        for row in rows:
            person_guid = row.get('person_guid', '').strip()
            name = row.get('name', '').strip()
            login = row.get('login', '').strip()
            email = row.get('email', '').strip()
            mobile = row.get('mobilePhone', '').strip()
            position = row.get('position', '').strip()
            operational = row.get('OperationalAuthorities', '').strip()
            electrical = row.get('electrical_safety_level', '').strip()
            roles = row.get('roles', '').strip()
            groups = row.get('groups', '').strip()
            parent_energy = row.get('parent_energy', '').strip()
            parent_sysconfig = row.get('parent_sysconfig', '').strip()

            if not name:
                continue

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

            # Сохраняем обновлённую строку
            updated_row = {
                'person_guid': person_guid,
                'name': name,
                'login': login,
                'email': email,
                'mobilePhone': mobile,
                'position': position,
                'OperationalAuthorities': operational,
                'electrical_safety_level': electrical,
                'roles': roles,
                'groups': groups,
                'parent_energy': parent_energy,
                'parent_sysconfig': parent_sysconfig
            }
            updated_rows.append(updated_row)
            users_data.append(updated_row)

        # Генерация XML
        sysconfig_xml = generate_sysconfig_xml(ad_guid, users_data)
        energy_xml = generate_energy_xml(users_data)

        # Сохранение XML
        base_name = os.path.splitext(csv_file)[0]
        with open(f"{base_name}.sysconfig.xml", 'w', encoding='utf-8') as f:
            f.write(sysconfig_xml)
        with open(f"{base_name}.energy.xml", 'w', encoding='utf-8') as f:
            f.write(energy_xml)

        # Перезапись CSV с обновлёнными GUID
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=updated_rows[0].keys(), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(updated_rows)

        print(f"✅ Созданы: {base_name}.energy.xml, {base_name}.sysconfig.xml, обновлён {csv_file}")

    # Сохраняем not_in_AD.csv
    if mode == 'y' and not_found_in_ad:
        not_found_in_ad.sort(key=lambda x: x['login'])
        with open('not_in_AD.csv', 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['login', 'name', 'person_guid']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(not_found_in_ad)
        print("\n🟡 Логины, не найденные в AD, сохранены в `not_in_AD.csv`")

    print("\n✅ Обработка завершена. Все person_guid записаны в исходные CSV!")

if __name__ == "__main__":
    main()