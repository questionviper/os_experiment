import threading
from datetime import datetime

class CommandTask:
    """
    (1) 命令进程/线程的基础：封装一个可执行的任务
    """
    def __init__(self, func, *args, **kwargs):
        self.task_id = id(self)
        self.func = func        # 原有的逻辑函数，如 self._raw_read_file
        self.args = args        # 函数参数
        self.kwargs = kwargs
        
        self.status = "READY"   # READY, RUNNING, FINISHED
        self.result = None
        self.error = None
        
        self.done_event = threading.Event()
        self.start_time = None
        self.end_time = None

    def execute(self):
        """执行封装的函数"""
        self.start_time = datetime.now()
        self.status = "RUNNING"
        # 直接调用传入的函数
        return self.func(*self.args, **self.kwargs)

    def mark_done(self, result=None, error=None):
        self.result = result
        self.error = error
        self.status = "FINISHED"
        self.end_time = datetime.now()
        self.done_event.set()