
PYTHON_INCLUDE = /usr/include/python3.5m #/usr/include/x86_64-linux-gnu/python3.5m /usr/include/numpy #/usr/include/python3.5
PYTHON_LIB = /usr/lib/python3.5/x86_64-linux-gnu
  
CUDA_INCLUDE = /usr/local/cuda/include
CUDA_LIB = /usr/local/cuda/lib64
  
BOOST_INC = /usr/include
BOOST_LIB = /usr/lib
OPENCV_LIB = /usr/local/lib
OPENCV_INC = /usr/local/include
OPENCV_LIBS = $$(pkg-config --libs opencv)

TARGET = pbcvt
CONVERSION = pyboostcvconverter

all: $(TARGET).so

$(TARGET).so: $(TARGET).o $(CONVERSION).o
	g++ -shared -Wl,--export-dynamic,--no-undefined $(TARGET).o $(CONVERSION).o \
	-L$(BOOST_LIB) -lboost_python-py35 \
	$(OPENCV_LIBS) \
	-L$(CUDA_LIB) -lcublas -lcudart -lcufft -lcuinj64 -lcurand -lcusolver -lcusparse \
	-L$(PYTHON_LIB) -lpython3.5m -lpthread -ldl -lutil -lm \
	-o $(TARGET).so
 
$(TARGET).o: $(TARGET).cpp
	g++ -g -Wall -std=c++11 -I$(PYTHON_INCLUDE) -I$(BOOST_INC) -I$(OPENCV_INC) -I$(CUDA_INCLUDE) -fPIC -c $(TARGET).cpp
	
$(CONVERSION).o: $(CONVERSION).cpp $(CONVERSION).h
	g++ -g -Wall -std=c++11 -I$(PYTHON_INCLUDE) -I$(BOOST_INC) -I$(OPENCV_INC) -I$(CUDA_INCLUDE) -fPIC -c $(CONVERSION).cpp


clean:
	rm -f *.so *.o

#-L$(OPENCV_LIB) -lopencv_core -lopencv_highgui -lopencv_objdetect -lopencv_cudabgsegm -lopencv_cudaobjdetect -lopencv_shape -lopencv_stitching \
	#				-lopencv_cudafeatures2d -lopencv_cudacodec -lopencv_videostab -lopencv_cudaoptflow -lopencv_cudalegacy -lopencv_calib3d \
	#				-lopencv_features2d -lopencv_videoio -lopencv_photo -lopencv_imgcodecs -lopencv_cudawarping -lopencv_cudaimgproc -lopencv_cudafilters -lopencv_video \
	#				-lopencv_ml -lopencv_imgproc -lopencv_flann -lopencv_cudaarithm -lopencv_cudev \ 
