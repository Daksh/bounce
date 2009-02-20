CXXFLAGS = $(shell pkg-config --cflags gdk-x11-2.0) \
           $(shell pkg-config --cflags gstreamer-0.10) \
		   $(shell pkg-config --cflags pygtk-2.0) \
		   $(shell python-config --cflags) \
           -fPIC -O2
LDFLAGS  = $(shell pkg-config --libs gdk-x11-2.0) \
           $(shell pkg-config --cflags gstreamer-0.10) \
		   $(shell pkg-config --libs pygtk-2.0) \
           $(shell python-config --libs)

all: _pongc.so

clean:
	rm -rf _pongc.so *_wrap.cxx pongc.py pongc.pyc *.o

%_wrap.cpp: %.i
	swig -c++ -python -o $*_wrap.cpp $<

pongc.o: pongc.h

_pongc.so: pongc.o pongc_wrap.o
	$(CXX) -shared $(LDFLAGS) -o $@ $^
