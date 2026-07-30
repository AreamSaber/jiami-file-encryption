
class InterruptController:
    """中断控制器"""
    def __init__(self):
        self._interrupted = False
        self._lock = threading.Lock()
    
    def interrupt(self):
        """设置中断标志"""
        with self._lock:
            self._interrupted = True
    
    def is_interrupted(self):
        """检查是否被中断"""
        with self._lock:
            return self._interrupted
    
    def reset(self):
        """重置中断标志"""
        with self._lock:
            self._interrupted = False

# 全局中断控制器
interrupt_controller = InterruptController()
