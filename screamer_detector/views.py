from .models import *

import os
import re
import math
import requests
import subprocess
import hashlib
import shlex
import json
import logging
import codecs
from tempfile import NamedTemporaryFile

from urllib.parse import urlparse

from django.shortcuts import render
from django.http import HttpResponse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

logging.basicConfig(filename='screamers.log',level=logging.DEBUG) #TODO: move config to settings.py
logger = logging.getLogger(__name__)

MIN_SIZE = 2**10
MAX_SIZE = 50*2**20
CHUNK_SIZE = 1024
DOWNLOAD_TIMEOUT = 2*60
ACCEPT_MIMETYPES = [None, 'video/webm']
SUPPORTED_SCHEMES = ['http', 'https']
FFPROBE_TIMEOUT=10
FFMPEG_TIMEOUT=2*60

# Change from loudness -27.1 to -5.7 have "badness" = FROM_TO_LOUDNESS_BADNESS[-25][-3] = 90 as -27 is in range (-30 .. -25) and -5 is in range (-6 .. -3)
FROM_TO_LOUDNESS_BADNESS = {
         -30:{-15:0, -10:20, -6:40, -3:95,  0:100, 3:100, math.inf: 100},
         -25:{-15:0, -10:10, -6:30, -3:90,  0:100, 3:100, math.inf: 100},
         -20:{-15:0, -10:5,  -6:15, -3:80,  0:95,  3:100, math.inf: 100},
         -15:{-15:0, -10:0,  -6:10, -3:75,  0:80,  3:99,  math.inf: 100},
         -10:{-15:0, -10:0,  -6:5,  -3:60,  0:70,  3:99,  math.inf: 100},
         -6 :{-15:0, -10:0,  -6:0,  -3:50,  0:60,  3:95,  math.inf: 100},
    math.inf:{-15:0, -10:0,  -6:0,  -3:40,  0:50,  3:95,  math.inf: 100}
}

ABSOLUTE_LOUDNESS_BADNESS = {-15:0, -10:0, -7:5, -5:30, -3:70, 0:95, math.inf: 100}

def check_min_file_size(size):
	if (size < MIN_SIZE):
		raise Exception('File is too small (%d bytes)' % length)
		
def check_max_file_size(size):
	if (size > MAX_SIZE):
		raise Exception('File is too large (%d bytes)' % length)

#TODO: custom Exception type?
def download_video(url):
	parsed_url = urlparse(url)

	if (not (parsed_url.scheme in SUPPORTED_SCHEMES)):
		raise Exception('Invalid URL scheme (only %s are supported)' % SUPPORTED_SCHEMES)

	req = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)

	if (req.status_code != 200):
		raise Exception('Got status %s while trying to retrieve URL' % res.status)

	if ('Content-Length' in req.headers):
		length = int(req.headers['Content-Length'])
		check_min_file_size(length)
		check_max_file_size(length)

	if (not (req.headers['Content-Type'] in ACCEPT_MIMETYPES)):
		raise Exception('Unsupported content MIME type')

	name = parsed_url.path.split('/')[-1]
	temp_file = NamedTemporaryFile(prefix='video', suffix=name, delete=False)
	content_size = 0
	for chunk in req.iter_content(CHUNK_SIZE):
		content_size += len(chunk)
		check_max_file_size(content_size)
		temp_file.write(chunk)

	check_min_file_size(content_size)

	return temp_file

def parse_ffmpeg_output(ffmpeg_output):
	#  Duration: 00:04:32.38, start: 0.000000, bitrate: 320 kb/s
	duration = None
	duration_re = re.compile('\\s*Duration: (\\d\\d):(\\d\\d):(\\d\\d).(\\d\\d),.*')

	#[Parsed_ebur128_0 @ 00000000005afe00] t: 23.303     M: -40.0 S: -39.3     I: -34.5 LUFS     LRA:   6.9 LU  FTPK: -27.9 -28.0 dBFS  TPK: -19.5 -19.5 dBFS
	#[Parsed_ebur128_0 @ 00000000005ed940] t: 19         M: -56.2 S: -30.5     I: -35.1 LUFS     LRA:  12.6 LU  FTPK: -43.9 dBFS  TPK:  -6.0 dBFS
	data = []
	data_re = re.compile (
		'\\[Parsed_ebur128_\\d @ [0-9a-f]{16}\\]\\s+'   #'[Parsed_ebur128_0 @ 00000000005afe00] '
		+ 't:\\s*([\\d.]+)\\s+'                         #'t: 23.303     '     -> '23.303'
		+ 'M:\\s*([-\\d.]+)\\s+'                        #'M: -40.0 '          -> '-40.0'
		+ 'S:\\s*([-\\d.]+)\\s+'                        #'S: -39.3     '      -> '-39.3'
		+ 'I:\\s*([-\\d.]+) LUFS\\s+'                   #'I: -34.5 LUFS     ' -> '-34.5'
		+ 'LRA:\\s*([-\\d.]+) LU\\s+.*'                 #'LRA:   6.9 LU  '    -> '6.9'
		)

	#'    LRA:         4.2 LU'
	lra = None
	lra_re = re.compile('^\\s+LRA:\\s+([\\d.]+) LU')

	for line in ffmpeg_output:
		data_match = re.match(data_re, line)
		if data_match:
			data.append({'m': float(data_match.group(2)), 'i': float(data_match.group(4))})
		else:
			if (duration == None):
				duration_match = re.match(duration_re, line)
				if (duration_match):
					duration = sum(map(lambda i, msec: int(duration_match.group(i))*msec, [1, 2, 3, 4], [3600*1000, 60*1000, 1000, 10]))

			lra_match = re.match(lra_re, line)
			if (lra_match):
				lra = float(lra_match.group(1))

	return {'duration_msec': duration, 'data': data, 'range': lra}

def first_leq(n, lst):
	return next(x for x in sorted(lst) if x >= n)

def analyze_data(data):
	data_records = data['data']
	max_integral_loudness = max(map(lambda record: record['i'], data_records))

	screamer_chance = 0

	if (len(data_records) >= 20):
		for t in range(20, len(data_records)):
			last_second = sum(map(lambda record: record['m'], data_records[t-10 : t-1])) / 10 #TODO: use data_records[t-1]['i'] instead?
			if (last_second > -15):
				previous_second = max(map(lambda record: record['m'], data_records[t-20 : t-11]))
				previous_second = max(previous_second, -30)

				from_range =  first_leq(previous_second, FROM_TO_LOUDNESS_BADNESS.keys())
				to_ranges = FROM_TO_LOUDNESS_BADNESS[from_range]
				to_range = first_leq(last_second, to_ranges.keys())

				current_badness = FROM_TO_LOUDNESS_BADNESS[from_range][to_range]
				if (current_badness > screamer_chance):
					screamer_chance = current_badness
					#print("%f -> %f: %d" % (previous_second, last_second, current_badness))
	else:
		integral_badness_range = first_leq(max_integral_loudness, ABSOLUTE_LOUDNESS_BADNESS.keys())
		screamer_chance = ABSOLUTE_LOUDNESS_BADNESS(integral_badness_range)
	#TODO: take range into account
	return {'max_volume': max_integral_loudness, 'screamer_chance': screamer_chance, 'duration_msec': data['duration_msec'], 'volume_range': data['range']}

def analyze_video(video_filename):
	data = None
	cmd = shlex.split('ffmpeg -hide_banner -filter_complex "ebur128=dualmono=true" -f null - -i "%s"' % video_filename) #TODO: use '-threads N', 'ebur128=peak=true' ?
	logger.info('executing: %s' % cmd)
	with NamedTemporaryFile(prefix='ffmpeg_ebur128', mode="w+", encoding='utf-8') as ffmpeg_output:
		subprocess.run(cmd, stdout=ffmpeg_output, stderr=ffmpeg_output, timeout=FFMPEG_TIMEOUT)
		ffmpeg_output.seek(0)
		data = parse_ffmpeg_output(ffmpeg_output) #TODO: force utf-8?

	if (data == None or data['duration_msec'] == None):
		raise Exception("Can't parse file as video")

	if (data['range'] == None or len(data['data']) == 0):
		#No audio stream means no screamer, right?
		return {'max_volume': -120, 'screamer_chance': 0, 'duration_msec': data['duration_msec'], 'volume_range': 0}

	return analyze_data(data)

def md5(filename):
	hash_md5 = hashlib.md5()
	with open(filename, 'rb') as file:
		while True:
			chunk = file.read(4096)
			if not chunk:
				break
			hash_md5.update(chunk)

	return hash_md5.hexdigest()

def render_response(video, request):
	if (not video.error):
		report = {'max_volume': str(video.max_volume), 'screamer_chance': video.screamer_chance, 'duration_msec': video.duration_msec, 'volume_range': str(video.screamer_chance)}
		response = json.dumps(report)
		logger.info('%s -> %s' % (video.url, response))
		return HttpResponse(response)
	else:
		logger.info('%s -> %s' % (video.url, video.error))
		return HttpResponse(video.error, status=500)

def write_results(results, video_object):
	video_object.max_volume = results['max_volume']
	video_object.screamer_chance = results['screamer_chance']
	video_object.duration_msec = results['duration_msec']
	video_object.volume_range = results['volume_range']

def detect_screamers(request):
	if request.method == 'GET':
		try:
			#TODO: mirrors should be handled as single site
			url = urlparse(request.GET['url']).geturl() #to canonic form
			URLValidator()(url)
		except ValidationError:
			logger.debug('%s is invalid URL:' % (url))
			return HttpResponse('Invalid URL', status=500)

		existing_video_by_url = Video.objects.filter(url=url).first()
		if (existing_video_by_url):
			logger.info('%s is known URL: %s' % (url, str(existing_video_by_url)))
			return render_response(existing_video_by_url, request)

		video_object = None
		video_file = None
		try:
			logger.info('%s download started' % (url))
			video_file = download_video(url)
			logger.info('%s download finished' % (url))
			
			video_size = os.path.getsize(video_file.name)
			video_md5 = md5(video_file.name)

			existing_video_by_hash = Video.objects.filter(md5=video_md5, size=video_size).first()
			if (existing_video_by_hash):
				logger.info('%s refers to known video %s' % (url, str(existing_video_by_hash)))
				existing_video_by_hash.url = url
				existing_video_by_hash.save() #save a copy with new url
				return render_response(existing_video_by_hash, request)
			
			logger.info('%s analysis started' % (url))
			results = analyze_video(video_file.name)
			logger.info('%s analysis finished' % (url))

			video_object = Video(url=url, size=video_size, md5=video_md5)
			write_results(results, video_object)
			video_object.save()
			logger.info('%s stored as %s' % (url, str(video_object)))
		except Exception as e:
			video_object = Video(url=url, error=str(e))
			logger.exception('%s caused failure: %s' % (url, str(video_object)))
			video_object.save()
		finally:
			#TODO check if there is too many Video objects and remove the oldest one
			if (video_file):
				video_file.close()
				os.remove(video_file.name)

		return render_response(video_object, request)
	else:
		return HttpResponse(status=500)
