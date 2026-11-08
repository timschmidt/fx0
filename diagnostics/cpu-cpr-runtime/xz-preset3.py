#!/usr/bin/python3
import os,sys
args=[('--lzma2=preset=3,'+arg.split('=',1)[1]) if arg.startswith('--lzma2=') else arg for arg in sys.argv[1:]]
os.execv('/usr/bin/xz',['xz',*args])
