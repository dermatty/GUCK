from libcpp.vector cimport vector
from libc.string cimport memcpy
import numpy as np
cimport numpy as npc

cdef extern from "opencv2/core/cvdef.h":
	cdef int CV_8U
	cdef int CV_8S
	cdef int CV_16U
	cdef int CV_16S
	cdef int CV_32S
	cdef int CV_32F
	cdef int CV_64F
	cdef int CV_MAKETYPE(int, int)
	cdef int CV_MAT_DEPTH(int)
	cdef int CV_MAT_CN(int)

cdef extern from "opencv2/core/mat.hpp" namespace "cv":
	cdef cppclass Mat:
		Mat()
		Mat(int, int, int)
		int type()
		void* data
		int cols
		int rows

def nptype2cvtype(npty, nch):
	if npty == np.uint8:
		r = CV_8U
	elif npty == np.int8:
		r = CV_8S
	elif npty == np.uint16:
		r = CV_16U
	elif npty == np.int16:
		r = CV_16S
	elif npty == np.int32:
		r = CV_32S
	elif npty == np.float32:
		r = CV_32F
	elif npty == np.float64:
		r = CV_64F 
	return CV_MAKETYPE(r, nch)

cdef Mat nparray2cvmat(npc.ndarray ary):
	if ary.ndim==3 and ary.shape[2]==1:
		ary = ary.reshape(ary.shape[0], ary.shape[1])
	cdef int r = ary.shape[0]
	cdef int c = ary.shape[1]
	if ary.ndim == 2:
		nch = 1
	else:
		nch = ary.shape[2]
	cdef Mat outmat = Mat(r, c, nptype2cvtype(ary.dtype, nch))
	memcpy(outmat.data, ary.data, ary.nbytes)
	return outmat

cdef extern from "ocvgpu.h": 
	cdef cppclass Gpu_hog:
		Gpu_hog(double scale, double ht)
		vector[vector[long]] detectMultiScale(Mat);
		
cdef class pyGpu_hog: 
	cdef Gpu_hog* thisptr # hold a C++ instance
	def __cinit__(self, scale0, ht0):
		self.thisptr = new Gpu_hog(scale0, ht0)
	def __dealloc__(self):
		del self.thisptr
	def detectMultiScale(self, img0):
		cdef Mat img = nparray2cvmat(img0);
		cdef vector[vector[long]] res
		res = self.thisptr.detectMultiScale(img)
		return [tuple(ll) for ll in res]
