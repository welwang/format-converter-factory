"""Compare actual PE icon resources with the supplied ICO, without Windows cache."""
from pathlib import Path
import struct, hashlib, json, sys
import pefile

ROOT = Path(__file__).resolve().parent


def find_ico():
    """發行用的 logo.ico 在 _build\\logo.ico；測試資料夾本身沒有它。
    先前這裡直接讀 ROOT/'logo.ico'，因此 test_installer.ps1 一定會在這一行崩潰。
    命令列可明確指定（第 2 個參數），否則依序找幾個常見位置。"""
    if len(sys.argv) > 2 and Path(sys.argv[2]).is_file():
        return Path(sys.argv[2])
    candidates = [ROOT / 'logo.ico', ROOT.parent.parent / 'logo.ico',
                  Path('E:/四維八德/_build/logo.ico'), ROOT / 'release' / 'logo.ico']
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit('找不到 logo.ico（找過 %s）' % ', '.join(str(c) for c in candidates))


ico = find_ico().read_bytes()
reserved, kind, count = struct.unpack_from('<HHH', ico)
assert reserved == 0 and kind == 1 and count > 0
expected = set()
for index in range(count):
    size, offset = struct.unpack_from('<II', ico, 6 + index * 16 + 8)
    payload = ico[offset:offset + size]
    assert len(payload) == size
    expected.add(hashlib.sha256(payload).hexdigest())

def verify(path):
    # Inno appends a large compressed payload after its PE image. Read only
    # the executable sections needed for icons, avoiding a 1.47 GB allocation.
    with path.open('rb') as stream:
        header = stream.read(65536)
        probe = pefile.PE(data=header, fast_load=True)
        extent = max([probe.OPTIONAL_HEADER.SizeOfHeaders] +
                     [section.PointerToRawData + section.SizeOfRawData for section in probe.sections])
        probe.close()
        assert 0 < extent <= 64 * 1024 * 1024 and extent <= path.stat().st_size
        stream.seek(0)
        payload = stream.read(extent)
    pe = pefile.PE(data=payload, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
    actual = set()
    for resource in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if resource.id != 3:  # RT_ICON
            continue
        for item in resource.directory.entries:
            for language in item.directory.entries:
                record = language.data.struct
                actual.add(hashlib.sha256(pe.get_data(record.OffsetToData, record.Size)).hexdigest())
    pe.close()
    assert expected <= actual, f'New icon payload missing in {path.name}'
    return {'name': path.name + '_new_icon_resources', 'ok': True,
            'validation': f'{count} ICO entries embedded; payload SHA-256 matches'}

if len(sys.argv) > 1:
    print(json.dumps(verify(Path(sys.argv[1])), ensure_ascii=False))
else:
    records = [verify(ROOT / 'release' / name) for name in ['四維八德.exe', 'swbd-core.exe']]
    (ROOT / 'logo-resource-results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS:', len(records), 'program icon resources')
