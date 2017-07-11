#!/home/stephan/.virtualenvs/cvp0/bin/python

import cv2
import time
from pbcvt_arch import GPU_HOG, BGS_MOG2
surl = "http://admin:pascal29@dlink1.iv.at:81/video.cgi#" 
video = "video2.h264"
CAP = cv2.VideoCapture(video)

# gpu
gpuhog = GPU_HOG(1.15, 0)
gpumog2 = BGS_MOG2(2, 2)

'''
# cpu
cpuhog = cv2.HOGDescriptor()
cpuhog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

#img = cv2.imread("photo.jpg")
#a0 = gpuhog.detectMultiScale(img)
while True:
	ret, img = CAP.read()
	t = time.time()
	gpuhogrects = gpuhog.detectMultiScale(img)
	vi = gpumog2.apply(img)
	print(len(vi))
	print(img.shape)
	print("--------------------------")

	if gpuhogrects:
		x,y,w,h = gpuhogrects[0]
		cv2.rectangle(img, (x,y), (x+w,y+h),(255,0,0),2)
	cv2.imshow("AI",img)
	ch = cv2.waitKey(1) & 0xFF
	if ch == 27 or ch == ord("q"):
		break
	time.sleep(0.01)'''

