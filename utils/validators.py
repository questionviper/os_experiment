"""
输入验证工具
"""

import re
from config import SystemConfig

class Validator:
    """输入验证器"""
    
    @staticmethod
    def validate_name(name: str) -> tuple:
        """验证文件/目录名（单层名称，不含路径）"""
        if not name:
            return False, "名称不能为空"
        
        if len(name) > SystemConfig.MAX_FILENAME_LENGTH:
            return False, f"名称超过{SystemConfig.MAX_FILENAME_LENGTH}字符"
        
        invalid_chars = r'[<>:"|?*\\/\x00-\x1f]'
        if re.search(invalid_chars, name):
            return False, "名称包含非法字符"
        
        reserved = ['CON', 'PRN', 'AUX', 'NUL', '.', '..']
        if name.upper() in reserved:
            return False, "名称为系统保留字"
        
        return True, ""
    
    @staticmethod
    def validate_file_size(size: int) -> tuple:
        """验证文件大小"""
        if size < 0:
            return False, "文件大小不能为负"
        
        if size > SystemConfig.MAX_FILE_SIZE:
            return False, f"文件超过限制({SystemConfig.MAX_FILE_SIZE}B)"
        
        return True, ""
