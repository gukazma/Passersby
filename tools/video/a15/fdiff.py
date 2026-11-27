import subprocess, shutil, sys
ff = shutil.which('ffmpeg'); f = sys.argv[1]
for t in sys.argv[2:]:
    t = float(t); outs = []
    for k in (0, 0.2):
        r = subprocess.run([ff, '-loglevel', 'error', '-ss', str(t + k), '-i', f, '-frames:v', '1', '-vf', 'scale=480:270,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
        outs.append(r.stdout)
    a, b = outs; n = sum(1 for x, y in zip(a, b) if abs(x - y) > 8)
    print(t, 'changed px', n)
