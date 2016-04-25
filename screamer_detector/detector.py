import os
import re
import math
import requests
import subprocess
import shlex
from tempfile import NamedTemporaryFile
from concurrent.futures import Future

from urllib.parse import urlparse

MIN_SIZE = 1024
MAX_SIZE = 50*1024*1024
CHUNK_SIZE = 1024
DOWNLOAD_TIMEOUT = 2*60
ACCEPT_MIMETYPES = [None, 'video/webm']
SUPPORTED_SCHEMES = ['http', 'https']
FFMPEG_TIMEOUT=2*60

#TODO: custom Exception type?

'''This dict is used as a lookup table of "badness" of fast transition from one volume level to another.
Volume values are grouped into ranges. Dict key values are upper bounds of range they represent.
Look for lowest key value which is >= your value. Then get dict[former_volume_range_upper_bound][latter_volume_range_upper_bound]
E.g. Change from loudness -27.1 to -5.7 have "badness" = FROM_TO_LOUDNESS_BADNESS[-25][-3] = 90 as -27 is in range (-30 .. -25) and -5 is in range (-6 .. -3)
'''
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

def download_video(url, directory=None):
	'''Download video, checking it's size and MIME type'''
	parsed_url = urlparse(url)

	if (not (parsed_url.scheme in SUPPORTED_SCHEMES)):
		raise Exception('Invalid URL scheme (only %s are supported)' % SUPPORTED_SCHEMES)

	req = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)

	if (req.status_code != 200):
		raise Exception('Got code %s while trying to retrieve URL' % req.status_code)

	if ('Content-Length' in req.headers):
		length = int(req.headers['Content-Length'])
		check_min_file_size(length)
		check_max_file_size(length)

	if (not (req.headers['Content-Type'] in ACCEPT_MIMETYPES)):
		raise Exception('Unsupported content MIME type')

	url_name = parsed_url.path.split('/')[-1] if (not parsed_url.path.endswith('/')) else 'video'

	if (directory and os.path.exists(directory)):
		temp_file = NamedTemporaryFile(prefix=url_name, suffix='.webm', delete=False, dir=directory)
	else:
		temp_file = NamedTemporaryFile(prefix=url_name, suffix='.webm', delete=False)

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

def badness(from_loudness, to_loudness):
	'''Sudden great increase of volume may indicate screamer. Or not.
	Anyway it is bad for ears.
	"badness" value may vary from 0 to 100.
	We report max "badness" value as "screamer_chance".'''
	from_range =  first_leq(from_loudness, FROM_TO_LOUDNESS_BADNESS.keys())
	to_ranges = FROM_TO_LOUDNESS_BADNESS[from_range]
	to_range = first_leq(to_loudness, to_ranges.keys())
	return FROM_TO_LOUDNESS_BADNESS[from_range][to_range]

def analyze_data(data):
	data_records = data['data']
	max_integral_loudness = max(map(lambda record: record['i'], data_records))

	screamer_chance = 0

	if (len(data_records) >= 20):
		for t in range(20, len(data_records)):
			previous_second = sum(map(lambda record: record['m'], data_records[t-10 : t-1])) / 10 #TODO: use data_records[t-1]['i'] instead?
			if (previous_second > -15):
				this_second = max(map(lambda record: record['m'], data_records[t-20 : t-11]))
				current_badness = badness(previous_second, this_second)
				if (current_badness > screamer_chance):
					screamer_chance = current_badness
					#print("%f -> %f: %d" % (this_second, previous_second, current_badness))
	else:
		badness_range = first_leq(max_integral_loudness, ABSOLUTE_LOUDNESS_BADNESS.keys())
		screamer_chance = ABSOLUTE_LOUDNESS_BADNESS[badness_range]
	#TODO: take range into account?
	return {'max_volume': max_integral_loudness, 'screamer_chance': screamer_chance, 'duration_msec': data['duration_msec'], 'volume_range': data['range']}

def analyze_video(video_filename):
	data = None
	cmd = shlex.split('ffmpeg -hide_banner -filter_complex "ebur128=dualmono=true" -f null - -i "%s"' % video_filename) #TODO: use '-threads N', 'ebur128=peak=true' ?
	with NamedTemporaryFile(prefix='ffmpeg_ebur128', mode="w+", encoding='utf-8') as ffmpeg_output:
		subprocess.run(cmd, stdout=ffmpeg_output, stderr=ffmpeg_output, timeout=FFMPEG_TIMEOUT)
		ffmpeg_output.seek(0)
		data = parse_ffmpeg_output(ffmpeg_output)

	if (data == None or data['duration_msec'] == None):
		raise Exception("Can't parse file as video")

	if (data['range'] == None or len(data['data']) == 0):
		#No audio stream means no screamer, right?
		return {'max_volume': -120, 'screamer_chance': 0, 'duration_msec': data['duration_msec'], 'volume_range': 0}

	return analyze_data(data)
