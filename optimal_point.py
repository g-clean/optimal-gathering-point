import numpy as np
from typing import List, Tuple, Optional, Dict, Union
from map_api import MapAPI
from sklearn.cluster import KMeans
import hdbscan
from collections import defaultdict
import math

class OptimalPointFinder:
    def __init__(self, api: MapAPI):
        self.api = api
        self.search_radius = 0.01  # 初始搜索半径（经纬度）
        self.min_radius = 0.0001  # 最小搜索半径
        self.directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # 东南西北四个方向
        self.cluster_threshold = 20  # 点位数量超过此阈值时启用聚类
    
    def calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """计算两点间的直线距离（米）
        使用Haversine公式计算地球表面两点间的距离
        """
        lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
        lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（米）
        earth_radius = 6371000
        distance = earth_radius * c
        
        return distance

    def calculate_centroid(self, coordinates: List[Tuple[float, float]], weights: List[float] = None) -> Tuple[float, float]:
        """计算多个坐标点的加权重心"""
        if not coordinates:
            return None
            
        # 如果没有提供权重，则使用默认权重1
        if weights is None:
            weights = [1.0] * len(coordinates)
        
        # 确保权重和坐标数量一致
        if len(weights) != len(coordinates):
            weights = weights[:len(coordinates)] + [1.0] * (len(coordinates) - len(weights))
            
        points = np.array(coordinates)
        weights_array = np.array(weights).reshape(-1, 1)
        
        # 计算加权平均
        weighted_sum = np.sum(points * weights_array, axis=0)
        total_weight = np.sum(weights)
        
        if total_weight == 0:
            return points.mean(axis=0)  # 如果总权重为0，则使用普通平均
            
        centroid = weighted_sum / total_weight
        # 将重心坐标四舍五入到小数点后六位
        return (round(centroid[0], 6), round(centroid[1], 6))

    def calculate_total_time(self, point: Tuple[float, float], coordinates: List[Tuple[float, float]], weights: List[float] = None) -> Optional[int]:
        """计算从一个点到所有其他点的加权总时间"""
        if not coordinates:
            return 0
            
        total_time = 0
        
        # 如果没有提供权重，则使用默认权重1
        if weights is None:
            weights = [1.0] * len(coordinates)
            
        # 确保权重和坐标数量一致
        if len(weights) != len(coordinates):
            weights = weights[:len(coordinates)] + [1.0] * (len(coordinates) - len(weights))
        
        # 将起点坐标四舍五入到小数点后六位
        rounded_point = (round(point[0], 6), round(point[1], 6))
            
        for i, coord in enumerate(coordinates):
            try:
                # 将目标坐标四舍五入到小数点后六位
                rounded_coord = (round(coord[0], 6), round(coord[1], 6))
                
                # 尝试使用calculate_route方法
                time = self.api.calculate_route(rounded_point, rounded_coord)
                if time is None:
                    # 如果calculate_route返回None，尝试使用calculate_route_time方法
                    try:
                        time = self.api.calculate_route_time(rounded_point, rounded_coord)
                    except AttributeError:
                        # 如果calculate_route_time方法不存在，继续使用None
                        pass
                
                if time is None:
                    # 添加更详细的日志，记录无法计算的坐标对
                    print(f"无法计算从 {rounded_point} 到 {rounded_coord} 的路径时间。API 返回 None。")
                    continue  # 跳过无法计算的路径，而不是返回None
                
                # 添加调试输出，显示API返回的原始时间值
                print(f"API返回时间: 从 {rounded_point} 到 {rounded_coord} = {time}秒, 权重={weights[i]}")
                    
                # 将时间乘以权重（用于寻找最优点的计算过程）
                total_time += time * weights[i]
            except Exception as e:
                # 添加更详细的错误日志，记录出错的坐标对和错误信息
                print(f"计算从 {rounded_point} 到 {rounded_coord} 的路径时间时出错: {str(e)}")
                continue  # 跳过出错的路径
                
        return int(total_time) if total_time > 0 else 0  # 确保返回非负整数
    
    def calculate_pure_total_time(self, point: Tuple[float, float], coordinates: List[Tuple[float, float]]) -> Optional[int]:
        """计算从一个点到所有其他点的纯时间总和（不乘权重，用于最终显示）"""
        if not coordinates:
            return 0
            
        total_time = 0
        
        # 将起点坐标四舍五入到小数点后六位
        rounded_point = (round(point[0], 6), round(point[1], 6))
            
        for i, coord in enumerate(coordinates):
            try:
                # 将目标坐标四舍五入到小数点后六位
                rounded_coord = (round(coord[0], 6), round(coord[1], 6))
                
                # 尝试使用calculate_route方法
                time = self.api.calculate_route(rounded_point, rounded_coord)
                if time is None:
                    # 如果calculate_route返回None，尝试使用calculate_route_time方法
                    try:
                        time = self.api.calculate_route_time(rounded_point, rounded_coord)
                    except AttributeError:
                        # 如果calculate_route_time方法不存在，继续使用None
                        pass
                
                if time is None:
                    # 添加更详细的日志，记录无法计算的坐标对
                    print(f"无法计算从 {rounded_point} 到 {rounded_coord} 的路径时间。API 返回 None。")
                    continue  # 跳过无法计算的路径，而不是返回None
                
                # 直接累加时间，不乘权重（用于最终显示的纯时间总和）
                total_time += time
            except Exception as e:
                # 添加更详细的错误日志，记录出错的坐标对和错误信息
                print(f"计算从 {rounded_point} 到 {rounded_coord} 的路径时间时出错: {str(e)}")
                continue  # 跳过出错的路径
                
        return int(total_time) if total_time > 0 else 0  # 确保返回非负整数
    
    def calculate_max_time(self, point: Tuple[float, float], coordinates: List[Tuple[float, float]]) -> Optional[int]:
        """计算从一个点到所有其他点的最长时间"""
        if not coordinates:
            return 0
            
        max_time = 0
        
        # 将起点坐标四舍五入到小数点后六位
        rounded_point = (round(point[0], 6), round(point[1], 6))
            
        for i, coord in enumerate(coordinates):
            try:
                # 将目标坐标四舍五入到小数点后六位
                rounded_coord = (round(coord[0], 6), round(coord[1], 6))
                
                # 尝试使用calculate_route方法
                time = self.api.calculate_route(rounded_point, rounded_coord)
                if time is None:
                    # 如果calculate_route返回None，尝试使用calculate_route_time方法
                    try:
                        time = self.api.calculate_route_time(rounded_point, rounded_coord)
                    except AttributeError:
                        # 如果calculate_route_time方法不存在，继续使用None
                        pass
                
                if time is None:
                    # 添加更详细的日志，记录无法计算的坐标对
                    print(f"无法计算从 {rounded_point} 到 {rounded_coord} 的路径时间。API 返回 None。")
                    continue  # 跳过无法计算的路径，而不是返回None
                
                # 找出最长时间
                if time > max_time:
                    max_time = time
            except Exception as e:
                # 添加更详细的错误日志，记录出错的坐标对和错误信息
                print(f"计算从 {rounded_point} 到 {rounded_coord} 的路径时间时出错: {str(e)}")
                continue  # 跳过出错的路径
                
        return int(max_time) if max_time > 0 else 0  # 确保返回非负整数

    def apply_hdbscan(self, coordinates: List[Tuple[float, float]], weights: List[float], min_cluster_size: int = 5) -> List[Tuple[Tuple[float, float], float]]:
        """使用HDBSCAN算法进行聚类，返回聚类中心点及其权重"""
        if len(coordinates) < min_cluster_size:
            return [(coord, weight) for coord, weight in zip(coordinates, weights)]
            
        # 将坐标转换为numpy数组
        points = np.array(coordinates)
        
        # 应用HDBSCAN聚类
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=True)
        cluster_labels = clusterer.fit_predict(points)
        
        # 按簇分组并计算每个簇的加权中心
        clusters = defaultdict(list)
        cluster_weights = defaultdict(list)
        
        for i, label in enumerate(cluster_labels):
            clusters[label].append(coordinates[i])
            cluster_weights[label].append(weights[i])
        
        # 计算每个簇的加权中心点
        cluster_centers = []
        for label in clusters:
            if label == -1:  # 噪声点单独处理
                for i, coord in enumerate(clusters[label]):
                    cluster_centers.append((coord, cluster_weights[label][i]))
            else:
                # 计算簇的加权中心
                centroid = self.calculate_centroid(clusters[label], cluster_weights[label])
                # 计算簇的总权重
                total_weight = sum(cluster_weights[label])
                cluster_centers.append((centroid, total_weight))
                
        return cluster_centers
    
    def apply_capacity_kmeans(self, coordinates: List[Tuple[float, float]], weights: List[float], max_cluster_size: int = 10) -> List[Tuple[Tuple[float, float], float]]:
        """使用容量约束的K-Means算法进行聚类，返回聚类中心点及其权重"""
        if len(coordinates) <= max_cluster_size:
            return [(coord, weight) for coord, weight in zip(coordinates, weights)]
            
        # 估计需要的簇数量
        k = max(2, len(coordinates) // max_cluster_size)
        
        # 将坐标转换为numpy数组
        points = np.array(coordinates)
        
        # 应用K-Means聚类
        kmeans = KMeans(n_clusters=k, random_state=42)
        cluster_labels = kmeans.fit_predict(points)
        
        # 按簇分组并计算每个簇的加权中心
        clusters = defaultdict(list)
        cluster_weights = defaultdict(list)
        
        for i, label in enumerate(cluster_labels):
            clusters[label].append(coordinates[i])
            cluster_weights[label].append(weights[i])
        
        # 计算每个簇的加权中心点
        cluster_centers = []
        for label in clusters:
            # 计算簇的加权中心
            centroid = self.calculate_centroid(clusters[label], cluster_weights[label])
            # 计算簇的总权重
            total_weight = sum(cluster_weights[label])
            cluster_centers.append((centroid, total_weight))
                
        return cluster_centers
        
    def _perform_clustering(self, coordinates: List[Tuple[float, float]], weights: List[float], method: str, param: int) -> List[Tuple[List[Tuple[float, float]], List[float]]]:
        """执行聚类操作，根据指定的方法和参数
        
        Args:
            coordinates: 坐标点列表
            weights: 权重列表
            method: 聚类方法，'hdbscan'或'kmeans'
            param: 聚类参数，对于hdbscan是min_cluster_size，对于kmeans是max_cluster_size
            
        Returns:
            聚类结果列表，每个元素是(簇内坐标列表, 簇内权重列表)的元组
        """
        if not coordinates or len(coordinates) == 0:
            return []
            
        # 按簇分组的结果
        clusters = []
        
        if method.lower() == 'hdbscan':
            # 使用HDBSCAN聚类
            min_cluster_size = param if param > 0 else 5
            
            if len(coordinates) < min_cluster_size:
                # 如果点数少于最小簇大小，则作为一个簇返回
                return [(coordinates, weights)]
                
            # 将坐标转换为numpy数组
            points = np.array(coordinates)
            
            # 应用HDBSCAN聚类
            clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, gen_min_span_tree=True)
            cluster_labels = clusterer.fit_predict(points)
            
            # 按簇分组
            cluster_dict = defaultdict(list)
            cluster_weights_dict = defaultdict(list)
            
            for i, label in enumerate(cluster_labels):
                cluster_dict[label].append(coordinates[i])
                cluster_weights_dict[label].append(weights[i])
            
            # 将分组结果转换为列表
            for label in cluster_dict:
                clusters.append((cluster_dict[label], cluster_weights_dict[label]))
                
        elif method.lower() == 'kmeans':
            # 使用K-Means聚类
            max_cluster_size = param if param > 0 else 10
            
            if len(coordinates) <= max_cluster_size:
                # 如果点数少于等于最大簇大小，则作为一个簇返回
                return [(coordinates, weights)]
                
            # 估计需要的簇数量
            k = max(2, len(coordinates) // max_cluster_size)
            
            # 将坐标转换为numpy数组
            points = np.array(coordinates)
            
            # 应用K-Means聚类
            kmeans = KMeans(n_clusters=k, random_state=42)
            cluster_labels = kmeans.fit_predict(points)
            
            # 按簇分组
            cluster_dict = defaultdict(list)
            cluster_weights_dict = defaultdict(list)
            
            for i, label in enumerate(cluster_labels):
                cluster_dict[label].append(coordinates[i])
                cluster_weights_dict[label].append(weights[i])
            
            # 将分组结果转换为列表
            for label in cluster_dict:
                clusters.append((cluster_dict[label], cluster_weights_dict[label]))
        else:
            # 未知的聚类方法，将所有点作为一个簇返回
            clusters = [(coordinates, weights)]
            
        return clusters
    
    def find_optimal_point(self, coordinates: List[Tuple[float, float]], weights: List[float] = None, 
                           clustering_method: str = None, min_cluster_size: int = 5, max_cluster_size: int = 10, search_step: int = 100, algorithm_type: str = 'total_cost') -> Tuple[Tuple[float, float], int, Optional[Dict]]:
        """寻找最优集合点，考虑权重因素"""
        if not coordinates:
            return None

        # 初始化计算过程日志列表
        calculation_logs = []
        # 初始化聚类信息
        clustering_info = None
        iteration_count = 0
        print("\n开始计算最优集合点...")

        # 如果点位数量超过阈值且未指定聚类方法，默认使用HDBSCAN
        if len(coordinates) > self.cluster_threshold and clustering_method is None:
            clustering_method = 'hdbscan'
            
        # 应用聚类算法（如果指定）
        if clustering_method and len(coordinates) > self.cluster_threshold:
            print(f"使用{clustering_method}聚类算法处理{len(coordinates)}个点位")
            if clustering_method.lower() == 'hdbscan':
                # 使用HDBSCAN聚类
                cluster_centers = self.apply_hdbscan(coordinates, weights, min_cluster_size)
                clustering_info = {
                    'method': 'HDBSCAN',
                    'min_cluster_size': min_cluster_size,
                    'original_points': len(coordinates),
                    'clusters': len([c for c in cluster_centers if isinstance(c[0], tuple)])
                }
                print(f"HDBSCAN聚类完成: 原始点位数={len(coordinates)}, 聚类数={clustering_info['clusters']}")
            elif clustering_method.lower() == 'kmeans':
                # 使用容量约束的K-Means聚类
                cluster_centers = self.apply_capacity_kmeans(coordinates, weights, max_cluster_size)
                clustering_info = {
                    'method': 'Capacity Constrained K-Means',
                    'max_cluster_size': max_cluster_size,
                    'original_points': len(coordinates),
                    'clusters': len(cluster_centers)
                }
                print(f"K-Means聚类完成: 原始点位数={len(coordinates)}, 聚类数={clustering_info['clusters']}")
            else:
                # 未知的聚类方法，使用原始坐标
                cluster_centers = [(coord, weight) for coord, weight in zip(coordinates, weights)]
                print(f"未知聚类方法'{clustering_method}'，使用原始{len(coordinates)}个点位")
                
            # 提取聚类中心点和权重
            cluster_coordinates = [center[0] for center in cluster_centers]
            cluster_weights = [center[1] for center in cluster_centers]
            
            # 计算初始重心点（基于聚类中心）
            current_point = self.calculate_centroid(cluster_coordinates, cluster_weights)
            print(f"初始重心点（基于聚类中心）: ({current_point[0]:.6f}, {current_point[1]:.6f})")
            # 根据算法类型计算初始目标值
            if algorithm_type == 'min_max_time':
                current_time = self.calculate_max_time(current_point, coordinates)
                metric_name = "最长时间"
            else:
                current_time = self.calculate_total_time(current_point, coordinates, weights)
                metric_name = "总时间成本"
            
            if current_time is not None:
                hours = current_time // 3600
                minutes = (current_time % 3600) // 60
                seconds = current_time % 60
                print(f"初始{metric_name}: {hours}小时{minutes}分钟{seconds}秒")
            else:
                print(f"无法计算初始{metric_name}，可能是API请求失败")
        else:
            # 不使用聚类，直接计算重心
            current_point = self.calculate_centroid(coordinates, weights)
            print(f"初始重心点（不使用聚类）: ({current_point[0]:.6f}, {current_point[1]:.6f})")
            # 根据算法类型计算初始目标值
            if algorithm_type == 'min_max_time':
                current_time = self.calculate_max_time(current_point, coordinates)
                metric_name = "最长时间"
            else:
                current_time = self.calculate_total_time(current_point, coordinates, weights)
                metric_name = "总时间成本"
            
            if current_time is not None:
                hours = current_time // 3600
                minutes = (current_time % 3600) // 60
                seconds = current_time % 60
                print(f"初始{metric_name}: {hours}小时{minutes}分钟{seconds}秒")
            else:
                print(f"无法计算初始{metric_name}，可能是API请求失败")
            
        if current_time is None:
            print("无法计算时间成本，终止计算")
            return None

        # 动态设置搜索步长：计算所有输入地点到初始重心点的直线距离
        max_distance = 0
        for coord in coordinates:
            distance = self.calculate_distance(current_point, coord)
            if distance > max_distance:
                max_distance = distance
        
        # 根据传入的搜索步长参数设置搜索半径
        # 将米转换为经纬度差值（约1米 = 0.000009度）
        radius = search_step * 0.000009
        calculation_logs.append(f"设置搜索步长为{search_step}米（半径: {radius:.6f}度）")
        calculation_logs.append(f"最大距离: {max_distance:.0f}米")
        print(f"使用自定义搜索步长: {search_step}米（半径: {radius:.6f}度）")
        print(f"最大距离: {max_distance:.0f}米")
        
        # 更新搜索半径
        self.search_radius = radius
        print(f"\n开始迭代搜索最优点...")
        while radius >= self.min_radius:
            iteration_count += 1
            print(f"\n迭代 #{iteration_count} - 搜索半径: {radius:.6f}")
            improved = False

            # 在四个方向上搜索
            for dx, dy in self.directions:
                direction_name = {(1, 0): "东", (0, 1): "北", (-1, 0): "西", (0, -1): "南"}[(dx, dy)]
                # 生成新点并四舍五入到小数点后六位
                new_point = (round(current_point[0] + dx * radius, 6), round(current_point[1] + dy * radius, 6))
                print(f"  尝试{direction_name}方向点: ({new_point[0]:.6f}, {new_point[1]:.6f})")
                
                # 根据算法类型计算不同的目标值
                if algorithm_type == 'min_max_time':
                    # 最长时间最低算法：计算最长时间
                    new_metric = self.calculate_max_time(new_point, coordinates)
                    metric_name = "最长时间"
                else:
                    # 总成本最低算法：计算加权总时间
                    new_metric = self.calculate_total_time(new_point, coordinates, weights)
                    metric_name = "总时间成本"

                if new_metric is not None:
                    hours = new_metric // 3600
                    minutes = (new_metric % 3600) // 60
                    seconds = new_metric % 60
                    print(f"  {direction_name}方向{metric_name}: {hours}小时{minutes}分钟{seconds}秒")
                    
                    if new_metric < current_time:
                        print(f"  发现更优点！{metric_name}减少: {(current_time - new_metric) // 60}分{(current_time - new_metric) % 60}秒")
                        current_point = new_point
                        current_time = new_metric
                        improved = True
                        break
                    else:
                        print(f"  未改进，保持当前点")
                else:
                    print(f"  无法计算{direction_name}方向{metric_name}，跳过")

            if not improved:
                # 如果没有找到更好的点，减小搜索半径
                old_radius = radius
                radius /= 2
                print(f"未找到更优点，缩小搜索半径: {old_radius:.6f} -> {radius:.6f}")

        print(f"\n迭代搜索完成，共{iteration_count}次迭代")
        print(f"最终最优点: ({current_point[0]:.6f}, {current_point[1]:.6f})")
        hours = current_time // 3600
        minutes = (current_time % 3600) // 60
        seconds = current_time % 60
        print(f"最终总时间成本: {hours}小时{minutes}分钟{seconds}秒")
        
        # 计算各点到最优集合点的时间
        print(f"\n计算各点到最优集合点的时间...")
        individual_times = []
        for i, coord in enumerate(coordinates):
            try:
                # 计算从最优点到各个原始点的时间
                time_to_point = self.api.calculate_route(current_point, coord)
                if time_to_point is None:
                    # 如果calculate_route返回None，尝试使用calculate_route_time方法
                    try:
                        time_to_point = self.api.calculate_route_time(current_point, coord)
                    except AttributeError:
                        time_to_point = None
                
                if time_to_point is not None:
                    hours = time_to_point // 3600
                    minutes = (time_to_point % 3600) // 60
                    seconds = time_to_point % 60
                    individual_times.append({
                        'point_index': i,
                        'coordinates': coord,
                        'time_seconds': time_to_point,
                        'time_formatted': f"{hours}小时{minutes}分钟{seconds}秒",
                        'weight': weights[i]
                    })
                    print(f"  点{i+1} {coord}: {hours}小时{minutes}分钟{seconds}秒 (权重: {weights[i]})")
                else:
                    individual_times.append({
                        'point_index': i,
                        'coordinates': coord,
                        'time_seconds': None,
                        'time_formatted': "无法计算",
                        'weight': weights[i]
                    })
                    print(f"  点{i+1} {coord}: 无法计算时间 (权重: {weights[i]})")
            except Exception as e:
                individual_times.append({
                    'point_index': i,
                    'coordinates': coord,
                    'time_seconds': None,
                    'time_formatted': f"计算错误: {str(e)}",
                    'weight': weights[i]
                })
                print(f"  点{i+1} {coord}: 计算错误 - {str(e)} (权重: {weights[i]})")
        
        # 添加最终结果到计算日志
        calculation_logs.append(f"\n计算完成!")
        calculation_logs.append(f"最终最优点: ({current_point[0]:.6f}, {current_point[1]:.6f})")
        calculation_logs.append(f"总时间: {current_time}")
        calculation_logs.append(f"迭代次数: {iteration_count}")
        calculation_logs.append(f"各点到最优点的时间已计算完成")
        
        # 计算纯时间总和（不乘权重，用于最终显示）
        pure_total_time = self.calculate_pure_total_time(current_point, coordinates)
        
        # 返回字典格式，与其他find_optimal_point函数保持一致
        return {
            'optimal_point': current_point,
            'total_time': current_time,
            'pure_total_time': pure_total_time,  # 添加纯时间总和字段
            'clustering_info': clustering_info,
            'calculation_logs': calculation_logs,  # 添加计算过程日志
            'individual_times': individual_times  # 添加各点到最优点的时间信息
        }

    def format_result(self, point: Tuple[float, float], total_time: int, clustering_info: Optional[Dict] = None) -> str:
        """格式化结果输出，包含最近POI点信息"""
        hours = total_time // 3600
        minutes = (total_time % 3600) // 60
        seconds = total_time % 60
        
        # 获取最优点的结构化地址
        address_info = self.api.reverse_geocode(point)
        address_str = ""
        poi_str = ""
        
        if address_info:
            # 处理formatted_address字段
            formatted_address = address_info.get("formatted_address", "")
            # 处理可能的数据类型
            if isinstance(formatted_address, list):
                formatted_address = formatted_address[0] if formatted_address else ""
            elif isinstance(formatted_address, str):
                formatted_address = formatted_address
            else:
                formatted_address = str(formatted_address)
                
            address_str = f"\n最优集合点地址：{formatted_address}"
            
            # 添加详细的结构化地址信息
            province = address_info.get("province", "")
            city = address_info.get("city", "")
            district = address_info.get("district", "")
            township = address_info.get("township", "")
            street = address_info.get("street", "")
            street_number = address_info.get("street_number", "")
            
            # 通用函数处理可能是列表或其他类型的字段
            def process_field(field):
                if isinstance(field, list):
                    return field[0] if field else ""
                elif isinstance(field, str):
                    return field
                elif field is None:
                    return ""
                else:
                    return str(field)
            
            # 处理各个字段
            province = process_field(province)
            city = process_field(city)
            district = process_field(district)
            township = process_field(township)
            street = process_field(street)
            
            # 处理street_number可能是字典的情况
            street_number_str = ""
            if isinstance(street_number, dict):
                # 处理street字段
                if "street" in street_number:
                    street_value = street_number["street"]
                    street_value = process_field(street_value)
                    street_number_str += street_value
                
                # 处理number字段
                if "number" in street_number:
                    number_value = street_number["number"]
                    number_value = process_field(number_value)
                    street_number_str += number_value
                
                # 添加位置信息
                if "location" in street_number:
                    location = street_number["location"]
                    if location:  # 确保location不为空
                        street_number_str += f" (位置: {location})"
                
                street_number = street_number_str
            else:
                street_number = process_field(street_number)
            
            # 构建地址字符串
            address_str += "\n详细地址信息："
            if province: address_str += f"\n  省/自治区/直辖市：{province}"
            if city: address_str += f"\n  城市：{city}"
            if district: address_str += f"\n  区/县：{district}"
            if township: address_str += f"\n  乡镇/街道：{township}"
            if street: address_str += f"\n  道路：{street}"
            if street_number: address_str += f"\n  门牌号：{street_number}"
            
            # 处理最近POI点信息
            nearest_poi = address_info.get("nearest_poi", None)
            if nearest_poi:
                poi_name = nearest_poi.get("name", "未知")
                poi_distance = nearest_poi.get("distance", "未知")
                poi_direction = nearest_poi.get("direction", "未知")
                poi_type = nearest_poi.get("type", "")
                
                poi_str = "\n\n最近POI点信息："
                poi_str += f"\n  名称：{poi_name}"
                poi_str += f"\n  距离：{poi_distance}米"
                poi_str += f"\n  方向：{poi_direction}"
                if poi_type:
                    poi_str += f"\n  类型：{poi_type}"
        
        # 构建结果字符串
        result = f"最优集合点坐标：({point[0]:.6f}, {point[1]:.6f}){address_str}{poi_str}\n" \
               f"总时间成本：{hours}小时{minutes}分钟{seconds}秒"
        
        # 添加聚类信息（如果有）
        if clustering_info:
            result += f"\n\n聚类算法：{clustering_info['method']}"
            if 'min_cluster_size' in clustering_info:
                result += f"\n最小簇大小：{clustering_info['min_cluster_size']}"
            if 'max_cluster_size' in clustering_info:
                result += f"\n最大簇大小：{clustering_info['max_cluster_size']}"
            result += f"\n原始点位数量：{clustering_info['original_points']}"
            result += f"\n聚类后簇数量：{clustering_info['clusters']}"
        
        return result



    # 此处删除重复的calculate_total_time方法，使用上面已定义的方法

    def find_optimal_point_with_clustering(self, coordinates, weights=None, method='HDBSCAN', param=5, search_step=100, algorithm_type='total_cost'):
        """
        使用聚类算法寻找最优集合点
        
        参数:
            coordinates: 坐标列表，每个元素为(lat, lng)
            weights: 权重列表，与坐标列表一一对应
            method: 聚类方法，'HDBSCAN'或'CCKM'
            param: 聚类参数，对于HDBSCAN是最小簇大小，对于CCKM是最大簇大小
            
        返回:
            包含最优点信息的字典
        """
        # 检查坐标列表是否为空或None
        if not coordinates:
            raise ValueError("坐标列表不能为空")
        
        # 如果没有提供权重，则使用默认权重1.0
        if weights is None:
            weights = [1.0] * len(coordinates)
        
        # 确保坐标和权重长度一致
        if len(coordinates) != len(weights):
            raise ValueError("坐标列表和权重列表长度必须一致")
        
        # 执行聚类
        clusters = self._perform_clustering(coordinates, weights, method, param)
        if not clusters:
            raise ValueError(f"聚类失败，请尝试其他聚类方法或参数")
        
        # 计算每个簇的重心
        cluster_centroids = []
        cluster_weights = []
        
        for cluster_coords, cluster_weights_list in clusters:
            if not cluster_coords:
                continue
            centroid = self.calculate_centroid(cluster_coords, cluster_weights_list)
            if centroid:
                cluster_centroids.append(centroid)
                # 簇的权重是其包含的所有点的权重之和
                cluster_weights.append(sum(cluster_weights_list))
        
        if not cluster_centroids:
            raise ValueError("无法计算簇重心，请检查聚类结果")
        
        # 使用簇重心计算最优点
        result = self.find_optimal_point(cluster_centroids, cluster_weights, search_step, algorithm_type)
        
        # 计算最优点到原始所有点的目标值（根据算法类型）
        optimal_point = result['optimal_point']
        if algorithm_type == 'min_max_time':
            total_time = self.calculate_max_time(optimal_point, coordinates)
        else:
            total_time = self.calculate_total_time(optimal_point, coordinates, weights)
        
        # 计算各点到最优集合点的时间（使用原始坐标和权重）
        print(f"\n计算各点到最优集合点的时间...")
        individual_times = []
        for i, coord in enumerate(coordinates):
            try:
                # 计算从最优点到各个原始点的时间
                time_to_point = self.api.calculate_route(optimal_point, coord)
                if time_to_point is None:
                    # 如果calculate_route返回None，尝试使用calculate_route_time方法
                    try:
                        time_to_point = self.api.calculate_route_time(optimal_point, coord)
                    except AttributeError:
                        time_to_point = None
                
                if time_to_point is not None:
                    hours = time_to_point // 3600
                    minutes = (time_to_point % 3600) // 60
                    seconds = time_to_point % 60
                    individual_times.append({
                        'point_index': i,
                        'coordinates': coord,
                        'time_seconds': time_to_point,
                        'time_formatted': f"{hours}小时{minutes}分钟{seconds}秒",
                        'weight': weights[i]
                    })
                    print(f"  点{i+1} {coord}: {hours}小时{minutes}分钟{seconds}秒 (权重: {weights[i]})")
                else:
                    individual_times.append({
                        'point_index': i,
                        'coordinates': coord,
                        'time_seconds': None,
                        'time_formatted': "无法计算",
                        'weight': weights[i]
                    })
                    print(f"  点{i+1} {coord}: 无法计算时间 (权重: {weights[i]})")
            except Exception as e:
                individual_times.append({
                    'point_index': i,
                    'coordinates': coord,
                    'time_seconds': None,
                    'time_formatted': f"计算错误: {str(e)}",
                    'weight': weights[i]
                })
                print(f"  点{i+1} {coord}: 计算错误 - {str(e)} (权重: {weights[i]})")
        
        # 计算纯时间总和（不乘权重，用于最终显示）
        pure_total_time = self.calculate_pure_total_time(optimal_point, coordinates)
        
        # 更新结果
        result['total_time'] = total_time
        result['pure_total_time'] = pure_total_time  # 添加纯时间总和字段
        result['clusters'] = clusters  # 保存聚类结果列表，而不是聚类数量
        result['cluster_count'] = len(clusters)  # 单独保存聚类数量
        result['clustering_method'] = method
        result['clustering_param'] = param
        result['individual_times'] = individual_times  # 添加各点到最优点的时间信息
        
        return result
