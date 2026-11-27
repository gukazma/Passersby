import os, shutil, subprocess, sys
W = sys.argv[1]; OUT = sys.argv[2]; FF = shutil.which('ffmpeg')
ids = ["yongan_day_2", "yongan_day_1", "binjiang_2", "binjiang_1", "noodle_shop_2", "noodle_shop_1"]
segs = []
for i in ids:
    o = os.path.join(W, 'bgmseg_' + i + '.mp4')
    subprocess.run([FF, '-y', '-loglevel', 'error', '-loop', '1', '-t', '40', '-i', os.path.join(W, 'bgmcards', i + '.png'), '-i', os.path.join(W, 'bgmsrc', i + '.mp3'),
                    '-filter_complex', '[0]fps=25,format=yuv420p[v];[1]atrim=0:40,afade=t=in:d=0.5,afade=t=out:st=38.5:d=1.5,aresample=48000,loudnorm=I=-16:TP=-1.5[a]',
                    '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '20', '-tune', 'stillimage', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-t', '40', o], check=True)
    segs.append(o)
lst = os.path.join(W, 'bgmlist.txt'); open(lst, 'w', encoding='utf-8').write(''.join(f"file '{p.replace(chr(92), '/')}'\n" for p in segs))
cover = os.path.splitext(OUT)[0].rsplit('_v', 1)[0] + '_封面.jpg'
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', os.path.join(W, 'bgmcards', ids[0] + '.png'), '-q:v', '2', cover], check=True)
subprocess.run([FF, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-i', cover, '-map', '0', '-map', '1', '-c', 'copy', '-c:v:1', 'mjpeg', '-disposition:v:1', 'attached_pic', '-movflags', '+faststart', OUT], check=True)
print('OUT', OUT)
