#!/usr/bin/env python3
"""
配置管理器模块

提供统一的配置加载、验证和热加载功能
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from threading import Lock, Thread, Event
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.exceptions import (
    ConfigurationError,
    SchemaValidationError,
    ConfigNotFoundError,
    ConfigLoadError,
)


class ConfigManager:
    """
    统一配置管理器
    
    提供配置加载、JSON Schema验证和热加载功能
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, config_dir: Optional[str] = None):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置目录路径，默认为项目根目录下的config
        """
        if self._initialized:
            return
            
        self.config_dir = Path(config_dir) if config_dir else self._get_default_config_dir()
        self.schemas_dir = self.config_dir / "schemas"
        
        self._configs: Dict[str, Dict] = {}
        self._config_timestamps: Dict[str, float] = {}
        self._watchers: List[Callable[[str, Dict], None]] = []
        self._schema_cache: Dict[str, Dict] = {}
        
        # 热加载相关
        self._watch_thread: Optional[Thread] = None
        self._stop_watching: Event = Event()
        self._watch_interval: float = 1.0  # 默认1秒检查一次
        self._watching: bool = False
        
        self._initialized = True
    
    def _get_default_config_dir(self) -> Path:
        """获取默认配置目录"""
        return Path(__file__).parent.parent.parent / "config"
    
    def load_config(self, name: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        加载配置文件
        
        Args:
            name: 配置文件名（不含.json后缀）
            force_reload: 是否强制重新加载
            
        Returns:
            配置字典
            
        Raises:
            ConfigNotFoundError: 配置文件不存在
            ConfigLoadError: 配置加载失败
            SchemaValidationError: Schema验证失败
        """
        # 检查缓存
        if not force_reload and name in self._configs:
            # 检查文件是否被修改
            if not self._is_config_modified(name):
                return self._configs[name].copy()
        
        config_path = self.config_dir / f"{name}.json"
        
        if not config_path.exists():
            raise ConfigNotFoundError(
                config_name=name,
                config_path=str(config_path)
            )
        
        try:
            config = self._read_json(config_path)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(
                f"配置文件JSON格式错误: {e}",
                config_path=str(config_path)
            )
        except Exception as e:
            raise ConfigLoadError(
                f"读取配置文件失败: {e}",
                config_path=str(config_path)
            )
        
        # 验证Schema
        self._validate_schema(name, config)
        
        # 缓存配置
        self._configs[name] = config
        self._config_timestamps[name] = config_path.stat().st_mtime
        
        # 通知观察者
        self._notify_watchers(name, config)
        
        return config.copy()
    
    def _read_json(self, path: Path) -> Dict:
        """读取JSON文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _is_config_modified(self, name: str) -> bool:
        """检查配置文件是否被修改"""
        config_path = self.config_dir / f"{name}.json"
        if not config_path.exists():
            return True
        
        current_mtime = config_path.stat().st_mtime
        cached_mtime = self._config_timestamps.get(name, 0)
        
        return current_mtime > cached_mtime
    
    def _validate_schema(self, name: str, config: Dict) -> None:
        """
        使用JSON Schema验证配置
        
        Args:
            name: 配置名称
            config: 配置字典
            
        Raises:
            SchemaValidationError: 验证失败
        """
        schema_path = self.schemas_dir / f"{name}.schema.json"
        
        if not schema_path.exists():
            # 没有Schema文件，跳过验证
            return
        
        try:
            # 加载Schema（使用缓存）
            if name not in self._schema_cache:
                self._schema_cache[name] = self._read_json(schema_path)
            
            schema = self._schema_cache[name]
            
            # 尝试使用jsonschema库验证
            try:
                import jsonschema
                jsonschema.validate(config, schema)
            except ImportError:
                # jsonschema未安装，使用简单验证
                self._simple_validate(config, schema, name)
            except jsonschema.ValidationError as e:
                raise SchemaValidationError(
                    f"配置验证失败: {e.message}",
                    config_name=name,
                    validation_errors=[str(e)]
                )
                
        except SchemaValidationError:
            raise
        except Exception as e:
            # Schema加载失败，记录警告但不阻止
            pass
    
    def _simple_validate(self, config: Dict, schema: Dict, name: str) -> None:
        """简单的Schema验证（不依赖jsonschema库）"""
        errors = []
        
        # 检查必需字段
        required = schema.get('required', [])
        for field in required:
            if field not in config:
                errors.append(f"缺少必需字段: {field}")
        
        # 检查类型
        properties = schema.get('properties', {})
        for field, field_schema in properties.items():
            if field in config:
                expected_type = field_schema.get('type')
                if expected_type:
                    if not self._check_type(config[field], expected_type):
                        errors.append(f"字段 {field} 类型错误，期望 {expected_type}")
        
        if errors:
            raise SchemaValidationError(
                f"配置验证失败",
                config_name=name,
                validation_errors=errors
            )
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        type_map = {
            'string': str,
            'integer': int,
            'number': (int, float),
            'boolean': bool,
            'array': list,
            'object': dict,
        }
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        return True
    
    def get_config(self, name: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            name: 配置文件名
            key: 配置键（支持点号分隔的嵌套键）
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            config = self.load_config(name)
        except ConfigNotFoundError:
            return default
        
        if key is None:
            return config
        
        # 支持嵌套键
        keys = key.split('.')
        value = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def save_config(self, name: str, config: Dict) -> None:
        """
        保存配置文件
        
        Args:
            name: 配置文件名
            config: 配置字典
        """
        config_path = self.config_dir / f"{name}.json"
        
        # 验证Schema
        self._validate_schema(name, config)
        
        # 保存文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 更新缓存
        self._configs[name] = config
        self._config_timestamps[name] = config_path.stat().st_mtime
        
        # 通知观察者
        self._notify_watchers(name, config)
    
    def watch_changes(self, callback: Callable[[str, Dict], None]) -> None:
        """
        注册配置变更回调
        
        Args:
            callback: 回调函数，接收(config_name, config_dict)参数
        """
        self._watchers.append(callback)
    
    def unwatch_changes(self, callback: Callable[[str, Dict], None]) -> None:
        """取消注册配置变更回调"""
        if callback in self._watchers:
            self._watchers.remove(callback)
    
    def _notify_watchers(self, name: str, config: Dict) -> None:
        """通知所有观察者"""
        for callback in self._watchers:
            try:
                callback(name, config)
            except Exception:
                pass
    
    def reload_all(self) -> None:
        """重新加载所有已缓存的配置"""
        for name in list(self._configs.keys()):
            try:
                self.load_config(name, force_reload=True)
            except Exception:
                pass
    
    def list_configs(self) -> List[str]:
        """列出所有可用的配置文件"""
        if not self.config_dir.exists():
            return []
        
        return [
            f.stem for f in self.config_dir.glob("*.json")
            if not f.name.endswith('.schema.json')
        ]
    
    def get_config_info(self, name: str) -> Dict[str, Any]:
        """获取配置文件信息"""
        config_path = self.config_dir / f"{name}.json"
        schema_path = self.schemas_dir / f"{name}.schema.json"
        
        info = {
            'name': name,
            'exists': config_path.exists(),
            'has_schema': schema_path.exists(),
            'cached': name in self._configs,
        }
        
        if config_path.exists():
            stat = config_path.stat()
            info['size'] = stat.st_size
            info['modified'] = stat.st_mtime
        
        return info
    
    def to_json(self, name: str) -> str:
        """将配置序列化为JSON字符串"""
        config = self.load_config(name)
        return json.dumps(config, ensure_ascii=False, indent=2)
    
    # ============ 热加载功能 ============
    
    def start_watching(self, interval: float = 1.0) -> None:
        """
        启动配置文件监控（热加载）
        
        Args:
            interval: 检查间隔（秒）
        """
        if self._watching:
            return
        
        self._watch_interval = interval
        self._stop_watching.clear()
        self._watching = True
        
        self._watch_thread = Thread(
            target=self._watch_loop,
            daemon=True,
            name="ConfigWatcher"
        )
        self._watch_thread.start()
    
    def stop_watching(self) -> None:
        """停止配置文件监控"""
        if not self._watching:
            return
        
        self._stop_watching.set()
        self._watching = False
        
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2.0)
        
        self._watch_thread = None
    
    def _watch_loop(self) -> None:
        """监控循环"""
        while not self._stop_watching.is_set():
            try:
                self._check_for_changes()
            except Exception:
                pass
            
            # 等待指定间隔或直到停止信号
            self._stop_watching.wait(timeout=self._watch_interval)
    
    def _check_for_changes(self) -> None:
        """检查配置文件变更"""
        for name in list(self._configs.keys()):
            if self._is_config_modified(name):
                try:
                    # 重新加载配置
                    self.load_config(name, force_reload=True)
                except Exception:
                    pass
    
    def is_watching(self) -> bool:
        """检查是否正在监控"""
        return self._watching
    
    def get_watch_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            'watching': self._watching,
            'interval': self._watch_interval,
            'watched_configs': list(self._configs.keys()),
            'watcher_count': len(self._watchers)
        }
    
    def __del__(self):
        """析构函数，确保停止监控线程"""
        try:
            self.stop_watching()
        except Exception:
            pass


# 全局配置管理器实例
config_manager = ConfigManager()
