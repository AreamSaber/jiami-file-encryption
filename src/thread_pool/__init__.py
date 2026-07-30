"""
线程管理模块

提供全局线程管理功能

注意：此模块原名为 threading，但与 Python 标准库冲突，已重命名为 thread_pool
"""

from .thread_manager import GlobalThreadManager, ThreadPriority, thread_manager

__all__ = ['GlobalThreadManager', 'ThreadPriority', 'thread_manager']
