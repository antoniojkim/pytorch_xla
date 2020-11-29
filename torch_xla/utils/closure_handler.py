from queue import Queue
from threading import Event, Thread


class ClosureHandler:
  """A handler that keeps track of closures and executes them in order either
  synchronously or asynchronously.

  Args:
    max_queue_size (int): The maximum size of the queue of closures to run
      asynchronously. Default: -1
    timeout (int): The time in seconds to wait for a closure to be added to
      the queue before checking if the kill event has been set. Default: 2
  """

  def __init__(self, max_queue_size=-1, timeout=2):
    self.max_queue_size = max_queue_size
    self.timeout = timeout

  def __del__(self):
    self.reset()

  def is_initialized(self):
    return getattr(self, "closure_thread", None) is not None

  def initialize(self):
    self.reset()

    self.kill_event = Event()
    self.queue = Queue(self.max_queue_size)
    self.closure_exceptions = Queue()

    def closure_loop():
      while not self.kill_event.is_set() and not self.queue.empty():
        try:
          closure = self.queue.get(block=True, timeout=self.timeout)
          closure()
          self.queue.task_done()
        except queue.Empty:
          pass
        except Exception as e:
          self.closure_exceptions.put(e)
          return

    self.closure_thread = Thread(target=closure_loop)
    self.closure_thread.start()

  def reset(self):
    if self.is_initialized() and self.closure_thread.is_alive():
      self.kill_event.set()
      self.queue.join()
      self.closure_thread.join()

    self.kill_event = None
    self.queue = None
    self.closure_exceptions = None
    self.closure_thread = None


  def run(self, closure, run_async=False):
    if not run_async:
      closure()
    else:
      if not self.is_initialized():
        self.initialize()

      if not self.closure_exceptions.empty():
        e = self.closure_exceptions.get()
        raise RuntimeError(f"Closure thread already killed with exception: {e}")
      if not self.closure_thread.is_alive():
        raise RuntimeError("Closure thread already killed")

      self.queue.put(closure)
