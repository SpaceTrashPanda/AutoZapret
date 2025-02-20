import sys
import os
import subprocess
import shutil
import requests
import zipfile
import re
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QScrollArea, QFrame, QSizePolicy, QDialog
)

GITHUB_API_RELEASE = "https://api.github.com/repos/Flowseal/zapret-discord-youtube/releases/latest"
EXTRACT_DIR = os.path.join(os.getcwd(), "ZAPRET")


def get_latest_release_zip_url() -> str:
    """Запрашивает GitHub API и возвращает ссылку на zip‑архив последнего релиза."""
    resp = requests.get(GITHUB_API_RELEASE, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    for asset in data.get("assets", []):
        if asset.get("name", "").lower().endswith(".zip"):
            return asset.get("browser_download_url")
    raise ValueError("Zip‑архив не найден в последнем релизе.")


class DownloadThread(QThread):
    finished = Signal(bool, str)

    def __init__(self, target_dir=None):
        super().__init__()
        self.target_dir = target_dir or EXTRACT_DIR

    def run(self):
        try:
            zip_url = get_latest_release_zip_url()
            response = requests.get(zip_url, stream=True, timeout=30)
            response.raise_for_status()
            zip_path = os.path.join(os.getcwd(), "autozapret.zip")
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            if os.path.exists(self.target_dir):
                shutil.rmtree(self.target_dir)
            os.makedirs(self.target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(self.target_dir)
            os.remove(zip_path)
            self.finished.emit(True, "Файлы успешно загружены!")
        except Exception as e:
            self.finished.emit(False, f"Ошибка загрузки: {e}")


class InstallServiceThread(QThread):
    finished_install = Signal(str, str)

    def __init__(self, service_install_path: str, cwd: str):
        super().__init__()
        self.service_install_path = service_install_path
        self.cwd = cwd

    def run(self):
        try:
            proc = subprocess.Popen(
                ["cmd.exe", "/c", self.service_install_path],
                cwd=self.cwd,
                shell=True
            )
            proc.wait()
            self.finished_install.emit("Если вы всё правильно ввели, нажмите 'Обновить статус' и увидите, что всё работает.", "")
        except Exception as e:
            self.finished_install.emit("", f"Ошибка установки: {e}")


class RemoveServiceThread(QThread):
    finished_remove = Signal(str, str)

    def __init__(self, service_remove_path: str, cwd: str):
        super().__init__()
        self.service_remove_path = service_remove_path
        self.cwd = cwd

    def run(self):
        try:
            proc = subprocess.Popen(
                ["cmd.exe", "/c", self.service_remove_path],
                cwd=self.cwd,
                shell=True
            )
            proc.wait()
            self.finished_remove.emit("Сервис успешно удалён.", "")
        except Exception as e:
            self.finished_remove.emit("", f"Ошибка удаления сервиса: {e}")


class ServiceStatusThread(QThread):
    status = Signal(str)

    def run(self):
        try:
            output = subprocess.check_output("sc query zapret", shell=True, text=True, encoding="cp866")
            if "RUNNING" in output:
                self.status.emit("Сервис запущен")
            else:
                self.status.emit("Сервис остановлен")
        except subprocess.CalledProcessError:
            self.status.emit("Сервис не найден")


class FilePanel(QFrame):
    clicked = Signal(str)

    def __init__(self, file_path: str, variant_number: int, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.variant_number = variant_number
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #3e3e3e;
                border: 2px solid #4caf50;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: #ffffff;
                font-size: 16px;
            }
            QFrame:hover {
                background-color: #4a4a4a;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        fname = os.path.basename(file_path)
        lower = fname.lower()
        if "discord" in lower:
            label_text = f"{self.variant_number}. Discord <span style='color:#00BCD4;'>(discord.bat)</span>"
        else:
            label_text = f"{self.variant_number}. Общая настройка"
            if "alt" in lower:
                label_text += f" <span style='color:#FFA500;'>(альтернативный вариант {self.variant_number})</span>"
            label_text += f" <span style='color:#8BC34A;'>({fname})</span>"
            if "mgts" in lower or "мгтс" in lower:
                label_text += " <span style='color:#FF5722;'>[МГТС]</span>"
        self.label = QLabel(label_text)
        self.label.setTextFormat(Qt.RichText)
        layout.addWidget(self.label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.file_path)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setStyleSheet("background-color: #263238; color: #ffffff;")
        layout = QVBoxLayout(self)
        message = (
            "<h2 style='color:#4caf50;'>AUTOZAPRET</h2>"
            "<p style='font-size:14px;'>Данная утилита создана на основе скриптов из проектов:</p>"
            "<p style='font-size:14px;'><a href='https://github.com/Flowseal/zapret-discord-youtube' style='color:#00BCD4;'>"
            "Flowseal/zapret-discord-youtube</a> – скрипты установки Windows,</p>"
            "<p style='font-size:14px;'><a href='https://github.com/bol-van/zapret/' style='color:#00BCD4;'>"
            "bol-van/zapret</a> – проект Zapret.</p>"
            "<p style='font-size:14px;'>Использую их проекты для реализации данной утилиты. Огромное спасибо авторам за их труд!</p>"
            "<p style='font-size:14px;'>Спасибо за использование программы!</p>"
        )
        self.label = QLabel(message)
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.label.setOpenExternalLinks(True)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать")
        self.setStyleSheet("background-color: #263238; color: #ffffff;")
        layout = QVBoxLayout(self)
        message = (
            "<h2 style='color:#4caf50;'>Добро пожаловать в AUTOZAPRET!</h2>"
            "<p style='font-size:14px;'>Эта утилита, созданная <b>SpaceTrashPanda</b>, предназначена для быстрого и "
            "удобного обхода ограничений с помощью сервиса Zapret.</p>"
            "<p style='font-size:14px;'>Вам будет предложено выбрать оптимальный вариант установки, после чего откроется "
            "консоль с подробными инструкциями. Просто следуйте указаниям для успешной настройки сервиса.</p>"
            "<p style='font-size:14px;'>Нажмите 'OK', чтобы продолжить.</p>"
        )
        self.label = QLabel(message)
        self.label.setTextFormat(Qt.RichText)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.ok_button = QPushButton("OK (10)")
        self.ok_button.setEnabled(False)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:disabled {
                background-color: #81c784;
            }
        """)
        layout.addWidget(self.ok_button)
        self.counter = 10
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateCountdown)
        self.timer.start(1000)
        self.ok_button.clicked.connect(self.accept)

    def updateCountdown(self):
        self.counter -= 1
        if self.counter > 0:
            self.ok_button.setText(f"OK ({self.counter})")
        else:
            self.ok_button.setText("OK")
            self.ok_button.setEnabled(True)
            self.timer.stop()


class AutoZapretGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AUTOZAPRET")
        self.setGeometry(500, 200, 800, 500)
        self.file_list = []
        self.current_filter = "all"
        self.download_mode = "normal"
        self.init_ui()
        self.prepare_update()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(10)
        filter_label = QLabel("Фильтр:")
        filter_label.setStyleSheet("font-size:16px; color:#ffffff;")
        sidebar.addWidget(filter_label)
        btn_style = """
            QPushButton {
                background-color: #607D8B;
                color: #ffffff;
                padding: 8px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """
        self.all_btn = QPushButton("🌟 Все настройки")
        self.all_btn.setStyleSheet(btn_style)
        self.all_btn.clicked.connect(lambda: self.set_filter("all"))
        sidebar.addWidget(self.all_btn)
        self.mgts_btn = QPushButton("🏢 Настройки для МГТС")
        self.mgts_btn.setStyleSheet(btn_style)
        self.mgts_btn.clicked.connect(lambda: self.set_filter("mgts"))
        sidebar.addWidget(self.mgts_btn)
        self.normal_btn = QPushButton("🔧 Обычные настройки")
        self.normal_btn.setStyleSheet(btn_style)
        self.normal_btn.clicked.connect(lambda: self.set_filter("normal"))
        sidebar.addWidget(self.normal_btn)
        self.about_btn = QPushButton("ℹ️ О программе")
        self.about_btn.setStyleSheet(btn_style)
        self.about_btn.clicked.connect(self.show_about)
        sidebar.addWidget(self.about_btn)
        sidebar.addStretch()
        self.delete_service_btn = QPushButton("❌ Удалить сервис")
        self.delete_service_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: #ffffff;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        self.delete_service_btn.clicked.connect(self.on_delete_service)
        sidebar.addWidget(self.delete_service_btn)
        main_layout.addLayout(sidebar, 1)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)
        self.header_label = QLabel("AUTOZAPRET")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.header_label.setStyleSheet("font-size: 28px; font-weight: bold; color:#ffffff;")
        content_layout.addWidget(self.header_label)
        self.service_status_label = QLabel("Проверка статуса сервиса...")
        self.service_status_label.setAlignment(Qt.AlignCenter)
        self.service_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.service_status_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        content_layout.addWidget(self.service_status_label)
        btns_layout = QHBoxLayout()
        self.refresh_status_btn = QPushButton("🔄 Обновить статус")
        self.refresh_status_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: #ffffff;
                padding: 10px;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.refresh_status_btn.clicked.connect(self.check_service_status)
        btns_layout.addWidget(self.refresh_status_btn)
        content_layout.addLayout(btns_layout)
        self.files_container = QWidget()
        self.files_layout = QVBoxLayout(self.files_container)
        self.files_layout.setSpacing(10)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.files_container)
        content_layout.addWidget(self.scroll)
        main_layout.addLayout(content_layout, 4)

    def show_about(self):
        about = AboutDialog(self)
        about.exec()

    def set_filter(self, mode: str):
        self.current_filter = mode
        self.populate_file_panels()

    def check_service_status(self):
        self.refresh_status_btn.setText("Проверка...")
        self.refresh_status_btn.setEnabled(False)
        self.status_thread = ServiceStatusThread()
        self.status_thread.status.connect(self.update_status)
        self.status_thread.start()

    def update_status(self, status_text: str):
        color = "#4caf50" if "запущен" in status_text.lower() else "#d32f2f"
        self.service_status_label.setText(f"Статус сервиса: {status_text}")
        self.service_status_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        self.refresh_status_btn.setText("🔄 Обновить статус")
        self.refresh_status_btn.setEnabled(True)

    def prepare_update(self):
        if os.path.exists(EXTRACT_DIR):
            try:
                output = subprocess.check_output("sc query zapret", shell=True, text=True, encoding="cp866")
            except subprocess.CalledProcessError:
                output = ""
            if output:
                reply = QMessageBox.question(
                    self,
                    "Сервис обнаружен",
                    "Обнаружено, что сервис уже установлен. Желаете удалить установленный сервис?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.delete_service_directly()
                    return
                else:
                    QMessageBox.information(self, "Обновление отменено",
                                            "Обновление отменено. Используйте текущую установку сервиса.")
                    self.populate_file_panels()
                    self.check_service_status()
                    return
            else:
                self.populate_file_panels()
                self.check_service_status()
        else:
            self.download_latest_release()

    def download_latest_release(self):
        self.download_mode = "normal"
        self.download_thread = DownloadThread()
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def on_download_finished(self, success: bool, message: str):
        if success:
            QMessageBox.information(self, "Успех", message)
            self.populate_file_panels()
            self.check_service_status()
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def delete_service_directly(self):
        service_remove_path = os.path.join(EXTRACT_DIR, "service_remove.bat")
        if not os.path.exists(service_remove_path):
            QMessageBox.critical(self, "Ошибка", "Файл service_remove.bat не найден!")
            return
        self.remove_thread = RemoveServiceThread(service_remove_path, EXTRACT_DIR)
        self.remove_thread.finished_remove.connect(self.on_remove_finished)
        self.remove_thread.start()

    def on_remove_finished(self, out: str, err: str):
        message = out if out else err
        QMessageBox.information(self, "Результат удаления сервиса", message)
        self.check_service_status()

    def on_delete_service(self):
        reply = QMessageBox.question(
            self,
            "Удаление сервиса",
            "Вы действительно хотите удалить установленный сервис?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.delete_service_directly()

    def populate_file_panels(self):
        for i in reversed(range(self.files_layout.count())):
            widget = self.files_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        try:
            files = []
            for fname in os.listdir(EXTRACT_DIR):
                lower = fname.lower()
                if lower.endswith(".bat") and all(x not in lower for x in ["service_remove", "check_updates", "service_install", "service_status"]):
                    files.append(os.path.join(EXTRACT_DIR, fname))
            if not files:
                lbl = QLabel("Подходящих файлов для установки сервиса не найдено.")
                lbl.setAlignment(Qt.AlignCenter)
                self.files_layout.addWidget(lbl)
                return
            def sort_key(path):
                name = os.path.basename(path).lower()
                if name == "discord.bat":
                    return (0, name)
                elif name == "general.bat":
                    return (1, name)
                elif "alt" in name:
                    return (2, name)
                else:
                    return (3, name)
            files = sorted(files, key=sort_key)
            self.file_list = files
            filtered_files = []
            for file_path in self.file_list:
                fname = os.path.basename(file_path).lower()
                if self.current_filter == "mgts":
                    if "mgts" in fname or "мгтс" in fname:
                        filtered_files.append(file_path)
                elif self.current_filter == "normal":
                    if ("mgts" not in fname and "мгтс" not in fname):
                        filtered_files.append(file_path)
                else:
                    filtered_files.append(file_path)
            for i, file_path in enumerate(filtered_files, start=1):
                panel = FilePanel(file_path, i)
                panel.clicked.connect(self.on_file_panel_clicked)
                self.files_layout.addWidget(panel)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файлы из папки {EXTRACT_DIR}.\n{e}")

    def on_file_panel_clicked(self, file_path: str):
        base = os.path.basename(file_path)
        reply = QMessageBox.question(
            self,
            "Подтверждение установки",
            f"Вы действительно хотите установить сервис для варианта:\n«{base}»?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.launch_install_prompt(file_path)

    def launch_install_prompt(self, selected_file: str):
        menu_lines = []
        for i, file in enumerate(self.file_list, start=1):
            menu_lines.append(f"{i}. {os.path.basename(file)}")
        menu_str = "<br>".join(menu_lines)
        try:
            recommended_index = self.file_list.index(selected_file) + 1
        except ValueError:
            recommended_index = "?"
        instructions = (
            f"<h2 style='color:#4caf50;'>🚀 Установка сервиса</h2>"
            f"<p style='font-size:16px;'>Вы выбрали вариант установки, который отображается как "
            f"<span style='background-color:#ffcc00; padding:4px 8px; border-radius:4px; color:#000; font-weight:bold;'>{recommended_index}</span>.</p>"
            f"<p style='font-size:14px;'>Доступные варианты установки:</p>"
            f"<p style='font-size:14px;'>{menu_str}</p>"
            f"<p style='font-size:14px;'>После нажатия «ОК» откроется консоль, где вам будет предложено ввести номер выбранного варианта. "
            f"Следуйте инструкциям в консоли для завершения установки сервиса.</p>"
        )
        instr_box = QMessageBox(self)
        instr_box.setWindowTitle("Инструкция по установке")
        instr_box.setTextFormat(Qt.RichText)
        instr_box.setText(instructions)
        instr_box.setIcon(QMessageBox.Information)
        instr_box.setStandardButtons(QMessageBox.Ok)
        instr_box.exec()
        service_install_path = os.path.join(EXTRACT_DIR, "service_install.bat")
        if not os.path.exists(service_install_path):
            QMessageBox.critical(self, "Ошибка", "Файл service_install.bat не найден!")
            return
        self.install_thread = InstallServiceThread(service_install_path, EXTRACT_DIR)
        self.install_thread.finished_install.connect(self.on_install_finished)
        self.install_thread.start()

    def on_install_finished(self, out: str, err: str):
        message = out if out else err
        QMessageBox.information(self, "Результат установки сервиса", message)
        self.check_service_status()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    welcome = WelcomeDialog()
    welcome.exec()
    window = AutoZapretGUI()
    window.show()
    sys.exit(app.exec())
