#!/usr/bin/env python

"""
setup.py file for 3dpong
"""

from distutils.core import setup, Extension

pongc_module = Extension('_pongc', sources=['pongc.cpp', 'pongc_wrap.cxx'] )

setup (name = 'pongc', version = '0.1',
       author      = "Wade Brainerd",
       description = """3DPong C extension library.""",
       ext_modules = [pongc_module],  py_modules = ["pongc"])

