"""
نظام الجلسات - سرعة فائقة
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from core.database import db
from core.cache import cache
from core.logger import get_logger

logger = get_logger(__name__)


def set_session(user_id: int, step: str, temp_data: Dict = None, ttl_minutes: int = 30) -> bool:
    """حفظ جلسة"""
    try:
        json_data = json.dumps(temp_data, ensure_ascii=False) if temp_data else None
        expires_at = (datetime.now() + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        
        query = """
            INSERT OR REPLACE INTO sessions 
            (user_id, step, temp_data, expires_at, created_at) 
            VALUES (?, ?, ?, ?, datetime('now'))
        """
        
        db.execute_query(query, (user_id, step, json_data, expires_at))
        
        # حفظ في الكاش للسرعة
        cache_key = f"session_{user_id}"
        cache.cache.set(cache_key, {
            "step": step,
            "temp_data": temp_data,
            "expires_at": expires_at
        }, ttl=ttl_minutes * 60)
        
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الجلسة: {e}")
        return False


def get_session(user_id: int) -> Optional[Dict[str, Any]]:
    """جلب جلسة"""
    try:
        # التحقق من الكاش أولاً
        cache_key = f"session_{user_id}"
        cached = cache.cache.get(cache_key)
        if cached:
            # التحقق من الصلاحية
            expires_at = datetime.strptime(cached['expires_at'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expires_at:
                cache.cache.delete(cache_key)
                return None
            return cached
        
        # جلب من قاعدة البيانات
        query = """
            SELECT step, temp_data, expires_at 
            FROM sessions 
            WHERE user_id = ? AND expires_at > datetime('now')
        """
        
        result = db.fetch_one(query, (user_id,))
        if result:
            temp_data = None
            if result['temp_data']:
                try:
                    temp_data = json.loads(result['temp_data'])
                except json.JSONDecodeError:
                    temp_data = result['temp_data']
            
            session_data = {
                "step": result['step'],
                "temp_data": temp_data,
                "expires_at": result['expires_at']
            }
            
            # حفظ في الكاش
            ttl = (datetime.strptime(result['expires_at'], "%Y-%m-%d %H:%M:%S") - datetime.now()).seconds
            if ttl > 0:
                cache.cache.set(cache_key, session_data, ttl=min(ttl, 3600))
            
            return session_data
        
        return None
    except Exception as e:
        logger.error(f"خطأ في جلب الجلسة: {e}")
        return None


def clear_session(user_id: int) -> bool:
    """مسح جلسة"""
    try:
        query = "DELETE FROM sessions WHERE user_id = ?"
        db.execute_query(query, (user_id,))
        
        # حذف من الكاش
        cache_key = f"session_{user_id}"
        cache.cache.delete(cache_key)
        
        return True
    except Exception as e:
        logger.error(f"خطأ في مسح الجلسة: {e}")
        return False


def cleanup_expired_sessions() -> int:
    """تنظيف الجلسات المنتهية"""
    try:
        query = "DELETE FROM sessions WHERE expires_at <= datetime('now')"
        cursor = db.execute_query(query)
        
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.debug(f"تم تنظيف {deleted_count} جلسة منتهية")
        
        return deleted_count
    except Exception as e:
        logger.error(f"خطأ في تنظيف الجلسات: {e}")
        return 0


def update_session_data(user_id: int, **kwargs) -> bool:
    """تحديث بيانات الجلسة"""
    try:
        session = get_session(user_id)
        if not session:
            return False
        
        temp_data = session.get("temp_data", {})
        temp_data.update(kwargs)
        
        return set_session(user_id, session["step"], temp_data)
    except Exception as e:
        logger.error(f"خطأ في تحديث الجلسة: {e}")
        return False


def get_session_step(user_id: int) -> Optional[str]:
    """جلب خطوة الجلسة فقط"""
    session = get_session(user_id)
    return session.get("step") if session else None


def session_exists(user_id: int) -> bool:
    """التحقق من وجود جلسة"""
    return get_session(user_id) is not None