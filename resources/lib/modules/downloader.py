# -*- coding: utf-8 -*-

"""
	Venom Add-on
"""

import os
import re

try:
	from urlparse import parse_qsl, urlparse
except:
	from urllib.parse import parse_qsl, urlparse

try:
	from urllib.request import urlopen, Request
except:
	from urllib2 import urlopen, Request

from resources.lib.modules import control
from resources.lib.modules import log_utils


def download(name, image, url):
	# log_utils.log('name = %s' % str(name), log_utils.LOGDEBUG)
	try:
		if url is None:
			control.hide()
			return
		try:
			headers = dict(parse_qsl(url.rsplit('|', 1)[1]))
		except:
			headers = dict('')

		url = url.split('|')[0]

		content = re.compile('(.+?)(?:\.| - |-|\s)(?:S|s)(\d*)(?:E|e)\d*').findall(name.replace('\'', ''))
		transname = name.translate(None, '\/:*?"<>|').strip('.')
		ext_list = ['.mp4', '.mkv', '.flv', '.avi', '.mpg']
		for i in ext_list:
			transname = transname.rstrip(i)

		levels =['../../../..', '../../..', '../..', '..']
		if len(content) == 0:
			dest = control.setting('movie.download.path')
			dest = control.transPath(dest)
			for level in levels:
				try:
					control.makeFile(os.path.abspath(os.path.join(dest, level)))
				except:
					pass
			control.makeFile(dest)
			dest = os.path.join(dest, transname)
			control.makeFile(dest)
		else:
			dest = control.setting('tv.download.path')
			dest = control.transPath(dest)
			for level in levels:
				try:
					control.makeFile(os.path.abspath(os.path.join(dest, level)))
				except:
					pass
			control.makeFile(dest)
			transtvshowtitle = content[0][0].translate(None, '\/:*?"<>|').strip('.').replace('.', ' ')
			if not transtvshowtitle[0].isupper():
				transtvshowtitle = transtvshowtitle.capitalize()

			dest = os.path.join(dest, transtvshowtitle)
			control.makeFile(dest)
			dest = os.path.join(dest, 'Season %01d' % int(content[0][1]))
			control.makeFile(dest)
		ext = os.path.splitext(urlparse(url).path)[1][1:]
		if not ext in ['mp4', 'mkv', 'flv', 'avi', 'mpg']:
			ext = 'mp4'
		dest = os.path.join(dest, transname + '.' + ext)
		doDownload(url, dest, name, image, headers)
	except:
		log_utils.error()
		pass


def getResponse(url, headers, size):
	try:
		if size > 0:
			size = int(size)
			headers['Range'] = 'bytes=%d-' % size
		req = Request(url, headers=headers)
		resp = urlopen(req, timeout=30)
		return resp
	except:
		log_utils.error()
		return None


def done(title, dest, downloaded):
	try:
		playing = control.player.isPlaying()
		text = control.window.getProperty('GEN-DOWNLOADED')

		if len(text) > 0:
			text += '[CR]'
		if downloaded:
			text += '%s : %s' % (dest.rsplit(os.sep)[-1], '[COLOR forestgreen]Download succeeded[/COLOR]')
		else:
			text += '%s : %s' % (dest.rsplit(os.sep)[-1], '[COLOR red]Download failed[/COLOR]')
		control.window.setProperty('GEN-DOWNLOADED', text)

		if (not downloaded) or (not playing): 
			control.okDialog(title, text)
			control.window.clearProperty('GEN-DOWNLOADED')
	except:
		log_utils.error()
		pass


def doDownload(url, dest, title, image, headers):
	file = dest.rsplit(os.sep, 1)[-1]
	resp = getResponse(url, headers, 0)
	if not resp:
		control.hide()
		control.okDialog(title, dest + 'Download failed: No response from server')
		return
	try:
		content = int(resp.headers['Content-Length'])
	except:
		content = 0
	try:
		resumable = 'bytes' in resp.headers['Accept-Ranges'].lower()
	except:
		resumable = False
	if resumable:
		print("Download is resumable")
	if content < 1:
		control.hide()
		control.okDialog(title, file + 'Unknown filesize: Unable to download')
		return
	size = 1024 * 1024
	mb   = content / (1024 * 1024)
	if content < size:
		size = content
	total   = 0
	notify  = 0
	errors  = 0
	count   = 0
	resume  = 0
	sleep   = 0
	control.hide()
	if control.yesnoDialog(file, 'Complete file is %dMB' % mb, 'Continue with download?', 'Confirm Download', 'Confirm',  'Cancel') == 1:
		return
	print('Download File Size : %dMB %s ' % (mb, dest))

	#f = open(dest, mode='wb')
	f = control.openFile(dest, 'w')
	chunk  = None
	chunks = []

	while True:
		downloaded = total
		for c in chunks:
			downloaded += len(c)
		percent = min(100 * downloaded / content, 100)
		if percent >= notify:
			control.execute("XBMC.Notification(%s,%s,%i,%s)" % ( title + ' - Download Progress - ' + str(percent)+'%', dest, 10000, image))
			print('Download percent : %s %s %dMB downloaded : %sMB File Size : %sMB' % (str(percent)+'%', dest, mb, downloaded / 1000000, content / 1000000))
			notify += 10
		chunk = None
		error = False
		try:
			chunk  = resp.read(size)
			if not chunk:
				if percent < 99:
					error = True
				else:
					while len(chunks) > 0:
						c = chunks.pop(0)
						f.write(c)
						del c
					f.close()
					print('%s download complete' % (dest))
					return done(title, dest, True)
		except Exception, e:
			print(str(e))
			error = True
			sleep = 10
			errno = 0
			if hasattr(e, 'errno'):
				errno = e.errno
			if errno == 10035: # 'A non-blocking socket operation could not be completed immediately'
				pass
			if errno == 10054: #'An existing connection was forcibly closed by the remote host'
				errors = 10 #force resume
				sleep  = 30
			if errno == 11001: # 'getaddrinfo failed'
				errors = 10 #force resume
				sleep  = 30

		if chunk:
			errors = 0
			chunks.append(chunk)
			if len(chunks) > 5:
				c = chunks.pop(0)
				f.write(c)
				total += len(c)
				del c

		if error:
			errors += 1
			count  += 1
			print('%d Error(s) whilst downloading %s' % (count, dest))
			# xbmc.sleep(sleep*1000)
			control.sleep(sleep*1000)

		if (resumable and errors > 0) or errors >= 10:
			if (not resumable and resume >= 50) or resume >= 500:
				#Give up!
				print('%s download canceled - too many error whilst downloading' % (dest))
				return done(title, dest, False)
			resume += 1
			errors  = 0

			if resumable:
				chunks  = []
				#create new response
				print('Download resumed (%d) %s' % (resume, dest))
				resp = getResponse(url, headers, total)
			else:
				#use existing response
				pass
