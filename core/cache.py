 """
نظام التخزين المؤقت المتقدم مع LRU وTTL
"""

import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Dict, List
import hashlib
import json

from .config import PERFORMANCE
from .logger import get_logger

logger = get_logger(__name__)


class LRUCache:
    """ذاكرة تخزين مؤقت مع LRU (Least Recently Used)"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self.lock = threading.RLock()
        logger.info(f"تم تهيئة LRU Cache بحجم {max_size}")
    
    def get(self, key: str) -> Optional[Any]:
        """استرجاع قيمة من الكاش"""
        with self.lock:
            if key in self.cache:
                # نقل العنصر للنهاية (الأحدث)
                self.cache.move_to_end(key)
                self.hits += 1
                value, expiry = self.cache[key]
                
                # التحقق من الصلاحية
                if expiry and time.time() > expiry:
                    del self.cache[key]
                    self.misses += 1
                    return None
                
                return value
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """حفظ قيمة في الكاش"""
        with self.lock:
            expiry = time.time() + ttl if ttl else None
            
            if key in self.cache:
                self.cache.move_to_end(key)
            
            self.cache[key] = (value, expiry)
            
            # إذا تجاوز الحجم، إزالة الأقدم
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    def delete(self, key: str) -> bool:
        """حذف قيمة من الكاش"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """مسح الكاش بالكامل"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict:
        """الحصول على إحصائيات الكاش"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "keys": list(self.cache.keys())
            }
    
    def cleanup_expired(self) -> int:
        """تنظيف العناصر المنتهية الصلاحية"""
        with self.lock:
            count = 0
            now = time.time()
            expired_keys = []
            
            for key, (_, expiry) in self.cache.items():
                if expiry and now > expiry:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                count += 1
            
            if count > 0:
                logger.debug(f"تم تنظيف {count} عنصر منتهي من الكاش")
            
            return count


class CacheManager:
    """مدير التخزين المؤقت الرئيسي"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """تهيئة المدير"""
        max_size = PERFORMANCE["CACHE_MAX_SIZE"]
        self.cache = LRUCache(max_size=max_size)
        
        # كاشات خاصة
        self.user_cache = {}
        self.settings_cache = {}
        self.rate_limit_cache = {}
        
        # مؤقت للتنظيف التلقائي
        self.last_cleanup = time.time()
        logger.info("تم تهيئة CacheManager")
    
    # ========== دوال سريعة للاستخدام الشائع ==========
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """جلب بيانات مستخدم من الكاش"""
        cache_key = f"user_{user_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        # إذا لم يكن في الكاش، يتم جلبها من قاعدة البيانات
        # (سيتم استدعاء هذه الدالة من user_service)
        return None
    
    def set_user(self, user_id: int, user_data: Dict, ttl: int = 300) -> None:
        """حفظ بيانات مستخدم في الكاش"""
        cache_key = f"user_{user_id}"
        self.cache.set(cache_key, user_data, ttl)
    
    def delete_user(self, user_id: int) -> None:
        """حذف بيانات مستخدم من الكاش"""
        cache_key = f"user_{user_id}"
        self.cache.delete(cache_key)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """جلب إعداد من الكاش"""
        cache_key = f"setting_{key}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        return default
    
    def set_setting(self, key: str, value: Any, ttl: int = 60) -> None:
        """حفظ إعداد في الكاش"""
        cache_key = f"setting_{key}"
        self.cache.set(cache_key, value, ttl)
    
    def delete_setting(self, key: str) -> None:
        """حذف إعداد من الكاش"""
        cache_key = f"setting_{key}"
        self.cache.delete(cache_key)
    
    def get_admin_status(self, user_id: int) -> Optional[bool]:
        """التحقق من حالة الأدمن"""
        cache_key = f"admin_{user_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        return None
    
    def set_admin_status(self, user_id: int, is_admin: bool, ttl: int = 300) -> None:
        """حفظ حالة الأدمن"""
        cache_key = f"admin_{user_id}"
        self.cache.set(cache_key, is_admin, ttl)
    
    def delete_admin_status(self, user_id: int) -> None:
        """حذف حالة الأدمن"""
        cache_key = f"admin_{user_id}"
        self.cache.delete(cache_key)
    
    # ========== دوال متقدمة ==========
    
    def generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """توليد مفتاح كاش فريد"""
        key_parts = [prefix]
        
        for arg in args:
            key_parts.append(str(arg))
        
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def cached_query(self, ttl: int = 60):
        """ديكورير لاستعلامات قاعدة البيانات"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # توليد مفتاح فريد للكاش
                cache_key = self.generate_cache_key(
                    func.__name__,
                    *args,
                    **{k: v for k, v in kwargs.items() if k != 'db'}
                )
                
                # التحقق من الكاش
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit: {func.__name__}")
                    return cached_result
                
                # جلب من قاعدة البيانات
                result = func(*args, **kwargs)
                
                # حفظ في الكاش
                if result is not None:
                    self.cache.set(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator
    
    def invalidate_pattern(self, pattern: str) -> int:
        """إبطال جميع المفاتيح التي تطابق نمطاً معيناً"""
        count = 0
        keys_to_delete = []
        
        for key in self.cache.cache.keys():
            if pattern in key:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            if self.cache.delete(key):
                count += 1
        
        logger.info(f"تم إبطال {count} مفتاح بنمط: {pattern}")
        return count
    
    def auto_cleanup(self):
        """تنظيف تلقائي كل 5 دقائق"""
        now = time.time()
        if now - self.last_cleanup > 300:  # 5 دقائق
            expired_count = self.cache.cleanup_expired()
            self.last_cleanup = now
            if expired_count > 0:
                logger.debug(f"التنظيف التلقائي: تم إزالة {expired_count} عنصر")
    
    def get_detailed_stats(self) -> Dict:
        """إحصائيات مفصلة"""
        cache_stats = self.cache.get_stats()
        
        return {
            "lru_cache": cache_stats,
            "user_cache_size": len(self.user_cache),
            "settings_cache_size": len(self.settings_cache),
            "rate_limit_cache_size": len(self.rate_limit_cache),
            "total_cached_items": cache_stats["size"],
            "memory_usage": "N/A"  # يمكن إضافة psutil للحساب الدقيق
        }


# إنشاء نسخة عامة
cache = CacheManager()