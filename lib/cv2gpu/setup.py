from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

#  python setup.py build_ext --inplace

cudapath = "/usr/local/cuda"
libdr = ["/usr/local/lib", "/usr/local/cuda/lib64"]
incdr = ["/usr/local/include/", "/usr/local/cuda/include"]
 
 
setup(
  name = 'app',
  ext_modules=[ 
    Extension("cvgpu", 
              sources=["cvgpu.pyx", "ocvgpu.cpp"], # Note, you can link against a c++ library instead of including the source
              include_dirs=incdr,
              library_dirs = libdr,
              extra_compile_args=["-std=c++11"],
              libraries=["opencv_core", "opencv_highgui", "opencv_objdetect","opencv_cudabgsegm","opencv_cudaobjdetect","opencv_shape","opencv_stitching",
					"opencv_cudafeatures2d","opencv_cudacodec","opencv_videostab","opencv_cudaoptflow","opencv_cudalegacy","opencv_calib3d",
					"opencv_features2d", "opencv_videoio","opencv_photo","opencv_imgcodecs", "opencv_cudawarping", "opencv_cudaimgproc", "opencv_cudafilters", "opencv_video",
					"opencv_ml", "opencv_imgproc","opencv_flann","opencv_cudaarithm","opencv_cudev", "cublas", "cudart", "cufft", "cuinj64", "curand", "cusolver",
					"cusparse"],
              language="c++"),
    ],
  cmdclass = {'build_ext': build_ext},
 
)
