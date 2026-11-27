# 当前像素行走行 ×10 放大，排成 4x2 网格（1536x1024，洋红底）= 出图的像素尺寸/外观参考
import sys, numpy as np
from PIL import Image
G='/tmp/yh/g/'
for n in ['hero','npc_office','npc_student']:
    w=Image.open(G+n+'.png').convert('RGBA')
    for r,d in enumerate(['down','left','right','up']):
        C=Image.new('RGBA',(1536,1024),(255,0,255,255))
        for k in range(8):
            f=w.crop((32*k,40*r,32*k+32,40*r+40)).resize((320,400),Image.NEAREST)
            C.alpha_composite(f,((k%4)*384+32,(k//4)*512+56))
        C.convert('RGB').save(f'ref/{n}_walkpx_{d}.png')
