"""驗證 whisper 非 ASCII 路徑缺陷與 ascii_model_path() 修法（直接驅動 ffmpeg 的 whisper 濾鏡）。"""
import os, subprocess, sys, tempfile

ROOT = r'E:\四維八德'
sys.path[:0] = [os.path.join(ROOT, '_build', 'src'), os.path.join(ROOT, '_build', 'vendor')]
import tools as T

FFMPEG = os.path.join(ROOT, 'tools', 'ffmpeg.exe')
MODEL = os.path.join(ROOT, 'tools', 'models', 'ggml-base.bin')
WAV = sys.argv[1] if len(sys.argv) > 1 else ''
NOWIN = 0x08000000


def run(model_path, tag):
    work = tempfile.mkdtemp(prefix='whisper-%s-' % tag)
    af = ("aresample=16000,whisper=model='%s':language=zh:queue=10:destination=out.srt:format=srt"
          % model_path.replace('\\', '/').replace(':', '\\:'))
    cmd = [FFMPEG, '-hide_banner', '-y', '-v', 'error', '-i', WAV, '-vn', '-af', af, '-f', 'null', '-']
    p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       creationflags=NOWIN, timeout=900)
    srt = os.path.join(work, 'out.srt')
    size = os.path.getsize(srt) if os.path.isfile(srt) else 0
    head = ''
    if size:
        with open(srt, encoding='utf-8', errors='replace') as fh:
            head = ' / '.join(x.strip() for x in fh.read().splitlines() if x.strip())[:90]
    print('[%s] rc=%d  srt=%d bytes  %s' % (tag, p.returncode, size, head))
    err = (p.stderr or '').strip().replace('\n', ' ')[:160]
    if err:
        print('        stderr: %s' % err)
    return p.returncode == 0 and size > 0


print('模型路徑：%s' % MODEL)
print('路徑是 ASCII：%s' % MODEL.isascii())
print('素材：%s' % WAV)
print()
print('--- 1) 未修正：直接把非 ASCII 路徑交給 whisper 濾鏡 ---')
before = run(MODEL, 'before')

print()
print('--- 2) ascii_model_path() 修正後的路徑 ---')
fixed = T.ascii_model_path(MODEL)
print('修正後：%s（ASCII=%s，存在=%s）' % (fixed, fixed.isascii(), os.path.isfile(fixed)))
print('--- 3) 用修正後的路徑再跑一次 ---')
after = run(fixed, 'after')

print()
print('缺陷重現：%s    修法有效：%s' % (not before, after))
sys.exit(0 if (after and not before) else 1)
