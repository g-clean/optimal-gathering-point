import requests
import time
import json
import math
import re
from typing import Dict, List, Tuple, Optional, Union, Literal


class MapAPI:
    """地图API抽象基类，定义了地图服务的通用接口"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 1  # 重试延迟时间（秒）
        self.api_call_count = 0  # API调用计数器
        
    def _preprocess_address(self, address: str) -> str:
        """预处理地址字符串，处理括号等特殊字符
        
        Args:
            address: 原始地址字符串
            
        Returns:
            处理后的地址字符串
        """
        # 将括号替换为空格，保留括号内的内容
        processed = re.sub(r'[\(\)（）]', ' ', address)
        # 去除多余空格
        processed = re.sub(r'\s+', ' ', processed).strip()
        return processed
        
    def _handle_api_request(self, request_func, error_msg_prefix, *args, **kwargs):
        """处理API请求，支持自动重试
        
        Args:
            request_func: 请求函数，接受*args和**kwargs参数
            error_msg_prefix: 错误消息前缀
            *args: 传递给请求函数的位置参数
            **kwargs: 传递给请求函数的关键字参数
            
        Returns:
            请求函数的返回值
            
        Raises:
            ValueError: 请求失败且重试次数用尽时抛出
        """
        retries = 0
        last_error = None
        
        # 增加API调用计数
        self.api_call_count += 1
        
        while retries <= self.max_retries:
            try:
                return request_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # 检查是否为QPS超限错误
                if any(limit_err in error_str for limit_err in ['qps', 'exceeded', 'limit', 'cuqps_has_exceeded_the_limit']):
                    retries += 1
                    if retries <= self.max_retries:
                        print(f"{error_msg_prefix}遇到API限流，等待{self.retry_delay}秒后第{retries}次重试...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        print(f"{error_msg_prefix}重试{self.max_retries}次后仍然失败: {str(e)}")
                else:
                    # 非限流错误，直接抛出
                    break
        
        # 所有重试都失败，抛出最后一个错误
        if last_error:
            raise last_error
        return None
        
    @staticmethod
    def validate_api_key(api_key: str, api_type: str) -> Tuple[bool, str]:
        """验证API密钥格式是否符合规则
        
        Args:
            api_key: API密钥
            api_type: API类型，可选值为 'amap', 'baidu', 'tencent'
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if api_type.lower() == "amap":
            return AmapAPI.validate_api_key(api_key)
        elif api_type.lower() == "baidu":
            return BaiduMapAPI.validate_api_key(api_key)
        elif api_type.lower() == "tencent":
            return TencentMapAPI.validate_api_key(api_key)
        else:
            return False, f"不支持的地图API类型: {api_type}"
        
    def geocode(self, address: str, city: str = "") -> Optional[Tuple[float, float]]:
        """将地址转换为经纬度坐标，由子类实现
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            
        Returns:
            经纬度坐标元组 (经度, 纬度) 或 None
        """
        raise NotImplementedError("子类必须实现此方法")
        
    def calculate_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[int]:
        """计算两点之间的驾车时间（秒），由子类实现"""
        raise NotImplementedError("子类必须实现此方法")
        
    def reverse_geocode(self, location: Tuple[float, float]) -> Optional[Dict[str, str]]:
        """将经纬度坐标转换为结构化地址，由子类实现"""
        raise NotImplementedError("子类必须实现此方法")
        
    def batch_geocode(self, addresses: List[str], city: str = "") -> List[Optional[Tuple[float, float]]]:
        """批量将地址转换为经纬度坐标
        
        Args:
            addresses: 地址字符串列表
            city: 城市名称，用于限制搜索范围
            
        Returns:
            经纬度坐标元组列表
        """
        results = []
        for address in addresses:
            try:
                result = self.geocode(address, city=city)
                results.append(result)
                # 添加延时以避免触发API限制
                time.sleep(0.2)  # 增加延时时间，降低触发限流的可能性
            except Exception as e:
                print(f"批量地理编码错误，地址：{address}，错误：{str(e)}")
                results.append(None)
                # 发生错误时增加等待时间
                time.sleep(1.0)
        return results


class AmapAPI(MapAPI):
    """高德地图API实现"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://restapi.amap.com/v3"
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:
        """验证高德地图API密钥格式
        
        规则：32位（数字英文字母无大写字母）
        
        Args:
            api_key: API密钥
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not api_key:
            return False, "API密钥不能为空"
        
        if len(api_key) != 32:
            return False, f"高德地图API密钥长度应为32位，当前长度为{len(api_key)}位"
        
        if not re.match(r'^[a-z0-9]{32}$', api_key):
            return False, "高德地图API密钥只能包含数字和小写字母"
        
        return True, ""

    def geocode(self, address: str, city=None):
        """
        将地址转换为经纬度坐标
        
        参数:
            address: 要转换的地址
            city: 城市名称，用于限制搜索范围
            
        返回:
            成功返回(纬度, 经度)元组，失败返回None
        """
        # 调用search_locations获取候选列表，然后返回第一个结果
        candidates = self.search_locations(address, city)
        if candidates:
            return (candidates[0]['lat'], candidates[0]['lng'])
        return None
    
    def search_locations(self, address: str, city: str = "", limit: int = 5) -> List[Dict]:
        """搜索地址并返回候选地点列表
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            limit: 返回结果数量限制，默认5个
            
        返回:
            候选地点列表，每个元素包含name, address, type, lat, lng字段
        """
        # 预处理地址
        address = self._preprocess_address(address)
        
        url = "https://restapi.amap.com/v3/place/text"
        params = {
            "key": self.api_key,
            "keywords": address,
            "output": "json",
            "offset": min(limit, 20),  # 高德API最多返回20个结果
            "page": 1,
            "extensions": "all"  # 返回详细信息
        }
        
        # 如果提供了城市，添加到请求参数中
        if city:
            params["city"] = city
        
        def request_func():
            response = requests.get(url, params=params)
            data = response.json()
            
            # 添加调试输出，显示API请求和响应信息
            print(f"高德地图关键字搜索请求: {url}")
            print(f"请求参数: {params}")
            print(f"响应数据: {data}")
            
            candidates = []
            if data["status"] == "1" and int(data["count"]) > 0:
                # 关键字搜索API返回的是pois数组
                for poi in data["pois"][:limit]:
                    location = poi["location"]
                    lng, lat = map(float, location.split(","))
                    
                    candidate = {
                        'name': poi.get("name", "未知地点"),
                        'address': poi.get("address", ""),
                        'type': poi.get("type", "未知类型"),
                        'lat': lat,
                        'lng': lng
                    }
                    candidates.append(candidate)
                    
                print(f"解析结果: 搜索'{address}' -> 找到{len(candidates)}个候选地点")
                return candidates
            else:
                error_info = data.get("info", "未知错误")
                print(f"高德地图关键字搜索失败: {error_info}")
                raise ValueError(f"高德地图API错误: {error_info}")
                
        try:
            return self._handle_api_request(request_func, "高德地图地理编码")
        except requests.RequestException as e:
            raise ValueError(f"网络请求错误: {str(e)}")
        except (KeyError, IndexError, ValueError) as e:
            if isinstance(e, ValueError) and "高德地图API错误" in str(e):
                raise
            raise ValueError(f"解析地址失败: {str(e)}")

    def calculate_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[int]:
        """计算两点之间的驾车时间（秒）
        
        Args:
            origin: 起点坐标元组 (纬度, 经度)
            destination: 终点坐标元组 (纬度, 经度)
            
        Returns:
            路线规划的时间（秒）或 None
        """
        url = f"{self.base_url}/direction/driving"
        # 确保经度在前，纬度在后，且小数点不超过6位
        origin_lon = round(origin[1], 6)
        origin_lat = round(origin[0], 6)
        dest_lon = round(destination[1], 6)
        dest_lat = round(destination[0], 6)
        
        params = {
            "key": self.api_key,
            "origin": f"{origin_lon},{origin_lat}",  # 高德地图API使用经度,纬度的顺序
            "destination": f"{dest_lon},{dest_lat}",  # 高德地图API使用经度,纬度的顺序
            "output": "JSON"
        }

        def request_func():
            response = requests.get(url, params=params)
            data = response.json()

            if data.get("status") == "1" and data.get("route"):
                # 返回路线规划的时间，单位为秒
                return int(data["route"]["paths"][0]["duration"])
            else:
                # 记录API返回的错误信息
                error_info = data.get("info", "未知错误")
                print(f"高德地图路径规划失败：URL={url}, Params={params}, 状态码={data.get('status')}, 错误信息={error_info}")
                # 如果返回的数据中包含route但结构不符合预期，记录详细信息
                if data.get("route") and not data.get("route").get("paths"):
                    print(f"高德地图返回的route数据结构异常：{data.get('route')}")
                # 如果是QPS超限错误，抛出异常以便触发重试机制
                if "CUQPS_HAS_EXCEEDED_THE_LIMIT" in data.get("info", ""):
                    raise ValueError(f"高德地图API错误: {error_info}")
                return None
                
        try:
            return self._handle_api_request(request_func, "高德地图路径规划")
        except Exception as e:
            # 添加更详细的错误日志
            print(f"高德地图路径规划错误：URL={url}, Params={params}, Error={str(e)}")
            return None
            
    def reverse_geocode(self, location: Tuple[float, float]) -> Optional[Dict[str, str]]:
        """将经纬度坐标转换为结构化地址，并返回附近POI信息"""
        url = f"{self.base_url}/geocode/regeo"
        params = {
            "key": self.api_key,
            "location": f"{location[1]},{location[0]}",  # 高德地图API使用经度,纬度的顺序
            "extensions": "all",  # 使用全部返回信息，包含POI数据
            "output": "JSON"
        }

        def request_func():
            response = requests.get(url, params=params)
            data = response.json()

            if data.get("status") == "1" and data.get("regeocode"):
                regeocode = data["regeocode"]
                address_component = regeocode.get("addressComponent", {})
                formatted_address = regeocode.get("formatted_address", "")
                
                # 获取POI信息
                pois = regeocode.get("pois", [])
                nearest_poi = None
                if pois and len(pois) > 0:
                    # 找到距离最小的POI作为最近的POI点
                    nearest_poi = min(pois, key=lambda poi: float(poi.get('distance', float('inf'))))
                
                result = {
                    "formatted_address": formatted_address,
                    "province": address_component.get("province", ""),
                    "city": address_component.get("city", ""),
                    "district": address_component.get("district", ""),
                    "township": address_component.get("township", ""),
                    "street": address_component.get("street", ""),
                    "street_number": address_component.get("streetNumber", ""),
                    "nearest_poi": nearest_poi,  # 添加最近POI点信息
                    "pois": pois  # 添加所有POI点信息
                }
                return result
            else:
                # 如果是QPS超限错误，抛出异常以便触发重试机制
                error_info = data.get("info", "未知错误")
                if "CUQPS_HAS_EXCEEDED_THE_LIMIT" in error_info:
                    raise ValueError(f"高德地图API错误: {error_info}")
                return None
                
        try:
            return self._handle_api_request(request_func, "高德地图逆地理编码")
        except Exception as e:
            print(f"高德地图逆地理编码错误：{str(e)}")
            return None


class BaiduMapAPI(MapAPI):
    """百度地图API实现"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "http://api.map.baidu.com"
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:
        """验证百度地图API密钥格式
        
        规则：33位（数字英文字母有大小写字母）
        
        Args:
            api_key: API密钥
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not api_key:
            return False, "API密钥不能为空"
        
        if len(api_key) != 32:
            return False, f"百度地图API密钥长度应为32位，当前长度为{len(api_key)}位"
        
        if not re.match(r'^[a-zA-Z0-9]{32}$', api_key):
            return False, "百度地图API密钥只能包含数字和英文字母（区分大小写）"
        
        return True, ""
    
    def geocode(self, address: str, city: str = "") -> Optional[Tuple[float, float]]:
        """将地址转换为经纬度坐标
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            
        Returns:
            经纬度坐标元组 (经度, 纬度) 或 None
        """
        # 调用search_locations获取候选列表，然后返回第一个结果
        candidates = self.search_locations(address, city)
        if candidates:
            return (candidates[0]['lat'], candidates[0]['lng'])
        return None
    
    def search_locations(self, address: str, city: str = "", limit: int = 5) -> List[Dict]:
        """搜索地址并返回候选地点列表
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            limit: 返回结果数量限制，默认5个
            
        返回:
            候选地点列表，每个元素包含name, address, type, lat, lng字段
        """
        # 调用search_locations获取候选列表，然后返回第一个结果
        candidates = self.search_locations(address, city)
        if candidates:
            return (candidates[0]['lat'], candidates[0]['lng'])
        return None
    
    def search_locations(self, address: str, city: str = "", limit: int = 5) -> List[Dict]:
        """搜索地址并返回候选地点列表
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            limit: 返回结果数量限制，默认5个
            
        返回:
            候选地点列表，每个元素包含name, address, type, lat, lng字段
        """
        # 百度地图使用地点搜索API来获取多个候选结果
        # 预处理地址，处理括号等特殊字符
        processed_address = self._preprocess_address(address)
        
        url = f"{self.base_url}/place/v2/search"
        params = {
            "ak": self.api_key,
            "query": processed_address,
            "output": "json",
            "page_size": min(limit, 20),  # 百度API最多返回20个结果
            "page_num": 0
        }
        
        # 如果指定了城市，添加城市参数
        if city:
            params["region"] = city
        
        def request_func():
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()  # 检查HTTP状态码
                
                # 检查响应内容是否为空
                if not response.text.strip():
                    raise ValueError("API返回空响应")
                
                # 尝试解析JSON
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    # 如果JSON解析失败，记录响应内容
                    print(f"百度地图API返回非JSON格式响应: {response.text[:200]}")
                    raise ValueError(f"API返回非JSON格式响应: {str(e)}")
                
                candidates = []
                if data.get("status") == 0 and "results" in data:
                    for result in data["results"][:limit]:
                        location = result.get("location", {})
                        if "lng" in location and "lat" in location:
                            # 百度地图返回的是BD09坐标系，需要转换为GCJ-02坐标系
                            lng, lat = self._bd09_to_gcj02(location["lng"], location["lat"])
                            
                            candidate = {
                                'name': result.get("name", "未知地点"),
                                'address': result.get("address", ""),
                                'type': result.get("detail_info", {}).get("tag", "未知类型"),
                                'lat': lat,
                                'lng': lng
                            }
                            candidates.append(candidate)
                    
                    print(f"百度地图搜索结果: 搜索'{address}' -> 找到{len(candidates)}个候选地点")
                    return candidates
                else:
                    # 检查是否为QPS超限错误
                    error_msg = data.get("message", "")
                    status = data.get("status", "unknown")
                    print(f"百度地图API错误: status={status}, message={error_msg}")
                    
                    if any(limit_err in error_msg.lower() for limit_err in ['qps', 'exceeded', 'limit']):
                        raise ValueError(f"百度地图API错误: {error_msg}")
                    return []
                    
            except requests.exceptions.RequestException as e:
                print(f"百度地图API网络请求错误: {str(e)}")
                raise ValueError(f"网络请求失败: {str(e)}")
                
        try:
            return self._handle_api_request(request_func, "百度地图地点搜索")
        except Exception as e:
            print(f"百度地图地点搜索错误：{str(e)}")
            return []
    
    def calculate_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[int]:
        """计算两点之间的驾车时间（秒）
        
        Args:
            origin: 起点坐标元组 (纬度, 经度)
            destination: 终点坐标元组 (纬度, 经度)
            
        Returns:
            路线规划的时间（秒）或 None
        """
        # 将GCJ-02坐标转换为BD09坐标
        origin_bd = self._gcj02_to_bd09(origin[0], origin[1])
        dest_bd = self._gcj02_to_bd09(destination[0], destination[1])
        
        # 确保小数点后不超过6位
        origin_lat = round(origin_bd[1], 6)
        origin_lng = round(origin_bd[0], 6)
        dest_lat = round(dest_bd[1], 6)
        dest_lng = round(dest_bd[0], 6)
        
        url = f"{self.base_url}/direction/v2/driving"
        params = {
            "ak": self.api_key,
            "origin": f"{origin_lat},{origin_lng}",  # 百度地图API使用纬度,经度的顺序
            "destination": f"{dest_lat},{dest_lng}",  # 百度地图API使用纬度,经度的顺序
            "output": "json"
        }
        
        def request_func():
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()  # 检查HTTP状态码
                
                # 检查响应内容是否为空
                if not response.text.strip():
                    raise ValueError("API返回空响应")
                
                # 尝试解析JSON
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    # 如果JSON解析失败，记录响应内容
                    print(f"百度地图API返回非JSON格式响应: {response.text[:200]}")
                    raise ValueError(f"API返回非JSON格式响应: {str(e)}")
                
                if data.get("status") == 0 and "result" in data and "routes" in data["result"]:
                    # 返回路线规划的时间，单位为秒
                    return int(data["result"]["routes"][0]["duration"])
                else:
                    # 检查是否为QPS超限错误
                    error_msg = data.get("message", "")
                    status = data.get("status", "unknown")
                    print(f"百度地图API错误: status={status}, message={error_msg}")
                    
                    if any(limit_err in error_msg.lower() for limit_err in ['qps', 'exceeded', 'limit']):
                        raise ValueError(f"百度地图API错误: {error_msg}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"百度地图API网络请求错误: {str(e)}")
                raise ValueError(f"网络请求失败: {str(e)}")
                
        try:
            return self._handle_api_request(request_func, "百度地图路径规划")
        except Exception as e:
            # 添加更详细的错误日志
            print(f"百度地图路径规划错误：URL={url}, Params={params}, Error={str(e)}")
            return None

    def _bd09_to_gcj02(self, bd_lng, bd_lat):
        """BD09坐标系转GCJ-02坐标系"""
        x_pi = 3.14159265358979324 * 3000.0 / 180.0
        x = bd_lng - 0.0065
        y = bd_lat - 0.006
        z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
        gg_lng = z * math.cos(theta)
        gg_lat = z * math.sin(theta)
        return gg_lng, gg_lat
        
    def reverse_geocode(self, location: Tuple[float, float]) -> Optional[Dict[str, str]]:
        """将经纬度坐标转换为结构化地址
        
        Args:
            location: 坐标元组 (纬度, 经度)
            
        Returns:
            结构化地址信息字典或 None
        """
        # 将GCJ-02坐标转换为BD09坐标
        location_bd = self._gcj02_to_bd09(location[0], location[1])
        
        # 确保小数点后不超过6位
        location_lat = round(location_bd[1], 6)
        location_lng = round(location_bd[0], 6)
        
        url = f"{self.base_url}/reverse_geocoding/v3/"
        params = {
            "ak": self.api_key,
            "location": f"{location_lat},{location_lng}",  # 百度地图API使用纬度,经度的顺序
            "output": "json",
            "coordtype": "bd09ll",  # 坐标类型：BD09经纬度坐标
            "extensions_poi": "1",  # 是否显示周边POI列表
            "entire_poi": "1",  # 是否显示完整POI信息
            "sort_strategy": "distance"  # POI排序策略：按距离排序
        }
        
        def request_func():
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()  # 检查HTTP状态码
                
                # 检查响应内容是否为空
                if not response.text.strip():
                    raise ValueError("API返回空响应")
                
                # 尝试解析JSON
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    # 如果JSON解析失败，记录响应内容
                    print(f"百度地图API返回非JSON格式响应: {response.text[:200]}")
                    raise ValueError(f"API返回非JSON格式响应: {str(e)}")
                
                if data.get("status") == 0 and "result" in data:
                    result_data = data["result"]
                    address_component = result_data.get("addressComponent", {})
                    formatted_address = result_data.get("formatted_address", "")
                    
                    # 获取POI信息
                    pois = result_data.get("pois", [])
                    nearest_poi = None
                    if pois and len(pois) > 0:
                        # 找到距离最小的POI作为最近的POI点
                        nearest_poi = min(pois, key=lambda poi: float(poi.get('distance', float('inf'))))
                    
                    result = {
                        "formatted_address": formatted_address,
                        "province": address_component.get("province", ""),
                        "city": address_component.get("city", ""),
                        "district": address_component.get("district", ""),
                        "township": address_component.get("town", ""),
                        "street": address_component.get("street", ""),
                        "street_number": address_component.get("street_number", ""),
                        "nearest_poi": nearest_poi,  # 添加最近POI点信息
                        "pois": pois  # 添加所有POI点信息
                    }
                    return result
                else:
                    # 检查是否为QPS超限错误
                    error_msg = data.get("message", "")
                    status = data.get("status", "unknown")
                    print(f"百度地图API错误: status={status}, message={error_msg}")
                    
                    if any(limit_err in error_msg.lower() for limit_err in ['qps', 'exceeded', 'limit']):
                        raise ValueError(f"百度地图API错误: {error_msg}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"百度地图API网络请求错误: {str(e)}")
                raise ValueError(f"网络请求失败: {str(e)}")
                
        try:
            return self._handle_api_request(request_func, "百度地图逆地理编码")
        except Exception as e:
            print(f"百度地图逆地理编码错误：{str(e)}")
            return None
    
    def _gcj02_to_bd09(self, lng, lat):
        """GCJ-02坐标系转BD09坐标系"""
        x_pi = 3.14159265358979324 * 3000.0 / 180.0
        z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * x_pi)
        theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * x_pi)
        bd_lng = z * math.cos(theta) + 0.0065
        bd_lat = z * math.sin(theta) + 0.006
        return bd_lng, bd_lat


class TencentMapAPI(MapAPI):
    """腾讯地图API实现"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://apis.map.qq.com"
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:
        """验证腾讯地图API密钥格式
        
        规则：35位（数字英文字母只有大写字母，每5个数字或字母后-连接例如ABCDE-FGHIJ-KLMN4-OPQ2R-STUVW-S7Y6Z）
        
        Args:
            api_key: API密钥
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not api_key:
            return False, "API密钥不能为空"
        
        # 移除所有连字符后应该是30个字符
        key_without_dash = api_key.replace('-', '')
        if len(key_without_dash) != 30:
            return False, f"腾讯地图API密钥格式错误，移除连字符后应为30个字符，当前为{len(key_without_dash)}个字符"
        
        # 检查是否只包含大写字母和数字
        if not re.match(r'^[A-Z0-9]+$', key_without_dash):
            return False, "腾讯地图API密钥只能包含大写字母和数字"
        
        # 检查格式是否为每5个字符一组，用连字符分隔
        if not re.match(r'^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$', api_key):
            return False, "腾讯地图API密钥格式错误，应为每5个字符一组，用连字符分隔"
        
        return True, ""
    
    def geocode(self, address: str, city: str = "") -> Optional[Tuple[float, float]]:
        """将地址转换为经纬度坐标
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            
        Returns:
            经纬度坐标元组 (经度, 纬度) 或 None
        """
        # 调用search_locations获取候选地点列表，然后返回第一个结果
        candidates = self.search_locations(address, city, limit=1)
        if candidates:
            first_candidate = candidates[0]
            return (first_candidate['lat'], first_candidate['lng'])
        return None
    
    def search_locations(self, address: str, city: str = "", limit: int = 5) -> List[Dict[str, any]]:
        """搜索地址对应的候选地点列表
        
        Args:
            address: 地址字符串
            city: 城市名称，用于限制搜索范围
            limit: 返回结果数量限制，默认5个
            
        Returns:
            候选地点列表，每个地点包含name、address、type、lat、lng字段
        """
        # 腾讯地图使用地点搜索API来获取多个候选结果
        # 预处理地址，处理括号等特殊字符
        processed_address = self._preprocess_address(address)
        
        url = f"{self.base_url}/ws/place/v1/search"
        params = {
            "key": self.api_key,
            "keyword": processed_address,
            "page_size": min(limit, 20),  # 腾讯API最多返回20个结果
            "page_index": 1
        }
        
        # 如果指定了城市，添加城市参数
        if city:
            params["boundary"] = f"region({city})"
        
        def request_func():
            response = requests.get(url, params=params)
            data = response.json()
            
            print(f"腾讯地图搜索请求: {url}")
            print(f"请求参数: {params}")
            print(f"响应数据: {data}")
            
            candidates = []
            if data.get("status") == 0 and "data" in data:
                for result in data["data"][:limit]:
                    location = result.get("location", {})
                    if "lat" in location and "lng" in location:
                        candidate = {
                            'name': result.get("title", "未知地点"),
                            'address': result.get("address", ""),
                            'type': result.get("category", "未知类型"),
                            'lat': location["lat"],
                            'lng': location["lng"]
                        }
                        candidates.append(candidate)
                
                print(f"腾讯地图搜索结果: 搜索'{address}' -> 找到{len(candidates)}个候选地点")
                return candidates
            else:
                # 检查是否为QPS超限错误
                error_msg = data.get("message", "")
                if any(limit_err in error_msg.lower() for limit_err in ['qps', 'exceeded', 'limit']):
                    raise ValueError(f"腾讯地图API错误: {error_msg}")
                return []
                
        try:
            return self._handle_api_request(request_func, "腾讯地图地点搜索")
        except Exception as e:
            print(f"腾讯地图地点搜索错误：{str(e)}")
            return []
    
    def calculate_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Optional[int]:
        """计算两点之间的驾车时间（秒）
        
        Args:
            origin: 起点坐标元组 (纬度, 经度)
            destination: 终点坐标元组 (纬度, 经度)
            
        Returns:
            路线规划的时间（秒）或 None
        """
        # 确保小数点后不超过6位
        origin_lat = round(origin[0], 6)
        origin_lng = round(origin[1], 6)
        dest_lat = round(destination[0], 6)
        dest_lng = round(destination[1], 6)
        
        url = f"{self.base_url}/ws/direction/v1/driving"
        params = {
            "key": self.api_key,
            "from": f"{origin_lat},{origin_lng}",  # 腾讯地图API使用纬度,经度的顺序
            "to": f"{dest_lat},{dest_lng}",  # 腾讯地图API使用纬度,经度的顺序
            "output": "json"  # 添加输出格式参数
        }
        
        def request_func():
            response = requests.get(url, params=params)
            data = response.json()
            
            # 添加详细的调试信息
            print(f"腾讯地图API请求URL: {url}")
            print(f"腾讯地图API请求参数: {params}")
            print(f"腾讯地图API响应数据: {data}")
            
            if data.get("status") == 0 and "result" in data and "routes" in data["result"]:
                # 返回路线规划的时间，单位为秒
                return int(data["result"]["routes"][0]["duration"])
            else:
                # 检查是否为QPS超限错误
                error_msg = data.get("message", "")
                if any(limit_err in error_msg.lower() for limit_err in ['qps', 'exceeded', 'limit']):
                    raise ValueError(f"腾讯地图API错误: {error_msg}")
                print(f"腾讯地图API返回错误: status={data.get('status')}, message={data.get('message')}")
                return None
                
        try:
            return self._handle_api_request(request_func, "腾讯地图路径规划")
        except Exception as e:
            # 添加更详细的错误日志
            print(f"腾讯地图路径规划错误：URL={url}, Params={params}, Error={str(e)}")
            return None
            
    def reverse_geocode(self, location: Tuple[float, float]) -> Optional[Dict[str, str]]:
        """将经纬度坐标转换为结构化地址
        
        Args:
            location: 坐标元组 (纬度, 经度)
            
        Returns:
            结构化地址信息字典或 None
        """
        # 确保小数点后不超过6位
        location_lat = round(location[0], 6)
        location_lng = round(location[1], 6)
        
        url = f"{self.base_url}/ws/geocoder/v1/"
        params = {
            "key": self.api_key,
            "location": f"{location_lat},{location_lng}",  # 腾讯地图API使用纬度,经度的顺序
            "get_poi": "1",  # 获取POI信息
            "output": "json"
        }
        
        def request_func():
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get("status") == 0 and "result" in data:
                result_data = data["result"]
                address_component = result_data.get("address_component", {})
                formatted_address = result_data.get("address", "")
                
                # 获取POI信息
                pois = result_data.get("pois", [])
                nearest_poi = None
                if pois and len(pois) > 0:
                    # 腾讯地图POI中包含_distance字段，表示到逆地址解析传入坐标的直线距离
                    if any('_distance' in poi for poi in pois):
                        nearest_poi = min(pois, key=lambda poi: float(poi.get('_distance', float('inf'))))
                    elif any('distance' in poi for poi in pois):
                        nearest_poi = min(pois, key=lambda poi: float(poi.get('distance', float('inf'))))
                    else:
                        # 如果没有距离字段，取第一个POI作为最近的POI点
                        nearest_poi = pois[0]
                
                result = {
                    "formatted_address": formatted_address,
                    "province": address_component.get("province", ""),
                    "city": address_component.get("city", ""),
                    "district": address_component.get("district", ""),
                    "township": address_component.get("street", ""),  # 腾讯地图API中street相当于township
                    "street": address_component.get("street", ""),
                    "street_number": address_component.get("street_number", ""),
                    "nearest_poi": nearest_poi,  # 添加最近POI点信息
                    "pois": pois  # 添加所有POI点信息
                }
                return result
            else:
                # 检查是否为QPS超限错误
                error_msg = data.get("message", "")
                if any(limit_err in error_msg.lower() for limit_err in ['qps', 'exceeded', 'limit']):
                    raise ValueError(f"腾讯地图API错误: {error_msg}")
                return None
                
        try:
            return self._handle_api_request(request_func, "腾讯地图逆地理编码")
        except Exception as e:
            print(f"腾讯地图逆地理编码错误：{str(e)}")
            return None


def create_map_api(api_type: str, api_key: str) -> MapAPI:
    """根据指定的地图API类型创建相应的API实例
    
    Args:
        api_type: 地图API类型，可选值为 'amap', 'baidu', 'tencent'
        api_key: API密钥
        
    Returns:
        MapAPI: 地图API实例
        
    Raises:
        ValueError: 当API类型不支持或API密钥格式不正确时抛出
    """
    # 验证API密钥格式
    is_valid, error_msg = MapAPI.validate_api_key(api_key, api_type)
    if not is_valid:
        raise ValueError(error_msg)
    
    if api_type.lower() == "amap":
        return AmapAPI(api_key)
    elif api_type.lower() == "baidu":
        return BaiduMapAPI(api_key)
    elif api_type.lower() == "tencent":
        return TencentMapAPI(api_key)
    else:
        raise ValueError(f"不支持的地图API类型: {api_type}")