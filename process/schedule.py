import threading
import time
from queue import Queue

class TaskScheduler:
    """
    (2) 进程通信：Queue
    (3) 互斥控制：Semaphore (信号量)
    (4) 进程调度：模拟 RR (时间片轮转)
    """
    def __init__(self, max_io_threads=2):
        self.task_queue = Queue()
        # 信号量：控制最大并发IO数，模拟磁盘物理限制
        self.io_semaphore = threading.Semaphore(max_io_threads)
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.scheduler_thread.start()

    def _schedule_loop(self):
        """轮询队列，模拟时间片分配"""
        while self.running:
            if not self.task_queue.empty():
                task = self.task_queue.get()
                
                # 为每个命令开启独立线程 
                worker = threading.Thread(target=self._execute_wrapper, args=(task,))
                worker.start()
                
                # 模拟时间片切换间隔
                time.sleep(0.5) 
            else:
                time.sleep(0.1)

    def _execute_wrapper(self, task):
        """带信号量保护的执行包装器"""
        with self.io_semaphore:  # 信号量互斥控制
            try:
                # 模拟系统调度延迟
                print(f"--- 线程 {threading.current_thread().name} 开始处理任务 ---")
                time.sleep(0.5)
                
                # 执行原有的函数逻辑
                res = task.execute()
                task.mark_done(result=res)
            except Exception as e:
                task.mark_done(error=str(e))