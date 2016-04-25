import functools
from concurrent.futures import ThreadPoolExecutor
import threading
import logging

logger = logging.getLogger(__name__)

#TODO: It is possible to avoid any locking here using implementation of Future, which can wrap another Future (after creation).
class UniqueTaskThreadPoolExecutor(ThreadPoolExecutor):
	'''submit() is extended with limited memoization. Two consecutive calls to submit: submit(A) and submit(B) will return same Future instance if A == B and processing of submit(A) wasn't finished before call to submit(B).
	Such limited memoization may be useful if fn does it's own caching internally. It helps in situations when several identical requests were made BEFORE any of them was processed and saved result into cache.
	It's buggy. Don't use it.'''

	_jobs_registry = {}

	def _wrap_fn(self, fn, job_id, *args, **kwargs):
		try:
			return fn(*args, **kwargs)
		finally:
			del self._jobs_registry[job_id] # Do cleanup.
			#logger.debug("Task '%s' removed from registry " % frozenset({fn, args, frozenset(kwargs)}))

	def submit(self, fn, *args, **kwargs):
		# Let's hope that args and kwargs are immutable and reference transparent, so that job_id may be used as dict key
		#logger.debug('Task submitted')

		try:
			job_id = frozenset({fn, args, frozenset(kwargs)})
			#logger.debug('Task "%s" submitted' % job_id)
			new_job_lock = threading.Lock()
			new_job_value = {'lock': new_job_lock}
			new_job_lock.acquire()

			# Atomic CAS-like set. First thread which sets value of _jobs_registry[job_id] should call ThreadPoolExecutor.submit(), set job_value['future'] and then unlock job_value['lock'].
			# Rest of threads tries to acquire job_value['lock'] in a blocking manner. By the time they acquire it job_value['future'] is already set by first thread, so they may simply return this value.
			job_value = self._jobs_registry.setdefault(job_id, new_job_value)
			is_first = bool(job_value is new_job_value)
			if (is_first):
				#logger.debug("Task '%s' will be executed" % job_id)
				wrapped_fn = functools.partial(self._wrap_fn, fn, job_id)
				future = ThreadPoolExecutor.submit(self, wrapped_fn, *args, **kwargs)
				job_value['future'] = future
				#logger.debug("Task '%s' registered as %s" % (job_id, future))
				return future
			else:
				#logger.debug("Task '%s' is a duplicate of another active task" % job_id)
				job_value['lock'].acquire(True)
				job_value['lock'].release()
				#logger.debug("Task '%s' bound to running task %s" % (job_id, job_value['future']))
				return job_value['future']
		except BaseException as t:
			logger.exception("Task '%s' failed" % job_id)
		finally:
			new_job_lock.release()
