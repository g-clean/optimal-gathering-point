import sys
import os
import json
import uuid
import time
import math
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
                             QComboBox, QScrollArea, QFrame, QMessageBox,
                             QGroupBox, QToolTip, QStatusBar, QProgressBar,
                             QFileDialog, QTabWidget, QCheckBox, QDialog,
                             QListWidget, QListWidgetItem, QDialogButtonBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QIcon, QFont, QPixmap, QTextCursor, QTextCharFormat, QColor, QCursor
from map_api import create_map_api
from optimal_point import OptimalPointFinder
from style import apply_stylesheet, style_section_header, style_card, set_spacing, AppColors

import base64

# 创建一个计算线程类，用于后台处理耗时操作
class CalculationThread(QThread):
    # 定义信号
    calculation_complete = pyqtSignal(dict)
    calculation_error = pyqtSignal(str)    
    progress_update = pyqtSignal(int)
    
    def __init__(self, api, finder, coordinates, weights, clustering_method, clustering_param, search_step=100, algorithm_type='total_cost'):
        super().__init__()
        self.api = api
        self.finder = finder
        self.coordinates = coordinates
        self.weights = weights
        self.clustering_method = clustering_method
        self.clustering_param = clustering_param
        self.search_step = search_step  # 搜索步长参数
        self.algorithm_type = algorithm_type  # 算法类型参数
    
    def run(self):
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 模拟进度更新
            self.progress_update.emit(10)
            time.sleep(0.3)  # 短暂延迟以显示进度
            
            # 执行计算
            if self.clustering_method:
                self.progress_update.emit(30)
                result = self.finder.find_optimal_point_with_clustering(
                    self.coordinates, 
                    self.weights,
                    method=self.clustering_method,
                    param=self.clustering_param,
                    search_step=self.search_step,
                    algorithm_type=self.algorithm_type
                )
            else:
                self.progress_update.emit(40)
                result = self.finder.find_optimal_point(self.coordinates, self.weights, self.search_step, self.algorithm_type)
            
            self.progress_update.emit(70)
            time.sleep(0.3)  # 短暂延迟
            
            # 反向地理编码获取地址
            if 'optimal_point' in result:
                lat, lng = result['optimal_point']
                address = self.api.reverse_geocode((lat, lng))
                print(f"逆地理编码返回数据: {address}")  # 调试输出
                result['address'] = address
            
            # 计算总耗时并添加到结果中
            end_time = time.time()
            calculation_time = end_time - start_time
            result['calculation_time'] = calculation_time
            
            # 添加API调用次数到结果中
            result['api_call_count'] = self.api.api_call_count
            
            self.progress_update.emit(100)
            self.calculation_complete.emit(result)
            
        except Exception as e:
            self.calculation_error.emit(str(e))

class GatheringPointApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.api_key = ''  # 地图API密钥
        self.api_type = 'amap'  # 默认使用高德地图
        self.locations = {}  # 存储格式: {id: (地址, 坐标, 权重)}
        self.location_widgets = {}  # 存储地点对应的控件
        self.city = ''  # 存储当前选择的城市
        self.calculation_thread = None  # 计算线程

        
        # 设置工具提示样式
        QToolTip.setFont(QFont('Segoe UI', 9))
        # 修改这里：使用QApplication的样式表来设置工具提示样式
        app = QApplication.instance()
        app.setStyleSheet(
            f"QToolTip {{ background-color: {AppColors.CARD_BG}; "
            f"color: {AppColors.TEXT}; "
            f"border: 1px solid {AppColors.BORDER}; "
            "padding: 5px; }}"
        )

    def initUI(self):
        self.setWindowTitle('最优集合点计算器')
        self.setGeometry(300, 300, 900, 700)  # 稍微增加窗口大小
        self.setMinimumSize(800, 600)  # 设置窗口最小尺寸，允许调整大小
        

        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('准备就绪', 3000)
        
        # 创建进度条并添加到状态栏
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setFixedWidth(150)
        self.progressBar.setVisible(False)
        self.statusBar.addPermanentWidget(self.progressBar)

        # 创建中心部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        set_spacing(layout, margin=15, spacing=12)  # 设置更合理的间距

        # 创建API设置组
        api_group = QGroupBox("API设置")
        api_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {AppColors.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        api_layout = QHBoxLayout(api_group)
        set_spacing(api_layout, margin=12, spacing=10)
        
        # 添加API类型选择下拉框
        api_type_label = QLabel('地图API类型：')
        api_type_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY};")
        self.api_type_combo = QComboBox()
        self.api_type_combo.addItems(['高德地图', '百度地图', '腾讯地图'])
        self.api_type_combo.setMaxVisibleItems(3)  # 显示全部三个选项
        self.api_type_combo.setMinimumContentsLength(10)  # 设置最小内容长度
        self.api_type_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)  # 根据内容调整大小
        self.api_type_combo.setMinimumWidth(120)  # 设置最小宽度
        self.api_type_combo.view().setMinimumHeight(90)  # 设置下拉列表的最小高度以显示3个选项
        self.api_type_combo.setToolTip('选择要使用的地图API服务提供商')
        
        # 添加API密钥输入框
        key_label = QLabel('API密钥：')
        key_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY};")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText('输入地图API密钥')
        self.key_input.setToolTip('输入对应地图服务的API密钥')
        
        api_layout.addWidget(api_type_label)
        api_layout.addWidget(self.api_type_combo)
        api_layout.addWidget(key_label)
        api_layout.addWidget(self.key_input)
        layout.addWidget(api_group)

        # 创建地点输入组
        location_group = QGroupBox("添加地点")
        location_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {AppColors.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        input_layout = QHBoxLayout(location_group)
        set_spacing(input_layout, margin=12, spacing=10)
        
        # 添加城市输入框
        city_label = QLabel('城市：')
        city_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY};")
        input_layout.addWidget(city_label)
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText('可选，限制搜索范围')
        self.city_input.setFixedWidth(150)
        self.city_input.setToolTip('输入城市名称可以提高地址搜索精度')
        input_layout.addWidget(self.city_input)
        
        # 添加地址输入框
        address_label = QLabel('地址：')
        address_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY};")
        input_layout.addWidget(address_label)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText('输入完整地址')
        self.address_input.setToolTip('输入需要添加的地点地址')
        input_layout.addWidget(self.address_input)
        
        # 添加权重输入框
        weight_label = QLabel('权重：')
        weight_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY};")
        input_layout.addWidget(weight_label)
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText('1.0')
        self.weight_input.setFixedWidth(60)
        self.weight_input.setToolTip('设置地点的权重值，默认为1.0')
        input_layout.addWidget(self.weight_input)
        
        # 添加按钮布局
        button_layout = QHBoxLayout()
        
        # 添加地点按钮
        add_btn = QPushButton('添加地点')
        add_btn.setToolTip('将当前输入的地点添加到列表中')
        add_btn.clicked.connect(self.add_location)
        button_layout.addWidget(add_btn)
        
        # 导入Excel按钮
        import_btn = QPushButton('导入Excel')
        import_btn.setToolTip('从Excel文件批量导入地点信息')
        import_btn.clicked.connect(self.import_locations_from_excel)
        button_layout.addWidget(import_btn)
        
        input_layout.addLayout(button_layout)
        layout.addWidget(location_group)

        # 创建地址列表显示区域
        locations_group = QGroupBox("已添加地点")
        locations_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {AppColors.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        locations_layout = QVBoxLayout(locations_group)
        set_spacing(locations_layout, margin=12, spacing=8)
        
        # 添加地点数量显示
        count_layout = QHBoxLayout()
        count_layout.setAlignment(Qt.AlignLeft)
        self.location_count_label = QLabel("当前地点数量: 0")
        self.location_count_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY}; font-size: 12px;")
        count_layout.addWidget(self.location_count_label)
        count_layout.addStretch(1)
        locations_layout.addLayout(count_layout)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        style_card(scroll_area)
        
        # 创建滚动区域的内容控件
        self.locations_container = QWidget()
        self.locations_layout = QVBoxLayout(self.locations_container)
        self.locations_layout.setAlignment(Qt.AlignTop)
        set_spacing(self.locations_layout, margin=8, spacing=6)
        scroll_area.setWidget(self.locations_container)
        locations_layout.addWidget(scroll_area)
        layout.addWidget(locations_group)

        # 创建聚类算法选择区域
        clustering_group = QGroupBox("聚类设置")
        clustering_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {AppColors.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        clustering_layout = QHBoxLayout(clustering_group)
        set_spacing(clustering_layout, margin=12, spacing=10)
        
        clustering_layout.addWidget(QLabel('聚类算法：'))
        
        self.clustering_combo = QComboBox()
        self.clustering_combo.addItems(['不使用聚类', 'HDBSCAN', 'Capacity Constrained K-Means'])
        self.clustering_combo.setMaxVisibleItems(3)  # 显示全部三个选项
        self.clustering_combo.setMinimumContentsLength(30)  # 增加最小内容长度
        self.clustering_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)  # 根据内容调整大小
        self.clustering_combo.setMinimumWidth(250)  # 设置最小宽度确保长选项能完全显示
        self.clustering_combo.view().setMinimumHeight(90)  # 设置下拉列表的最小高度以显示3个选项
        self.clustering_combo.currentTextChanged.connect(self.update_clustering_options)
        clustering_layout.addWidget(self.clustering_combo)
        
        # 添加聚类参数设置
        self.cluster_param_label = QLabel('最小簇大小：')
        self.cluster_param_label.setVisible(False)
        clustering_layout.addWidget(self.cluster_param_label)
        
        self.cluster_param_input = QLineEdit('5')
        self.cluster_param_input.setFixedWidth(60)
        self.cluster_param_input.setVisible(False)
        clustering_layout.addWidget(self.cluster_param_input)
        
        # 添加搜索步长设置
        step_label = QLabel('搜索步长：')
        step_label.setStyleSheet(f"font-weight: bold; color: {AppColors.PRIMARY};")
        step_label.setToolTip('设置最优点搜索的步长，单位为米，较小的步长可以提高精度但增加计算时间')
        clustering_layout.addWidget(step_label)
        
        self.search_step_input = QLineEdit('100')
        self.search_step_input.setFixedWidth(80)
        self.search_step_input.setPlaceholderText('100')
        self.search_step_input.setToolTip('搜索步长，单位：米，建议范围：50-500米')
        clustering_layout.addWidget(self.search_step_input)
        
        step_unit_label = QLabel('米')
        step_unit_label.setStyleSheet(f"color: {AppColors.LIGHT_TEXT};")
        clustering_layout.addWidget(step_unit_label)
        
        # 添加自动步长勾选框
        self.auto_step_checkbox = QCheckBox('自动步长')
        self.auto_step_checkbox.setToolTip('根据输入地点的坐标范围自动计算最优步长\n计算方式：选择东西或南北距离中较短的距离除以10，最小值为10米')
        self.auto_step_checkbox.stateChanged.connect(self.on_auto_step_changed)
        clustering_layout.addWidget(self.auto_step_checkbox)
        
        clustering_layout.addStretch(1)
        layout.addWidget(clustering_group)
        
        # 创建优化算法选择区域
        algorithm_group = QGroupBox("优化算法")
        algorithm_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {AppColors.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        algorithm_layout = QHBoxLayout(algorithm_group)
        set_spacing(algorithm_layout, margin=12, spacing=10)
        
        algorithm_layout.addWidget(QLabel('算法类型：'))
        
        # 添加算法选择下拉框
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(['总成本最低', '最长时间最低'])
        self.algorithm_combo.setMaxVisibleItems(2)
        self.algorithm_combo.setMinimumContentsLength(20)
        self.algorithm_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.algorithm_combo.setMinimumWidth(150)
        # 增加下拉框的高度，增加一个字符的高度（约16像素）
        self.algorithm_combo.setMinimumHeight(32)  # 原来默认高度约16像素，增加到32像素
        self.algorithm_combo.setMaximumHeight(32)  # 设置最大高度保持一致
        # 设置下拉列表的高度，确保两个选项都能完整显示，但保持与其他控件一致的外观样式
        self.algorithm_combo.view().setMinimumHeight(60)  # 设置下拉列表的最小高度以显示2个选项
        self.algorithm_combo.setToolTip('选择优化算法类型：\n总成本最低：最小化所有地点到集合点的加权总时间\n最长时间最低：最小化所有地点到集合点的最长时间')
        algorithm_layout.addWidget(self.algorithm_combo)
        
        algorithm_layout.addStretch(1)
        layout.addWidget(algorithm_group)
        
        # 创建计算按钮
        calc_btn = QPushButton('计算最优集合点')
        calc_btn.setObjectName("calcButton")  # 设置对象名以便应用特殊样式
        calc_btn.setMinimumHeight(40)  # 增加按钮高度
        calc_btn.setToolTip('根据已添加的地点计算最优集合点')
        font = calc_btn.font()
        font.setPointSize(11)
        font.setBold(True)
        calc_btn.setFont(font)
        

        
        calc_btn.clicked.connect(self.calculate_optimal_point)
        layout.addWidget(calc_btn)

        # 创建结果显示区域
        result_group = QGroupBox("计算结果")
        result_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {AppColors.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 10px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}")
        result_layout = QVBoxLayout(result_group)
        set_spacing(result_layout, margin=12, spacing=8)
        
        # 创建标签页
        self.result_tabs = QTabWidget()
        
        # 文本结果标签页
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setMinimumHeight(80)  # 减少最小高度，优先缩短结果输出框
        text_layout.addWidget(self.result_display)
        self.result_tabs.addTab(text_tab, "文本结果")
        
        # 地图标签页
        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        self.map_view = QWebEngineView()
        self.map_view.setMinimumHeight(300)  # 减少地图视图最小高度
        map_layout.addWidget(self.map_view)
        self.result_tabs.addTab(map_tab, "地图显示")
        
        result_layout.addWidget(self.result_tabs)
        

        
        layout.addWidget(result_group)

    def add_location(self):
        address = self.address_input.text().strip()
        if not address:
            self.statusBar.showMessage('请输入地址', 3000)
            return
        
        # 设置鼠标等待状态
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self.statusBar.showMessage('正在解析地址...')
        
        # 获取权重，默认为1.0
        weight_text = self.weight_input.text().strip()
        try:
            weight = float(weight_text) if weight_text else 1.0
            if weight <= 0:
                raise ValueError("权重必须大于0")
        except ValueError:
            self.result_display.clear()
            self.format_result_text('权重必须是有效的正数', AppColors.WARNING)
            self.statusBar.showMessage('无效的权重值', 3000)
            QApplication.restoreOverrideCursor()
            return
        
        if not self.api_key:
            self.api_key = self.key_input.text().strip()
            if not self.api_key:
                self.result_display.clear()
                self.format_result_text('请先输入地图API密钥', AppColors.WARNING)
                self.statusBar.showMessage('缺少API密钥', 3000)
                QApplication.restoreOverrideCursor()
                return
        else:
            # 检查用户是否输入了新的API密钥，如果有则更新
            new_key = self.key_input.text().strip()
            if new_key and new_key != self.api_key:
                self.api_key = new_key
                self.result_display.clear()
                self.format_result_text('API密钥已更新', AppColors.SUCCESS)
                self.statusBar.showMessage('API密钥已更新', 3000)
        
        # 获取当前选择的地图API类型
        api_type_text = self.api_type_combo.currentText()
        if api_type_text == '高德地图':
            self.api_type = 'amap'
        elif api_type_text == '百度地图':
            self.api_type = 'baidu'
        elif api_type_text == '腾讯地图':
            self.api_type = 'tencent'

        # 获取城市信息
        city = self.city_input.text().strip()
        if city:
            self.city = city
        
        # 创建地图API实例并搜索候选地点
        try:
            api = create_map_api(self.api_type, self.api_key)
            candidates = api.search_locations(address, city=self.city, limit=10)
            
            if not candidates:
                # 修改错误提示，提供更多信息
                error_msg = f'地址"{address}"解析失败。可能原因：\n'
                error_msg += '1. 地址拼写错误或不完整\n'
                error_msg += '2. 该地址在当前地图API中不存在\n'
                error_msg += '3. 地图API服务暂时不可用\n'
                error_msg += '请检查地址是否正确，或尝试使用其他地图API'
                
                self.result_display.clear()
                self.format_result_text(error_msg, AppColors.WARNING)
                self.statusBar.showMessage('地址解析失败', 3000)
                # 保留地址输入，但设置焦点，以便用户可以直接修改
                self.address_input.setFocus()
                self.address_input.selectAll()
                QApplication.restoreOverrideCursor()
                return
            
            # 如果只有一个候选结果，直接使用
            if len(candidates) == 1:
                selected_candidate = candidates[0]
                coordinates = (selected_candidate['lat'], selected_candidate['lng'])
            else:
                # 显示候选地点选择对话框
                selected_candidate = self.show_location_selection_dialog(candidates, address)
                if selected_candidate is None:
                    # 用户取消选择
                    QApplication.restoreOverrideCursor()
                    return
                coordinates = (selected_candidate['lat'], selected_candidate['lng'])
                
        except ValueError as e:
            self.result_display.clear()
            self.format_result_text(str(e), AppColors.HIGHLIGHT)
            self.statusBar.showMessage('API错误', 3000)
            QApplication.restoreOverrideCursor()
            return
        except Exception as e:
            self.result_display.clear()
            self.format_result_text(f'发生错误：{str(e)}', AppColors.HIGHLIGHT)
            self.statusBar.showMessage('发生未知错误', 3000)
            QApplication.restoreOverrideCursor()
            return
        
        # 生成唯一ID
        location_id = str(uuid.uuid4())
        self.locations[location_id] = (address, coordinates, weight)
        
        # 添加到UI
        self.add_location_to_ui(location_id, address, coordinates, weight)
        
        # 更新地点数量显示
        self.update_location_count()
        
        # 如果启用了自动步长，重新计算步长
        if self.auto_step_checkbox.isChecked():
            auto_step = self.calculate_auto_step()
            self.search_step_input.setText(str(auto_step))
        
        self.address_input.clear()
        self.weight_input.clear()
        self.weight_input.setPlaceholderText('1.0')
        
        # 恢复鼠标状态并显示成功消息
        QApplication.restoreOverrideCursor()
        self.statusBar.showMessage(f'已添加地点: {address}', 3000)

    def add_location_to_ui(self, location_id, address, coordinates, weight):
        # 创建地点项容器
        location_frame = QFrame()
        location_frame.setFrameShape(QFrame.StyledPanel)
        location_frame.setLineWidth(1)
        style_card(location_frame)  # 应用卡片样式
        location_layout = QHBoxLayout(location_frame)
        set_spacing(location_layout, margin=8, spacing=8)
        
        # 地点信息标签
        info_label = QLabel(f"{address}\n({coordinates[0]:.6f}, {coordinates[1]:.6f})")
        info_label.setWordWrap(True)
        font = info_label.font()
        font.setBold(True)
        info_label.setFont(font)
        location_layout.addWidget(info_label, 1)  # 1表示拉伸因子
        
        # 权重显示和编辑
        weight_layout = QHBoxLayout()
        weight_layout.setSpacing(5)
        weight_label = QLabel('权重:')
        weight_label.setStyleSheet(f"color: {AppColors.LIGHT_TEXT};")
        weight_layout.addWidget(weight_label)
        weight_input = QLineEdit(str(weight))
        weight_input.setFixedWidth(60)
        weight_layout.addWidget(weight_input)
        
        # 更新权重按钮
        update_btn = QPushButton('更新')
        update_btn.setFixedWidth(60)
        update_btn.clicked.connect(lambda: self.update_location_weight(location_id, weight_input))
        weight_layout.addWidget(update_btn)
        
        # 删除按钮
        delete_btn = QPushButton('删除')
        delete_btn.setFixedWidth(60)
        delete_btn.clicked.connect(lambda: self.delete_location(location_id))
        weight_layout.addWidget(delete_btn)
        
        location_layout.addLayout(weight_layout)
        
        # 保存控件引用
        self.location_widgets[location_id] = {
            'frame': location_frame,
            'weight_input': weight_input
        }
        
        # 添加到布局
        self.locations_layout.addWidget(location_frame)

    def update_location_weight(self, location_id, weight_input):
        if location_id not in self.locations:
            return
            
        try:
            new_weight = float(weight_input.text().strip())
            if new_weight <= 0:
                raise ValueError("权重必须大于0")
                
            # 更新权重
            address, coordinates, _ = self.locations[location_id]
            self.locations[location_id] = (address, coordinates, new_weight)
            
            # 高亮显示更新的地点项
            if location_id in self.location_widgets:
                frame = self.location_widgets[location_id]['frame']
                original_style = frame.styleSheet()
                frame.setStyleSheet(original_style + f"background-color: {AppColors.SUCCESS}; color: white;")
                
                # 使用定时器恢复原样式
                QTimer.singleShot(800, lambda: frame.setStyleSheet(original_style))
            
            self.result_display.clear()
            self.format_result_text(f'已更新地点 "{address}" 的权重为 {new_weight}', AppColors.SUCCESS)
            self.statusBar.showMessage(f'已更新权重: {address}', 3000)
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", "请输入有效的权重数值（大于0）")
            # 恢复原来的权重值
            _, _, old_weight = self.locations[location_id]
            weight_input.setText(str(old_weight))
            self.statusBar.showMessage('权重更新失败', 3000)

    def delete_location(self, location_id):
        if location_id not in self.locations:
            return
            
        # 获取地点信息用于显示
        address, _, _ = self.locations[location_id]
        
        # 高亮显示要删除的地点项
        if location_id in self.location_widgets:
            frame = self.location_widgets[location_id]['frame']
            original_style = frame.styleSheet()
            frame.setStyleSheet(original_style + f"background-color: {AppColors.HIGHLIGHT}; color: white;")
            
            # 使用定时器延迟删除，以便用户看到高亮效果
            QTimer.singleShot(500, lambda: self._complete_deletion(location_id, address))
        else:
            self._complete_deletion(location_id, address)
    
    def _complete_deletion(self, location_id, address):
        """完成删除操作"""
        # 从数据中删除
        if location_id in self.locations:
            del self.locations[location_id]
        
        # 从UI中删除
        if location_id in self.location_widgets:
            self.locations_layout.removeWidget(self.location_widgets[location_id]['frame'])
            self.location_widgets[location_id]['frame'].deleteLater()
            del self.location_widgets[location_id]
        
        # 更新地点数量显示
        self.update_location_count()
        
        # 如果启用了自动步长，重新计算步长
        if self.auto_step_checkbox.isChecked():
            auto_step = self.calculate_auto_step()
            self.search_step_input.setText(str(auto_step))
        
        self.result_display.clear()
        self.format_result_text(f'已删除地点 "{address}"', AppColors.SUCCESS)
        self.statusBar.showMessage(f'已删除地点: {address}', 3000)

    def update_location_count(self):
        """更新地点数量显示"""
        count = len(self.locations)
        self.location_count_label.setText(f"当前地点数量: {count}")
        
        # 根据地点数量设置不同的颜色提示
        if count == 0:
            self.location_count_label.setStyleSheet(f"font-weight: bold; color: {AppColors.LIGHT_TEXT}; font-size: 12px;")
        elif count < 3:
            self.location_count_label.setStyleSheet(f"font-weight: bold; color: {AppColors.WARNING}; font-size: 12px;")
        else:
            self.location_count_label.setStyleSheet(f"font-weight: bold; color: {AppColors.SUCCESS}; font-size: 12px;")

    def update_clustering_options(self, selected_method):
        """根据选择的聚类方法更新参数设置UI"""
        if selected_method == 'HDBSCAN':
            self.cluster_param_label.setText('最小簇大小：')
            self.cluster_param_label.setVisible(True)
            self.cluster_param_input.setText('5')
            self.cluster_param_input.setVisible(True)
        elif selected_method == 'Capacity Constrained K-Means':
            self.cluster_param_label.setText('最大簇大小：')
            self.cluster_param_label.setVisible(True)
            self.cluster_param_input.setText('10')
            self.cluster_param_input.setVisible(True)
        else:  # 不使用聚类
            self.cluster_param_label.setVisible(False)
            self.cluster_param_input.setVisible(False)
    
    def on_auto_step_changed(self, state):
        """处理自动步长勾选框状态变化"""
        if state == Qt.Checked:
            # 勾选自动步长时，禁用手动输入并计算自动步长
            self.search_step_input.setEnabled(False)
            auto_step = self.calculate_auto_step()
            self.search_step_input.setText(str(auto_step))
        else:
            # 取消勾选时，恢复手动输入
            self.search_step_input.setEnabled(True)
            self.search_step_input.setText('100')  # 恢复默认值
    
    def calculate_auto_step(self):
        """根据输入地点的坐标范围计算自动步长"""
        if not self.locations:
            return 100  # 没有地点时返回默认值
        
        # 获取所有地点的坐标
        coordinates = []
        for location_id, (address, coord, weight) in self.locations.items():
            coordinates.append(coord)
        
        if len(coordinates) < 2:
            return 100  # 少于2个地点时返回默认值
        
        # 计算坐标范围
        lats = [coord[0] for coord in coordinates]
        lngs = [coord[1] for coord in coordinates]
        
        lat_min, lat_max = min(lats), max(lats)
        lng_min, lng_max = min(lngs), max(lngs)
        
        # 计算南北距离（纬度差）和东西距离（经度差）
        # 1度纬度约等于111公里
        north_south_distance = (lat_max - lat_min) * 111000  # 米
        
        # 1度经度的距离随纬度变化，在中纬度地区约为111公里*cos(纬度)
        avg_lat = (lat_min + lat_max) / 2
        import math
        east_west_distance = (lng_max - lng_min) * 111000 * math.cos(math.radians(avg_lat))  # 米
        
        # 选择较短的距离除以10作为步长
        shorter_distance = min(north_south_distance, east_west_distance)
        auto_step = max(10, int(shorter_distance / 10))  # 最小值为10米
        
        return auto_step
    
    def calculate_optimal_point(self):
        if not self.locations:
            self.result_display.clear()
            self.format_result_text('请先添加地点', AppColors.WARNING)
            self.statusBar.showMessage('没有添加地点', 3000)
            return

        # 设置鼠标等待状态
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.statusBar.showMessage('准备计算...')

        try:
            api = create_map_api(self.api_type, self.api_key)
            finder = OptimalPointFinder(api)
        except ValueError as e:
            self.result_display.clear()
            self.format_result_text(str(e), AppColors.HIGHLIGHT)
            self.statusBar.showMessage('API错误', 3000)
            QApplication.restoreOverrideCursor()
            self.progressBar.setVisible(False)
            return
        
        # 提取所有坐标和权重
        coordinates = [loc[1] for loc in self.locations.values()]
        weights = [loc[2] for loc in self.locations.values()]
        
        # 获取聚类设置
        clustering_method = None
        clustering_param = None
        selected_method = self.clustering_combo.currentText()
        
        if selected_method == 'HDBSCAN':
            clustering_method = 'hdbscan'
            try:
                min_cluster_size = int(self.cluster_param_input.text())
                if min_cluster_size < 2:
                    raise ValueError("最小簇大小必须大于等于2")
                clustering_param = min_cluster_size
            except ValueError:
                self.result_display.clear()
                self.format_result_text('请输入有效的最小簇大小（整数且大于等于2）', AppColors.WARNING)
                self.statusBar.showMessage('错误：无效的聚类参数', 3000)
                QApplication.restoreOverrideCursor()
                self.progressBar.setVisible(False)
                return
                                              
        elif selected_method == 'Capacity Constrained K-Means':
            clustering_method = 'kmeans'
            try:
                max_cluster_size = int(self.cluster_param_input.text())
                if max_cluster_size < 2:
                    raise ValueError("最大簇大小必须大于等于2")
                clustering_param = max_cluster_size
            except ValueError:
                self.result_display.clear()
                self.format_result_text('请输入有效的最大簇大小（整数且大于等于2）', AppColors.WARNING)
                self.statusBar.showMessage('错误：无效的聚类参数', 3000)
                QApplication.restoreOverrideCursor()
                self.progressBar.setVisible(False)
                return
        
        # 获取搜索步长设置
        try:
            search_step = int(self.search_step_input.text())
            if search_step <= 0:
                search_step = 100  # 默认值
        except ValueError:
            search_step = 100  # 默认值
        
        # 获取算法类型设置
        algorithm_type = 'total_cost' if self.algorithm_combo.currentText() == '总成本最低' else 'min_max_time'
        
        # 创建并启动计算线程
        self.calculation_thread = CalculationThread(
            api, finder, coordinates, weights, clustering_method, clustering_param, search_step, algorithm_type
        )
        
        # 连接信号
        self.calculation_thread.calculation_complete.connect(self.handle_calculation_complete)
        self.calculation_thread.calculation_error.connect(self.handle_calculation_error)
        self.calculation_thread.progress_update.connect(self.update_progress)
        
        # 启动线程
        self.calculation_thread.start()
        self.statusBar.showMessage('正在计算中...')
        
        # 清空结果显示区域
        self.result_display.clear()

        # 添加所有地点到结果显示
        self.format_result_text("已添加的地点：", AppColors.PRIMARY, True, 11)

        for address, coord, weight in self.locations.values():
            location_text = f"{address}: ({coord[0]:.6f}, {coord[1]:.6f}) [权重: {weight}]"
            self.format_result_text(location_text, AppColors.TEXT)

    def format_result_text(self, text, color=None, bold=False, size=None):
        """格式化结果文本显示"""
        cursor = self.result_display.textCursor()
        format = QTextCharFormat()
        
        # 设置文本颜色
        if color:
            format.setForeground(QColor(color))
        
        # 设置文本粗细
        if bold:
            format.setFontWeight(QFont.Bold)
        else:
            format.setFontWeight(QFont.Normal)
        
        # 设置文本大小
        if size:
            format.setFontPointSize(size)
        
        # 移动到文档末尾
        cursor.movePosition(QTextCursor.End)
        
        # 插入文本
        cursor.insertText(text + '\n', format)
        
        # 滚动到底部
        self.result_display.setTextCursor(cursor)
        self.result_display.ensureCursorVisible()
    
    def show_map(self, result):
        """在地图上显示计算结果"""
        try:
            # 准备地图数据
            lat, lng = result['optimal_point']
            locations = [{
                'coordinates': [coord[1], coord[0]] if self.api_type == 'amap' else [coord[0], coord[1]],  # 根据API类型调整坐标格式
                'address': addr
            } for addr, coord, _ in self.locations.values()]
            
            # 根据API类型生成不同的地图HTML内容
            if self.api_type == 'amap':
                html_content = self.generate_amap_html(lat, lng, locations)
            elif self.api_type == 'baidu':
                # 百度地图显示说明信息
                html_content = self.generate_baidu_notice_html()
            elif self.api_type == 'tencent':
                html_content = self.generate_tencent_map_html(lat, lng, locations)
            else:
                # 默认使用高德地图
                html_content = self.generate_amap_html(lat, lng, locations)
            
            # 显示地图
            self.map_view.setHtml(html_content)
            
        except Exception as e:
            self.statusBar.showMessage(f'地图显示失败: {str(e)}', 5000)
    
    def generate_amap_html(self, lat, lng, locations):
        """生成高德地图HTML内容"""
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>高德地图显示</title>
    <style>
        html, body, #container {{
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
        }}
    </style>
    <script type="text/javascript" src="https://webapi.amap.com/maps?v=2.0&key={self.api_key}"></script>
</head>
<body>
    <div id="container"></div>
    <script type="text/javascript">
        var map = new AMap.Map('container', {{
            zoom: 13,
            center: [{lng}, {lat}],
            viewMode: '2D'
        }});

        // 添加结果点标记
        var resultMarker = new AMap.Marker({{
            position: [{lng}, {lat}],
            map: map,
            icon: new AMap.Icon({{
                size: new AMap.Size(25, 34),
                image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png'
            }}),
            title: '最优集合点',
            offset: new AMap.Pixel(-12, -34)
        }});

        // 添加所有地点标记（使用圆点样式）
        var locations = {json.dumps(locations)};
        locations.forEach(function(loc) {{
            new AMap.CircleMarker({{
                center: loc.coordinates,
                map: map,
                radius: 4,
                fillColor: '#808080',
                fillOpacity: 0.6,
                strokeWeight: 1,
                strokeColor: '#404040',
                title: loc.address
            }});

            // 绘制连线
            new AMap.Polyline({{
                path: [loc.coordinates, [{lng}, {lat}]],
                map: map,
                strokeColor: '#409EFF',
                strokeWeight: 2,
                strokeOpacity: 0.6,
                strokeStyle: 'dashed',
                strokeDasharray: [5, 5]
            }});
        }});

        // 自适应显示所有点
        var points = locations.map(function(loc) {{ return loc.coordinates; }});
        points.push([{lng}, {lat}]);
        map.setFitView();
    </script>
</body>
</html>
        '''
    
    def generate_baidu_notice_html(self):
        """生成百度地图说明页面HTML内容"""
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>百度地图说明</title>
    <style>
        html, body {{
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
        }}
        .notice-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            padding: 20px;
            box-sizing: border-box;
        }}
        .notice-content {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 500px;
        }}
        .notice-title {{
            font-size: 24px;
            color: #333;
            margin-bottom: 20px;
        }}
        .notice-message {{
            font-size: 16px;
            color: #666;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="notice-container">
        <div class="notice-content">
            <div class="notice-title">百度地图说明</div>
            <div class="notice-message">
                百度地图API类型不同，无法使用地图显示功能
            </div>
        </div>
    </div>
</body>
</html>
        '''

    def generate_baidu_map_html(self, lat, lng, locations):
        """生成百度地图HTML内容"""
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>百度地图显示</title>
    <style>
        html, body, #container {{
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
        }}
        #loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 16px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div id="container"></div>
    <div id="loading">
        <div style="text-align: center; font-size: 16px; color: #666; margin-bottom: 20px;">百度地图API类型不同，无法使用地图显示功能</div>
    </div>
    
    <script type="text/javascript">
        // 动态加载百度地图API
        function loadBaiduMapAPI() {{
            return new Promise((resolve, reject) => {{
                // 检查是否已经加载
                if (typeof BMap !== 'undefined') {{
                    resolve();
                    return;
                }}
                
                // 验证API密钥格式
                const apiKey = '{self.api_key}';
                if (!apiKey || apiKey.length !== 32) {{
                    reject(new Error('百度地图API密钥格式错误，应为32位字符'));
                    return;
                }}
                
                const script = document.createElement('script');
                script.type = 'text/javascript';
                script.src = 'https://api.map.baidu.com/api?v=3.0&ak=' + apiKey + '&callback=initBaiduMap';
                
                // 设置加载超时
                const timeout = setTimeout(() => {{
                    reject(new Error('百度地图API加载超时，请检查网络连接和API密钥'));
                }}, 10000);
                
                script.onerror = () => {{
                    clearTimeout(timeout);
                    reject(new Error('百度地图API脚本加载失败，请检查API密钥是否有效'));
                }};
                
                // 设置全局回调函数
                window.initBaiduMap = function() {{
                    clearTimeout(timeout);
                    // 检查BMap是否真正可用
                    if (typeof BMap === 'undefined') {{
                        reject(new Error('百度地图API加载失败，可能是API密钥无效'));
                        return;
                    }}
                    resolve();
                }};
                
                document.head.appendChild(script);
            }});
        }}
        
        // 初始化地图
        function initMap() {{
            try {{
                // 隐藏加载提示
                document.getElementById('loading').style.display = 'none';
                
                var map = new BMap.Map('container');
                var point = new BMap.Point({lng}, {lat});
                map.centerAndZoom(point, 13);
                map.enableScrollWheelZoom(true);

                // 添加结果点标记（使用自定义图标）
                var resultIcon = new BMap.Icon(
                    'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="25" height="34" viewBox="0 0 25 34"><path d="M12.5 0C5.6 0 0 5.6 0 12.5c0 12.5 12.5 21.5 12.5 21.5s12.5-9 12.5-21.5C25 5.6 19.4 0 12.5 0z" fill="#ff0000"/><circle cx="12.5" cy="12.5" r="6" fill="#ffffff"/></svg>'),
                    new BMap.Size(25, 34),
                    {{
                        anchor: new BMap.Size(12, 34)
                    }}
                );
                var resultMarker = new BMap.Marker(point, {{icon: resultIcon}});
                map.addOverlay(resultMarker);
                
                var resultLabel = new BMap.Label('最优集合点', {{
                    offset: new BMap.Size(20, -10)
                }});
                resultMarker.setLabel(resultLabel);

                // 添加所有地点标记
                var locations = {json.dumps(locations)};
                var points = [point];
                locations.forEach(function(loc, index) {{
                    var locPoint = new BMap.Point(loc.coordinates[0], loc.coordinates[1]);
                    points.push(locPoint);
                    
                    // 添加圆形标记
                    var circle = new BMap.Circle(locPoint, 50, {{
                        fillColor: '#808080',
                        fillOpacity: 0.6,
                        strokeWeight: 1,
                        strokeColor: '#404040'
                    }});
                    map.addOverlay(circle);
                    
                    // 添加标签
                    var label = new BMap.Label(loc.address, {{
                        position: locPoint,
                        offset: new BMap.Size(10, -10)
                    }});
                    label.setStyle({{
                        backgroundColor: 'rgba(255,255,255,0.8)',
                        border: '1px solid #ccc',
                        borderRadius: '3px',
                        padding: '2px 5px',
                        fontSize: '12px'
                    }});
                    map.addOverlay(label);

                    // 绘制连线
                    var polyline = new BMap.Polyline([locPoint, point], {{
                        strokeColor: '#409EFF',
                        strokeWeight: 2,
                        strokeOpacity: 0.6,
                        strokeStyle: 'dashed'
                    }});
                    map.addOverlay(polyline);
                }});

                // 自适应显示所有点
                if (points.length > 1) {{
                    map.setViewport(points, {{
                        margins: [20, 20, 20, 20]
                    }});
                }}
                
            }} catch (error) {{
                console.error('地图初始化失败:', error);
                document.getElementById('loading').innerHTML = '地图加载失败: ' + error.message;
            }}
        }}
        
        // 页面加载完成后初始化地图
         document.addEventListener('DOMContentLoaded', function() {{
             loadBaiduMapAPI()
                 .then(() => {{
                     // 等待一小段时间确保API完全加载
                     setTimeout(initMap, 100);
                 }})
                 .catch(error => {{
                     console.error('百度地图API加载失败:', error);
                     const loadingDiv = document.getElementById('loading');
                     loadingDiv.innerHTML = `
                         <div style="text-align: center; padding: 20px;">
                             <h3 style="color: #ff4444; margin-bottom: 10px;">百度地图加载失败</h3>
                             <p style="margin-bottom: 10px; color: #666;">${{error.message}}</p>
                             <div style="font-size: 12px; color: #999; line-height: 1.5;">
                                   <p>百度地图API类型不同，无法使用地图显示功能</p>
                               </div>
                         </div>
                     `;
                 }});
         }});
    </script>
</body>
</html>
        '''
    
    def generate_tencent_map_html(self, lat, lng, locations):
        """生成腾讯地图HTML内容"""
        # 先将locations转换为JSON字符串，避免f字符串中的大括号冲突
        locations_json = json.dumps(locations)
        
        html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>腾讯地图显示</title>
    <style>
        html, body, #container {
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
        }
    </style>
    <script charset="utf-8" src="https://map.qq.com/api/gljs?v=1.exp&key=API_KEY"></script>
</head>
<body>
    <div id="container"></div>
    <script type="text/javascript">
        var center = new TMap.LatLng(LAT_VALUE, LNG_VALUE);
        var map = new TMap.Map('container', {
            center: center,
            zoom: 13
        });

        // 添加结果点标记
        var resultMarker = new TMap.MultiMarker({
            map: map,
            styles: {
                'result': new TMap.MarkerStyle({
                    'width': 25,
                    'height': 34,
                    'anchor': { x: 12, y: 34 },
                    'color': '#ff0000',
                    'src': 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="25" height="34" viewBox="0 0 25 34"><path d="M12.5 0C5.6 0 0 5.6 0 12.5c0 12.5 12.5 21.5 12.5 21.5s12.5-9 12.5-21.5C25 5.6 19.4 0 12.5 0z" fill="red"/><circle cx="12.5" cy="12.5" r="6" fill="white"/></svg>')
                })
            },
            geometries: [{
                id: 'result',
                styleId: 'result',
                position: center,
                properties: {
                    title: '最优集合点'
                }
            }]
        });

        // 添加所有地点标记和连线
        var locations = LOCATIONS_JSON;
        var geometries = [];
        var polylines = [];
        
        locations.forEach(function(loc, index) {
            var locLatLng = new TMap.LatLng(loc.coordinates[1], loc.coordinates[0]);
            
            // 添加圆形标记
            geometries.push({
                id: 'loc_' + index,
                styleId: 'location',
                position: locLatLng,
                properties: {
                    title: loc.address
                }
            });
            
            // 添加连线
            polylines.push({
                id: 'line_' + index,
                styleId: 'line',
                paths: [locLatLng, center],
                properties: {}
            });
        });
        
        // 创建地点标记
        var locationMarkers = new TMap.MultiMarker({
            map: map,
            styles: {
                'location': new TMap.MarkerStyle({
                    'width': 12,
                    'height': 12,
                    'anchor': { x: 6, y: 6 },
                    'color': '#808080',
                    'src': 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="5" fill="gray" stroke="black" stroke-width="1"/></svg>')
                })
            },
            geometries: geometries
        });
        
        // 创建连线
        var polylineLayer = new TMap.MultiPolyline({
            map: map,
            styles: {
                'line': new TMap.PolylineStyle({
                    'color': '#409EFF',
                    'width': 2,
                    'borderWidth': 0,
                    'lineCap': 'round',
                    'dashArray': [5, 5]
                })
            },
            geometries: polylines
        });

        // 自适应显示所有点
        var bounds = new TMap.LatLngBounds();
        bounds.extend(center);
        locations.forEach(function(loc) {
            bounds.extend(new TMap.LatLng(loc.coordinates[1], loc.coordinates[0]));
        });
        map.fitBounds(bounds);
    </script>
</body>
</html>
        '''
        
        # 使用字符串替换来避免f字符串的复杂性
        return html_template.replace('API_KEY', self.api_key).replace('LAT_VALUE', str(lat)).replace('LNG_VALUE', str(lng)).replace('LOCATIONS_JSON', locations_json)
    
    def handle_calculation_complete(self, result):
        """处理计算完成的结果"""
        # 恢复光标并隐藏进度条
        QApplication.restoreOverrideCursor()
        self.progressBar.setVisible(False)
        
        if not result:
            self.format_result_text('计算失败，请稍后重试', AppColors.HIGHLIGHT)
            self.statusBar.showMessage('计算失败', 3000)
            return
        
        # 显示结果
        if 'optimal_point' in result:
            # 清空结果显示区域
            self.result_display.clear()
            
            lat, lng = result['optimal_point']
            address_info = result.get('address', {})
            # 使用纯时间总和（不乘权重）来显示总时间成本
            total_time = result.get('pure_total_time', result.get('total_time', 0))
            calculation_time = result.get('calculation_time', 0)
            api_call_count = result.get('api_call_count', 0)
            
            # 优先显示最近POI点名称，如果没有则显示格式化地址
            display_address = '未知地址'
            if isinstance(address_info, dict):
                # 优先使用最近POI点的名称
                nearest_poi = address_info.get('nearest_poi')
                if nearest_poi and isinstance(nearest_poi, dict):
                    poi_name = nearest_poi.get('name', '')
                    if poi_name:
                        display_address = poi_name
                    else:
                        # 如果POI没有名称，使用格式化地址
                        display_address = address_info.get('formatted_address', '未知地址')
                else:
                    # 如果没有POI信息，使用格式化地址
                    display_address = address_info.get('formatted_address', '未知地址')
            elif isinstance(address_info, str):
                display_address = address_info
            
            # 显示已添加的地点
            self.format_result_text("已添加的地点：", AppColors.PRIMARY, True, 11)
            for address, coord, weight in self.locations.values():
                location_text = f"{address}: ({coord[0]:.6f}, {coord[1]:.6f}) [权重: {weight}]"
                self.format_result_text(location_text, AppColors.TEXT)
            
            # 显示计算过程日志（如果有）
            if 'calculation_logs' in result and result['calculation_logs']:
                self.format_result_text("\n计算过程：", AppColors.PRIMARY, True, 11)
                for log in result['calculation_logs']:
                    # 根据日志内容设置不同的颜色
                    if "✓" in log:
                        self.format_result_text(log, AppColors.SUCCESS)
                    elif "✗" in log:
                        self.format_result_text(log, AppColors.LIGHT_TEXT)
                    elif "迭代" in log and ":\n" not in log:
                        self.format_result_text(log, AppColors.HIGHLIGHT, True)
                    elif "计算完成" in log or "最终最优点" in log:
                        self.format_result_text(log, AppColors.SUCCESS, True)
                    elif "改进" in log:
                        self.format_result_text(log, AppColors.SUCCESS)
                    else:
                        self.format_result_text(log, AppColors.TEXT)
            
            # 显示最终结果
            self.format_result_text("\n✅ 计算完成！", AppColors.SUCCESS, True, 12)
            self.format_result_text(f'最优集合点坐标: ({lat:.6f}, {lng:.6f})', AppColors.PRIMARY, True)
            self.format_result_text(f'地址: {display_address}')
            
            # 显示总时间成本（根据API类型添加相应单位）
            if total_time > 0:
                if self.api_type == 'tencent':
                    # 腾讯地图返回的时间单位是分钟
                    hours = total_time // 60
                    minutes = total_time % 60
                    if hours > 0:
                        self.format_result_text(f'总时间成本: {hours}小时{minutes}分钟', AppColors.HIGHLIGHT)
                    else:
                        self.format_result_text(f'总时间成本: {minutes}分钟', AppColors.HIGHLIGHT)
                else:
                    # 高德和百度地图返回的时间单位是秒
                    hours = total_time // 3600
                    minutes = (total_time % 3600) // 60
                    seconds = total_time % 60
                    if hours > 0:
                        self.format_result_text(f'总时间成本: {hours}小时{minutes}分钟{seconds}秒', AppColors.HIGHLIGHT)
                    elif minutes > 0:
                        self.format_result_text(f'总时间成本: {minutes}分钟{seconds}秒', AppColors.HIGHLIGHT)
                    else:
                        self.format_result_text(f'总时间成本: {seconds}秒', AppColors.HIGHLIGHT)
            
            # 显示各点到最优集合点的时间
            if 'individual_times' in result and result['individual_times']:
                self.format_result_text("\n各点到最优集合点的时间：", AppColors.PRIMARY, True, 11)
                for time_info in result['individual_times']:
                    point_index = time_info.get('point_index', 0)
                    coordinates = time_info.get('coordinates', (0, 0))
                    time_formatted = time_info.get('time_formatted', '未知')
                    weight = time_info.get('weight', 1)
                    
                    # 获取对应地点的地址信息
                    location_address = '未知地点'
                    for address, coord, loc_weight in self.locations.values():
                        if abs(coord[0] - coordinates[0]) < 0.000001 and abs(coord[1] - coordinates[1]) < 0.000001:
                            location_address = address
                            break
                    
                    # 根据时间计算结果设置不同颜色
                    if time_info.get('time_seconds') is not None:
                        self.format_result_text(f"  {location_address}: {time_formatted} (权重: {weight})", AppColors.TEXT)
                    else:
                        self.format_result_text(f"  {location_address}: {time_formatted} (权重: {weight})", AppColors.LIGHT_TEXT)
            
            # 如果有POI信息，显示详细的POI信息
            if isinstance(address_info, dict) and address_info.get('nearest_poi'):
                nearest_poi = address_info['nearest_poi']
                if isinstance(nearest_poi, dict):
                    poi_distance = nearest_poi.get('distance', '')
                    poi_direction = nearest_poi.get('direction', '')
                    poi_type = nearest_poi.get('type', '')
                    
                    poi_details = []
                    if poi_distance: poi_details.append(f'距离: {poi_distance}米')
                    if poi_direction: poi_details.append(f'方向: {poi_direction}')
                    if poi_type: poi_details.append(f'类型: {poi_type}')
                    
                    if poi_details:
                        self.format_result_text(f'POI详情: {" | ".join(poi_details)}', AppColors.LIGHT_TEXT)
            
            # 显示格式化地址作为补充信息
            if isinstance(address_info, dict) and address_info.get('formatted_address'):
                formatted_addr = address_info['formatted_address']
                if formatted_addr != display_address:  # 避免重复显示
                    self.format_result_text(f'详细地址: {formatted_addr}', AppColors.LIGHT_TEXT)
            self.format_result_text(f'计算耗时: {calculation_time:.2f}秒')
            self.format_result_text(f'API调用次数: {api_call_count}次')
            
            # 如果有聚类信息，显示聚类结果
            if 'clusters' in result and result['clusters']:
                self.format_result_text('\n聚类结果:', AppColors.PRIMARY, True)
                for i, cluster in enumerate(result['clusters']):
                    # cluster是一个包含(coordinates, weights)的元组
                    if isinstance(cluster, tuple) and len(cluster) == 2:
                        coordinates, weights = cluster
                        point_count = len(coordinates) if coordinates else 0
                        self.format_result_text(f'簇 {i+1}: {point_count}个点')
                    else:
                        # 兼容其他可能的数据格式
                        self.format_result_text(f'簇 {i+1}: {len(cluster)}个点')
            

            
            # 显示地图
            self.show_map(result)
            # 切换到地图标签页
            self.result_tabs.setCurrentIndex(1)
            
            self.statusBar.showMessage('计算完成', 5000)
        else:
            self.format_result_text('计算结果格式错误', AppColors.HIGHLIGHT)
            self.statusBar.showMessage('计算结果异常', 3000)

    
    def handle_calculation_error(self, error_msg):
        """处理计算过程中的错误"""
        QApplication.restoreOverrideCursor()
        self.progressBar.setVisible(False)
        self.format_result_text(f'计算过程中发生错误: {error_msg}', AppColors.HIGHLIGHT)
        self.statusBar.showMessage('计算错误', 3000)
    
    def update_progress(self, value):
        """更新进度条"""
        self.progressBar.setValue(value)
    
    def closeEvent(self, event):
        """处理窗口关闭事件，确保程序正常终止"""
        # 接受关闭事件，程序将正常终止
        event.accept()
        

    
    def show_location_selection_dialog(self, candidates, original_address):
        """显示候选地点选择对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f'选择地点 - "{original_address}"')
        dialog.setModal(True)
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # 添加说明标签
        info_label = QLabel(f'找到 {len(candidates)} 个候选地点，请选择正确的地点：')
        layout.addWidget(info_label)
        
        # 创建候选地点列表
        list_widget = QListWidget()
        for i, candidate in enumerate(candidates):
            item_text = f"{candidate['name']}\n"
            item_text += f"地址: {candidate['address']}\n"
            item_text += f"类型: {candidate.get('type', '未知')}\n"
            item_text += f"坐标: ({candidate['lat']:.6f}, {candidate['lng']:.6f})"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, candidate)  # 存储候选地点数据
            list_widget.addItem(item)
        
        # 默认选择第一个
        if candidates:
            list_widget.setCurrentRow(0)
        
        # 添加双击选择功能
        list_widget.itemDoubleClicked.connect(dialog.accept)
        
        layout.addWidget(list_widget)
        
        # 添加按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            current_item = list_widget.currentItem()
            if current_item:
                return current_item.data(Qt.UserRole)
        
        return None

    def import_locations_from_excel(self):
        """从Excel文件导入地点信息"""
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '选择Excel文件',
            '',
            'Excel文件 (*.xlsx *.xls *.csv);;所有文件 (*)'
        )
        
        if not file_path:
            return
        
        try:
            # 设置鼠标等待状态
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            self.statusBar.showMessage('正在读取文件...')
            
            # 根据文件扩展名选择读取方法
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # 读取CSV文件，尝试不同的编码
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(file_path, encoding='gbk')
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, encoding='latin-1')
            elif file_ext in ['.xlsx', '.xls']:
                # 读取Excel文件
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f'不支持的文件格式: {file_ext}')
            
            # 检查必要的列
            required_columns = ['name']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(
                    self,
                    '文件格式错误',
                    f'文件缺少必要的列: {", ".join(missing_columns)}\n\n'
                    f'请确保文件包含以下列:\n'
                    f'- name (必需): 地点名称\n'
                    f'- cityname (可选): 城市名称\n'
                    f'- lon (可选): 经度\n'
                    f'- lat (可选): 纬度\n'
                    f'- 权重 (可选): 权重值'
                )
                return
            
            # 处理每一行数据
            success_count = 0
            error_count = 0
            error_messages = []
            
            self.statusBar.showMessage('正在处理地点数据...')
            
            # 在开始处理前检查API密钥（如果需要搜索坐标）
            needs_api = False
            for index, row in df.iterrows():
                lon = None
                lat = None
                if 'lon' in df.columns and pd.notna(row['lon']):
                    try:
                        lon = float(row['lon'])
                    except (ValueError, TypeError):
                        pass
                if 'lat' in df.columns and pd.notna(row['lat']):
                    try:
                        lat = float(row['lat'])
                    except (ValueError, TypeError):
                        pass
                if lon is None or lat is None:
                    needs_api = True
                    break
            
            # 如果需要API但没有密钥，提前提示用户
            if needs_api:
                if not self.api_key:
                    self.api_key = self.key_input.text().strip()
                    if not self.api_key:
                        QApplication.restoreOverrideCursor()
                        QMessageBox.warning(
                            self,
                            'API密钥缺失',
                            'Excel文件中存在缺少经纬度的地点，需要通过地图API搜索坐标。\n\n'
                            '请先在界面中输入地图API密钥，然后重新导入。'
                        )
                        self.statusBar.showMessage('请先输入API密钥', 3000)
                        return
                else:
                    # 检查用户是否输入了新的API密钥，如果有则更新
                    new_key = self.key_input.text().strip()
                    if new_key and new_key != self.api_key:
                        self.api_key = new_key
                        self.statusBar.showMessage('API密钥已更新', 2000)
                
                # 获取当前选择的地图API类型
                api_type_text = self.api_type_combo.currentText()
                if api_type_text == '高德地图':
                    self.api_type = 'amap'
                elif api_type_text == '百度地图':
                    self.api_type = 'baidu'
                elif api_type_text == '腾讯地图':
                    self.api_type = 'tencent'
            
            for index, row in df.iterrows():
                try:
                    # 获取地点名称
                    name = str(row['name']).strip()
                    if not name or name == 'nan':
                        error_count += 1
                        error_messages.append(f'第{index+2}行: 地点名称为空')
                        continue
                    
                    # 获取城市名称
                    cityname = ''
                    if 'cityname' in df.columns and pd.notna(row['cityname']):
                        cityname = str(row['cityname']).strip()
                    
                    # 如果没有城市名称，使用UI界面输入的城市
                    if not cityname:
                        cityname = self.city_input.text().strip()
                    
                    # 获取经纬度
                    lon = None
                    lat = None
                    if 'lon' in df.columns and pd.notna(row['lon']):
                        try:
                            lon = float(row['lon'])
                        except (ValueError, TypeError):
                            pass
                    
                    if 'lat' in df.columns and pd.notna(row['lat']):
                        try:
                            lat = float(row['lat'])
                        except (ValueError, TypeError):
                            pass
                    
                    # 获取权重
                    weight = 1.0  # 默认权重
                    weight_column = None
                    # 查找权重列（可能的列名）
                    for col in ['权重', 'weight', 'Weight', 'WEIGHT']:
                        if col in df.columns:
                            weight_column = col
                            break
                    
                    if weight_column and pd.notna(row[weight_column]):
                        try:
                            weight = float(row[weight_column])
                            if weight <= 0:
                                weight = 1.0
                        except (ValueError, TypeError):
                            weight = 1.0
                    
                    # 如果有经纬度，直接使用
                    if lon is not None and lat is not None:
                        coordinates = (lat, lon)
                        self.add_imported_location(name, coordinates, weight)
                        success_count += 1
                    else:
                        # 没有经纬度，通过地名搜索
                        coordinates = self.search_location_coordinates(name, cityname)
                        if coordinates:
                            self.add_imported_location(name, coordinates, weight)
                            success_count += 1
                        else:
                            error_count += 1
                            error_messages.append(f'第{index+2}行: 无法找到地点 "{name}" 的坐标')
                
                except Exception as e:
                    error_count += 1
                    error_messages.append(f'第{index+2}行: 处理错误 - {str(e)}')
            
            # 恢复鼠标状态
            QApplication.restoreOverrideCursor()
            
            # 显示导入结果
            result_msg = f'导入完成！\n\n成功导入: {success_count} 个地点\n失败: {error_count} 个地点'
            
            if error_messages:
                # 限制错误消息数量，避免对话框过大
                max_errors = 10
                if len(error_messages) > max_errors:
                    shown_errors = error_messages[:max_errors]
                    shown_errors.append(f'... 还有 {len(error_messages) - max_errors} 个错误')
                else:
                    shown_errors = error_messages
                
                result_msg += '\n\n错误详情:\n' + '\n'.join(shown_errors)
            
            if success_count > 0:
                QMessageBox.information(self, '导入结果', result_msg)
                # 更新地点数量显示
                self.update_location_count()
                # 如果启用了自动步长，重新计算步长
                if self.auto_step_checkbox.isChecked():
                    auto_step = self.calculate_auto_step()
                    self.search_step_input.setText(str(auto_step))
                self.statusBar.showMessage(f'成功导入 {success_count} 个地点', 5000)
            else:
                QMessageBox.warning(self, '导入失败', result_msg)
                self.statusBar.showMessage('导入失败', 3000)
        
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self,
                '文件读取错误',
                f'读取文件时发生错误:\n{str(e)}\n\n'
                f'请检查文件格式是否正确，或尝试另存为Excel格式后重新导入。'
            )
            self.statusBar.showMessage('文件读取失败', 3000)

    def add_imported_location(self, name, coordinates, weight):
        """添加从Excel导入的地点"""
        # 生成唯一ID
        location_id = str(uuid.uuid4())
        self.locations[location_id] = (name, coordinates, weight)
        
        # 添加到UI
        self.add_location_to_ui(location_id, name, coordinates, weight)
    
    def search_location_coordinates(self, name, cityname=''):
        """搜索地点坐标"""
        try:
            # 确保有API密钥
            if not self.api_key:
                self.api_key = self.key_input.text().strip()
                if not self.api_key:
                    return None
            else:
                # 检查用户是否输入了新的API密钥，如果有则更新
                new_key = self.key_input.text().strip()
                if new_key and new_key != self.api_key:
                    self.api_key = new_key
            
            # 获取当前选择的地图API类型
            api_type_text = self.api_type_combo.currentText()
            if api_type_text == '高德地图':
                self.api_type = 'amap'
            elif api_type_text == '百度地图':
                self.api_type = 'baidu'
            elif api_type_text == '腾讯地图':
                self.api_type = 'tencent'
            
            # 创建地图API实例并搜索地点
            api = create_map_api(self.api_type, self.api_key)
            candidates = api.search_locations(name, city=cityname, limit=1)
            
            if candidates:
                # 返回第一个候选结果的坐标
                return (candidates[0]['lat'], candidates[0]['lng'])
            else:
                return None
                
        except Exception as e:
            print(f"搜索地点坐标时发生错误: {str(e)}")
            return None

def main():
    app = QApplication(sys.argv)
    
    # 应用样式表
    stylesheet = apply_stylesheet(app)
    app.setStyleSheet(stylesheet)
    
    window = GatheringPointApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()