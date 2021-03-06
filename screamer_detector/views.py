from .models import *
from .executor import UniqueTaskThreadPoolExecutor
import screamer_detector.detector as detector

import os
import hashlib
import json
import logging
import itertools
import multiprocessing
import types

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, ParseResult

from django.shortcuts import render
from django.http import HttpResponse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

MAIN_DOMAIN = '2ch.hk'
MIRRORS = {MAIN_DOMAIN, '2ch.cm', '2ch.pm', '2ch.re', '2ch.tf', '2ch.wf', '2ch.yt', '2-ch.so'}
PROCESSING_TIMEOUT_SEC = 30

DOWNLOADERS_POOL_SIZE = 10
ANALIZERS_POOL_SIZE = multiprocessing.cpu_count()
MAIN_POOL_SIZE = DOWNLOADERS_POOL_SIZE + ANALIZERS_POOL_SIZE


#TODO: background prefetch threads
#TODO: queue size limits?

def url_preprocess(parsed_url):
	if (not parsed_url.netloc in MIRRORS):
		raise Exception("Supported domains are: %s" % MIRRORS)
	return ParseResult(parsed_url.scheme, MAIN_DOMAIN, parsed_url.path, None, parsed_url.query, None)

def md5(filename):
	hash_md5 = hashlib.md5()
	with open(filename, 'rb') as file:
		while True:
			chunk = file.read(4096)
			if not chunk:
				break
			hash_md5.update(chunk)

	return hash_md5.hexdigest()

def render_response(url_object, request):
	if (not url_object.error):
		content_object = url_object.content
		report = {'max_volume': str(content_object.max_volume), 'screamer_chance': content_object.screamer_chance, 'duration_msec': content_object.duration_msec, 'volume_range': str(content_object.screamer_chance)}
		response = json.dumps(report)
		logger.info('%s -> %s' % (url_object.url, response))
		return HttpResponse(response)
	else:
		logger.info('%s -> %s' % (url_object.url, url_object.error))
		return HttpResponse(url_object.error, status=500)

def write_results_to_object(results, content_object):
	content_object.max_volume = results['max_volume']
	content_object.screamer_chance = results['screamer_chance']
	content_object.duration_msec = results['duration_msec']
	content_object.volume_range = results['volume_range']


def download_video(url):
	try:
		logger.info('%s download started' % (url))
		file = detector.download_video(url)
		logger.info('%s download finished' % (url))
		return file
	except Exception as e:
		logger.info('%s download failed: %s' % (url, str(e)))
		raise e

downloaders_pool = ThreadPoolExecutor(max_workers=DOWNLOADERS_POOL_SIZE)

def analyze_video(url, filename):
	try:
		logger.info('%s analize started' % (url))
		results = detector.analyze_video(filename)
		logger.info('%s analize finished' % (url))
		return results
	except Exception as e:
		logger.exception('%s analize failed: %s' % url)
		raise e

analizers_pool = ThreadPoolExecutor(max_workers=ANALIZERS_POOL_SIZE)

def main_process(url):
	logger.info("%s processing started" % url)

	# Look in DB
	existing_url_object = URL.objects.filter(url=url).first()
	if (existing_url_object):
		logger.info('%s is known URL: %s' % (url, str(existing_url_object)))
		return existing_url_object

	video_file = None
	try:
		# Download
		try:
			video_file = downloaders_pool.submit(download_video, url).result() # Download using threads pool
		except Exception as e:
			(url_object, _) = URL.objects.get_or_create(url=url, defaults={'error': str(e)}) # this should always create new object unless something broke
			logger.exception('%s caused failure: %s' % (url, str(url_object)))
			return url_object
		
		# Search for content in DB
		video_size = os.path.getsize(video_file.name)
		video_md5 = md5(video_file.name)
		existing_content = Content.objects.filter(size=video_size, md5=video_md5).first()
		if (existing_content):
			(url_object, _) = URL.objects.get_or_create(url=url, defaults={'content': existing_content}) # this should always create new object unless something broke
			logger.info('%s refers to known video %s' % (url, str(existing_content)))
			return url_object

		# Analize
		try:
			result = analizers_pool.submit(analyze_video, url, video_file.name).result()
			
			content_object = Content(size=video_size, md5=video_md5)
			write_results_to_object(result, content_object)
			content_object.save()
			
			logger.info('%s stored as %s' % (url, str(content_object)))
			
			(url_object, _) = URL.objects.get_or_create(url=url, defaults={'content': content_object}) # this should always create new object unless something broke
			return url_object
		except Exception as e:
			(url_object, _) = URL.objects.get_or_create(url=url, defaults={'error': str(e)}) # this should always create new object unless something broke
			logger.exception('%s caused failure: %s' % (url, str(content_object)))
			return url_object
	finally:
		if (video_file):
			video_file.close()
			os.remove(video_file.name)

main_pool = UniqueTaskThreadPoolExecutor(max_workers=MAIN_POOL_SIZE)

def detect_screamers(request):
	if request.method == 'GET':
		try:
			url = request.GET['url']
			URLValidator()(url)
			parsed_url = url_preprocess(urlparse(url))
			url = parsed_url.geturl()
		except Throwable:
			logger.debug('%s is invalid URL:' % (url))
			return HttpResponse('Invalid URL', status=500)

		try:
			url_object = main_pool.submit(main_process, url).result(timeout=PROCESSING_TIMEOUT_SEC)
			return render_response(url_object, request)
		except TimeoutError:
			logger.info("%s processing timed out" % url)
			return HttpResponse('Processing was timed out after %d seconds' % PROCESSING_TIMEOUT_SEC, status=500)
		except Exception as e:
			logger.info("%s processing failed - %s" % (url, str(e)))
			return HttpResponse('Error while processing', status=500)
	else:
		return HttpResponse(status=500)

def lookup_url_in_db(url):
	logger.debug('%s is being checked' % url)
	url_object = URL.objects.filter(url=url).first()
	if (not url_object):
		logger.info("%s is unknown URL, it will be analized." % url)
		main_pool.submit(main_process, url)
	else:
		logger.debug('%s was found in DB: %s' % (url, str(url_object)))
	return url_object

@csrf_exempt
def detect_screamers_batch(request):
	if request.method == 'POST': # POST is used as list of URLs can be long
		urls = request.POST['urls']
		if (not urls):
			return HttpResponse('Request should contain JSON list of WEBM urls as "urls" parameter', status=500)
		urls_list = []
		try:
			urls_list = json.loads(urls)
		except json.decoder.JSONDecodeError as e:
			return HttpResponse('Request "urls" parameter isn\'t valid JSON string', status=500)
		if (not type(urls_list) is list):
			return HttpResponse('Request "urls" parameter isn\'t JSON list', status=500)

		responses = {}
		for url in urls_list:
			if (type(url) is not str):
				continue
			try:
				URLValidator()(url)
				parsed_url = url_preprocess(urlparse(url))
				fixed_url = parsed_url.geturl()

				url_object = lookup_url_in_db(fixed_url)

				if (not url_object):
					continue # Skip url if it is valid, but wasn't analized yes

				content_object = url_object.content

				if (url_object.error):
					responses[url] = None # Return null for URLs which were processed with error
				else:
					if (content_object.max_volume):
						responses[url] = str(content_object.max_volume) # Return result for valid URLs
			except Exception:
				responses[url] = None # Return null for invalid URLs
			
		return HttpResponse(json.dumps(responses))
	return HttpResponse('Only POST is supported by this method', status=500)