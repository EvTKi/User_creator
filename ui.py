# ui.py (обновленная версия с современным дизайном)
"""
GUI для приложения User Creator на основе PyQt5 с современным дизайном.
"""
import sys
import os
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QRadioButton, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QProgressBar, QGroupBox, QMessageBox, QCheckBox, QScrollArea, QFrame,
    QSizePolicy, QStackedWidget, QToolBar, QAction, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QSize
from PyQt5.QtGui import QTextCursor, QFont, QIcon, QPixmap, QPalette, QColor
import logging
import traceback

# Импорты модулей приложения (остаются без изменений)
try:
    from modules.config_loader import CONFIG
    from modules.ad_operations import connect_to_ad, get_domain_guid
    from modules.csv_processing import find_csv_files, process_user_row
    from modules.xml_generation import generate_access_xml, generate_energy_xml
    from modules.logging_config import LogManager
    from modules.csv_processing import get_file_encoding, read_csv_file, write_csv_file
    from modules.ad_operations import get_user_guid
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    QMessageBox.critical(
        None, "Ошибка", f"Не удалось импортировать необходимые модули: {e}")
    sys.exit(1)

# Константы из конфигурации (остаются без изменений)
ACCESS_SUFFIX = CONFIG['output']['access_xml_suffix']
ENERGY_SUFFIX = CONFIG['output']['energy_xml_suffix']
NOT_IN_AD_CSV = CONFIG['output']['not_in_ad_csv']
AD_ENABLED = CONFIG['ad']['enabled']

# Настройка логгера для UI (обновленная)
ui_logger = logging.getLogger("UserCreatorUI")
ui_logger.setLevel(logging.DEBUG)


class Worker(QThread):
    """Поток для выполнения основной логики обработки."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, mode, ad_password, manual_guid, input_dir):
        super().__init__()
        self.mode = mode
        self.ad_password = ad_password
        self.manual_guid = manual_guid
        self.input_dir = input_dir
        self.logger = logging.getLogger("UserCreatorUI.Worker")

    def run(self):
        """Выполняет обработку в отдельном потоке."""
        try:
            self.logger.info("Начало выполнения рабочего потока")
            self.log_signal.emit("🚀 Начало выполнения рабочего потока")

            # Меняем директорию
            original_dir = os.getcwd()
            self.logger.debug(f"Исходная директория: {original_dir}")
            if self.input_dir and os.path.exists(self.input_dir):
                os.chdir(self.input_dir)
                self.logger.info(
                    f"Рабочая директория изменена на: {os.getcwd()}")
            else:
                self.logger.warning(
                    f"Указанная директория не существует: {self.input_dir}. Используется текущая.")
            self.log_signal.emit(f"📂 Рабочая директория: {os.getcwd()}")

            # Инициализация AD (если нужно)
            ad_conn = None
            ad_guid = None
            not_found_in_ad = []

            if self.mode == 'y' and AD_ENABLED:
                self.logger.info("Выбран режим работы с Active Directory")
                if not self.ad_password:
                    error_msg = "❌ Не введен пароль AD!"
                    self.logger.error(error_msg)
                    self.log_signal.emit(error_msg)
                    return
                self.log_signal.emit("🔐 Подключение к Active Directory...")
                self.logger.info(
                    f"Попытка подключения к AD: сервер={CONFIG['ad']['domain_controller']}, пользователь={CONFIG['ad']['user']}")
                ad_conn = connect_to_ad(self.ad_password)
                if not ad_conn:
                    error_msg = "❌ Не удалось подключиться к AD."
                    self.logger.error(error_msg)
                    self.log_signal.emit(error_msg)
                    return
                self.logger.info("✅ Успешное подключение к Active Directory")
                self.log_signal.emit("✅ Подключено к AD")
                self.log_signal.emit("📡 Получение GUID домена...")
                self.logger.info("Получение GUID домена...")
                ad_guid = get_domain_guid(ad_conn)
                if not ad_guid:
                    error_msg = "❌ Не удалось получить GUID домена."
                    self.logger.error(error_msg)
                    self.log_signal.emit(error_msg)
                    return
                self.logger.info(f"✅ GUID домена успешно получен: {ad_guid}")
                self.log_signal.emit(f"✅ GUID домена: {ad_guid}")
            else:
                self.logger.info(
                    "Выбран режим работы без Active Directory (ручной ввод GUID)")
                if not self.manual_guid:
                    error_msg = "❌ Не введен GUID домена!"
                    self.logger.error(error_msg)
                    self.log_signal.emit(error_msg)
                    return
                ad_guid = self.manual_guid.strip()
                self.logger.info(
                    f"Используется введенный GUID домена: {ad_guid}")
                self.log_signal.emit(f"✅ Используется GUID: {ad_guid}")

            self.progress_signal.emit(20)
            self.log_signal.emit("🔍 Поиск CSV файлов...")
            self.logger.info("Начало поиска CSV файлов")
            csv_files = find_csv_files()
            if not csv_files:
                warning_msg = "⚠️ Нет подходящих CSV-файлов для обработки."
                self.logger.warning(warning_msg)
                self.log_signal.emit(warning_msg)
                return
            self.logger.info(f"Найдено файлов для обработки: {len(csv_files)}")
            self.log_signal.emit(
                f"📄 Найдено файлов для обработки: {len(csv_files)}")

            for i, csv_file in enumerate(csv_files):
                self.logger.info(f"Обнаружен файл для обработки: {csv_file}")

            self.progress_signal.emit(30)
            total_files = len(csv_files)

            # Обработка файлов
            for i, csv_file in enumerate(csv_files):
                self.logger.info(
                    f"Начало обработки файла {i+1}/{total_files}: {csv_file}")
                self.log_signal.emit(
                    f"📄 Обработка файла ({i+1}/{total_files}): {csv_file}")

                try:
                    file_path = os.path.join('.', csv_file)
                    base_name = os.path.splitext(csv_file)[0]
                    self.logger.debug(f"Полный путь к файлу: {file_path}")

                    # Создаём LogManager и получаем логгер
                    log_manager = LogManager(csv_file)
                    logger = log_manager.get_logger()
                    logger.info(f"🚀 Начата обработка файла: {csv_file}")

                    if self.mode == 'y' and AD_ENABLED:
                        logger.info(
                            f"✅ Используется GUID домена из AD: {ad_guid}")
                    else:
                        logger.info(
                            f"✅ Используется вручную введённый GUID домена: {ad_guid}")

                    # Определение кодировки и чтение CSV
                    self.logger.debug(
                        f"Определение кодировки файла: {file_path}")
                    encoding = get_file_encoding(file_path)
                    logger.info(f"Определена кодировка: {encoding}")
                    self.logger.info(f"Кодировка файла {csv_file}: {encoding}")
                    self.logger.debug(f"Чтение CSV файла: {file_path}")
                    rows = read_csv_file(file_path, encoding)
                    logger.info(f"Прочитано строк: {len(rows)}")
                    self.logger.info(
                        f"Прочитано {len(rows)} строк из файла {csv_file}")

                    updated_rows = []
                    users_data = []
                    self.logger.debug(
                        f"Начало обработки строк из файла {csv_file}")

                    for row_idx, row in enumerate(rows):
                        name = (row.get('name') or '').strip()
                        if not name:
                            logger.debug(
                                f"Строка {row_idx + 1}: пропущена (пустое имя)")
                            continue
                        # Передаем все необходимые аргументы
                        processed_row = process_user_row(
                            row,           # row
                            row_idx,       # row_index
                            csv_file,      # csv_file
                            self.mode,     # mode
                            ad_conn,       # ad_conn
                            ad_guid,       # ad_guid
                            not_found_in_ad,  # not_found_in_ad
                            logger         # logger
                        )
                        if processed_row:
                            updated_rows.append(processed_row)
                            users_data.append(processed_row)

                    self.logger.info(
                        f"Обработано {len(users_data)} записей из файла {csv_file}")
                    self.log_signal.emit(
                        f"  ✅ Обработано записей: {len(users_data)}")

                    # Генерация XML
                    self.logger.info(
                        f"Начало генерации XML файлов для {csv_file}")
                    self.log_signal.emit(f"  📄 Генерация XML файлов...")
                    sys_xml = generate_access_xml(ad_guid, users_data)
                    energy_xml = generate_energy_xml(users_data)
                    sys_xml_filename = f"{base_name}{ACCESS_SUFFIX}"
                    energy_xml_filename = f"{base_name}{ENERGY_SUFFIX}"
                    self.logger.debug(f"Запись Access XML: {sys_xml_filename}")
                    with open(sys_xml_filename, 'w', encoding='utf-8') as f:
                        f.write(sys_xml)
                    self.logger.debug(
                        f"Запись Energy XML: {energy_xml_filename}")
                    with open(energy_xml_filename, 'w', encoding='utf-8') as f:
                        f.write(energy_xml)
                    logger.info(f"✅ Успешно сгенерированы XML-файлы: "
                                f"{sys_xml_filename}, {energy_xml_filename}")
                    self.logger.info(
                        f"XML файлы успешно созданы: {sys_xml_filename}, {energy_xml_filename}")
                    self.log_signal.emit(
                        f"  ✅ XML файлы созданы: {ACCESS_SUFFIX}, {ENERGY_SUFFIX}")

                    # Перезапись CSV
                    self.logger.debug(f"Перезапись CSV файла: {file_path}")
                    write_csv_file(file_path, updated_rows)
                    logger.info(f"✅ CSV файл обновлён и сохранён: {csv_file}")
                    self.logger.info(f"CSV файл успешно обновлён: {csv_file}")
                    self.log_signal.emit(f"  ✅ CSV файл обновлён")
                    logger.info(f"✅ Обработка файла '{csv_file}' завершена.")
                    self.logger.info(
                        f"Обработка файла {csv_file} завершена успешно")

                except Exception as e:
                    error_msg = f"❌ Ошибка обработки файла {csv_file}: {str(e)}"
                    self.logger.error(error_msg)
                    self.logger.debug(
                        f"Детали ошибки: {traceback.format_exc()}")
                    self.log_signal.emit(error_msg)
                    continue

                # Обновляем прогресс
                progress = 30 + int((i + 1) / total_files * 60)
                self.progress_signal.emit(progress)
                self.logger.debug(f"Прогресс обработки: {progress}%")

            # --- Сохранение not_in_AD.csv ---
            if self.mode == 'y' and AD_ENABLED and not_found_in_ad:
                self.logger.info(
                    f"Сохранение списка пользователей не найденных в AD: {len(not_found_in_ad)} записей")
                self.log_signal.emit(
                    f"💾 Сохранение списка пользователей не найденных в AD ({len(not_found_in_ad)} записей)...")
                try:
                    not_found_in_ad.sort(key=lambda x: x['login'])
                    with open(NOT_IN_AD_CSV, 'w', newline='', encoding='utf-8') as f:
                        import csv
                        writer = csv.DictWriter(
                            f, fieldnames=['login', 'name', 'person_guid'], delimiter=';')
                        writer.writeheader()
                        writer.writerows(not_found_in_ad)
                    if csv_files:
                        last_logger = logger  # Используем последний логгер
                        last_logger.warning(
                            f"🟡 Логины не из AD сохранены в: {NOT_IN_AD_CSV}")
                    self.log_signal.emit(
                        f"✅ Логины не из AD сохранены в: {NOT_IN_AD_CSV}")
                    self.logger.info(
                        f"Список пользователей не найденных в AD успешно сохранен в: {NOT_IN_AD_CSV}")
                except Exception as e:
                    if csv_files:
                        last_logger = logger
                        last_logger.error(
                            f"❌ Ошибка записи {NOT_IN_AD_CSV}: {e}")
                    error_msg = f"❌ Ошибка записи {NOT_IN_AD_CSV}: {e}"
                    self.logger.error(error_msg)
                    self.logger.debug(
                        f"Детали ошибки: {traceback.format_exc()}")
                    self.log_signal.emit(error_msg)

            success_msg = "✅ Обработка всех файлов завершена!"
            self.logger.info(success_msg)
            self.log_signal.emit(success_msg)
            self.progress_signal.emit(100)
            self.finished_signal.emit()

            # Возвращаемся в исходную директорию
            os.chdir(original_dir)
            self.logger.info(
                f"Возвращение в исходную директорию: {original_dir}")

        except Exception as e:
            error_msg = f"❌ Критическая ошибка в рабочем потоке: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug(f"Детали ошибки: {traceback.format_exc()}")
            self.error_signal.emit(error_msg)
            self.finished_signal.emit()


class UserCreatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("UserCreatorUI.MainWindow")
        self.logger.info("Инициализация главного окна приложения")
        self.settings = QSettings('UserCreator', 'GUI')
        self.worker = None
        self.init_ui()
        self.load_settings()
        self.logger.info("Главное окно приложения инициализировано")

    def init_ui(self):
        """Инициализирует пользовательский интерфейс с современным дизайном."""
        self.logger.debug("Начало инициализации UI")
        self.setWindowTitle("User Creator")
        self.setGeometry(100, 100, 1000, 750)
        self.logger.debug("Установлены параметры окна")

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.logger.debug("Создан центральный виджет")

        # --- Заголовок ---
        header_layout = QHBoxLayout()
        title_label = QLabel("User Creator")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # --- Панель настроек ---
        settings_group = QGroupBox("Настройки обработки")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #34495e;
            }
        """)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(10)
        self.logger.debug("Создана панель настроек")

        # Режим работы
        mode_label = QLabel("Режим обработки:")
        mode_label.setStyleSheet("font-weight: normal; color: #34495e;")
        mode_layout = QHBoxLayout()
        self.radio_ad = QRadioButton("Использовать AD")
        self.radio_manual = QRadioButton("Без AD (вручную)")
        self.radio_manual.setChecked(True)

        # Активируем/деактивируем радиокнопки в зависимости от конфигурации
        if not AD_ENABLED:
            self.radio_ad.setEnabled(False)
            self.radio_ad.setToolTip("AD отключен в config.json")
            self.logger.warning("Режим AD отключен в конфигурации")

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.radio_ad)
        mode_layout.addWidget(self.radio_manual)
        mode_layout.addStretch()
        settings_layout.addLayout(mode_layout)
        self.logger.debug("Настроены радиокнопки режима работы")

        # Поля для AD
        self.ad_widget = QFrame()
        self.ad_widget.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.ad_widget.setFrameStyle(QFrame.StyledPanel)
        ad_layout = QFormLayout(self.ad_widget)
        ad_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ad_layout.setHorizontalSpacing(15)
        ad_layout.setVerticalSpacing(10)

        self.ad_password_edit = QLineEdit()
        self.ad_password_edit.setEchoMode(QLineEdit.Password)
        self.ad_password_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #3498db;
                outline: none;
            }
        """)
        ad_layout.addRow(QLabel("Пароль AD:"), self.ad_password_edit)
        settings_layout.addWidget(self.ad_widget)
        self.logger.debug("Созданы поля для ввода данных AD")

        # Поле для ручного GUID
        self.manual_guid_widget = QFrame()
        self.manual_guid_widget.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.manual_guid_widget.setFrameStyle(QFrame.StyledPanel)
        manual_guid_layout = QFormLayout(self.manual_guid_widget)
        manual_guid_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        manual_guid_layout.setHorizontalSpacing(15)
        manual_guid_layout.setVerticalSpacing(10)

        self.manual_guid_edit = QLineEdit()
        self.manual_guid_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #3498db;
                outline: none;
            }
        """)
        manual_guid_layout.addRow(
            QLabel("GUID домена:"), self.manual_guid_edit)
        settings_layout.addWidget(self.manual_guid_widget)
        self.logger.debug("Созданы поля для ручного ввода GUID")

        # Директории
        dirs_frame = QFrame()
        dirs_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        dirs_layout = QFormLayout(dirs_frame)
        dirs_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        dirs_layout.setHorizontalSpacing(15)
        dirs_layout.setVerticalSpacing(10)

        dir_input_layout = QHBoxLayout()
        self.input_dir_edit = QLineEdit(".")
        self.input_dir_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #ffffff;
            }
        """)
        self.browse_input_button = QPushButton("Обзор...")
        self.browse_input_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.browse_input_button.clicked.connect(self.browse_input_directory)
        dir_input_layout.addWidget(self.input_dir_edit)
        dir_input_layout.addWidget(self.browse_input_button)
        dirs_layout.addRow(QLabel("Директория с CSV:"), dir_input_layout)
        settings_layout.addWidget(dirs_frame)
        self.logger.debug("Настроены поля выбора директории")

        main_layout.addWidget(settings_group)

        # --- Кнопка запуска ---
        self.run_button = QPushButton("▶ Запустить обработку")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                margin: 10px 0;
            }
            QPushButton:hover {
                background-color: #219653;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.run_button.clicked.connect(self.run_processing)
        main_layout.addWidget(self.run_button)
        self.logger.debug("Создана кнопка запуска обработки")

        # --- Прогресс и логи ---
        progress_group = QGroupBox("Прогресс и логи")
        progress_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #34495e;
            }
        """)
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(10)

        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        self.logger.debug("Создан индикатор прогресса")

        # Область логов с прокруткой
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #7f8c8d;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                padding: 10px;
            }
        """)

        log_layout.addWidget(self.log_text)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(log_container)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #ecf0f1;
                width: 15px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background: #bdc3c7;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical:hover {
                background: #95a5a6;
            }
        """)
        scroll_area.setMinimumHeight(300)
        progress_layout.addWidget(scroll_area)
        main_layout.addWidget(progress_group)
        self.logger.debug("Создана область отображения логов")

        # --- Статус бар ---
        self.statusBar().showMessage("Готов к обработке")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #ecf0f1;
                border-top: 1px solid #bdc3c7;
            }
            QLabel {
                color: #34495e;
            }
        """)
        self.logger.debug("Инициализирован статус бар")

        # Подключаем сигналы для изменения режима
        self.radio_ad.toggled.connect(self.on_mode_change)
        self.radio_manual.toggled.connect(self.on_mode_change)
        self.on_mode_change()

        # Применяем глобальные стили
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QWidget {
                color: #34495e;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11pt;
            }
            QLabel {
                color: #34495e;
            }
            QRadioButton {
                spacing: 5px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                image: url(none);
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                image: url(none);
                border: 2px solid #3498db;
                border-radius: 8px;
                background-color: #3498db;
            }
            QGroupBox {
                font-weight: bold;
            }
        """)

        self.logger.info("Интерфейс полностью инициализирован")

    def on_mode_change(self):
        """Обработчик изменения режима работы."""
        self.logger.debug("Изменение режима работы")
        if self.radio_ad.isChecked():
            self.ad_widget.setVisible(True)
            self.manual_guid_widget.setVisible(False)
            self.logger.info("Выбран режим работы с AD")
        else:
            self.ad_widget.setVisible(False)
            self.manual_guid_widget.setVisible(True)
            self.logger.info("Выбран режим работы без AD (ручной)")

    def browse_input_directory(self):
        """Открывает диалог выбора директории."""
        self.logger.debug("Открытие диалога выбора директории")
        dir_path = QFileDialog.getExistingDirectory(
            self, "Выберите директорию с CSV")
        if dir_path:
            self.input_dir_edit.setText(dir_path)
            self.logger.info(f"Выбрана директория: {dir_path}")

    def log_message(self, message: str):
        """Добавляет сообщение в лог."""
        self.logger.debug(f"Добавление сообщения в UI лог: {message}")
        self.log_text.append(message)
        # Прокручиваем вниз
        self.log_text.moveCursor(QTextCursor.End)

    def run_processing(self):
        """Запускает обработку."""
        self.logger.info("Начало запуска процесса обработки")
        # Сохраняем настройки
        self.save_settings()
        self.logger.debug("Настройки сохранены")

        mode = 'y' if self.radio_ad.isChecked() else 'n'
        ad_password = self.ad_password_edit.text()
        manual_guid = self.manual_guid_edit.text()
        input_dir = self.input_dir_edit.text()
        self.logger.info(
            f"Параметры запуска: режим={mode}, директория={input_dir}")

        # Валидация
        if mode == 'y' and AD_ENABLED and not ad_password:
            self.logger.warning("Попытка запуска без введенного пароля AD")
            QMessageBox.warning(
                self, "Внимание", "Пожалуйста, введите пароль AD.")
            return
        if mode == 'n' or not AD_ENABLED:
            if not manual_guid:
                self.logger.warning("Попытка запуска без введенного GUID")
                QMessageBox.warning(
                    self, "Внимание", "Пожалуйста, введите GUID домена.")
                return
        if not input_dir or not os.path.exists(input_dir):
            self.logger.warning(
                f"Указана несуществующая директория: {input_dir}")
            QMessageBox.warning(
                self, "Внимание", "Пожалуйста, выберите существующую директорию с CSV файлами.")
            return

        self.run_button.setEnabled(False)
        self.statusBar().showMessage("Обработка запущена...")
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.logger.info("Все проверки пройдены, запуск рабочего потока")

        # Создаем и запускаем поток обработки
        self.worker = Worker(mode, ad_password, manual_guid, input_dir)
        self.worker.log_signal.connect(self.log_message)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_processing_finished)
        self.worker.error_signal.connect(self.on_processing_error)
        self.worker.start()
        self.logger.info("Рабочий поток запущен")

    def on_processing_finished(self):
        """Обработчик завершения обработки."""
        self.logger.info("Обработка завершена успешно")
        self.run_button.setEnabled(True)
        self.statusBar().showMessage("Обработка завершена")
        self.log_message("=== Обработка завершена ===")

    def on_processing_error(self, error_message: str):
        """Обработчик ошибок во время обработки."""
        self.logger.error(f"Ошибка во время обработки: {error_message}")
        self.run_button.setEnabled(True)
        self.statusBar().showMessage("Ошибка во время обработки")
        QMessageBox.critical(self, "Ошибка", error_message)

    def save_settings(self):
        """Сохраняет настройки в реестр."""
        self.logger.debug("Сохранение настроек")
        self.settings.setValue(
            "mode", 'y' if self.radio_ad.isChecked() else 'n')
        self.settings.setValue("input_dir", self.input_dir_edit.text())
        self.logger.info("Настройки успешно сохранены")

    def load_settings(self):
        """Загружает настройки из реестра."""
        self.logger.debug("Загрузка настроек")
        mode = self.settings.value("mode", 'n')
        if mode == 'y' and AD_ENABLED:
            self.radio_ad.setChecked(True)
        else:
            self.radio_manual.setChecked(True)
        input_dir = self.settings.value("input_dir", ".")
        self.input_dir_edit.setText(input_dir)
        self.logger.info(
            f"Настройки загружены: режим={mode}, директория={input_dir}")

    def closeEvent(self, event):
        """Обработчик закрытия приложения."""
        self.logger.info("Получен запрос на закрытие приложения")
        if self.worker and self.worker.isRunning():
            self.logger.warning(
                "Попытка закрытия приложения во время выполнения задачи")
            reply = QMessageBox.question(
                self, "Подтверждение выхода",
                "Идет обработка. Вы уверены, что хотите выйти?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.logger.info("Пользователь подтвердил закрытие приложения")
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                self.logger.info("Пользователь отменил закрытие приложения")
                event.ignore()
        else:
            self.logger.info("Приложение закрывается")
            event.accept()


def main():
    # Настройка логгера для основного приложения с датой
    import datetime
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    ui_log_filename = f"log\\user_creator_ui_{today}.log"

    ui_logger = logging.getLogger("UserCreatorUI")
    ui_logger.setLevel(logging.DEBUG)

    # Создаем обработчик для файла с датой
    ui_file_handler = logging.FileHandler(ui_log_filename, encoding='utf-8')
    ui_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s')
    ui_file_handler.setFormatter(ui_formatter)
    ui_file_handler.setLevel(logging.DEBUG)

    # Добавляем обработчик к логгеру "UserCreatorUI"
    ui_logger.addHandler(ui_file_handler)

    # Также добавим вывод в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ui_formatter)
    console_handler.setLevel(logging.INFO)
    ui_logger.addHandler(console_handler)

    main_logger = logging.getLogger("UserCreatorUI")
    main_logger.info("Запуск приложения User Creator GUI")

    app = QApplication(sys.argv)
    # Установка стиля
    app.setStyle("Fusion")

    # Установка палитры цветов для Fusion стиля
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(245, 246, 250))
    palette.setColor(QPalette.WindowText, QColor(52, 73, 94))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(240, 240, 240))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(52, 73, 94))
    palette.setColor(QPalette.Button, QColor(236, 240, 241))
    palette.setColor(QPalette.ButtonText, QColor(52, 73, 94))
    palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
    palette.setColor(QPalette.Link, QColor(52, 152, 219))
    palette.setColor(QPalette.Highlight, QColor(52, 152, 219))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))

    app.setPalette(palette)

    window = UserCreatorWindow()
    window.show()
    main_logger.info("Главное окно отображено")

    exit_code = app.exec_()
    main_logger.info("Приложение завершено")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
