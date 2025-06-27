import os
import re
import csv
import uuid
import tempfile
from datetime import datetime
from typing import Callable, Optional

class CSVToXMLConverter:
    def __init__(self):
        pass

    def get_file_encoding(self, file_path: str) -> str:
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

    def get_user_guid(self, sam_account_name: str) -> Optional[str]:
        """Заглушка для получения GUID пользователя из AD"""
        # В реальной реализации используйте LDAP (например, модуль ldap3)
        return None

    def process(
        self, 
        mode: str, 
        ad_guid: str, 
        directory: str, 
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """Основной метод обработки файлов"""
        
        def log(message: str):
            if log_callback:
                log_callback(message)
            else:
                print(message)
        
        csv_files = [
            f for f in os.listdir(directory) 
            if f.endswith('.csv') #and f != 'Sample.csv'
        ]
        not_found_in_ad = []

        if not csv_files:
            log("Не найдено CSV файлов для обработки")
            return

        for csv_file in csv_files:
            try:
                file_path = os.path.join(directory, csv_file)
                log(f"\nОбработка файла: {csv_file}")
                
                encoding = self.get_file_encoding(file_path)
                log(f"Определена кодировка: {encoding}")
                
                with open(file_path, 'r', encoding=encoding) as f:
                    original_text = f.read()
                
                with tempfile.NamedTemporaryFile(
                    mode='w', encoding='windows-1251', delete=False
                ) as tmp:
                    tmp.write(original_text)
                    temp_path = tmp.name
                
                with open(temp_path, 'r', encoding='windows-1251') as f:
                    first_line = f.readline().strip()
                
                delimiter = ';' if ';' in first_line else ','
                log(f"Используется разделитель: {delimiter}")
                
                with open(temp_path, 'r', encoding='windows-1251') as f:
                    csv_reader = csv.DictReader(f, delimiter=delimiter)
                    csv_data = list(csv_reader)
                
                timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                sysconfig_xml = self._generate_sysconfig_header(timestamp)
                energy_xml = self._generate_energy_header(timestamp)
                
                updated_rows = []
                processed_count = 0
                
                for row in csv_data:
                    name_key = next((k for k in row.keys() if k.endswith("name")), None)
                    name = row.get(name_key, "")
                    if not name.strip():
                        continue
                    
                    processed_count += 1
                    result = self._process_row(
                        row, mode, ad_guid, not_found_in_ad
                    )
                    
                    if result:
                        person_data, person_xml = result
                        updated_rows.append(person_data)
                        energy_xml += person_xml['energy']
                        sysconfig_xml += person_xml['sysconfig']
                
                log(f"Обработано записей: {processed_count}")
                
                sysconfig_xml += "\n</rdf:RDF>"
                energy_xml += "\n</rdf:RDF>"
                
                base_name = os.path.splitext(file_path)[0]
                self._write_xml_file(f"{base_name}.sysconfig.xml", sysconfig_xml)
                self._write_xml_file(f"{base_name}.energy.xml", energy_xml)
                
                self._update_csv_file(
                    file_path, updated_rows, delimiter
                )
                
            except Exception as e:
                log(f"Ошибка при обработке файла {csv_file}: {str(e)}")
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        if mode == "ad" and not_found_in_ad:
            self._save_not_found_users(directory, not_found_in_ad)
            log(f"\nСоздан файл not_in_AD.csv с {len(not_found_in_ad)} записями")

    def _process_row(self, row, mode, ad_guid, not_found_in_ad):
        """Обработка одной строки CSV"""
        name_key = next((k for k in row.keys() if k.endswith("name")), None)
        name = row.get(name_key, "")
        if not name.strip():
            return None
        
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
        
        mark_not_found = False
        if mode == "ad":
            if login:
                ad_person_guid = self.get_user_guid(login)
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
        
        if mode == "ad" and mark_not_found:
            not_found_in_ad.append({
                'login': login,
                'name': name,
                'person_guid': person_guid
            })
        
        fio_parts = name.split()
        last_name = fio_parts[0] if fio_parts else ""
        first_name = fio_parts[1] if len(fio_parts) > 1 else ""
        middle_name = fio_parts[2] if len(fio_parts) > 2 else ""
        
        abbreviation = last_name
        if first_name:
            abbreviation += f" {first_name[0]}."
        if middle_name:
            abbreviation += f"{middle_name[0]}."
        
        # Generate XML blocks
        xml_blocks = self._generate_xml_blocks(
            person_guid=person_guid,
            name=name,
            abbreviation=abbreviation,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            email=email,
            mobile_phone=mobile_phone,
            position=position,
            operational_authorities=operational_authorities,
            electrical_safety_level=electrical_safety_level,
            roles=roles,
            groups=groups,
            parent_energy=parent_energy,
            parent_sysconfig=parent_sysconfig,
            ad_guid=ad_guid
        )
        
        # Prepare data for updated CSV
        person_data = {
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
        }
        
        return person_data, xml_blocks

    def _generate_xml_blocks(self, **kwargs):
        """Генерация XML блоков для одной персоны"""
        # Energy XML blocks
        email_block = ""
        if kwargs['email']:
            email_block = f"""
  <cim:Person.electronicAddress>
    <cim:ElectronicAddress>
      <cim:ElectronicAddress.email1>{kwargs['email']}</cim:ElectronicAddress.email1>
    </cim:ElectronicAddress>
  </cim:Person.electronicAddress>"""
        
        phone_block = ""
        if kwargs['mobile_phone']:
            phone_block = f"""
  <cim:Person.mobilePhone>
    <cim:TelephoneNumber>
      <cim:TelephoneNumber.localNumber>{kwargs['mobile_phone']}</cim:TelephoneNumber.localNumber>
    </cim:TelephoneNumber>
  </cim:Person.mobilePhone>"""
        
        position_block = ""
        if kwargs['position']:
            position_block = f"<me:Person.Position rdf:resource='#_{kwargs['position']}'/>"
        
        operational_blocks = ""
        if kwargs['operational_authorities']:
            for uid in kwargs['operational_authorities'].split('!'):
                uid = uid.strip()
                if uid:
                    operational_blocks += f'    <me:Person.OperationalAuthorities rdf:resource="#_{uid}" />\n'
        
        electrical_safety_block = ""
        if kwargs['electrical_safety_level']:
            electrical_safety_block = f'<me:Person.ElectricalSafetyLevel rdf:resource="#_{kwargs['electrical_safety_level']}"/>'
        
        name_abbreviation_guid = str(uuid.uuid4())
        cim_name_ref = f'<cim:IdentifiedObject.Names rdf:resource="#_{name_abbreviation_guid}" />'
        name_block = f"""
<cim:Name rdf:about="#_{name_abbreviation_guid}">
      <cim:Name.name>{kwargs['abbreviation']}</cim:Name.name>
      <cim:Name.IdentifiedObject rdf:resource="#_{kwargs['person_guid']}" />
      <cim:Name.NameType rdf:resource="#_00000002-0000-0000-c000-0000006d746c" />
  </cim:Name>"""
        
        # Sysconfig XML blocks
        roles_blocks = ""
        if kwargs['roles']:
            for role in kwargs['roles'].split('!'):
                role = role.strip()
                if role:
                    roles_blocks += f'<cim:Principal.Roles rdf:resource="#_{role}" />'
        
        groups_blocks = ""
        if kwargs['groups']:
            for group in kwargs['groups'].split('!'):
                group = group.strip()
                if group:
                    groups_blocks += f'<cim:Principal.Groups rdf:resource="#_{group}" />'
        
        # Complete XML for person
        energy_xml = f"""
  <cim:Person rdf:about="#_{kwargs['person_guid']}">
      <cim:IdentifiedObject.name>{kwargs['name']}</cim:IdentifiedObject.name>
      {cim_name_ref}
      <me:IdentifiedObject.ParentObject rdf:resource="#_{kwargs['parent_energy']}" />
      {email_block}
      <cim:Person.firstName>{kwargs['first_name']}</cim:Person.firstName>
      <cim:Person.lastName>{kwargs['last_name']}</cim:Person.lastName>
      <cim:Person.mName>{kwargs['middle_name']}</cim:Person.mName>
      {phone_block}
      {position_block}
      {electrical_safety_block}
{operational_blocks}
  </cim:Person>
{name_block}
"""
        sysconfig_xml = f"""
  <cim:User rdf:about="#_{kwargs['person_guid']}">
      <cim:IdentifiedObject.name>{kwargs['name']}</cim:IdentifiedObject.name>
      <cim:Principal.Domain rdf:resource="#_{kwargs['ad_guid']}" />
      <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
      <cim:User.login>{kwargs['login']}</cim:User.login>
      <cim:IdentifiedObject.ParentObject rdf:resource="#_{kwargs['parent_sysconfig']}" />
      {roles_blocks}
      {groups_blocks}
  </cim:User>
"""
        return {
            'energy': energy_xml,
            'sysconfig': sysconfig_xml
        }

    def _generate_sysconfig_header(self, timestamp):
        return f"""<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_sysconfig">
      <md:Model.created>{timestamp}</md:Model.created>
      <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
      <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
  </md:FullModel>
"""

    def _generate_energy_header(self, timestamp):
        return f"""<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_energy">
      <md:Model.created>{timestamp}</md:Model.created>
      <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
      <me:Model.name>CIM16</me:Model.name>
  </md:FullModel>
"""

    def _write_xml_file(self, file_path, content):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _update_csv_file(self, file_path, rows, delimiter):
        with open(file_path, 'w', newline='', encoding='windows-1251') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)

    def _save_not_found_users(self, directory, not_found_users):
        output_path = os.path.join(directory, 'not_in_AD.csv')
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f, fieldnames=['login', 'name', 'person_guid'], 
                delimiter=';'
            )
            writer.writeheader()
            writer.writerows(sorted(
                not_found_users, 
                key=lambda x: x['login']
            ))