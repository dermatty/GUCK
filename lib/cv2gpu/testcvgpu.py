#!/home/stephan/.virtualenvs/cvp0/bin/python

import cv2
import time
from cvgpu import pyGpu_hog
surl = "http://admin:pascal29@dlink1.iv.at:81/video.cgi#" 
video = "video2.h264"
CAP = cv2.VideoCapture(surl)

# gpu
gpuhog = pyGpu_hog(1.15, 0)

# cpu
cpuhog = cv2.HOGDescriptor()
cpuhog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

#img = cv2.imread("photo.jpg")
#a0 = gpuhog.detectMultiScale(img)
while True:
	ret, img = CAP.read()
	t = time.time()
	gpuhogrects = gpuhog.detectMultiScale(img)
	'''gputime = time.time() - t
	t = time.time()
	cpuhogrects = cpuhog.detectMultiScale(img,winStride=(4, 4), padding=(8, 8), scale=1.15)
	cputime = time.time() - t
	print(gputime,"     ", cputime,"    ",gputime/cputime)'''
	if gpuhogrects:
		x,y,w,h = gpuhogrects[0]
		cv2.rectangle(img, (x,y), (x+w,y+h),(255,0,0),2)
	cv2.imshow("AI",img)
	ch = cv2.waitKey(1) & 0xFF
	if ch == 27 or ch == ord("q"):
		break
	time.sleep(0.01)

