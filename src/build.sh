swig -c++ -python pongc.i
python setup.py build_ext --inplace
mv _pongc.so ../
mv pongc.py ../

