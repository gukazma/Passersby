import numpy as np
from PIL import Image
for n in ('run_side','walk_side'):
    p=f'out/wangcai/{n}.png'; a=np.array(Image.open(p).convert('RGBA')); H=a.shape[0]
    r,g,b,al=(a[...,i].astype(int) for i in range(4))
    leg=np.zeros_like(al,bool); leg[int(H*0.6):]=True
    pink=(al>0)&leg&(r-g>35)&(b-g>5)&(r>b)
    dark=(al>0)&leg&~pink&(r+g+b<420)&(r>g)&(g>b)
    if pink.any() and dark.any():
        a[pink,:3]=np.median(a[dark][:,:3],axis=0).astype(np.uint8)
    Image.fromarray(a).save(p)
