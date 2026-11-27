import subprocess, shutil, os, re, sys
ff = shutil.which('ffmpeg'); D = r'D:\games\passersby_work\a15video\clips'
for c in sys.argv[1:]:
    f = os.path.join(D, c + '.avi')
    r = subprocess.run([ff, '-i', f], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    dur = re.search(r'Duration: ([0-9:.]+)', r.stderr).group(1)
    subprocess.run([ff, '-loglevel', 'error', '-y', '-i', f, '-vf', "fps=1/2,scale=480:270,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='%{pts\\:hms}':x=8:y=8:fontsize=28:fontcolor=yellow:box=1:boxcolor=black", '-frames:v', '1', '-update', '1', os.path.join(D, c + '_dummy.jpg')], capture_output=True)
    subprocess.run([ff, '-loglevel', 'error', '-y', '-i', f, '-vf', "fps=1/2,scale=480:270,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='%{pts\\:hms}':x=8:y=8:fontsize=28:fontcolor=yellow:box=1:boxcolor=black,tile=4x8", '-frames:v', '1', os.path.join(D, c + '_sheet.jpg')], check=True)
    a = subprocess.run([ff, '-hide_banner', '-i', f, '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    print(c, dur, re.findall(r'mean_volume: ([-\d.]+)', a), re.findall(r'max_volume: ([-\d.]+)', a))
