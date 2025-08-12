"""
Модуль для работы с Active Directory.
"""
import uuid
from typing import Optional
import ldap3
from ldap3 import Server, Connection, ALL
import traceback
import logging

# Импортируем конфигурацию
from .config_loader import CONFIG

DOMAIN_CONTROLLER = CONFIG['ad']['domain_controller']
DOMAIN_DN = CONFIG['ad']['domain_dn']
AD_USER = CONFIG['ad']['user']


def connect_to_ad(password: str) -> Optional[Connection]:
    """
    Подключается к Active Directory.

    Args:
        password (str): Пароль для подключения к AD.

    Returns:
        Optional[Connection]: Объект подключения к AD или None в случае ошибки.
    """
    server = Server(DOMAIN_CONTROLLER, get_info=ALL)
    try:
        conn = Connection(server, user=AD_USER,
                          password=password, auto_bind=True)
        return conn
    except Exception as e:
        logging.getLogger(__name__).error(f"Ошибка подключения к AD: {e}")
        logging.getLogger(__name__).debug(
            f"Детали ошибки: {traceback.format_exc()}")
        return None


def get_user_guid(conn: Connection, sAMAccountName: str) -> Optional[str]:
    """
    Получает GUID пользователя из Active Directory по логину.

    Args:
        conn (Connection): Подключение к Active Directory.
        sAMAccountName (str): Логин пользователя (sAMAccountName).

    Returns:
        Optional[str]: GUID пользователя или None, если пользователь не найден.
    """
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
        logging.getLogger(__name__).warning(
            f"Ошибка получения GUID для пользователя {sAMAccountName}: {e}")
        logging.getLogger(__name__).debug(
            f"Детали ошибки: {traceback.format_exc()}")
        pass
    return None


def get_domain_guid(conn: Connection) -> Optional[str]:
    """
    Получает GUID домена из Active Directory.

    Args:
        conn (Connection): Подключение к Active Directory.

    Returns:
        Optional[str]: GUID домена или None в случае ошибки.
    """
    try:
        conn.search(
            search_base=DOMAIN_DN,
            search_filter='(objectClass=domainDNS)',
            attributes=['objectGUID']
        )
        if conn.entries:
            guid_bytes = conn.entries[0].objectGUID.raw_values[0]
            return str(uuid.UUID(bytes_le=guid_bytes)).upper()
    except Exception as e:
        logging.getLogger(__name__).error(f"Ошибка получения GUID домена: {e}")
        logging.getLogger(__name__).debug(
            f"Детали ошибки: {traceback.format_exc()}")
        return None
