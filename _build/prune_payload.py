"""Apply the tested non-runtime resource exclusions to a build candidate only."""
import sys,json,shutil,os,stat
from pathlib import Path
build=Path(__file__).resolve().parent;root=Path(sys.argv[1]).resolve()
if not root.is_relative_to(build) or root==build or root.is_symlink():raise SystemExit('Candidate must be inside the build workspace.')
recipe=json.loads((build/'packing-prune.json').read_text(encoding='utf-8'))
def retry(fn,path,error):
 p=Path(path);assert p.resolve().is_relative_to(root) and not p.is_symlink()
 os.chmod(p,stat.S_IWRITE);fn(path)
for name in recipe:
 p=root/name
 if not p.exists():continue
 assert p.resolve().is_relative_to(root) and not p.is_symlink()
 if p.is_dir():
  assert not any(f.is_symlink() for f in p.rglob('*'))
  shutil.rmtree(p,onexc=retry)
 else:os.chmod(p,stat.S_IWRITE);p.unlink()
print('Applied tested packaging resource exclusions. Model bytes unchanged.')
