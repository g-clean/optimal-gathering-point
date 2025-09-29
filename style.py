from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtGui import QColor, QPalette, QFont
from PyQt5.QtCore import Qt

# 定义应用程序的颜色方案
class AppColors:
    PRIMARY = "#3498db"  # 主色调（蓝色）
    SECONDARY = "#2ecc71"  # 次要色调（绿色）
    BACKGROUND = "#f5f5f5"  # 背景色（浅灰色）
    TEXT = "#333333"  # 文本颜色（深灰色）
    LIGHT_TEXT = "#7f8c8d"  # 浅色文本
    BORDER = "#bdc3c7"  # 边框颜色
    HIGHLIGHT = "#e74c3c"  # 高亮色（红色）
    WARNING = "#f39c12"  # 警告色（橙色）
    SUCCESS = "#27ae60"  # 成功色（深绿色）
    CARD_BG = "#ffffff"  # 卡片背景色（白色）

# 应用样式设置函数
def apply_stylesheet(app):
    # 设置应用程序风格
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # 创建自定义调色板
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(AppColors.BACKGROUND))
    palette.setColor(QPalette.WindowText, QColor(AppColors.TEXT))
    palette.setColor(QPalette.Base, QColor(AppColors.CARD_BG))
    palette.setColor(QPalette.AlternateBase, QColor(AppColors.BACKGROUND))
    palette.setColor(QPalette.ToolTipBase, QColor(AppColors.CARD_BG))
    palette.setColor(QPalette.ToolTipText, QColor(AppColors.TEXT))
    palette.setColor(QPalette.Text, QColor(AppColors.TEXT))
    palette.setColor(QPalette.Button, QColor(AppColors.BACKGROUND))
    palette.setColor(QPalette.ButtonText, QColor(AppColors.TEXT))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(AppColors.PRIMARY))
    palette.setColor(QPalette.Highlight, QColor(AppColors.PRIMARY))
    palette.setColor(QPalette.HighlightedText, QColor(AppColors.CARD_BG))
    
    # 应用调色板
    app.setPalette(palette)
    
    # 设置全局字体
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    # 返回样式表字符串
    return """
    /* 全局样式 */
    QWidget {
        font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
    }
    
    /* 标签样式 */
    QLabel {
        color: #333333;
        padding: 2px;
    }
    
    /* 按钮样式 */
    QPushButton {
        background-color: #3498db;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 4px;
        font-weight: bold;
    }
    
    QPushButton:hover {
        background-color: #2980b9;
    }
    
    QPushButton:pressed {
        background-color: #1c6ea4;
    }
    
    /* 输入框样式 */
    QLineEdit {
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 5px;
        background-color: white;
        selection-background-color: #3498db;
    }
    
    QLineEdit:focus {
        border: 1px solid #3498db;
    }
    
    /* 下拉框样式 */
    QComboBox {
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        padding: 5px;
        background-color: white;
        selection-background-color: #3498db;
    }
    
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left: 1px solid #bdc3c7;
    }
    
    /* 文本编辑区样式 */
    QTextEdit {
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        background-color: white;
        selection-background-color: #3498db;
    }
    
    /* 滚动区域样式 */
    QScrollArea {
        border: 1px solid #bdc3c7;
        border-radius: 4px;
        background-color: white;
    }
    
    /* 框架样式 */
    QFrame {
        border-radius: 4px;
    }
    
    /* 地点项样式 */
    QFrame[frameShape="4"] {
        background-color: white;
        border: 1px solid #bdc3c7;
        padding: 8px;
        margin: 2px 0px;
    }
    
    /* 计算按钮特殊样式 */
    QPushButton#calcButton {
        background-color: #2ecc71;
        font-size: 12px; /* 添加缺失的分号 */
        padding: 8px 16px;
    }
    
    QPushButton#calcButton:hover {
        background-color: #27ae60;
    }
    
    /* 删除按钮特殊样式 */
    QPushButton[text="删除"] {
        background-color: #e74c3c;
    }
    
    QPushButton[text="删除"]:hover {
        background-color: #c0392b;
    }
    
    /* 更新按钮特殊样式 */
    QPushButton[text="更新"] {
        background-color: #f39c12;
    }
    
    QPushButton[text="更新"]:hover {
        background-color: #d35400;
    }
    """

# 为特定控件设置样式的辅助函数
def style_section_header(label):
    """为区域标题设置样式"""
    font = label.font()
    font.setBold(True)
    font.setPointSize(10)
    label.setFont(font)
    label.setStyleSheet(f"color: {AppColors.PRIMARY}; margin-top: 10px;")

def style_card(frame):
    """为卡片式框架设置样式"""
    frame.setStyleSheet(f"""
    QFrame {{
        background-color: {AppColors.CARD_BG};
        border: 1px solid {AppColors.BORDER};
        border-radius: 6px;
        padding: 10px;
    }}
    """)

def set_spacing(layout, margin=10, spacing=10):
    """设置布局的间距"""
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)