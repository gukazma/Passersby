import subprocess, shutil, sys, os
ff = shutil.which('ffmpeg'); D = r'D:\games\passersby_work\a15video\clips'
c = sys.argv[1]; ts = sys.argv[2].split(','); crop = sys.argv[3] if len(sys.argv) > 3 else ''
ins = []; 
for t in ts: ins += ['-ss', t, '-i', os.path.join(D, c + '.avi')]
n = len(ts); cols = 2 if n > 1 else 1; rows = (n + 1) // 2
fc = ''.join(f"[{i}:v]trim=end_frame=1,{crop + ',' if crop else ''}scale=960:540:flags=neighbor,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{ts[i]}':x=8:y=8:fontsize=30:fontcolor=yellow:box=1:boxcolor=black[v{i}];" for i in range(n))
if n % 2: fc += f"color=black:s=960x540:d=1[v{n}];"; n2 = n + 1
else: n2 = n
fc += ''.join(f'[v{i}]' for i in range(n2)) + f'xstack=inputs={n2}:layout=' + '|'.join(f'{(i%2)*960}_{(i//2)*540}' for i in range(n2)) + '[o]'
subprocess.run([ff, '-loglevel', 'error', '-y', *ins, '-filter_complex', fc, '-map', '[o]', '-frames:v', '1', os.path.join(D, 'grab.jpg')], check=True)
