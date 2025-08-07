# ui.py
"""
GUI для приложения User Creator на основе PyQt5.
"""
import sys
import os
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QRadioButton, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QProgressBar, QGroupBox, QMessageBox, QCheckBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtGui import QTextCursor, QFont

# Импортируем логику приложения
try:
    # Импортируем конфигурацию
    from config_loader import CONFIG
    # Импортируем AD операции
    from ad_operations import connect_to_ad, get_domain_guid
    # Импортируем обработку CSV
    from csv_processing import find_csv_files, process_user_row
    # Импортируем генерацию XML
    from xml_generation import generate_sysconfig_xml, generate_energy_xml
    # Импортируем логирование
    from logging_config import LogManager
    # Импортируем вспомогательные функции
    from csv_processing import get_file_encoding, read_csv_file, write_csv_file
    # Импортируем AD функции
    from ad_operations import get_user_guid
    
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    QMessageBox.critical(None, "Ошибка", f"Не удалось импортировать необходимые модули: {e}")
    sys.exit(1)

# Импортируем основные константы из config
SYSCONFIG_SUFFIX = CONFIG['output']['sysconfig_xml_suffix']
ENERGY_SUFFIX = CONFIG['output']['energy_xml_suffix']
NOT_IN_AD_CSV = CONFIG['output']['not_in_ad_csv']
AD_ENABLED = CONFIG['ad']['enabled']


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
        
    def run(self):
        """Выполняет обработку в отдельном потоке."""
        try:
            # Меняем директорию
            original_dir = os.getcwd()
            if self.input_dir and os.path.exists(self.input_dir):
                os.chdir(self.input_dir)
                
            self.log_signal.emit(f"Начало обработки в директории: {os.getcwd()}")
            
            # Инициализация AD (если нужно)
            ad_conn = None
            ad_guid = None
            not_found_in_ad = []
            
            if self.mode == 'y' and AD_ENABLED:
                if not self.ad_password:
                    self.log_signal.emit("❌ Не введен пароль AD!")
                    return
                self.log_signal.emit("Подключение к Active Directory...")
                ad_conn = connect_to_ad(self.ad_password)
                if not ad_conn:
                    self.log_signal.emit("❌ Не удалось подключиться к AD.")
                    return
                self.log_signal.emit("✅ Подключено к AD")
                
                self.log_signal.emit("Получение GUID домена...")
                ad_guid = get_domain_guid(ad_conn)
                if not ad_guid:
                    self.log_signal.emit("❌ Не удалось получить GUID домена.")
                    return
                self.log_signal.emit(f"✅ GUID домена: {ad_guid}")
            else:
                if not self.manual_guid:
                    self.log_signal.emit("❌ Не введен GUID домена!")
                    return
                ad_guid = self.manual_guid.strip()
                self.log_signal.emit(f"✅ Используется GUID: {ad_guid}")
                
            self.progress_signal.emit(20)
            self.log_signal.emit("Поиск CSV файлов...")
            
            csv_files = find_csv_files()
            if not csv_files:
                self.log_signal.emit("⚠️ Нет подходящих CSV-файлов для обработки.")
                return
                
            self.log_signal.emit(f"Найдено файлов для обработки: {len(csv_files)}")
            
            self.progress_signal.emit(30)
            total_files = len(csv_files)
            
            # Обработка файлов
            for i, csv_file in enumerate(csv_files):
                self.log_signal.emit(f"Обработка файла: {csv_file}")
                
                try:
                    file_path = os.path.join('.', csv_file)
                    base_name = os.path.splitext(csv_file)[0]
                    
                    # Создаём LogManager и получаем логгер
                    log_manager = LogManager(csv_file)
                    logger = log_manager.get_logger()
                    logger.info(f"🚀 Начата обработка файла: {csv_file}")
                    
                    if self.mode == 'y' and AD_ENABLED:
                        logger.info(f"✅ Используется GUID домена из AD: {ad_guid}")
                    else:
                        logger.info(f"✅ Используется вручную введённый GUID домена: {ad_guid}")
                    
                    # Определение кодировки и чтение CSV
                    encoding = get_file_encoding(file_path)
                    logger.info(f"Определена кодировка: {encoding}")
                    rows = read_csv_file(file_path, encoding)
                    logger.info(f"Прочитано строк: {len(rows)}")
                    
                    updated_rows = []
                    users_data = []
                    
                                        # ...
                    for row_idx, row in enumerate(rows):
                        name = (row.get('name') or '').strip()
                        if not name:
                            logger.debug(f"Строка {row_idx + 1}: пропущена (пустое имя)")
                            continue
                            
                        # Передаем все необходимые аргументы
                        processed_row = process_user_row(
                            row,           # row
                            row_idx,       # row_index
                            csv_file,      # csv_file
                            self.mode,     # mode
                            ad_conn,       # ad_conn
                            ad_guid,       # ad_guid
                            not_found_in_ad, # not_found_in_ad
                            logger         # logger
                        )
                        # ...
                        
                        
                            
                            
                            
                        
                        if processed_row:
                            updated_rows.append(processed_row)
                            users_data.append(processed_row)
                    
                    # Генерация XML
                    sys_xml = generate_sysconfig_xml(ad_guid, users_data)
                    energy_xml = generate_energy_xml(users_data)
                    with open(f"{base_name}{SYSCONFIG_SUFFIX}", 'w', encoding='utf-8') as f:
                        f.write(sys_xml)
                    with open(f"{base_name}{ENERGY_SUFFIX}", 'w', encoding='utf-8') as f:
                        f.write(energy_xml)
                    logger.info(f"✅ Успешно сгенерированы XML-файлы: "
                               f"{base_name}{SYSCONFIG_SUFFIX}, {base_name}{ENERGY_SUFFIX}")
                    
                    # Перезапись CSV
                    write_csv_file(file_path, updated_rows)
                    logger.info(f"✅ CSV файл обновлён и сохранён: {csv_file}")
                    
                    logger.info(f"✅ Обработка файла '{csv_file}' завершена.")
                    
                except Exception as e:
                    self.log_signal.emit(f"❌ Ошибка обработки файла {csv_file}: {str(e)}")
                    continue
                    
                # Обновляем прогресс
                progress = 30 + int((i + 1) / total_files * 60)
                self.progress_signal.emit(progress)
                
            # --- Сохранение not_in_AD.csv ---
            if self.mode == 'y' and AD_ENABLED and not_found_in_ad:
                try:
                    not_found_in_ad.sort(key=lambda x: x['login'])
                    with open(NOT_IN_AD_CSV, 'w', newline='', encoding='utf-8') as f:
                        import csv
                        writer = csv.DictWriter(f, fieldnames=['login', 'name', 'person_guid'], delimiter=';')
                        writer.writeheader()
                        writer.writerows(not_found_in_ad)
                    if csv_files:
                        last_logger = logger  # Используем последний логгер
                        last_logger.warning(f"🟡 Логины не из AD сохранены в: {NOT_IN_AD_CSV}")
                    self.log_signal.emit(f"✅ Логины не из AD сохранены в: {NOT_IN_AD_CSV}")
                except Exception as e:
                    if csv_files:
                        last_logger = logger
                        last_logger.error(f"❌ Ошибка записи {NOT_IN_AD_CSV}: {e}")
                    self.log_signal.emit(f"❌ Ошибка записи {NOT_IN_AD_CSV}: {e}")
            
            self.log_signal.emit("✅ Обработка завершена!")
            self.progress_signal.emit(100)
            self.finished_signal.emit()
            
            # Возвращаемся в исходную директорию
            os.chdir(original_dir)
            
        except Exception as e:
            self.error_signal.emit(f"❌ Ошибка: {str(e)}")
            self.finished_signal.emit()


class UserCreatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('UserCreator', 'GUI')
        self.worker = None
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """Инициализирует пользовательский интерфейс."""
        self.setWindowTitle("User Creator GUI")
        self.setGeometry(100, 100, 900, 700)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # --- Панель настроек ---
        settings_group = QGroupBox("Настройки обработки")
        settings_layout = QVBoxLayout(settings_group)
        
        # Режим работы
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Режим обработки:"))
        self.radio_ad = QRadioButton("Использовать AD")
        self.radio_manual = QRadioButton("Без AD (вручную)")
        self.radio_manual.setChecked(True)
        
        # Активируем/деактивируем радиокнопки в зависимости от конфигурации
        if not AD_ENABLED:
            self.radio_ad.setEnabled(False)
            self.radio_ad.setToolTip("AD отключен в config.json")
            
        mode_layout.addWidget(self.radio_ad)
        mode_layout.addWidget(self.radio_manual)
        mode_layout.addStretch()
        settings_layout.addLayout(mode_layout)
        
        # Поля для AD
        self.ad_widget = QFrame()
        self.ad_widget.setFrameStyle(QFrame.StyledPanel)
        ad_layout = QFormLayout(self.ad_widget)
        
        self.ad_password_edit = QLineEdit()
        self.ad_password_edit.setEchoMode(QLineEdit.Password)
        ad_layout.addRow("Пароль AD:", self.ad_password_edit)
        
        settings_layout.addWidget(self.ad_widget)
        
        # Поле для ручного GUID
        self.manual_guid_widget = QFrame()
        self.manual_guid_widget.setFrameStyle(QFrame.StyledPanel)
        manual_guid_layout = QFormLayout(self.manual_guid_widget)
        
        self.manual_guid_edit = QLineEdit()
        manual_guid_layout.addRow("GUID домена:", self.manual_guid_edit)
        
        settings_layout.addWidget(self.manual_guid_widget)
        
        # Директории
        dirs_layout = QFormLayout()
        
        dir_input_layout = QHBoxLayout()
        self.input_dir_edit = QLineEdit(".")
        self.browse_input_button = QPushButton("Обзор...")
        self.browse_input_button.clicked.connect(self.browse_input_directory)
        dir_input_layout.addWidget(self.input_dir_edit)
        dir_input_layout.addWidget(self.browse_input_button)
        dirs_layout.addRow("Директория с CSV:", dir_input_layout)
        
        settings_layout.addLayout(dirs_layout)
        
        main_layout.addWidget(settings_group)
        
        # --- Кнопка запуска ---
        self.run_button = QPushButton("▶ Запустить обработку")
        self.run_button.clicked.connect(self.run_processing)
        self.run_button.setStyleSheet("font-weight: bold; padding: 10px;")
        main_layout.addWidget(self.run_button)
        
        # --- Прогресс и логи ---
        progress_group = QGroupBox("Прогресс и логи")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Область логов с прокруткой
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # Установка моноширинного шрифта для логов
        font = QFont("Courier New")
        font.setPointSize(9)
        self.log_text.setFont(font)
        
        log_layout.addWidget(self.log_text)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(log_container)
        scroll_area.setMinimumHeight(300)
        
        progress_layout.addWidget(scroll_area)
        
        main_layout.addWidget(progress_group)
        
        # --- Статус бар ---
        self.statusBar().showMessage("Готов к обработке")
        
        # Подключаем сигналы для изменения режима
        self.radio_ad.toggled.connect(self.on_mode_change)
        self.radio_manual.toggled.connect(self.on_mode_change)
        self.on_mode_change()
        
    def on_mode_change(self):
        """Обработчик изменения режима работы."""
        if self.radio_ad.isChecked():
            self.ad_widget.setVisible(True)
            self.manual_guid_widget.setVisible(False)
        else:
            self.ad_widget.setVisible(False)
            self.manual_guid_widget.setVisible(True)
            
    def browse_input_directory(self):
        """Открывает диалог выбора директории."""
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию с CSV")
        if dir_path:
            self.input_dir_edit.setText(dir_path)
            
    def log_message(self, message: str):
        """Добавляет сообщение в лог."""
        self.log_text.append(message)
        # Прокручиваем вниз
        self.log_text.moveCursor(QTextCursor.End)
        
    def run_processing(self):
        """Запускает обработку."""
        # Сохраняем настройки
        self.save_settings()
        
        mode = 'y' if self.radio_ad.isChecked() else 'n'
        ad_password = self.ad_password_edit.text()
        manual_guid = self.manual_guid_edit.text()
        input_dir = self.input_dir_edit.text()
        
        # Валидация
        if mode == 'y' and AD_ENABLED and not ad_password:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, введите пароль AD.")
            return
            
        if mode == 'n' or not AD_ENABLED:
            if not manual_guid:
                QMessageBox.warning(self, "Внимание", "Пожалуйста, введите GUID домена.")
                return
                
        if not input_dir or not os.path.exists(input_dir):
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите существующую директорию с CSV файлами.")
            return
            
        self.run_button.setEnabled(False)
        self.statusBar().showMessage("Обработка запущена...")
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        # Создаем и запускаем поток обработки
        self.worker = Worker(mode, ad_password, manual_guid, input_dir)
        self.worker.log_signal.connect(self.log_message)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_processing_finished)
        self.worker.error_signal.connect(self.on_processing_error)
        self.worker.start()
        
    def on_processing_finished(self):
        """Обработчик завершения обработки."""
        self.run_button.setEnabled(True)
        self.statusBar().showMessage("Обработка завершена")
        self.log_message("=== Обработка завершена ===")
        
    def on_processing_error(self, error_message: str):
        """Обработчик ошибок во время обработки."""
        self.run_button.setEnabled(True)
        self.statusBar().showMessage("Ошибка во время обработки")
        QMessageBox.critical(self, "Ошибка", error_message)
        
    def save_settings(self):
        """Сохраняет настройки в реестр."""
        self.settings.setValue("mode", 'y' if self.radio_ad.isChecked() else 'n')
        self.settings.setValue("input_dir", self.input_dir_edit.text())
        
    def load_settings(self):
        """Загружает настройки из реестра."""
        mode = self.settings.value("mode", 'n')
        if mode == 'y' and AD_ENABLED:
            self.radio_ad.setChecked(True)
        else:
            self.radio_manual.setChecked(True)
            
        input_dir = self.settings.value("input_dir", ".")
        self.input_dir_edit.setText(input_dir)
        
    def closeEvent(self, event):
        """Обработчик закрытия приложения."""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Подтверждение выхода",
                "Идет обработка. Вы уверены, что хотите выйти?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.terminate()
                self.worker.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    
    # Установка стиля
    app.setStyle("Fusion")
    
    window = UserCreatorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()