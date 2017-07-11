#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#define PY_ARRAY_UNIQUE_SYMBOL pbcvt_ARRAY_API

#include <iostream>
#include <sys/time.h>
#include <chrono>

#include "boost/python.hpp"
#include "boost/python/suite/indexing/vector_indexing_suite.hpp"
#include "pyboostcvconverter.h"
#include <opencv2/opencv.hpp>
#include <opencv2/objdetect.hpp>
#include <opencv2/opencv_modules.hpp>
#include <opencv2/highgui/highgui.hpp>
#include "opencv2/cudaobjdetect.hpp"
#include "opencv2/cudafeatures2d.hpp"
#include "opencv2/xfeatures2d/cuda.hpp"
#include "opencv2/features2d.hpp"
#include "opencv2/cudabgsegm.hpp"
#include "opencv2/cudalegacy.hpp"
#include "opencv2/core.hpp"
#include <opencv2/core/cuda.hpp>




	
	

class Point_pb {
	public:
		int x, y, w, h;
		bool operator==(Point_pb const& n) const 
			{ return (x == n.x) && (y == n.y) && (w == n.w) && (h == n.h); }
};

class CASCADE {
	
	public:
	cv::Ptr<cv::cuda::CascadeClassifier> cascade_gpu;
	CASCADE(std::string s, double scale) {
			cascade_gpu = cv::cuda::CascadeClassifier::create(s);
			cascade_gpu->setFindLargestObject(false);
            cascade_gpu->setScaleFactor(scale);
			cascade_gpu->setMinNeighbors(5);
			
	}
	std::vector<Point_pb>  detectMultiScale(PyObject* inputImage) {
		
		cv::Mat colormat = pbcvt::fromNDArrayToMat(inputImage);
		cv::Mat mat0; 
		cv::cvtColor(colormat, mat0, CV_BGR2GRAY);
		cv::cuda::GpuMat imggpu(mat0);
		cv::cuda::GpuMat imbuf_gpu;
		std::vector<cv::Rect> detections;
		
		cascade_gpu->detectMultiScale(imggpu, imbuf_gpu);
		cascade_gpu->convert(imbuf_gpu, detections);

		std::vector<Point_pb> res;
		Point_pb p0;
		for (size_t i = 0; i < detections.size(); i++) {
			p0.x = detections[i].x;
			p0.y = detections[i].y;
			p0.w = detections[i].width;
			p0.h = detections[i].height;
			res.push_back(p0);
		}
		return res;
	}
};

class GPU_HOG {
	public:
	cv::Ptr<cv::cuda::HOG> gpu_hog;
	double scale;
    double hit_threshold;
	GPU_HOG(double scale0, double ht0) {
		int win_width = 64;
		int win_stride_width = 8;
		int win_stride_height = 8;
		int block_width = 16;
		int block_stride_width = 8;
		int block_stride_height = 8;
		int cell_width = 8;
		int nbins = 9;
		int nlevels = 13;
		int gr_threshold = 4;
		cv::Size win_stride(win_stride_width, win_stride_height);
		cv::Size win_size(win_width, win_width * 2);
		cv::Size block_size(block_width, block_width);
		cv::Size block_stride(block_stride_width, block_stride_height);
		cv::Size cell_size(cell_width, cell_width);
		scale = scale0;
		hit_threshold =  ht0;
		gpu_hog = cv::cuda::HOG::create(win_size, block_size, block_stride, cell_size, nbins);
		cv::Mat detector = gpu_hog->getDefaultPeopleDetector();
		gpu_hog->setSVMDetector(detector);
		gpu_hog->setNumLevels(nlevels);
		gpu_hog->setHitThreshold(hit_threshold);
		gpu_hog->setWinStride(win_stride);
		gpu_hog->setScaleFactor(scale);
		gpu_hog->setGroupThreshold(gr_threshold);
	}

	std::vector<Point_pb>  detectMultiScale(PyObject* inputImage) {
		unsigned int i;
		std::vector<Point_pb> res;
		Point_pb p0;
		std::vector<cv::Rect> found_gpu;
		cv::Mat mat0 = pbcvt::fromNDArrayToMat(inputImage);
		if(mat0.empty()) {
			return res;
		}
		cv::Mat img0;
		cv::cvtColor(mat0, img0, cv::COLOR_BGR2BGRA);
		cv::cuda::GpuMat gpu_img;
		gpu_img.upload(img0);
		gpu_hog->detectMultiScale(gpu_img, found_gpu);
  
		if (!found_gpu.empty()) {	
			for(i = 0; i < found_gpu.size();i++) { 
				// warum hier [0] !!!?? und nicht [i] !!!???
				p0.x = found_gpu[i].x;
				p0.y = found_gpu[i].y;
				p0.w = found_gpu[i].width;
				p0.h = found_gpu[i].height;
				res.push_back(p0);
			}
		}	
		return res;
	}
};

class keypoint_pb {
	public:
		float angle;
		int class_id;
		int octave;
		boost::python::tuple pt;
		float response;
		float size;
		bool operator==(keypoint_pb const& n) const 
			{ return true; }
};

class GPU_ORB {
	public:
		cv::Ptr<cv::cuda::ORB> orb;		
		std::vector<keypoint_pb> keypoints0;
		
		GPU_ORB() {
/*
 * int nfeatures,  	
                                         float scaleFactor,
                                         int nlevels,
                                         int edgeThreshold,
                                         int firstLevel,
                                         int WTA_K,
                                         int scoreType,
                                         int patchSize,
                                         int fastThreshold,
										 bool blurForDescriptor)*/
			orb = cv::cuda::ORB::create(500, 1.15f, 8, 31, 1, 2, 0, 31, 20, true);
			// orb->setBlurForDescriptor(true);
		}
		
		std::vector<keypoint_pb> getkeypoints() {
			return keypoints0;
		}
			
		PyObject* detectAndCompute(PyObject* inputImage0, int x, int y, int w, int h) {
				keypoints0.clear();
				cv::Mat mat = pbcvt::fromNDArrayToMat(inputImage0);
				cv::Mat croppedinputImage;
				mat(cv::Rect(x,y,w,h)).copyTo(croppedinputImage);
				cv::cuda::GpuMat imggpu(croppedinputImage), imggraygpu;
				//cv::Mat mat0; 
				//cv::cvtColor(colormat, mat0, CV_BGR2GRAY);
				//cv::cuda::GpuMat imggpu(mat0);
				cv::cuda::cvtColor(imggpu, imggraygpu, CV_BGR2GRAY);
				std::vector<cv::KeyPoint> keypoints;
				cv::cuda::GpuMat desc_gpu, keyp_gpu;
				cv::Mat desc_cpu;

				//orb->detect(imggpu, keypoints);
				//orb->compute(imggpu, keypoints, desc_gpu);

				orb->detectAndComputeAsync(imggraygpu, cv::cuda::GpuMat(), keyp_gpu, desc_gpu, false);
				orb->convert(keyp_gpu, keypoints);
				int i;
				//orb->detectAndCompute(imggpu, cv::noArray(), keypoints, desc_gpu, false);
				for (i=0;i<keypoints.size();i++) {
					keypoint_pb kp0;
					kp0.angle = keypoints[i].angle;
					kp0.class_id = keypoints[i].class_id;
					kp0.octave = keypoints[i].octave;
					kp0.response = keypoints[i].response;
					kp0.size = keypoints[i].size;
					kp0.pt = boost::python::make_tuple(keypoints[i].pt.x, keypoints[i].pt.y);
					
					keypoints0.push_back(kp0); 
				}
				desc_gpu.download(desc_cpu);
				PyObject *ret = pbcvt::fromMatToNDArray(desc_cpu);
				return ret;
		}
};

class CPU_ORB {
	public:
		cv::Ptr<cv::ORB> orb;		
		std::vector<keypoint_pb> keypoints0;
		
		CPU_ORB() {
			orb = cv::ORB::create();
		}
		
		std::vector<keypoint_pb> getkeypoints() {
			return keypoints0;
		}
			
		PyObject* detectAndCompute(PyObject* inputImage) {
				keypoints0.clear();
				cv::Mat mat0 = pbcvt::fromNDArrayToMat(inputImage);
				std::vector<cv::KeyPoint> keypoints;
				cv::Mat desc_cpu;
				orb->detectAndCompute(mat0, cv::noArray(), keypoints, desc_cpu, false);
				int i;
				for (i=0;i<keypoints.size();i++) {
					keypoint_pb kp0;
					kp0.angle = keypoints[i].angle;
					kp0.class_id = keypoints[i].class_id;
					kp0.octave = keypoints[i].octave;
					kp0.response = keypoints[i].response;
					kp0.size = keypoints[i].size;
					kp0.pt = boost::python::make_tuple(keypoints[i].pt.x, keypoints[i].pt.y);
					
					keypoints0.push_back(kp0); 
				}
				PyObject *ret = pbcvt::fromMatToNDArray(desc_cpu);
				return ret;
		}
};


class BGS_MOG2 {
	public:
		cv::Ptr<cv::BackgroundSubtractor> mog2;
		BGS_MOG2(int hist, int thresh) {
			mog2 = cv::cuda::createBackgroundSubtractorMOG2(hist, thresh, true);
		}

		boost::python::tuple apply(PyObject* inputImage) {
			cv::Mat mat0 = pbcvt::fromNDArrayToMat(inputImage);
			
			cv::cuda::GpuMat d_frame, d_fgmask, d_bgimg, d_fgimg;
			cv::Mat fgmask, fgimg, bgimg;
			d_frame.upload(mat0);
			
			mog2->apply(d_frame, d_fgmask);
			mog2->getBackgroundImage(d_bgimg);
			
			d_fgimg.create(d_frame.size(), d_frame.type());
			d_fgimg.setTo(cv::Scalar::all(0));
			d_frame.copyTo(d_fgimg, d_fgmask);

			d_fgmask.download(fgmask);
			d_fgimg.download(fgimg);
			if (!d_bgimg.empty())
				d_bgimg.download(bgimg);
			
			//PyObject *ret = pbcvt::fromMatToNDArray(bgimg);
			//PyObject *ret = boost::python::make_tuple(fgmask, fgimg, bgimg);
			return boost::python::make_tuple(fgmask, fgimg, bgimg);
		}
}; // BGS_MOG2

namespace pbcvt {

using namespace boost::python;

PyObject *dot(PyObject *left, PyObject *right) {

        cv::Mat leftMat, rightMat;
        leftMat = pbcvt::fromNDArrayToMat(left);
        rightMat = pbcvt::fromNDArrayToMat(right);
        auto c1 = leftMat.cols, r2 = rightMat.rows;
        // Check that the 2-D matrices can be legally multiplied.
        if (c1 != r2) {
            PyErr_SetString(PyExc_TypeError,
                            "Incompatible sizes for matrix multiplication.");
            throw_error_already_set();
        }
        cv::Mat result = leftMat * rightMat;
        PyObject *ret = pbcvt::fromMatToNDArray(result);
        return ret;
}

PyObject *test(PyObject *left)
{
	cv::Mat leftMat;
	leftMat = pbcvt::fromNDArrayToMat(left);
	PyObject *ret = pbcvt::fromMatToNDArray(leftMat);
    return ret;
}

#if (PY_VERSION_HEX >= 0x03000000)
    static void *init_ar() {
#else
    static void init_ar(){
#endif

	Py_Initialize();
	import_array();
	return NUMPY_IMPORT_ARRAY_RETVAL;
}

BOOST_PYTHON_MODULE(pbcvt_arch)
{	
	 init_ar();
     //initialize converters
     to_python_converter<cv::Mat, pbcvt::matToNDArrayBoostConverter>();
	 pbcvt::matFromNDArrayBoostConverter();
	 
	 class_<Point_pb> ("Point_pb")
		.def_readwrite("x", &Point_pb::x)
		.def_readwrite("y", &Point_pb::y)
		.def_readwrite("w", &Point_pb::w)
		.def_readwrite("h", &Point_pb::h)
	 ;
	 
	 class_< std::vector<Point_pb> > ("pointArray")
        .def(vector_indexing_suite< std::vector<Point_pb> >())
     ;
    
     class_<keypoint_pb> ("keypoint_pb")
		.def_readwrite("angle", &keypoint_pb::angle)
		.def_readwrite("class_id", &keypoint_pb::class_id)
		.def_readwrite("octave", &keypoint_pb::octave)
		.def_readwrite("pt", &keypoint_pb::pt)
		.def_readwrite("response", &keypoint_pb::response)
		.def_readwrite("size", &keypoint_pb::size)
	 ;
     
     class_< std::vector<keypoint_pb> > ("keypointArray")
        .def(vector_indexing_suite< std::vector<keypoint_pb> >())
     ;
     
     
	 class_<GPU_ORB>("GPU_ORB")
		.def("detectAndCompute", &GPU_ORB::detectAndCompute)
		.def("getkeypoints", &GPU_ORB::getkeypoints);
  
     class_<CPU_ORB>("CPU_ORB")
		.def("detectAndCompute", &CPU_ORB::detectAndCompute)
		.def("getkeypoints", &CPU_ORB::getkeypoints);
     
     class_<BGS_MOG2>("BGS_MOG2",init<int, int>())
		.def("apply", &BGS_MOG2::apply);
		
	 class_<GPU_HOG>("GPU_HOG",init<double, double>())
		.def("detectMultiScale", &GPU_HOG::detectMultiScale);
		
	 class_<CASCADE>("CASCADE",init<std::string, double>())
		.def("detectMultiScale", &CASCADE::detectMultiScale);
		
}

}
