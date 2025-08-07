# xml_generation.py
"""
Модуль для генерации XML-файлов.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Dict
import traceback
import logging

# Импортируем конфигурацию
from config_loader import CONFIG

# Разделяем версии для разных моделей
MODEL_VERSION_SYS = CONFIG['xml']['model_version_sysconfig']  # Например: "2025-03-04(11.7.1.7)"
MODEL_VERSION_ENERGY = CONFIG['xml']['model_version_energy']  # Например: "1.0"

def generate_sysconfig_xml(ad_guid: str, users: List[Dict]) -> str:
    """
    Генерирует XML-файл для SysConfig.
    
    Args:
        ad_guid (str): GUID домена Active Directory.
        users (List[Dict]): Список словарей с данными пользователей.
        
    Returns:
        str: Сгенерированный XML-документ в виде строки.
    """
    try:
        created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        # Используем фиксированный GUID для FullModel, как в примере
        full_model_guid = "a1aa400b-15b3-473a-b9c0-64d1c86d321f"
        xml = f'''<?xml version="1.0" encoding="utf-8"?>
<?iec61970-552 version="2.0"?>
<?floatExporter 1?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2021/schema-access#">
  <md:FullModel rdf:about="#_{full_model_guid}">
    <md:Model.created>{created}</md:Model.created>
    <md:Model.version>{MODEL_VERSION_SYS}</md:Model.version>
    <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">Access</me:Model.name>
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
                f'    <cim:Principal.Roles rdf:resource="#_{r.strip()}" />\n'
                for r in roles.split('!') if r.strip()
            )
            groups_blocks = ''.join(
                f'    <cim:Principal.Groups rdf:resource="#_{g.strip()}" />\n'
                for g in groups.split('!') if g.strip()
            )
            
            # Формируем блок Principal
            xml += f'''  <cim:Principal rdf:about="#_{person_guid}">
    <cim:IdentifiedObject.name>{name}</cim:IdentifiedObject.name>
    <cim:Principal.Domain rdf:resource="#_{ad_guid}" />
    <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
    <cim:Principal.login>{login}</cim:Principal.login>
'''
            if parent_sysconfig:
                xml += f'    <cim:IdentifiedObject.ParentObject rdf:resource="#_{parent_sysconfig}" />\n'
            
            if roles_blocks:
                xml += roles_blocks
            if groups_blocks:
                xml += groups_blocks
                
            xml += '  </cim:Principal>\n'
            
        xml += '</rdf:RDF>'
        return xml
    except Exception as e:
        logging.getLogger(__name__).error(f"Ошибка генерации SysConfig XML: {e}")
        logging.getLogger(__name__).debug(f"Детали ошибки: {traceback.format_exc()}")
        raise

def generate_energy_xml(users: List[Dict]) -> str:
    """
    Генерирует XML-файл для Energy.
    
    Args:
        users (List[Dict]): Список словарей с данными пользователей.
        
    Returns:
        str: Сгенерированный XML-документ в виде строки.
    """
    try:
        created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        xml = f'''<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_energy">
      <md:Model.created>{created}</md:Model.created>
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
                f'    <me:Person.OperationalAuthorities rdf:resource="#_{u.strip()}" />'
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
    except Exception as e:
        logging.getLogger(__name__).error(f"Ошибка генерации Energy XML: {e}")
        logging.getLogger(__name__).debug(f"Детали ошибки: {traceback.format_exc()}")
        raise