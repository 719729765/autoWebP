import sys
import json
import time
import threading
import tempfile

from pathlib import Path
from datetime import datetime

from PIL import Image, features
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSlider,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QTextEdit,
    QFileDialog,
    QSystemTrayIcon,
    QMenu,
    QMessageBox,
    QStyle,
    QSpinBox,
    QSizePolicy,
)


# =========================================================
# 基础配置
# =========================================================

APP_NAME = "WebP 自动转换器"

APP_VERSION = "1.2"

WEBSITE_URL = "https://www.tudoucode.cn"


# =========================================================
# 程序文件
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

ICON_FILE = BASE_DIR / "ico.ico"

CONFIG_FILE = (
    Path.home() /
    ".webp_auto_converter.json"
)


# =========================================================
# 支持图片格式
# =========================================================

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
    ".avif",
}


# =========================================================
# 信号
# =========================================================

class WorkerSignals(QObject):

    log = Signal(str, str)

    stats = Signal(dict)

    status = Signal(bool, str)


# =========================================================
# 文件监控
# =========================================================

class ImageHandler(FileSystemEventHandler):

    def __init__(self, app):
        super().__init__()
        self.app = app

    def on_created(self, event):

        if not event.is_directory:
            self.app.queue_file(
                Path(event.src_path)
            )

    def on_modified(self, event):

        if not event.is_directory:
            self.app.queue_file(
                Path(event.src_path)
            )

    def on_moved(self, event):

        if not event.is_directory:
            self.app.queue_file(
                Path(event.dest_path)
            )


# =========================================================
# 主窗口
# =========================================================

class WebPConverter(QMainWindow):

    def __init__(self):

        super().__init__()

        # -------------------------------------------------
        # 窗口
        # -------------------------------------------------

        self.setWindowTitle(
            APP_NAME
        )

        if ICON_FILE.exists():

            self.setWindowIcon(
                QIcon(str(ICON_FILE))
            )

        # 宽一点，高度合理
        self.resize(
            1120,
            820
        )

        # 防止缩放后控件被压扁
        self.setMinimumSize(
            1000,
            760
        )

        # -------------------------------------------------
        # 信号
        # -------------------------------------------------

        self.signals = WorkerSignals()

        self.signals.log.connect(
            self.add_log
        )

        self.signals.stats.connect(
            self.update_stats
        )

        self.signals.status.connect(
            self.update_status
        )

        # -------------------------------------------------
        # 程序状态
        # -------------------------------------------------

        self.folder = None

        self.observer = None

        self.monitoring = False

        self.processing = set()

        self.stats_data = {
            "scanned": 0,
            "converted": 0,
            "skipped": 0,
            "failed": 0
        }

        # -------------------------------------------------
        # UI
        # -------------------------------------------------

        self.build_ui()

        # -------------------------------------------------
        # 设置
        # -------------------------------------------------

        self.load_settings()

        # -------------------------------------------------
        # 托盘
        # -------------------------------------------------

        self.create_tray()

        # -------------------------------------------------
        # 日志
        # -------------------------------------------------

        self.add_log(
            f"{APP_NAME} v{APP_VERSION} 已启动",
            ""
        )

        self.add_log(
            "支持 WebP / AVIF 输出",
            "success"
        )

    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):

        self.setStyleSheet("""
        /* =================================================
           全局
           ================================================= */

        QWidget {
            font-family:
                "Microsoft YaHei",
                "Segoe UI",
                sans-serif;
            font-size: 13px;
        }

        QMainWindow,
        QWidget {
            background: #f3f5f8;
            color: #20252b;
        }

        /* =================================================
           GroupBox
           ================================================= */

        QGroupBox {
            background: #ffffff;
            border: 1px solid #e1e5ea;
            border-radius: 12px;
            margin-top: 12px;
            padding: 12px;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 7px;
            color: #20252b;
            font-weight: 600;
            background: #f3f5f8;
        }

        /* =================================================
           输入框
           ================================================= */

        QLineEdit,
        QComboBox,
        QSpinBox {

            min-height: 36px;
            max-height: 40px;

            border: 1px solid #dfe3e8;

            border-radius: 8px;

            background: #f8f9fa;

            padding-left: 10px;
            padding-right: 10px;

            selection-background-color: #3478f6;
        }

        QLineEdit:focus,
        QComboBox:focus,
        QSpinBox:focus {

            border: 1px solid #3478f6;

            background: #ffffff;
        }

        QComboBox {

            min-width: 155px;
        }

        QSpinBox {

            min-width: 135px;
        }

        QComboBox::drop-down {

            width: 28px;

            border: none;

            background: transparent;
        }

        /* =================================================
           按钮
           ================================================= */

        QPushButton {

            min-height: 36px;
            max-height: 40px;

            border: none;

            border-radius: 8px;

            padding-left: 14px;
            padding-right: 14px;

            background: #eef1f4;

            color: #4e5660;
        }

        QPushButton:hover {

            background: #e4e8ec;
        }

        QPushButton:pressed {

            background: #dce1e6;
        }

        QPushButton:disabled {

            color: #aeb5bd;

            background: #eef0f2;
        }

        QPushButton#primary {

            background: #3478f6;

            color: white;
        }

        QPushButton#primary:hover {

            background: #2868df;
        }

        /* =================================================
           CheckBox
           ================================================= */

        QCheckBox {

            min-height: 28px;

            spacing: 8px;
        }

        /* =================================================
           Slider
           ================================================= */

        QSlider {

            min-height: 24px;
        }

        QSlider::groove:horizontal {

            height: 5px;

            border-radius: 2px;

            background: #dfe3e8;
        }

        QSlider::handle:horizontal {

            width: 16px;
            height: 16px;

            margin: -6px 0;

            border-radius: 8px;

            background: #3478f6;
        }

        /* =================================================
           日志
           ================================================= */

        QTextEdit {

            background: #17191d;

            color: #cbd1d8;

            border: none;

            border-radius: 9px;

            padding: 8px;

            font-family:
                Consolas,
                "Microsoft YaHei",
                monospace;

            font-size: 12px;
        }

        /* =================================================
           状态
           ================================================= */

        QLabel#statusTitle {

            font-size: 15px;

            font-weight: 600;
        }

        QLabel#statusDesc,
        QLabel#sub {

            color: #7b8490;
        }
        """)

        # =================================================
        # Central Widget
        # =================================================

        central = QWidget()

        self.setCentralWidget(
            central
        )

        root = QVBoxLayout(
            central
        )

        root.setContentsMargins(
            22,
            16,
            22,
            14
        )

        root.setSpacing(
            10
        )

        # =================================================
        # 顶部标题
        # =================================================

        title = QHBoxLayout()

        title.setSpacing(
            8
        )

        logo = QLabel()

        if ICON_FILE.exists():

            logo.setPixmap(
                QIcon(
                    str(ICON_FILE)
                ).pixmap(
                    34,
                    34
                )
            )

        else:

            logo.setText(
                "W"
            )

            logo.setAlignment(
                Qt.AlignCenter
            )

            logo.setStyleSheet("""
                background:#3478f6;
                color:white;
                border-radius:9px;
                font-size:18px;
                font-weight:bold;
            """)

        logo.setFixedSize(
            34,
            34
        )

        title.addWidget(
            logo
        )

        title_text = QLabel(
            APP_NAME
        )

        title_text.setStyleSheet("""
            font-size:15px;
            font-weight:600;
        """)

        title.addWidget(
            title_text
        )

        version_text = QLabel(
            f"v{APP_VERSION}"
        )

        version_text.setStyleSheet("""
            color:#9aa1aa;
            font-size:11px;
        """)

        title.addWidget(
            version_text
        )

        title.addStretch()

        root.addLayout(
            title
        )

        # =================================================
        # 上半部分
        #
        # 左：监控状态
        # 右：图片监控目录
        #
        # 原来的上下结构改成左右结构
        # =================================================

        top_container = QWidget()

        top_layout = QHBoxLayout(
            top_container
        )

        top_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        top_layout.setSpacing(
            10
        )

        # =================================================
        # 左：监控状态
        # =================================================

        status_box = QGroupBox()

        status_box.setMinimumHeight(
            82
        )

        status_box.setMaximumHeight(
            92
        )

        status_box.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        sl = QVBoxLayout(
            status_box
        )

        sl.setContentsMargins(
            10,
            7,
            10,
            7
        )

        sl.setSpacing(
            3
        )

        status_top = QHBoxLayout()

        status_top.setSpacing(
            8
        )

        self.status_dot = QLabel(
            "●"
        )

        self.status_dot.setFixedWidth(
            18
        )

        self.status_dot.setStyleSheet("""
            color:#aeb5bd;
            font-size:15px;
        """)

        self.status_title = QLabel(
            "未启动监控"
        )

        self.status_title.setObjectName(
            "statusTitle"
        )

        status_top.addWidget(
            self.status_dot
        )

        status_top.addWidget(
            self.status_title
        )

        status_top.addStretch()

        sl.addLayout(
            status_top
        )

        self.status_desc = QLabel(
            "请选择一个需要自动转换的图片文件夹。"
        )

        self.status_desc.setObjectName(
            "statusDesc"
        )

        self.status_desc.setWordWrap(
            True
        )

        sl.addWidget(
            self.status_desc
        )

        # =================================================
        # 右：图片监控目录
        # =================================================

        folder_box = QGroupBox(
            "📁  图片监控目录"
        )

        folder_box.setMinimumHeight(
            82
        )

        folder_box.setMaximumHeight(
            92
        )

        folder_box.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        fl = QHBoxLayout(
            folder_box
        )

        fl.setContentsMargins(
            8,
            7,
            8,
            7
        )

        fl.setSpacing(
            8
        )

        self.folder_edit = QLineEdit()

        self.folder_edit.setReadOnly(
            True
        )

        self.folder_edit.setPlaceholderText(
            "尚未选择文件夹"
        )

        browse = QPushButton(
            "选择文件夹"
        )

        browse.setObjectName(
            "primary"
        )

        browse.setMinimumWidth(
            110
        )

        browse.clicked.connect(
            self.select_folder
        )

        fl.addWidget(
            self.folder_edit,
            1
        )

        fl.addWidget(
            browse
        )

        # =================================================
        # 加入左右布局
        # =================================================

        top_layout.addWidget(
            status_box,
            1
        )

        top_layout.addWidget(
            folder_box,
            1
        )

        root.addWidget(
            top_container
        )

        # =================================================
        # 转换设置 + 输出设置
        #
        # 固定合理高度
        # 防止下面日志区域抢空间
        # =================================================

        settings_container = QWidget()

        settings_container.setMinimumHeight(
            365
        )

        settings_container.setMaximumHeight(
            390
        )

        settings_layout = QHBoxLayout(
            settings_container
        )

        settings_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        settings_layout.setSpacing(
            10
        )

        # =================================================
        # 左：转换设置
        # =================================================

        settings = QGroupBox(
            "⚙️  转换设置"
        )

        settings.setMinimumWidth(
            470
        )

        settings.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        s = QVBoxLayout(
            settings
        )

        s.setContentsMargins(
            10,
            9,
            10,
            10
        )

        s.setSpacing(
            6
        )

        # -------------------------------------------------
        # 输出格式
        # -------------------------------------------------

        row = QHBoxLayout()

        row.setSpacing(
            8
        )

        format_label = QLabel(
            "输出图片格式"
        )

        format_label.setMinimumWidth(
            100
        )

        self.output_format = QComboBox()

        self.output_format.addItem(
            "WebP",
            "webp"
        )

        self.output_format.addItem(
            "AVIF",
            "avif"
        )

        self.output_format.setMinimumWidth(
            155
        )

        row.addWidget(
            format_label
        )

        row.addStretch()

        row.addWidget(
            self.output_format
        )

        s.addLayout(
            row
        )

        # -------------------------------------------------
        # 质量
        # -------------------------------------------------

        row = QHBoxLayout()

        row.setSpacing(
            8
        )

        self.quality_label = QLabel(
            "WebP 图片质量"
        )

        self.quality_value = QLabel(
            "85"
        )

        self.quality_value.setFixedWidth(
            35
        )

        self.quality_value.setAlignment(
            Qt.AlignRight |
            Qt.AlignVCenter
        )

        self.quality_value.setStyleSheet("""
            color:#3478f6;
            font-weight:600;
        """)

        row.addWidget(
            self.quality_label
        )

        row.addStretch()

        row.addWidget(
            self.quality_value
        )

        s.addLayout(
            row
        )

        self.quality = QSlider(
            Qt.Horizontal
        )

        self.quality.setRange(
            10,
            100
        )

        self.quality.setValue(
            85
        )

        self.quality.valueChanged.connect(
            self.on_quality_changed
        )

        s.addWidget(
            self.quality
        )

        # -------------------------------------------------
        # 尺寸
        # -------------------------------------------------

        size_title = QLabel(
            "📐 输出图片大小"
        )

        size_title.setStyleSheet("""
            font-weight:600;
        """)

        s.addWidget(
            size_title
        )

        size_desc = QLabel(
            "限制最大尺寸，保持原图比例，不会放大原图"
        )

        size_desc.setObjectName(
            "sub"
        )

        s.addWidget(
            size_desc
        )

        # -------------------------------------------------
        # 最大宽度
        # -------------------------------------------------

        width_row = QHBoxLayout()

        width_label = QLabel(
            "最大宽度"
        )

        width_label.setMinimumWidth(
            70
        )

        self.max_width = QSpinBox()

        self.max_width.setRange(
            0,
            30000
        )

        self.max_width.setValue(
            0
        )

        self.max_width.setSpecialValueText(
            "不限"
        )

        self.max_width.setSuffix(
            " px"
        )

        self.max_width.setMinimumWidth(
            135
        )

        width_row.addWidget(
            width_label
        )

        width_row.addStretch()

        width_row.addWidget(
            self.max_width
        )

        s.addLayout(
            width_row
        )

        # -------------------------------------------------
        # 最大高度
        # -------------------------------------------------

        height_row = QHBoxLayout()

        height_label = QLabel(
            "最大高度"
        )

        height_label.setMinimumWidth(
            70
        )

        self.max_height = QSpinBox()

        self.max_height.setRange(
            0,
            30000
        )

        self.max_height.setValue(
            0
        )

        self.max_height.setSpecialValueText(
            "不限"
        )

        self.max_height.setSuffix(
            " px"
        )

        self.max_height.setMinimumWidth(
            135
        )

        height_row.addWidget(
            height_label
        )

        height_row.addStretch()

        height_row.addWidget(
            self.max_height
        )

        s.addLayout(
            height_row
        )

        # -------------------------------------------------
        # 扫描间隔
        # -------------------------------------------------

        interval_row = QHBoxLayout()

        interval_row.setSpacing(
            8
        )

        interval_row.addWidget(
            QLabel("扫描间隔")
        )

        self.interval_value = QLabel(
            "5 秒"
        )

        self.interval_value.setFixedWidth(
            45
        )

        self.interval_value.setAlignment(
            Qt.AlignRight |
            Qt.AlignVCenter
        )

        self.interval_value.setStyleSheet("""
            color:#3478f6;
            font-weight:600;
        """)

        interval_row.addStretch()

        interval_row.addWidget(
            self.interval_value
        )

        s.addLayout(
            interval_row
        )

        self.interval = QSlider(
            Qt.Horizontal
        )

        self.interval.setRange(
            1,
            60
        )

        self.interval.setValue(
            5
        )

        self.interval.valueChanged.connect(
            self.on_interval_changed
        )

        s.addWidget(
            self.interval
        )

        # -------------------------------------------------
        # 自动转换
        # -------------------------------------------------

        self.auto_convert = QCheckBox(
            "自动转换新增图片"
        )

        self.auto_convert.setChecked(
            True
        )

        s.addWidget(
            self.auto_convert
        )

        # -------------------------------------------------
        # 删除原图
        # -------------------------------------------------

        self.delete_original = QCheckBox(
            "转换成功后删除原图"
        )

        self.delete_original.setChecked(
            False
        )

        s.addWidget(
            self.delete_original
        )

        # -------------------------------------------------
        # 信号
        # -------------------------------------------------

        self.max_width.valueChanged.connect(
            self.save_settings
        )

        self.max_height.valueChanged.connect(
            self.save_settings
        )

        self.auto_convert.stateChanged.connect(
            self.save_settings
        )

        self.delete_original.stateChanged.connect(
            self.save_settings
        )

        self.output_format.currentIndexChanged.connect(
            self.on_format_changed
        )

        # =================================================
        # 右：输出设置
        # =================================================

        output = QGroupBox(
            "📦  输出设置"
        )

        output.setMinimumWidth(
            470
        )

        output.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        o = QVBoxLayout(
            output
        )

        o.setContentsMargins(
            10,
            9,
            10,
            10
        )

        o.setSpacing(
            8
        )

        # -------------------------------------------------
        # 输出位置
        # -------------------------------------------------

        output_title = QLabel(
            "输出位置"
        )

        o.addWidget(
            output_title
        )

        self.output_mode = QComboBox()

        self.output_mode.addItem(
            "与原图片放在同一目录",
            "same"
        )

        self.output_mode.addItem(
            "自动创建输出文件夹",
            "format"
        )

        self.output_mode.setMinimumWidth(
            260
        )

        o.addWidget(
            self.output_mode
        )

        # -------------------------------------------------
        # 重复文件
        # -------------------------------------------------

        duplicate_title = QLabel(
            "重复文件处理"
        )

        o.addWidget(
            duplicate_title
        )

        self.duplicate_mode = QComboBox()

        self.duplicate_mode.addItem(
            "已存在则跳过",
            "skip"
        )

        self.duplicate_mode.addItem(
            "已存在则覆盖",
            "replace"
        )

        self.duplicate_mode.setMinimumWidth(
            260
        )

        o.addWidget(
            self.duplicate_mode
        )

        # -------------------------------------------------
        # 记住设置
        # -------------------------------------------------

        self.remember = QCheckBox(
            "自动记住当前设置"
        )

        self.remember.setChecked(
            True
        )

        o.addWidget(
            self.remember
        )

        # -------------------------------------------------
        # 格式说明
        # -------------------------------------------------

        self.format_info = QLabel()

        self.format_info.setWordWrap(
            True
        )

        self.format_info.setObjectName(
            "sub"
        )

        self.format_info.setMinimumHeight(
            55
        )

        o.addWidget(
            self.format_info
        )

        o.addStretch()

        self.output_mode.currentIndexChanged.connect(
            self.save_settings
        )

        self.duplicate_mode.currentIndexChanged.connect(
            self.save_settings
        )

        self.remember.stateChanged.connect(
            self.save_settings
        )

        self.update_format_info()

        # =================================================
        # 左右加入设置区域
        # =================================================

        settings_layout.addWidget(
            settings,
            1
        )

        settings_layout.addWidget(
            output,
            1
        )

        root.addWidget(
            settings_container
        )

        # =================================================
        # 日志
        #
        # 这里使用 Expanding
        # 自动占据剩余空间
        # =================================================

        log_box = QGroupBox(
            "📋  运行日志"
        )

        log_box.setMinimumHeight(
            145
        )

        log_box.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        ll = QVBoxLayout(
            log_box
        )

        ll.setContentsMargins(
            8,
            7,
            8,
            7
        )

        self.log_edit = QTextEdit()

        self.log_edit.setReadOnly(
            True
        )

        ll.addWidget(
            self.log_edit
        )

        root.addWidget(
            log_box,
            1
        )

        # =================================================
        # 底部
        # =================================================

        bottom = QHBoxLayout()

        bottom.setSpacing(
            7
        )

        foot = QLabel(
            "支持 JPG / JPEG / PNG / BMP / GIF / TIFF / WebP / AVIF"
        )

        foot.setObjectName(
            "sub"
        )

        bottom.addWidget(
            foot
        )

        bottom.addStretch()

        # -------------------------------------------------
        # 网站
        # -------------------------------------------------

        website = QLabel(
            '<a href="https://www.tudoucode.cn" '
            'style="color:#3478f6;'
            'text-decoration:none;">'
            '🌐 www.tudoucode.cn'
            '</a>'
        )

        website.setOpenExternalLinks(
            True
        )

        bottom.addWidget(
            website
        )

        # -------------------------------------------------
        # 手动转换
        # -------------------------------------------------

        manual = QPushButton(
            "🖼️ 手动转换图片"
        )

        manual.setMinimumWidth(
            125
        )

        manual.clicked.connect(
            self.manual_convert
        )

        bottom.addWidget(
            manual
        )

        # -------------------------------------------------
        # 开始监控
        # -------------------------------------------------

        self.start_btn = QPushButton(
            "▶ 开始监控"
        )

        self.start_btn.setObjectName(
            "primary"
        )

        self.start_btn.setMinimumWidth(
            110
        )

        self.start_btn.clicked.connect(
            self.toggle_monitor
        )

        bottom.addWidget(
            self.start_btn
        )

        root.addLayout(
            bottom
        )

    # =====================================================
    # 扫描间隔
    # =====================================================

    def on_interval_changed(
        self,
        value
    ):

        self.interval_value.setText(
            f"{value} 秒"
        )

        self.save_settings()

    # =====================================================
    # 格式改变
    # =====================================================

    def on_format_changed(self):

        self.update_format_info()

        self.update_quality_label()

        self.save_settings()

    # =====================================================
    # 格式说明
    # =====================================================

    def update_format_info(self):

        fmt = (
            self.output_format.currentData()
        )

        if fmt == "avif":

            self.format_info.setText(
                "AVIF：压缩率更高，适合网站图片。"
                "当前 Pillow 如果支持 AVIF，即可直接输出。"
            )

        else:

            self.format_info.setText(
                "WebP：兼容性较好，适合网站和普通图片使用。"
            )

    # =====================================================
    # 质量标签
    # =====================================================

    def update_quality_label(self):

        fmt = (
            self.output_format.currentData()
        )

        if fmt == "avif":

            self.quality_label.setText(
                "AVIF 图片质量"
            )

        else:

            self.quality_label.setText(
                "WebP 图片质量"
            )

    # =====================================================
    # 质量
    # =====================================================

    def on_quality_changed(
        self,
        value
    ):

        self.quality_value.setText(
            str(value)
        )

        self.save_settings()

    # =====================================================
    # 系统托盘
    # =====================================================

    def create_tray(self):

        self.tray = QSystemTrayIcon(
            self
        )

        if ICON_FILE.exists():

            self.tray.setIcon(
                QIcon(
                    str(ICON_FILE)
                )
            )

        else:

            self.tray.setIcon(
                self.style().standardIcon(
                    QStyle.SP_DriveHDIcon
                )
            )

        self.tray.setToolTip(
            f"{APP_NAME} v{APP_VERSION}"
        )

        menu = QMenu()

        # -------------------------------------------------
        # 打开
        # -------------------------------------------------

        show_action = QAction(
            "🖥️ 打开主界面",
            self
        )

        show_action.triggered.connect(
            self.restore_window
        )

        menu.addAction(
            show_action
        )

        # -------------------------------------------------
        # 监控
        # -------------------------------------------------

        toggle_action = QAction(
            "⏯️ 开始 / 暂停监控",
            self
        )

        toggle_action.triggered.connect(
            self.toggle_monitor
        )

        menu.addAction(
            toggle_action
        )

        # -------------------------------------------------
        # 清空日志
        # -------------------------------------------------

        clear_action = QAction(
            "🧹 清空日志",
            self
        )

        clear_action.triggered.connect(
            self.log_edit.clear
        )

        menu.addAction(
            clear_action
        )

        menu.addSeparator()

        # -------------------------------------------------
        # 退出
        # -------------------------------------------------

        exit_action = QAction(
            "❌ 退出程序",
            self
        )

        exit_action.triggered.connect(
            self.quit_app
        )

        menu.addAction(
            exit_action
        )

        self.tray.setContextMenu(
            menu
        )

        self.tray.activated.connect(
            self.tray_activated
        )

        self.tray.show()

    # =====================================================
    # 托盘点击
    # =====================================================

    def tray_activated(
        self,
        reason
    ):

        if reason in (
            QSystemTrayIcon.Trigger,
            QSystemTrayIcon.DoubleClick
        ):

            self.restore_window()

    # =====================================================
    # 关闭
    # =====================================================

    def closeEvent(
        self,
        event
    ):

        event.ignore()

        self.hide()

        if hasattr(
            self,
            "tray"
        ) and self.tray:

            self.tray.showMessage(
                APP_NAME,
                "程序已转到后台运行。",
                QSystemTrayIcon.Information,
                1800
            )

    # =====================================================
    # 恢复
    # =====================================================

    def restore_window(self):

        self.show()

        self.showNormal()

        self.raise_()

        self.activateWindow()

    # =====================================================
    # 退出
    # =====================================================

    def quit_app(self):

        self.stop_monitor()

        if self.tray:

            self.tray.hide()

        QApplication.quit()

    # =====================================================
    # 选择文件夹
    # =====================================================

    def select_folder(self):

        path = QFileDialog.getExistingDirectory(
            self,
            "选择图片监控目录"
        )

        if path:

            self.folder = Path(
                path
            )

            self.folder_edit.setText(
                str(self.folder)
            )

            self.add_log(
                f"已选择监控文件夹：{self.folder}",
                "success"
            )

            self.status_desc.setText(
                "文件夹已选择，可以开始监控。"
            )

            self.save_settings()

    # =====================================================
    # 开始 / 停止
    # =====================================================

    def toggle_monitor(self):

        if self.monitoring:

            self.stop_monitor()

        else:

            if not self.folder:

                self.select_folder()

                if not self.folder:
                    return

            self.start_monitor()

    # =====================================================
    # 开始监控
    # =====================================================

    def start_monitor(self):

        if (
            not self.folder
            or not self.folder.exists()
        ):

            QMessageBox.warning(
                self,
                APP_NAME,
                "监控文件夹不存在，请重新选择。"
            )

            return

        # -------------------------------------------------
        # AVIF 检查
        # -------------------------------------------------

        if (
            self.output_format.currentData()
            == "avif"
        ):

            if not self.check_avif_support():

                QMessageBox.warning(
                    self,
                    "AVIF 不可用",
                    "当前 Pillow 不支持 AVIF。\n\n"
                    "请升级 Pillow 后重试。"
                )

                return

        self.monitoring = True

        self.start_btn.setText(
            "⏸ 暂停监控"
        )

        self.status_dot.setStyleSheet(
            "color:#19a974;font-size:15px;"
        )

        self.status_title.setText(
            "正在监控"
        )

        self.status_desc.setText(
            "程序会自动发现新增/修改的图片并转换。"
        )

        self.add_log(
            f"监控已启动：{self.folder}",
            "success"
        )

        self.observer = Observer()

        self.observer.schedule(
            ImageHandler(self),
            str(self.folder),
            recursive=True
        )

        self.observer.start()

        threading.Thread(
            target=self.initial_scan,
            daemon=True
        ).start()

    # =====================================================
    # 停止监控
    # =====================================================

    def stop_monitor(self):

        self.monitoring = False

        if self.observer:

            self.observer.stop()

            self.observer.join(
                timeout=2
            )

            self.observer = None

        if hasattr(
            self,
            "start_btn"
        ):

            self.start_btn.setText(
                "▶ 开始监控"
            )

        if hasattr(
            self,
            "status_dot"
        ):

            self.status_dot.setStyleSheet(
                "color:#aeb5bd;font-size:15px;"
            )

        if hasattr(
            self,
            "status_title"
        ):

            self.status_title.setText(
                "监控已暂停"
            )

        if hasattr(
            self,
            "status_desc"
        ):

            self.status_desc.setText(
                "监控已经暂停，重新点击开始即可继续。"
            )

    # =====================================================
    # 初始扫描
    # =====================================================

    def initial_scan(self):

        if not self.folder:
            return

        try:

            for p in self.folder.rglob("*"):

                if not self.monitoring:
                    break

                if (
                    p.is_file()
                    and p.suffix.lower()
                    in IMAGE_EXTS
                ):

                    self.process_path(
                        p
                    )

        except Exception as e:

            self.signals.log.emit(
                f"扫描失败：{e}",
                "error"
            )

    # =====================================================
    # 文件队列
    # =====================================================

    def queue_file(
        self,
        path
    ):

        if (
            not self.monitoring
            or not self.auto_convert.isChecked()
        ):

            return

        if (
            path.suffix.lower()
            not in IMAGE_EXTS
        ):

            return

        output_ext = (
            "."
            + self.output_format.currentData()
        )

        if (
            path.suffix.lower()
            == output_ext
        ):

            return

        key = str(
            path.resolve()
        )

        if key in self.processing:

            return

        self.processing.add(
            key
        )

        threading.Thread(
            target=self.process_path_thread,
            args=(
                path,
                key
            ),
            daemon=True
        ).start()

    # =====================================================
    # 等待文件写入
    # =====================================================

    def process_path_thread(
        self,
        path,
        key
    ):

        try:

            last_size = -1

            stable = 0

            for _ in range(
                max(
                    5,
                    self.interval.value() + 2
                )
            ):

                if not path.exists():
                    return

                size = path.stat().st_size

                if (
                    size == last_size
                    and size > 0
                ):

                    stable += 1

                    if stable >= 2:
                        break

                else:

                    stable = 0

                last_size = size

                time.sleep(
                    0.5
                )

            self.process_path(
                path
            )

        finally:

            self.processing.discard(
                key
            )

    # =====================================================
    # 输出目录
    # =====================================================

    def get_output_dir(
        self,
        path
    ):

        output_dir = path.parent

        if (
            self.output_mode.currentData()
            == "format"
        ):

            fmt = (
                self.output_format.currentData()
            )

            output_dir = (
                path.parent /
                fmt.upper()
            )

            output_dir.mkdir(
                exist_ok=True
            )

        return output_dir

    # =====================================================
    # 图片缩放
    # =====================================================

    def resize_image(
        self,
        img
    ):

        max_width = (
            self.max_width.value()
        )

        max_height = (
            self.max_height.value()
        )

        if (
            max_width <= 0
            and max_height <= 0
        ):

            return img

        original_width, original_height = (
            img.size
        )

        ratio = 1.0

        if max_width > 0:

            ratio = min(
                ratio,
                max_width /
                original_width
            )

        if max_height > 0:

            ratio = min(
                ratio,
                max_height /
                original_height
            )

        if ratio >= 1:

            return img

        new_width = max(
            1,
            round(
                original_width *
                ratio
            )
        )

        new_height = max(
            1,
            round(
                original_height *
                ratio
            )
        )

        return img.resize(
            (
                new_width,
                new_height
            ),
            Image.Resampling.LANCZOS
        )

    # =====================================================
    # AVIF 检查
    # =====================================================

    def check_avif_support(self):

        try:

            if hasattr(
                features,
                "check"
            ):

                try:

                    result = features.check(
                        "avif"
                    )

                    if result:

                        return True

                except Exception:

                    pass

            test_file = (
                Path(tempfile.gettempdir())
                /
                "autowbep_avif_test.avif"
            )

            image = Image.new(
                "RGB",
                (2, 2)
            )

            image.save(
                test_file,
                "AVIF"
            )

            if test_file.exists():

                test_file.unlink()

                return True

        except Exception:

            pass

        return False

    # =====================================================
    # 保存转换图片
    # =====================================================

    def save_converted_image(
        self,
        img,
        output
    ):

        fmt = (
            self.output_format.currentData()
        )

        quality = (
            self.quality.value()
        )

        if fmt == "webp":

            img.save(
                output,
                "WEBP",
                quality=quality,
                method=6
            )

        elif fmt == "avif":

            img.save(
                output,
                "AVIF",
                quality=quality
            )

    # =====================================================
    # 转换
    # =====================================================

    def process_path(
        self,
        path
    ):

        if not path.exists():
            return

        fmt = (
            self.output_format.currentData()
        )

        if (
            path.suffix.lower()
            == "." + fmt
        ):

            return

        self.stats_data[
            "scanned"
        ] += 1

        self.signals.stats.emit(
            self.stats_data.copy()
        )

        try:

            output_dir = (
                self.get_output_dir(
                    path
                )
            )

            output = (
                output_dir /
                (
                    path.stem
                    + "."
                    + fmt
                )
            )

            # -------------------------------------------------
            # 重复文件
            # -------------------------------------------------

            if (
                output.exists()
                and
                self.duplicate_mode.currentData()
                == "skip"
            ):

                self.stats_data[
                    "skipped"
                ] += 1

                self.signals.stats.emit(
                    self.stats_data.copy()
                )

                self.signals.log.emit(
                    f"跳过：{output.name}",
                    ""
                )

                return

            # -------------------------------------------------
            # 打开图片
            # -------------------------------------------------

            with Image.open(
                path
            ) as source:

                img = source.convert(
                    "RGBA"
                    if "A" in source.getbands()
                    else "RGB"
                )

                old_size = img.size

                img = self.resize_image(
                    img
                )

                new_size = img.size

                self.save_converted_image(
                    img,
                    output
                )

            self.stats_data[
                "converted"
            ] += 1

            self.signals.stats.emit(
                self.stats_data.copy()
            )

            resize_text = ""

            if old_size != new_size:

                resize_text = (
                    f" | "
                    f"{old_size[0]}×{old_size[1]}"
                    f" → "
                    f"{new_size[0]}×{new_size[1]}"
                )

            self.signals.log.emit(
                f"转换成功："
                f"{path.name} → "
                f"{output.name} "
                f"（{fmt.upper()} "
                f"质量 {self.quality.value()}"
                f"{resize_text}）",
                "success"
            )

            # -------------------------------------------------
            # 删除原图
            # -------------------------------------------------

            if (
                self.delete_original.isChecked()
            ):

                try:

                    path.unlink()

                    self.signals.log.emit(
                        f"已删除原图："
                        f"{path.name}",
                        "success"
                    )

                except Exception as e:

                    self.signals.log.emit(
                        f"删除原图失败：{e}",
                        "error"
                    )

        except Exception as e:

            self.stats_data[
                "failed"
            ] += 1

            self.signals.stats.emit(
                self.stats_data.copy()
            )

            self.signals.log.emit(
                f"转换失败："
                f"{path.name}：{e}",
                "error"
            )

    # =====================================================
    # 手动转换
    # =====================================================

    def manual_convert(self):

        files, _ = (
            QFileDialog.getOpenFileNames(
                self,
                "选择要转换的图片",
                "",
                "图片 (*.jpg *.jpeg *.png *.bmp "
                "*.gif *.tif *.tiff *.webp *.avif)"
            )
        )

        if not files:
            return

        if (
            self.output_format.currentData()
            == "avif"
        ):

            if not self.check_avif_support():

                QMessageBox.warning(
                    self,
                    "AVIF 不可用",
                    "当前 Pillow 不支持 AVIF 编码。\n\n"
                    "请升级 Pillow 后重试。"
                )

                return

        self.add_log(
            f"开始手动转换 "
            f"{len(files)} 张图片",
            ""
        )

        for f in files:

            threading.Thread(
                target=self.process_manual,
                args=(
                    Path(f),
                ),
                daemon=True
            ).start()

    # =====================================================
    # 手动转换处理
    # =====================================================

    def process_manual(
        self,
        path
    ):

        try:

            self.stats_data[
                "scanned"
            ] += 1

            self.signals.stats.emit(
                self.stats_data.copy()
            )

            fmt = (
                self.output_format.currentData()
            )

            output = path.with_suffix(
                "." + fmt
            )

            if (
                output.exists()
                and
                self.duplicate_mode.currentData()
                == "skip"
            ):

                self.stats_data[
                    "skipped"
                ] += 1

                self.signals.stats.emit(
                    self.stats_data.copy()
                )

                self.signals.log.emit(
                    f"跳过：{output.name}",
                    ""
                )

                return

            with Image.open(
                path
            ) as source:

                img = source.convert(
                    "RGBA"
                    if "A" in source.getbands()
                    else "RGB"
                )

                old_size = img.size

                img = self.resize_image(
                    img
                )

                new_size = img.size

                self.save_converted_image(
                    img,
                    output
                )

            self.stats_data[
                "converted"
            ] += 1

            self.signals.stats.emit(
                self.stats_data.copy()
            )

            resize_text = ""

            if old_size != new_size:

                resize_text = (
                    f" | "
                    f"{old_size[0]}×{old_size[1]}"
                    f" → "
                    f"{new_size[0]}×{new_size[1]}"
                )

            self.signals.log.emit(
                f"手动转换："
                f"{path.name} → "
                f"{output.name}"
                f"（{fmt.upper()} "
                f"质量 {self.quality.value()}"
                f"{resize_text}）",
                "success"
            )

        except Exception as e:

            self.stats_data[
                "failed"
            ] += 1

            self.signals.stats.emit(
                self.stats_data.copy()
            )

            self.signals.log.emit(
                f"手动转换失败："
                f"{path.name}：{e}",
                "error"
            )

    # =====================================================
    # 更新统计
    # =====================================================

    def update_stats(
        self,
        data
    ):

        # 当前界面暂时不显示统计数字
        # 保留接口方便以后扩展
        pass

    # =====================================================
    # 更新状态
    # =====================================================

    def update_status(
        self,
        running,
        desc
    ):

        self.status_desc.setText(
            desc
        )

    # =====================================================
    # 日志
    # =====================================================

    def add_log(
        self,
        message,
        typ=""
    ):

        now = (
            datetime.now()
            .strftime("%H:%M:%S")
        )

        if typ == "success":

            color = "#6bd8a9"

        elif typ == "error":

            color = "#ff7777"

        else:

            color = "#cbd1d8"

        self.log_edit.append(
            f'<span style="color:#777f89">'
            f'[{now}]'
            f'</span> '
            f'<span style="color:{color}">'
            f'{self.escape_html(message)}'
            f'</span>'
        )

    # =====================================================
    # HTML 转义
    # =====================================================

    @staticmethod
    def escape_html(
        s
    ):

        return (
            str(s)
            .replace(
                "&",
                "&amp;"
            )
            .replace(
                "<",
                "&lt;"
            )
            .replace(
                ">",
                "&gt;"
            )
        )

    # =====================================================
    # 保存设置
    # =====================================================

    def save_settings(
        self
    ):

        if not hasattr(
            self,
            "remember"
        ):

            return

        if not self.remember.isChecked():

            return

        data = {

            "folder":
                str(self.folder)
                if self.folder
                else "",

            "output_format":
                self.output_format.currentData(),

            "quality":
                self.quality.value(),

            "max_width":
                self.max_width.value(),

            "max_height":
                self.max_height.value(),

            "interval":
                self.interval.value(),

            "auto_convert":
                self.auto_convert.isChecked(),

            "delete_original":
                self.delete_original.isChecked(),

            "output_mode":
                self.output_mode.currentData(),

            "duplicate_mode":
                self.duplicate_mode.currentData(),

            "remember":
                self.remember.isChecked()
        }

        try:

            CONFIG_FILE.write_text(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2
                ),
                encoding="utf-8"
            )

        except Exception:

            pass

    # =====================================================
    # 读取设置
    # =====================================================

    def load_settings(
        self
    ):

        try:

            if not CONFIG_FILE.exists():

                return

            data = json.loads(
                CONFIG_FILE.read_text(
                    encoding="utf-8"
                )
            )

            # -------------------------------------------------
            # 文件夹
            # -------------------------------------------------

            folder = data.get(
                "folder",
                ""
            )

            if (
                folder
                and
                Path(folder).exists()
            ):

                self.folder = Path(
                    folder
                )

                self.folder_edit.setText(
                    folder
                )

            # -------------------------------------------------
            # 输出格式
            # -------------------------------------------------

            saved_format = data.get(
                "output_format",
                "webp"
            )

            for i in range(
                self.output_format.count()
            ):

                if (
                    self.output_format.itemData(i)
                    == saved_format
                ):

                    self.output_format.setCurrentIndex(
                        i
                    )

                    break

            # -------------------------------------------------
            # 质量
            # -------------------------------------------------

            self.quality.setValue(
                int(
                    data.get(
                        "quality",
                        85
                    )
                )
            )

            # -------------------------------------------------
            # 最大宽度
            # -------------------------------------------------

            self.max_width.setValue(
                int(
                    data.get(
                        "max_width",
                        0
                    )
                )
            )

            # -------------------------------------------------
            # 最大高度
            # -------------------------------------------------

            self.max_height.setValue(
                int(
                    data.get(
                        "max_height",
                        0
                    )
                )
            )

            # -------------------------------------------------
            # 扫描间隔
            # -------------------------------------------------

            self.interval.setValue(
                int(
                    data.get(
                        "interval",
                        5
                    )
                )
            )

            # -------------------------------------------------
            # 自动转换
            # -------------------------------------------------

            self.auto_convert.setChecked(
                bool(
                    data.get(
                        "auto_convert",
                        True
                    )
                )
            )

            # -------------------------------------------------
            # 删除原图
            # -------------------------------------------------

            self.delete_original.setChecked(
                bool(
                    data.get(
                        "delete_original",
                        False
                    )
                )
            )

            # -------------------------------------------------
            # 输出位置
            # -------------------------------------------------

            saved_output_mode = data.get(
                "output_mode",
                "same"
            )

            for i in range(
                self.output_mode.count()
            ):

                if (
                    self.output_mode.itemData(i)
                    == saved_output_mode
                ):

                    self.output_mode.setCurrentIndex(
                        i
                    )

                    break

            # -------------------------------------------------
            # 重复文件
            # -------------------------------------------------

            saved_duplicate = data.get(
                "duplicate_mode",
                "skip"
            )

            for i in range(
                self.duplicate_mode.count()
            ):

                if (
                    self.duplicate_mode.itemData(i)
                    == saved_duplicate
                ):

                    self.duplicate_mode.setCurrentIndex(
                        i
                    )

                    break

            # -------------------------------------------------
            # 记住设置
            # -------------------------------------------------

            self.remember.setChecked(
                bool(
                    data.get(
                        "remember",
                        True
                    )
                )
            )

            self.update_format_info()

            self.update_quality_label()

            self.interval_value.setText(
                f"{self.interval.value()} 秒"
            )

        except Exception as e:

            self.add_log(
                f"读取设置失败：{e}",
                "error"
            )

    # =====================================================
    # 清理
    # =====================================================

    def closeEventCleanup(
        self
    ):

        self.stop_monitor()


# =========================================================
# 程序入口
# =========================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setQuitOnLastWindowClosed(
        False
    )

    if ICON_FILE.exists():

        app.setWindowIcon(
            QIcon(
                str(ICON_FILE)
            )
        )

    window = WebPConverter()

    window.show()

    exit_code = app.exec()

    window.closeEventCleanup()

    sys.exit(
        exit_code
    )


# =========================================================
# 启动
# =========================================================

if __name__ == "__main__":

    main()