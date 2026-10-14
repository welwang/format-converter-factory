"""Simplified -> Traditional Chinese (Taiwan phrasing), using OpenCC's dictionaries (Apache-2.0).
Pure Python: longest-match on phrases, then characters, then Taiwan words/variants (same chain as OpenCC s2twp)."""
import os, sys, threading

_D = None; _LOCK = threading.Lock()

def _dir():
    b = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(b, 'zhdict')

def _load(name):
    d = {}
    with open(os.path.join(_dir(), name), encoding='utf-8') as fh:
        for line in fh:
            if not line.strip() or line.startswith('#'): continue
            k, _, v = line.rstrip('\n').partition('\t')
            if k and v: d[k] = v.split(' ')[0]
    return d

def _dicts():
    global _D
    with _LOCK:
        if _D is None:
            st = _load('STPhrases.txt'); st_c = _load('STCharacters.txt')
            tw = _load('TWPhrases.txt'); tw.update({k: v for k, v in _load('TWVariantsPhrases.txt').items() if k not in tw})
            tw_v = _load('TWVariants.txt')
            _D = (st, max(map(len, st)), st_c, tw, max(map(len, tw)), tw_v)
    return _D

def _maxmatch(text, phrases, maxlen, chars):
    out = []; i = 0; n = len(text)
    while i < n:
        for L in range(min(maxlen, n - i), 1, -1):
            v = phrases.get(text[i:i + L])
            if v is not None: out.append(v); i += L; break
        else:
            c = text[i]; out.append(chars.get(c, c) if chars is not None else c); i += 1
    return ''.join(out)

def s2twp(text):
    st, stl, st_c, tw, twl, tw_v = _dicts()
    t = _maxmatch(text, st, stl, st_c)
    # Taiwan phrasing / variants (single-character variants live in tw_v)
    return _maxmatch(t, tw, twl, tw_v)

if __name__ == '__main__':
    print(s2twp('这是一个测试，我们用软件下载视频，鼠标和内存都不够了。打印机的信息很重要，里面有个程序员在写代码。'))
