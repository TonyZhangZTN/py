import os
import requests
import json
import shutil
from requests.adapters import HTTPAdapter
import re
import difflib
import pymysql
import time
import threading
from datetime import datetime
playlistURL = "http://localhost:3000/user/playlist"
detailURL = "http://localhost:3000/user/detail"
followsURL = "http://localhost:3000/user/follows"
followedsURL = "http://localhost:3000/user/followeds"

def quickGet(url,args):
	try:
		s = requests.Session()
		s.mount('http://',HTTPAdapter(max_retries=100))#设置重试次数为10次
		s.mount('https://',HTTPAdapter(max_retries=100))
		buffer = s.get(url+args,timeout=0.1).text
	except requests.exceptions.ConnectionError as e:
		print("连接超时")
	return buffer
def getUserFolloweds(userId):
	#获取关注者
	a = 0
	ret = {}
	lasttime = "10000000000000"
	isMore = False
	while True:
		args = "?uid="+str(userId)+"&limit=300&lasttime=" + lasttime
		buffer = json.loads(quickGet(followedsURL,args))
		l = len(tuple(buffer))
		if buffer['more'] == True:
			isMore = True
			
		else:
			isMore = False
		for i in buffer['followeds']:
			buf = {}
			buf['nickname'] = i['nickname']
			buf['userId'] = i['userId']
			ret[a] = buf
			lasttime = str(i['time'])
			a += 1
		# print("当前id:"+str(userId)+"已有"+str(a)+"关注者")
		if isMore == False or a >= 5000:
			break 

	return ret
def getUserFollows(userId):
	#获取关注的人
	a = 0
	ret = {}
	offset = 0
	isMore = False
	while True:
		args = "?uid="+str(userId)+"&limit=300&offset=" + str(offset)
		buffer = json.loads(quickGet(followsURL,args))
		l = len(tuple(buffer))
		if buffer['more'] == True:
			isMore = True
		else:
			isMore = False
		for i in buffer['follow']:
			buf = {}
			buf['nickname'] = i['nickname']
			buf['userId'] = i['userId']
			ret[a] = buf
			offset += 1
			a += 1
		# print("当前id:"+str(userId)+"已有"+str(a)+"关注者")
		if isMore == False or a >= 5000:
			break 
	return ret
def getUserPlaylist(userId):
	#获取用户歌单
	a = 0
	ret = {}
	offset = 0
	isMore = False
	while True:
		args = "?uid="+str(userId)+"&limit=50&offset=" + str(offset)
		buffer = json.loads(quickGet(playlistURL,args))
		l = len(tuple(buffer))
		if buffer['more'] == True:
			isMore = True
		else:
			isMore = False
		for i in buffer['playlist']:
			buf = {}
			buf['name'] = i['name']
			if i['description'] != None:
				buf['description'] = i['description']
			else:
				buf['description'] = ""
			ret[a] = buf
			offset += 1
			a += 1
		#print("当前id:"+str(userId)+"已有"+str(a)+"歌单")
		if isMore == False or a >= 5000:
			break 
	# print("当前id:"+str(userId)+"有"+str(a)+"歌单")
	return ret
def getUserDetailed(userId):
	#获取用户详情
	ret = {}
	args = "?uid="+str(userId)
	buffer = json.loads(quickGet(detailURL,args))
	if buffer['code'] == 404:
		ret['code'] = 404
		print("[INFO]用户%d不存在"%(userId))
	else:
		ret['code'] = 200
		ret['nickname'] = buffer['profile']['nickname']
		ret['signature'] = buffer['profile']['signature']
		ret['follows'] = buffer['profile']['follows']
		ret['followeds'] = buffer['profile']['followeds']
	return ret
def isTouhouFan(playlist,detail):
	#是否是东方众
	ret = False
	sign = ["东方Project","车万","东方PROJECT"]
	for i in playlist:
		for j in sign:
			if playlist[i]['name'].find(j) != -1 or playlist[i]['description'].find(j) != -1:
				ret = True
				break
		if ret == True:
			break
	for j in sign:
		if detail['nickname'].find(j) != -1 or detail['signature'].find(j) != -1:
			ret = True
			break
	return ret
def pushNewTouhouFan(conn,userId,depth):
	#先判断有没有在库里，没有就找歌单
	if not ifInTable(conn,userId):
		detail = getUserDetailed(userId)
		if detail['code'] == 200:
			playlist = getUserPlaylist(userId)
			if isTouhouFan(playlist,detail):
				print("Depth"+str(depth)+"昵称\t"+detail['nickname'])
				cursor = conn.cursor()
				sql = 'insert into userinfo (userId,nickname,signature)value(%s,%s,%s)'
				try:
					#防止注入
					cursor.execute(sql,(str(userId),detail['nickname'],detail['signature']))
					conn.commit()	
				except:
					conn.rollback()
	else:
		print("%d已加入库，无需再加入"%(userId))
def traverseTouhouFan(conn,userId,times,depth):

	if ifInTable(conn,userId):
		if ifNeedTraverse(conn,times,userId):
			cursor = conn.cursor()
			followeds = getUserFolloweds(userId)
			follows = getUserFollows(userId)
			l = len(tuple(followeds))+len(tuple(follows))
			i = 0
			for a in followeds:
				i += 1
				print("[Depth:%d]%d/%d"%(depth,i,l))
				pushNewTouhouFan(conn,followeds[a]['userId'],depth)
			for a in follows:
				i += 1
				print("[Depth:%d]%d/%d"%(depth,i,l))
				pushNewTouhouFan(conn,follows[a]['userId'],depth)
			try:
				sql = 'update userinfo set lasttime=%s where userId=%s'
				cursor.execute(sql,(times,str(userId)))
				conn.commit()	
			except:
				conn.rollback()
			for a in followeds:
				traverseTouhouFan(conn,followeds[a]['userId'],time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),depth+1)
			for a in follows:
				traverseTouhouFan(conn,follows[a]['userId'],time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),depth+1)
			ret = 0
		else:
			ret = 1
	else:
		ret = -1
	return ret
def ifNeedTraverse(conn,nowtime,userId):
	#前提是userId存在于库
	ret = False
	cursor = conn.cursor()
	try:
		sql = 'select * from userinfo where userId=%s'
		cursor.execute(sql,(str(userId)))
		conn.commit()	
	except:
		conn.rollback()
	data = cursor.fetchall()
	#%Y-%m-%d %H:%M:%S
	if data[0][4] == None:
		print("%d的时间空的"%userId)
		ret = True
	else:
		ret = (datetime.strptime(nowtime, "%Y-%m-%d %H:%M:%S") - data[0][4]).total_seconds() > 604800
	return ret
def ifInTable(conn,userId):
	cursor = conn.cursor()
	try:
		sql = 'select * from userinfo where userId=%s'
		cursor.execute(sql,(str(userId)))
		conn.commit()	
	except:
		conn.rollback()
	data = cursor.fetchall()
	return len(data) >= 1
def detectFromAToB(conn,a,b):
	for userId in range(a,b+1):
		pushNewTouhouFan(conn,userId,0)
		#print(userId)
class processThread(threading.Thread):
	def __init__(self,threadId,startId,endId,conn):
		threading.Thread.__init__(self)
		self.threadId = threadId
		self.startId = startId
		self.endId = endId
		self.conn = conn
	def run(self):
		detectFromAToB(self.conn,self.startId,self.endId)
def divideTasks(conn,a,b,numThreads):
	thread = {}
	t = 0
	all = b - a + 1
	each = max(all//numThreads,1)
	while(all > 0):
		if all // each >= 1:
			thread[t] = processThread(t,a,a + each -1,conn)
			all -= each;
			a += each
			t += 1;
		else:
			thread[t] = processThread(t,a,b,conn)
			all = 0
	for t in thread:
		thread[t].start()
	for t in thread:
		thread[t].join()

def main():
	conn = pymysql.connect("127.0.0.1","root","tony20040219","cloudmusic",charset='utf8mb4')
	userId = int(input("人id"))
	times = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
	pushNewTouhouFan(conn,userId,0)
	print(traverseTouhouFan(conn,userId,times,1))
	# a = int(input("startId:"))
	# b = int(input("endId"))
	# divideTasks(conn,a,b,2)
	conn.close()
if __name__ == '__main__':
	main()
