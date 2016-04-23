import functools
from concurrent.futures import ThreadPoolExecutor
import threading

class UniqueTaskThreadPoolExecutor(ThreadPoolExecutor):
	'''submit() is extended with limited memoization. Two consecutive calls to submit: submit(A) and submit(B) will return same Future instance if processing of submit(A) wasn't finished before call to submit(B).
	Such limited memoization may be useful if fn does it's own caching internally. It helps in situations when several identical requests were made BEFORE any of them was processed and saved result into cache.
	It's buggy. Don't use it.'''

	_jobs_registry = {}

	def _wrap_fn(self, fn, job_id, *args, **kwargs):
		try:
			return fn(*args, **kwargs)
		finally:
			del self._jobs_registry[job_id] # Do cleanup.

	def submit(self, fn, *args, **kwargs):
		# Let's hope that args and kwargs aren't too complex so that job_id may be used as dict key
		job_id = frozenset({'fn': fn, 'args': args, 'kwargs': kwargs})
		new_job_lock = threading.Lock()
		new_job_value = {'lock': new_job_lock}
		new_job_lock.acquire()
		try:
			# Atomic CAS-like set. First thread which sets _jobs_registry[job_id] should call super.submit(), and set job_value['future'] and then unlock job_lock.
			# Rest of threads tries to acquire job_value['lock'] in a blocking manner. By the time they acquire it job_value['future'] is already set by first thread, so they may simply return this value.
			job_value = self._jobs_registry.setdefault(job_id, new_job_value) # Atomic.
			is_first = bool(job_value is new_job_value)
			if (is_first):
				wrapped_fn = functools.partial(self._wrap_fn, fn, job_id)
				future = ThreadPoolExecutor.submit(self, wrapped_fn, *args, **kwargs)
				job_value['future'] = future
				return future
			else:
				job_value['lock'].acquire(True)
				job_value['lock'].release()
				return job_value['future']
		finally:
			new_job_lock.release()
