#include "ocvgpu.h"

Gpu_hog::Gpu_hog(double scale0, double ht0) {
	win_width = 64;
    win_stride_width = 8;
    win_stride_height = 8;
    block_width = 16;
    block_stride_width = 8;
    block_stride_height = 8;
    cell_width = 8;
    nbins = 9;
    nlevels = 13;
    gr_threshold = 2;
    
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

Gpu_hog::~Gpu_hog() {
}

std::vector< std::vector <long> > Gpu_hog::detectMultiScale(cv::Mat inputImage) {
	
    unsigned int i;
	
	std::vector<cv::Rect> found_gpu;
	std::vector< std::vector <long> > res;
	
	if(inputImage.empty()) {
		return res;
	}
	
	cv::Mat img0;
	cv::cvtColor(inputImage, img0, cv::COLOR_BGR2BGRA);
	
	cv::cuda::GpuMat gpu_img;
	gpu_img.upload(img0);
	gpu_hog->detectMultiScale(gpu_img, found_gpu);
    
	if (!found_gpu.empty()) {	
		for(i = 0; i < found_gpu.size();i++) { 
				std::vector <long> rect {found_gpu[0].x, found_gpu[0].y, found_gpu[0].width, found_gpu[0].height};
				res.push_back(rect);
		}
	}	
	return res;
}
