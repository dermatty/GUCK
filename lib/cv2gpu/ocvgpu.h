#ifndef OCVTEST_H
#define OCVTEST_H

#include <iostream>
#include <sys/time.h>
#include <chrono>
#include <opencv2/opencv.hpp>
#include <opencv2/objdetect.hpp>
#include <opencv2/opencv_modules.hpp>
#include <opencv2/highgui/highgui.hpp>
#include "opencv2/cudaobjdetect.hpp"

class Gpu_hog { 
private:
	cv::Ptr<cv::cuda::HOG> gpu_hog;
	int win_width;
    int win_stride_width, win_stride_height;
    int block_width;
    int block_stride_width, block_stride_height;
    int cell_width;
    int nbins;
    int nlevels;
    int gr_threshold;
public:  
	double scale;
    double hit_threshold;
	Gpu_hog(double scale0, double ht0);
	~Gpu_hog();
    std::vector< std::vector <long> > detectMultiScale(cv::Mat inputImage); 
    
};
#endif
