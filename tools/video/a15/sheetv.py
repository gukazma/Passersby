import subprocess, shutil, sys, os
ff = shutil.which('ffmpeg'); f = sys.argv[1]; ts = sys.argv[3].split(','); out = sys.argv[2]
ins = []
for t in ts: ins += ['-ss', t, '-i', f]
n = len(ts); fc = ''.join(f"[{i}:v]trim=end_frame=1,scale=640:360[v{i}];" for i in range(n))
cols = 3; rows = (n + cols - 1) // cols
fc += ''.join(f'[v{i}]' for i in range(n)) + f'xstack=inputs={n}:layout=' + '|'.join(f'{(i%cols)*640}_{(i//cols)*360}' for i in range(n)) + ':fill=black[o]'
subprocess.run([ff, '-loglevel', 'error', '-y', *ins, '-filter_complex', fc, '-map', '[o]', '-frames:v', '1', out], check=True)
