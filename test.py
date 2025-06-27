import os
import re
import csv
import uuid
import tempfile
from datetime import datetime

def get_file_encoding(file_path):
    """Определение кодировки файла по BOM"""
    with open(file_path, 'rb') as f:
        header = f.read(4)
    
    bom_map = {
        b'\xef\xbb\xbf': "utf-8",
        b'\xff\xfe\x00\x00': "utf-32",
        b'\xff\xfe': "utf-16",
        b'\xfe\xff': "big-endian-unicode"
    }
    
    for bom, encoding in bom_map.items():
        if header.startswith(bom):
            return encoding
    return "windows-1251"

def get_user_guid(sam_account_name):
    """Заглушка для получения GUID пользователя из AD"""
    # В реальной реализации используйте LDAP (например, модуль ldap3)
    return None

def main():
    # Выбор режима работы
    mode = input("Использовать данные из AD по логину (Y) или по CSV (N)? (y/n) ").lower()
    ad_guid = ""

    if mode == 'y':
        # В реальной реализации здесь должно быть получение GUID домена из AD
        ad_guid = input("Введите GUID домена (adGuid): ")
    else:
        ad_guid = input("Введите GUID домена (adGuid): ")

    # Поиск CSV-файлов в текущей директории
    csv_files = [f for f in os.listdir() 
                if f.endswith('.csv')] #and f != 'Sample.csv']
    not_found_in_ad = []

    for csv_file in csv_files:
        try:
            # Определение кодировки и чтение файла
            encoding = get_file_encoding(csv_file)
            
            with open(csv_file, 'r', encoding=encoding) as f:
                original_text = f.read()
            
            # Создание временного файла в нужной кодировке
            with tempfile.NamedTemporaryFile(mode='w', encoding='windows-1251', delete=False) as tmp:
                tmp.write(original_text)
                temp_path = tmp.name
            
            # Определение разделителя
            with open(temp_path, 'r', encoding='windows-1251') as f:
                first_line = f.readline().strip()
            
            delimiter = ';' if ';' in first_line else ','
            
            # Чтение CSV данных
            with open(temp_path, 'r', encoding='windows-1251') as f:
                csv_reader = csv.DictReader(f, delimiter=delimiter)
                csv_data = list(csv_reader)
            
            # Инициализация XML-структур
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            sysconfig_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_sysconfig">
      <md:Model.created>{timestamp}</md:Model.created>
      <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
      <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
  </md:FullModel>
"""
            energy_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_energy">
      <md:Model.created>{timestamp}</md:Model.created>
      <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
      <me:Model.name>CIM16</me:Model.name>
  </md:FullModel>
"""
            updated_rows = []
            
            for row in csv_data:
                # Извлечение данных
                name_key = next((k for k in row.keys() if k.endswith("name")), None)
                name = row.get(name_key, "")
                if not name.strip():
                    continue
                
                person_guid = row.get('person_guid', '')
                login = row.get('login', '')
                email = row.get('email', '')
                mobile_phone = row.get('mobilePhone', '')
                position = row.get('position', '')
                operational_authorities = row.get('OperationalAuthorities', '')
                electrical_safety_level = row.get('electrical_safety_level', '')
                roles = row.get('roles', '')
                groups = row.get('groups', '')
                parent_energy = row.get('parent_energy', '')
                parent_sysconfig = row.get('parent_sysconfig', '')
                
                # Логика получения GUID
                mark_not_found = False
                if mode == 'y':
                    if login:
                        ad_person_guid = get_user_guid(login)
                        if ad_person_guid:
                            person_guid = ad_person_guid
                        elif person_guid:
                            mark_not_found = True
                        else:
                            person_guid = str(uuid.uuid4())
                            mark_not_found = True
                    else:
                        person_guid = str(uuid.uuid4())
                else:
                    if not person_guid:
                        person_guid = str(uuid.uuid4())
                
                # Запись пользователей, не найденных в AD
                if mode == 'y' and mark_not_found:
                    not_found_in_ad.append({
                        'login': login,
                        'name': name,
                        'person_guid': person_guid
                    })
                
                # Форматирование ФИО
                fio_parts = name.split()
                last_name = fio_parts[0] if fio_parts else ""
                first_name = fio_parts[1] if len(fio_parts) > 1 else ""
                middle_name = fio_parts[2] if len(fio_parts) > 2 else ""
                
                # Генерация сокращенного имени
                abbreviation = last_name
                if first_name:
                    abbreviation += f" {first_name[0]}."
                if middle_name:
                    abbreviation += f"{middle_name[0]}."
                
                # Формирование XML-блоков для energy
                email_block = ""
                if email:
                    email_block = f"""
  <cim:Person.electronicAddress>
    <cim:ElectronicAddress>
      <cim:ElectronicAddress.email1>{email}</cim:ElectronicAddress.email1>
    </cim:ElectronicAddress>
  </cim:Person.electronicAddress>"""
                
                phone_block = ""
                if mobile_phone:
                    phone_block = f"""
  <cim:Person.mobilePhone>
    <cim:TelephoneNumber>
      <cim:TelephoneNumber.localNumber>{mobile_phone}</cim:TelephoneNumber.localNumber>
    </cim:TelephoneNumber>
  </cim:Person.mobilePhone>"""
                
                position_block = ""
                if position:
                    position_block = f"<me:Person.Position rdf:resource='#_{position}'/>"
                
                operational_blocks = ""
                if operational_authorities:
                    for uid in operational_authorities.split('!'):
                        uid = uid.strip()
                        if uid:
                            operational_blocks += f'    <me:Person.OperationalAuthorities rdf:resource="#_{uid}" />\n'
                
                electrical_safety_block = ""
                if electrical_safety_level:
                    electrical_safety_block = f'<me:Person.ElectricalSafetyLevel rdf:resource="#_{electrical_safety_level}"/>'
                
                name_abbreviation_guid = str(uuid.uuid4())
                cim_name_ref = f'<cim:IdentifiedObject.Names rdf:resource="#_{name_abbreviation_guid}" />'
                name_block = f"""
<cim:Name rdf:about="#_{name_abbreviation_guid}">
      <cim:Name.name>{abbreviation}</cim:Name.name>
      <cim:Name.IdentifiedObject rdf:resource="#_{person_guid}" />
      <cim:Name.NameType rdf:resource="#_00000002-0000-0000-c000-0000006d746c" />
  </cim:Name>"""
                
                # Формирование XML-блоков для sysconfig
                roles_blocks = ""
                if roles:
                    for role in roles.split('!'):
                        role = role.strip()
                        if role:
                            roles_blocks += f'<cim:Principal.Roles rdf:resource="#_{role}" />'
                
                groups_blocks = ""
                if groups:
                    for group in groups.split('!'):
                        group = group.strip()
                        if group:
                            groups_blocks += f'<cim:Principal.Groups rdf:resource="#_{group}" />'
                
                # Добавление в energy XML
                energy_xml += f"""
  <cim:Person rdf:about="#_{person_guid}">
      <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>
      {cim_name_ref}
      <me:IdentifiedObject.ParentObject rdf:resource="#_{parent_energy}" />
      {email_block}
      <cim:Person.firstName>{first_name}</cim:Person.firstName>
      <cim:Person.lastName>{last_name}</cim:Person.lastName>
      <cim:Person.mName>{middle_name}</cim:Person.mName>
      {phone_block}
      {position_block}
      {electrical_safety_block}
{operational_blocks}
  </cim:Person>
{name_block}
"""
                # Добавление в sysconfig XML
                sysconfig_xml += f"""
  <cim:User rdf:about="#_{person_guid}">
      <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>
      <cim:Principal.Domain rdf:resource="#_{ad_guid}" />
      <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
      <cim:User.login>{login}</cim:User.login>
      <cim:IdentifiedObject.ParentObject rdf:resource="#_{parent_sysconfig}" />
      {roles_blocks}
      {groups_blocks}
  </cim:User>
"""
                # Обновление строки для CSV
                updated_rows.append({
                    'person_guid': person_guid,
                    'name': name,
                    'login': login,
                    'email': email,
                    'mobilePhone': mobile_phone,
                    'position': position,
                    'OperationalAuthorities': operational_authorities,
                    'electrical_safety_level': electrical_safety_level,
                    'roles': roles,
                    'groups': groups,
                    'parent_energy': parent_energy,
                    'parent_sysconfig': parent_sysconfig
                })
            
            # Завершение XML-документов
            sysconfig_xml += "\n</rdf:RDF>"
            energy_xml += "\n</rdf:RDF>"
            
            # Запись XML-файлов
            base_name = os.path.splitext(csv_file)[0]
            with open(f"{base_name}.sysconfig.xml", 'w', encoding='utf-8') as f:
                f.write(sysconfig_xml)
            
            with open(f"{base_name}.energy.xml", 'w', encoding='utf-8') as f:
                f.write(energy_xml)
            
            # Обновление CSV
            with open(csv_file, 'w', newline='', encoding='windows-1251') as f:
                writer = csv.DictWriter(f, fieldnames=updated_rows[0].keys(), delimiter=delimiter)
                writer.writeheader()
                writer.writerows(updated_rows)
            
        except Exception as e:
            print(f"Ошибка при обработке файла {csv_file}: {str(e)}")
        finally:
            # Удаление временного файла
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    # Запись списка пользователей, не найденных в AD
    if mode == 'y' and not_found_in_ad:
        try:
            with open('not_in_AD.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['login', 'name', 'person_guid'], delimiter=';')
                writer.writeheader()
                writer.writerows(sorted(not_found_in_ad, key=lambda x: x['login']))
            print("\nСоздан файл not_in_AD.csv с пользователями, не найденными в AD")
        except Exception as e:
            print(f"Ошибка при создании файла not_in_AD.csv: {str(e)}")
    
    print("\nОбработка завершена. Все person_guid записаны в исходные CSV!")

if __name__ == "__main__":
    main()