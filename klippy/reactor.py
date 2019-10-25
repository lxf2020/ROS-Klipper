# File descriptor and timer event helper
#
# Copyright (C) 2016-2019  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import os, select, math, time, Queue, logging
import greenlet
import chelper, util 

_NOW = 0.
_NEVER = 9999999999999999.

class ReactorTimer:
    def __init__(self, callback, waketime):
        logging.info("  ")
        logging.info("==================== reactor.ReactorTimer.__init__ =====================")
        self.callback = callback
        self.waketime = waketime
        self.name = callback.__name__
        
        logging.info("callback name is: "+self.name)
        logging.info("================== reactor.ReactorTimer.__init__ END ===================")
        logging.info("  ")
class ReactorCompletion:
    class sentinel: pass
    def __init__(self, reactor):
        self.reactor = reactor
        self.result = self.sentinel
        self.waiting = None
    def test(self):
        return self.result is not self.sentinel
    def complete(self, result):
        self.result = result
        if self.waiting is not None:
            self.reactor.update_timer(self.waiting.timer, self.reactor.NOW)
    def wait(self, waketime=_NEVER, waketime_result=None):
        if self.result is self.sentinel:
            self.waiting = greenlet.getcurrent()
            self.reactor.pause(waketime)
            self.waiting = None
            if self.result is self.sentinel:
                return waketime_result
        return self.result

class ReactorCallback:
    def __init__(self, reactor, callback, waketime):
        logging.info("=============== reactor.ReactorCallback.__init__ ==================")
        self.reactor = reactor
        self.timer = reactor.register_timer(self.invoke, waketime)
        self.callback = callback
        logging.info("ReactorCallback--callback name is: ")
        logging.info(callback.__name__)
        self.completion = ReactorCompletion(reactor)
        logging.info("============= reactor.ReactorCallback.__init__ END ================")
    def invoke(self, eventtime):
        self.reactor.unregister_timer(self.timer)
        res = self.callback(eventtime)
        self.completion.complete(res)
        return self.reactor.NEVER

class ReactorFileHandler:
    def __init__(self, fd, callback):
        self.fd = fd
        self.callback = callback
    def fileno(self):
        return self.fd

class ReactorGreenlet(greenlet.greenlet):
    def __init__(self, run):
        greenlet.greenlet.__init__(self, run=run)
        self.timer = None

class ReactorMutex:
    def __init__(self, reactor, is_locked):
        self.reactor = reactor
        self.is_locked = is_locked
        self.next_pending = False
        self.queue = []
        self.lock = self.__enter__
        self.unlock = self.__exit__
    def test(self):
        return self.is_locked
    def __enter__(self):
        if not self.is_locked:
            self.is_locked = True
            return
        g = greenlet.getcurrent()
        self.queue.append(g)
        while 1:
            self.reactor.pause(self.reactor.NEVER)
            if self.next_pending and self.queue[0] is g:
                self.next_pending = False
                self.queue.pop(0)
                return
    def __exit__(self, type=None, value=None, tb=None):
        if not self.queue:
            self.is_locked = False
            return
        self.next_pending = True
        self.reactor.update_timer(self.queue[0].timer, self.reactor.NOW)

class SelectReactor:
    NOW = _NOW
    NEVER = _NEVER
    def __init__(self):
        logging.info("=============== reactor.SelectReactor.__init__ ================")
        # Main code
        self._process = False
        self.monotonic = chelper.get_ffi()[1].get_monotonic
        # Timers
        self._timers = []
        self._next_timer = self.NEVER
        # Callbacks
        self._pipe_fds = None
        self._async_queue = Queue.Queue()
        # File descriptors
        self._fds = []
        # Greenlets
        self._g_dispatch = None
        self._greenlets = []
        logging.info("============== reactor.SelectReactor.__init__ END ==============")
    # Timers
    def update_timer(self, timer_handler, waketime):
        timer_handler.waketime = waketime
        self._next_timer = min(self._next_timer, waketime)
    def register_timer(self, callback, waketime=NEVER):
        logging.info("  ")
        logging.info("============= reactor.SelectReactor.register_timer() START =============")
        logging.info("callback is: ")
        logging.info(callback)
        timer_handler = ReactorTimer(callback, waketime) 
        
        logging.info("self._timers is: ")
        logging.info(self._timers)
        timers = list(self._timers)
        timers.append(timer_handler)
        self._timers = timers
        self._next_timer = min(self._next_timer, waketime)
        logging.info("self._timers is: ")
        logging.info(self._timers)
        logging.info("=========== reactor.SelectReactor.register_timer() END ===========")
        logging.info("  ")
        return timer_handler
    def unregister_timer(self, timer_handler):
        timer_handler.waketime = self.NEVER
        timers = list(self._timers)
        timers.pop(timers.index(timer_handler))
        self._timers = timers
    def _check_timers(self, eventtime):
        logging.info("================= _check_timers()-[SelectReactor] START =================")
        if eventtime < self._next_timer:
            logging.info("eee+111111111111111111")
            return min(1., max(.001, self._next_timer - eventtime))
        
        self._next_timer = self.NEVER
        g_dispatch = self._g_dispatch
        logging.info("self._timers is: ")
        logging.info(self._timers)
        logging.info("  ")
        
        for t in self._timers:
            waketime = t.waketime
            logging.info("eventtime is: ")
            logging.info(eventtime)
            logging.info("waketime is: ")
            logging.info(waketime)
            logging.info("  ")
            if eventtime >= waketime:
                t.waketime = self.NEVER
                logging.info("self._timers is: ")
                logging.info(self._timers)
                logging.info("t is: ")
                logging.info(t)
                t.waketime = waketime = t.callback(eventtime)
                logging.info("t.waketime is: ")
                logging.info(t.waketime)
                if g_dispatch is not self._g_dispatch:
                    self._next_timer = min(self._next_timer, waketime)
                    self._end_greenlet(g_dispatch)
                    return 0.
            self._next_timer = min(self._next_timer, waketime)
        if eventtime >= self._next_timer:
            logging.info("================ _check_timers()-[SelectReactor] END 00================")
            return 0.
        logging.info("================= _check_timers()-[SelectReactor] END =================")
        return min(1., max(.001, self._next_timer - self.monotonic()))
    # Callbacks and Completions
    def completion(self):
        return ReactorCompletion(self)
    def register_callback(self, callback, waketime=NOW):
        rcb = ReactorCallback(self, callback, waketime)
        return rcb.completion
    # Asynchronous (from another thread) callbacks and completions
    def register_async_callback(self, callback, waketime=NOW):
        self._async_queue.put_nowait(
            (ReactorCallback, (self, callback, waketime)))
        try:
            os.write(self._pipe_fds[1], '.')
        except os.error:
            pass
    def async_complete(self, completion, result):
        self._async_queue.put_nowait((completion.complete, (result,)))
        try:
            os.write(self._pipe_fds[1], '.')
        except os.error:
            pass
    def _got_pipe_signal(self, eventtime):
        try:
            os.read(self._pipe_fds[0], 4096)
        except os.error:
            pass
        while 1:
            try:
                func, args = self._async_queue.get_nowait()
            except Queue.Empty:
                break
            func(*args)
    def _setup_async_callbacks(self):
        logging.info("========== _setup_async_callbacks()-[SelectReactor] START ============")
        self._pipe_fds = os.pipe()
        logging.info("self._pipe_fds: ")
        logging.info(self._pipe_fds)
        
        util.set_nonblock(self._pipe_fds[0])
        util.set_nonblock(self._pipe_fds[1])
        self.register_fd(self._pipe_fds[0], self._got_pipe_signal)
        logging.info("============ _setup_async_callbacks()-[SelectReactor] END =============")
    def __del__(self):
        if self._pipe_fds is not None:
            os.close(self._pipe_fds[0])
            os.close(self._pipe_fds[1])
            self._pipe_fds = None
    # Greenlets
    def _sys_pause(self, waketime):
        # Pause using system sleep for when reactor not running
        delay = waketime - self.monotonic()
        if delay > 0.:
            time.sleep(delay)
        return self.monotonic()
    def pause(self, waketime):
        logging.info("  ")
        logging.info("====================== reactor.pause()-[SelectReactor] START ======================")
        g = greenlet.getcurrent()
        logging.info("greenlet.getcurrent() :") 
        logging.info(g) 
        logging.info("self._g_dispatch :") 
        logging.info(self._g_dispatch) 
        logging.info("================this is reactor.pause============== ") 
        if g is not self._g_dispatch:
            if self._g_dispatch is None:
                logging.info("======================= reactor.pause()-[SelectReactor] END 00=======================")
                return self._sys_pause(waketime)
            # Switch to _check_timers (via g.timer.callback return)
            logging.info("======================= reactor.pause()-[SelectReactor] END 11=======================")
            return self._g_dispatch.switch(waketime)
        # Pausing the dispatch greenlet - prepare a new greenlet to do dispatch
        if self._greenlets:
            logging.info("================ self._greenlets is true ============== 00") 
            g_next = self._greenlets.pop()
        else:
            logging.info("================ self._greenlets is false ============== 11") 
            g_next = ReactorGreenlet(run=self._dispatch_loop)
        g_next.parent = g.parent
        g.timer = self.register_timer(g.switch, waketime)
        self._next_timer = self.NOW
        # Switch to _dispatch_loop (via _end_greenlet or direct)
        eventtime = g_next.switch()
        logging.info("======================= reactor.pause()-[SelectReactor] END =======================")
        # This greenlet activated from g.timer.callback (via _check_timers)
        return eventtime
    def _end_greenlet(self, g_old):
        # Cache this greenlet for later use
        self._greenlets.append(g_old)
        self.unregister_timer(g_old.timer)
        g_old.timer = None
        # Switch to _check_timers (via g_old.timer.callback return)
        self._g_dispatch.switch(self.NEVER)
        # This greenlet reactivated from pause() - return to main dispatch loop
        self._g_dispatch = g_old
    # Mutexes
    def mutex(self, is_locked=False):
        return ReactorMutex(self, is_locked)
    # File descriptors
    def register_fd(self, fd, callback):
        file_handler = ReactorFileHandler(fd, callback)
        self._fds.append(file_handler)
        return file_handler
    def unregister_fd(self, file_handler):
        self._fds.pop(self._fds.index(file_handler))
    # Main loop
    def _dispatch_loop(self):
        logging.info("================ _dispatch_loop()-[SelectReactor] START =================")
        self._g_dispatch = g_dispatch = greenlet.getcurrent()
        eventtime = self.monotonic()
        while self._process:
            timeout = self._check_timers(eventtime)
            res = select.select(self._fds, [], [], timeout)
            eventtime = self.monotonic()
            for fd in res[0]:
                fd.callback(eventtime)
                if g_dispatch is not self._g_dispatch:
                    self._end_greenlet(g_dispatch)
                    eventtime = self.monotonic()
                    break
        self._g_dispatch = None
        logging.info("================ _dispatch_loop()-[SelectReactor] END =================")
    def run(self):
        logging.info("=============== reactor.run()-[SelectReactor] START ================")
        if self._pipe_fds is None:
            self._setup_async_callbacks()
        self._process = True
        g_next = ReactorGreenlet(run=self._dispatch_loop)
        logging.info("g_next : ")
        logging.info(g_next)
        logging.info("========================= call switch() ============================")
        g_next.switch()
        logging.info("================ reactor.run()-[SelectReactor] END =================")
    def end(self):
        self._process = False

class PollReactor(SelectReactor):
    def __init__(self):
        logging.info("================= reactor.PollReactor.__init__ =================")
        SelectReactor.__init__(self)
        self._poll = select.poll()
        self._fds = {}
        logging.info("=============== reactor.PollReactor.__init__ END ===============")
    # File descriptors
    def register_fd(self, fd, callback):
        file_handler = ReactorFileHandler(fd, callback)
        fds = self._fds.copy()
        fds[fd] = callback
        self._fds = fds
        self._poll.register(file_handler, select.POLLIN | select.POLLHUP)
        return file_handler
    def unregister_fd(self, file_handler):
        self._poll.unregister(file_handler)
        fds = self._fds.copy()
        del fds[file_handler.fd]
        self._fds = fds
    # Main loop
    def _dispatch_loop(self):
        logging.info("============== reactor.PollReactor._dispatch_loop START ===============")
        self._g_dispatch = g_dispatch = greenlet.getcurrent()
        eventtime = self.monotonic()
        #logging.info("eventtime:", eventtime)
        conut = 0
        while self._process:
            conut = conut+1
            logging.info("  ")
            logging.info("_dispatch_loop while conut is :"+str(conut)+"*************************")
            timeout = self._check_timers(eventtime)
            res = self._poll.poll(int(math.ceil(timeout * 1000.)))
            logging.info("in reactor.PollReactor._dispatch_loop loop.............")
            eventtime = self.monotonic()
            logging.info("eventtime is :")
            logging.info(eventtime)

            for fd, event in res:
                self._fds[fd](eventtime)
                if g_dispatch is not self._g_dispatch:
                    logging.info("=============_end_greenlet?============")
                    logging.info(g_dispatch)
                    logging.info(g_dispatch.__name__)
                    self._end_greenlet(g_dispatch)
                    eventtime = self.monotonic()
                    break
        self._g_dispatch = None
        logging.info("====================== reactor.PollReactor._dispatch_loop END ======================")
class EPollReactor(SelectReactor):
    def __init__(self):
        SelectReactor.__init__(self)
        self._epoll = select.epoll()
        self._fds = {}
    # File descriptors
    def register_fd(self, fd, callback):
        file_handler = ReactorFileHandler(fd, callback)
        fds = self._fds.copy()
        fds[fd] = callback
        self._fds = fds
        self._epoll.register(fd, select.EPOLLIN | select.EPOLLHUP)
        return file_handler
    def unregister_fd(self, file_handler):
        self._epoll.unregister(file_handler.fd)
        fds = self._fds.copy()
        del fds[file_handler.fd]
        self._fds = fds
    # Main loop
    def _dispatch_loop(self):
        logging.info("================ _dispatch_loop()-[EPollReactor] START =================")
        self._g_dispatch = g_dispatch = greenlet.getcurrent()
        eventtime = self.monotonic()
        while self._process:
            timeout = self._check_timers(eventtime)
            res = self._epoll.poll(timeout)
            eventtime = self.monotonic()
            for fd, event in res:
                self._fds[fd](eventtime)
                if g_dispatch is not self._g_dispatch:
                    self._end_greenlet(g_dispatch)
                    eventtime = self.monotonic()
                    break
        self._g_dispatch = None
        logging.info("================= _dispatch_loop()-[EPollReactor] END ==================")
# Use the poll based reactor if it is available
try:
    select.poll
    logging.info("----------------this is PollReactor-----------------")
    Reactor = PollReactor
except:
    logging.info("----------------this is SelectReactor-----------------")
    Reactor = SelectReactor
