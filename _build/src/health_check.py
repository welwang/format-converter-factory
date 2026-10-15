"""電腦健康檢查：讓電腦自己檢查自己，再用一般人聽得懂的話說明結果。

結果分三層：
  overview  給一般使用者：一句結論，加上每個項目「正常／需注意／異常／部分檢查／未測試」
  explain   問題解釋：這是什麼、會造成什麼影響、怎麼處理，以及可能原因（附這次量到的證據）
  pro       專業資料：原始數值、Windows 事件記錄、測試期間的時間序列

兩條不可違反的規則：
  1. 沒有量到的項目一律標「未測試」並寫出原因，絕不推定為正常。
  2. 「可能原因」只有在這次量測真的找到證據時才標為「有證據」，不靠使用者的選擇認定故障。

五個階段都會即時回報進度（job.progress／job.msg），不使用假進度條。
Windows 以外的系統只會執行可攜的運算、記憶體與磁碟測試，其餘項目標為未測試。
"""
import os, time, json, socket, struct, hashlib, threading, subprocess, statistics, base64, zlib, ctypes
import engine as E

OK, WARN, BAD, PARTIAL, UNTESTED = 'ok', 'warn', 'bad', 'partial', 'untested'
STATE_TEXT = {OK: '正常', WARN: '需注意', BAD: '異常', PARTIAL: '部分檢查', UNTESTED: '未測試'}
STAGES = ['認識你的電腦硬體', '檢查設備是否能正常使用', '測試電腦的運算能力', '檢查長時間使用的穩定性', '整理完整健康報告']
MODES = dict(
    quick=dict(name='快速檢查', stress=30, mem_mb=256, disk_mb=128, pings=5),
    standard=dict(name='標準檢查', stress=120, mem_mb=512, disk_mb=256, pings=10),
    pro=dict(name='專業檢查', stress=180, mem_mb=1024, disk_mb=512, pings=20),
)
PRO_STRESS = (60, 180, 600, 1800)
PRO_MEM = (256, 512, 1024, 2048)
EVENT_DAYS = 30
POWER_SAVER = 'a1841308-3541-4fab-bc81-f71556f20b4a'
DEVICE_CODES = {1: '設定不正確', 3: '驅動程式可能損毀', 10: '無法啟動', 12: '找不到足夠的可用資源', 14: '需要重新開機',
                18: '需要重新安裝驅動程式', 19: '登錄資訊不完整或損毀', 21: '正在移除裝置', 22: '已停用', 24: '裝置不存在或未連接',
                28: '沒有安裝驅動程式', 31: '驅動程式無法載入', 39: '驅動程式損毀或遺失', 43: 'Windows 已停止此裝置（回報問題）',
                45: '目前沒有連接到電腦', 52: '驅動程式簽章無法驗證'}


def options(raw):
    """Validated options from the page: {mode, stress, mem_mb, network}."""
    raw = raw or {}
    mode = raw.get('mode') if raw.get('mode') in MODES else 'standard'
    o = dict(MODES[mode]); o['mode'] = mode
    if mode == 'pro':
        try: stress = int(raw.get('stress') or o['stress'])
        except (TypeError, ValueError): stress = o['stress']
        try: mem = int(raw.get('mem_mb') or o['mem_mb'])
        except (TypeError, ValueError): mem = o['mem_mb']
        o['stress'] = stress if stress in PRO_STRESS else o['stress']
        o['mem_mb'] = mem if mem in PRO_MEM else o['mem_mb']
    o['network'] = raw.get('network', True) is not False
    return o


def as_list(v):
    """PowerShell's ConvertTo-Json writes a single object instead of a one-element array."""
    if v is None: return []
    return v if isinstance(v, list) else [v]


# ---------------------------------------------------------------- stage 1: inventory (one PowerShell run)

PS_INVENTORY = r'''
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$r=[ordered]@{}
$since=(Get-Date).AddDays(-%DAYS%)
function Step($name,[scriptblock]$b){ try { $r[$name]= & $b } catch { $r[$name+'_error']=$_.Exception.Message } }
function Ev($providers,$ids,$max=25){
  $f=@{LogName='System';ProviderName=$providers;StartTime=$since}
  if($ids){ $f['Id']=$ids }
  @(Get-WinEvent -FilterHashtable $f -MaxEvents $max -ErrorAction SilentlyContinue | ForEach-Object {
    [ordered]@{Time=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm');Id=$_.Id;Provider=$_.ProviderName;Level=$_.LevelDisplayName;Message=((([string]$_.Message) -split "`n")[0]).Trim()} })
}
Step os { $o=Get-CimInstance Win32_OperatingSystem; [ordered]@{Caption=$o.Caption;Version=$o.Version;Build=$o.BuildNumber;LastBoot=$o.LastBootUpTime.ToString('yyyy-MM-dd HH:mm')} }
Step admin { ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }
Step cpu { @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,Status) }
Step gpu { @(Get-CimInstance Win32_VideoController | Select-Object Name,Status,ConfigManagerErrorCode,DriverVersion,@{n='DriverDate';e={if($_.DriverDate){$_.DriverDate.ToString('yyyy-MM-dd')}}},AdapterRAM) }
Step ram { @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber,DeviceLocator) }
Step ram_total { [double](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory }
Step disks { @(Get-PhysicalDisk | ForEach-Object { $d=$_; $c=$null; try { $c=$d | Get-StorageReliabilityCounter -ErrorAction Stop } catch {}
  [ordered]@{Id=[string]$d.DeviceId;Name=$d.FriendlyName;Media=[string]$d.MediaType;Bus=[string]$d.BusType;Health=[string]$d.HealthStatus;
    Operational=((@($d.OperationalStatus) | ForEach-Object {[string]$_}) -join ',');Size=[double]$d.Size;
    Reliability=$(if($c){[ordered]@{ReadErrorsTotal=$c.ReadErrorsTotal;ReadErrorsUncorrected=$c.ReadErrorsUncorrected;WriteErrorsTotal=$c.WriteErrorsTotal;
      WriteErrorsUncorrected=$c.WriteErrorsUncorrected;Wear=$c.Wear;Temperature=$c.Temperature;TemperatureMax=$c.TemperatureMax;PowerOnHours=$c.PowerOnHours}}else{$null})} }) }
Step net { @(Get-NetAdapter -Physical | Select-Object Name,InterfaceDescription,@{n='Status';e={[string]$_.Status}},LinkSpeed,@{n='Wireless';e={$_.NdisPhysicalMedium -eq 9}}) }
Step gateway { @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | ForEach-Object {$_.NextHop} | Where-Object {$_ -and $_ -ne '0.0.0.0'})[0] }
Step problem_devices { @(Get-CimInstance Win32_PnPEntity -Filter 'ConfigManagerErrorCode<>0' | Select-Object Name,PNPClass,ConfigManagerErrorCode,DeviceID) }
Step ev_whea { Ev @('Microsoft-Windows-WHEA-Logger') $null }
Step ev_disk { Ev @('disk','stornvme','storahci','Ntfs','iaStorAC','iaStorA','iaStorAVC') @(7,11,51,55,129,140,153,157) }
Step ev_display { Ev @('Display') @(4101) }
Step ev_power { Ev @('Microsoft-Windows-Kernel-Power') @(41) }
Step ev_bugcheck { Ev @('Microsoft-Windows-WER-SystemErrorReporting','BugCheck') @(1001) }
Step memdiag { @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-MemoryDiagnostics-Results'} -MaxEvents 3 -ErrorAction SilentlyContinue | ForEach-Object { [ordered]@{Time=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm');Id=$_.Id} }) }
Step power_scheme { ((powercfg /getactivescheme) -join ' ') }
Step battery { @(Get-CimInstance Win32_Battery | Select-Object Name,BatteryStatus,EstimatedChargeRemaining) }
Step top_processes { @(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object { $_.Name -ne '_Total' -and $_.Name -ne 'Idle' } | Sort-Object PercentProcessorTime -Descending | Select-Object -First 5 Name,PercentProcessorTime,IDProcess) }
Step thermal { @(Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation | Select-Object Name,HighPrecisionTemperature,Temperature,PercentPassiveLimit,ThrottleReasons) }
$r | ConvertTo-Json -Depth 6 -Compress
'''

PS_MONITOR = r'''
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
while($true){
  $p=Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation -Filter "Name='_Total'"
  $t=@(Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation)
  [ordered]@{perf=$p.PercentProcessorPerformance;freq=$p.ProcessorFrequency;util=$p.PercentProcessorTime;
    temps=@($t | ForEach-Object { if($_.HighPrecisionTemperature){[math]::Round($_.HighPrecisionTemperature/10-273.15,1)}elseif($_.Temperature){[math]::Round($_.Temperature-273.15,1)} });
    thr=@($t | ForEach-Object { $_.ThrottleReasons })} | ConvertTo-Json -Compress
  Start-Sleep -Milliseconds 800
}
'''


def _powershell():
    return os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')


def _ps_args(script):
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    return [_powershell(), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded]


def inventory():
    """Everything Windows can tell about the hardware without a driver of our own. {} off Windows."""
    if os.name != 'nt': return {}
    try:
        r = E.run(_ps_args(PS_INVENTORY.replace('%DAYS%', str(EVENT_DAYS))), timeout=120)
        line = next((l for l in reversed(r.stdout.splitlines()) if l.strip().startswith('{')), '')
        return json.loads(line) if line else {'_error': (r.stderr or '沒有輸出')[:300]}
    except Exception as ex:
        return {'_error': str(ex)[:300]}


def battery_report(folder):
    """Design vs. full-charge capacity from `powercfg /batteryreport /xml` (works without administrator)."""
    if os.name != 'nt': return None
    path = os.path.join(folder, 'battery-report.xml')
    try:
        E.run(['powercfg', '/batteryreport', '/xml', '/output', path], timeout=60)
        import xml.etree.ElementTree as ET
        root = ET.parse(path).getroot()
        out = []
        for b in root.iter():
            if b.tag.endswith('}Battery'):
                vals = {c.tag.split('}')[-1]: (c.text or '').strip() for c in b}
                try: design = float(vals.get('DesignCapacity') or 0); full = float(vals.get('FullChargeCapacity') or 0)
                except ValueError: continue
                if design > 0: out.append(dict(name=vals.get('Id') or vals.get('Manufacturer') or '電池', design=design, full=full,
                                               cycles=vals.get('CycleCount') or ''))
        return out
    except Exception:
        return None
    finally:
        try: os.remove(path)
        except OSError: pass


class Monitor:
    """Samples processor performance, frequency, load and thermal zones about once a second (Windows only)."""

    def __init__(self):
        self.samples = []; self.proc = None; self.t0 = time.time(); self._lock = threading.Lock(); self.phase = ''

    def start(self):
        if os.name != 'nt': return self
        try:
            self.proc = subprocess.Popen(_ps_args(PS_MONITOR), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                         text=True, encoding='utf-8', errors='replace', creationflags=E.NOWIN)
            threading.Thread(target=self._read, daemon=True).start()
        except Exception:
            self.proc = None
        return self

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line.startswith('{'): continue
            try: d = json.loads(line)
            except ValueError: continue
            temps = [t for t in as_list(d.get('temps')) if isinstance(t, (int, float)) and -20 < t < 150]
            s = dict(t=round(time.time() - self.t0, 1), phase=self.phase, perf=d.get('perf'), freq=d.get('freq'), util=d.get('util'),
                     temp=max(temps) if temps else None, thr=sum(int(x or 0) for x in as_list(d.get('thr')) if isinstance(x, (int, float))))
            with self._lock: self.samples.append(s)

    def mark(self, phase):
        self.phase = phase

    def window(self, phase):
        with self._lock: return [s for s in self.samples if s['phase'] == phase]

    def stop(self):
        if self.proc:
            try: self.proc.kill()
            except Exception: pass


# ---------------------------------------------------------------- measurements

SEED = hashlib.sha512(b'SiWeiBaDe health check').digest()
BLOCK = SEED * (4 * 1048576 // len(SEED))           # 4 MB, large enough that hashlib and zlib release the GIL
EXPECT_SHA = hashlib.sha256(BLOCK).digest()
EXPECT_CRC = zlib.crc32(zlib.compress(BLOCK, 1))


class Cancelled(Exception):
    pass


def _cpu_round():
    """One unit of verified work: a hash and a compress/checksum round trip with known answers."""
    ok = hashlib.sha256(BLOCK).digest() == EXPECT_SHA
    ok = zlib.crc32(zlib.compress(BLOCK, 1)) == EXPECT_CRC and ok
    return ok


def cpu_run(threads, seconds, cancelled, per_second=None):
    """Run verified work on `threads` threads; returns (rounds, errors, elapsed, rounds per one-second bucket)."""
    stop = time.perf_counter() + seconds; t0 = time.perf_counter()
    counts = [0] * threads; errors = [0] * threads; buckets = {}; lock = threading.Lock()

    def work(i):
        while time.perf_counter() < stop and not cancelled():
            good = _cpu_round(); counts[i] += 1
            if not good: errors[i] += 1
            if per_second is not None:
                b = int(time.perf_counter() - t0)
                with lock: buckets[b] = buckets.get(b, 0) + 1
    ts = [threading.Thread(target=work, args=(i,), daemon=True) for i in range(threads)]
    for t in ts: t.start()
    while any(t.is_alive() for t in ts):
        time.sleep(.2)
        if per_second: per_second(min(1.0, (time.perf_counter() - t0) / seconds))
    return sum(counts), sum(errors), time.perf_counter() - t0, [buckets.get(i, 0) for i in range(int(seconds))]


def available_mb():
    if os.name == 'nt':
        class MS(ctypes.Structure):
            _fields_ = [('len', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong), ('avail', ctypes.c_ulonglong),
                        ('tp', ctypes.c_ulonglong), ('ap', ctypes.c_ulonglong), ('tv', ctypes.c_ulonglong), ('av', ctypes.c_ulonglong), ('ext', ctypes.c_ulonglong)]
        m = MS(); m.len = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)): return m.avail / 1048576
    try:
        with open('/proc/meminfo') as fh:
            for line in fh:
                if line.startswith('MemAvailable:'): return int(line.split()[1]) / 1024
    except OSError: pass
    return E.mem_gb() * 1024 / 2


INVERT = bytes(255 - i for i in range(256))


def memory_test(want_mb, cancelled, progress):
    """Fill `size` MB with chunk-specific patterns, read everything back, then repeat with the inverted pattern."""
    size = int(max(64, min(want_mb, available_mb() * .5)) // 16 * 16)
    chunk = 16 * 1048576; n = size // 16
    chunks, errors = [], 0
    try:
        for i in range(n):
            if cancelled(): raise Cancelled
            chunks.append(bytearray(hashlib.sha256(SEED + i.to_bytes(4, 'little')).digest() * (chunk // 32)))
            progress(.25 * (i + 1) / n)
        for p in (0, 1):
            for i, c in enumerate(chunks):
                if cancelled(): raise Cancelled
                pattern = hashlib.sha256(SEED + i.to_bytes(4, 'little')).digest() * (chunk // 32)
                if p: pattern = pattern.translate(INVERT)
                if c != pattern: errors += 1
                if not p: c[:] = pattern.translate(INVERT)
                progress(.25 + .75 * (p * n + i + 1) / (2 * n))
    except MemoryError:
        size = len(chunks) * 16
    finally:
        chunks.clear()
    return dict(tested_mb=size, errors=errors, passes=2)


def disk_test(folder, want_mb, cancelled, progress):
    """Write distinct 4 MB blocks, flush them to the drive, read them back and compare."""
    import shutil
    free = shutil.disk_usage(folder).free / 1048576
    if free < want_mb * 3: return dict(skipped=f'可用空間不足（剩 {free:.0f} MB），沒有執行讀寫驗證')
    path = os.path.join(folder, f'zdgc_health_{os.getpid()}.tmp'); block = 4 * 1048576; n = want_mb // 4; bad = 0
    pattern = lambda i: hashlib.sha256(SEED + b'disk' + i.to_bytes(4, 'little')).digest() * (block // 32)
    try:
        t = time.perf_counter()
        with open(path, 'wb') as fh:
            for i in range(n):
                if cancelled(): raise Cancelled
                fh.write(pattern(i)); progress(.5 * (i + 1) / n)
            fh.flush(); os.fsync(fh.fileno())
        write = time.perf_counter() - t; t = time.perf_counter()
        with open(path, 'rb') as fh:
            for i in range(n):
                if cancelled(): raise Cancelled
                if fh.read(block) != pattern(i): bad += 1
                progress(.5 + .5 * (i + 1) / n)
        read = time.perf_counter() - t
        return dict(mb=n * 4, bad_blocks=bad, write_mbps=round(n * 4 / max(write, .001)), read_mbps=round(n * 4 / max(read, .001)),
                    drive=os.path.splitdrive(os.path.abspath(folder))[0] or folder)
    finally:
        try: os.remove(path)
        except OSError: pass


def _icmp(ip, count, cancelled):
    """Round-trip times (ms, None = lost) using the Windows ICMP API, which needs no administrator rights."""
    if os.name != 'nt': return None
    try:
        lib = ctypes.windll.iphlpapi
        lib.IcmpCreateFile.restype = ctypes.c_void_p
        lib.IcmpSendEcho.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ushort, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
        lib.IcmpCloseHandle.argtypes = [ctypes.c_void_p]
        h = lib.IcmpCreateFile(); addr = struct.unpack('<L', socket.inet_aton(ip))[0]
        data = b'SiWeiBaDe' * 4; buf = ctypes.create_string_buffer(64 + len(data) + 64); out = []
        for _ in range(count):
            if cancelled(): break
            n = lib.IcmpSendEcho(h, addr, data, len(data), None, buf, len(buf), 1000)
            status, rtt = struct.unpack_from('<LL', buf.raw, 4)
            out.append(rtt if n and status == 0 else None)
            time.sleep(.2)
        lib.IcmpCloseHandle(h)
        return out
    except Exception:
        return None


def _tcp(host, port, count, cancelled):
    out = []
    for _ in range(count):
        if cancelled(): break
        t = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=2): out.append(round((time.perf_counter() - t) * 1000, 1))
        except OSError: out.append(None)
        time.sleep(.2)
    return out


def _rtt_stats(values):
    if not values: return None
    got = [v for v in values if v is not None]
    return dict(sent=len(values), lost=len(values) - len(got), loss=round(100 * (len(values) - len(got)) / len(values)),
                avg=round(statistics.mean(got), 1) if got else None, max=max(got) if got else None,
                jitter=round(statistics.pstdev(got), 1) if len(got) > 1 else 0)


def network_test(gateway, count, cancelled):
    r = dict(gateway=gateway)
    if gateway: r['gateway_ping'] = _rtt_stats(_icmp(gateway, count, cancelled))
    r['internet'] = _rtt_stats(_tcp('1.1.1.1', 443, count, cancelled) + _tcp('8.8.8.8', 443, count, cancelled))
    dns = []
    for name in ('www.microsoft.com', 'dns.google'):
        t = time.perf_counter()
        try: socket.getaddrinfo(name, 443); dns.append(round((time.perf_counter() - t) * 1000, 1))
        except OSError: dns.append(None)
    r['dns'] = _rtt_stats(dns)
    return r


# ---------------------------------------------------------------- evaluation (pure: inventory + measurements -> items)

def _item(id, name, question, state, headline, explain, **kw):
    d = dict(id=id, name=name, question=question, state=state, state_text=STATE_TEXT[state], headline=headline, explain=explain,
             impact='', advice=[], causes=[], pro=[], events=[], not_tested=[])
    d.update(kw); return d


def _cause(title, evidence, finding, plain, next_step):
    return dict(title=title, evidence=evidence, finding=finding, plain=plain, next=next_step)


def _median(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return statistics.median(values) if values else None


def eval_cpu(inv, m):
    cpu = (as_list(inv.get('cpu')) or [{}])[0]
    name = cpu.get('Name') or m.get('cpu_name') or '處理器'
    pro = [['型號', name], ['實體核心／邏輯執行緒', f"{cpu.get('NumberOfCores', '?')}／{cpu.get('NumberOfLogicalProcessors', m.get('threads', '?'))}"],
           ['額定時脈', f"{cpu['MaxClockSpeed']} MHz" if cpu.get('MaxClockSpeed') else '未取得']]
    c = m.get('cpu') or {}
    if not c: return _item('cpu', '處理器 CPU', '運算正常嗎？', UNTESTED, '這次沒有執行運算測試', '處理器負責電腦裡所有的計算。', pro=pro,
                           not_tested=['運算測試沒有執行（檢查被取消或中斷）'])
    errors = c.get('errors', 0) + (m.get('stress') or {}).get('errors', 0)
    pro += [['單執行緒驗證運算', f"{c['single_rps']:.1f} 輪／秒"], ['全部執行緒驗證運算', f"{c['multi_rps']:.1f} 輪／秒（{c['threads']} 執行緒）"],
            ['多核心倍數', f"{c['scaling']:.2f}×"], ['運算錯誤', f'{errors} 次']]
    s = m.get('stress') or {}
    perf = s.get('perf_median'); drop = s.get('rate_drop')
    if perf is not None: pro.append(['負載下效能（相對額定時脈）', f'{perf:.0f}%'])
    if drop is not None: pro.append(['負載後段運算量／前段', f'{drop:.2f}'])
    explain = '處理器就是電腦的「大腦」，負責所有計算。這次讓它重複做答案已知的計算題，看它算得對不對、快不快。'
    if errors:
        return _item('cpu', '處理器 CPU', '運算正常嗎？', BAD, f'運算結果出現 {errors} 次錯誤', explain, pro=pro,
                     impact='計算出錯可能造成程式當機、檔案損毀或藍色畫面。',
                     advice=['先備份重要資料', '確認電腦沒有超頻；若有，恢復 BIOS 預設值', '清潔散熱後再檢查一次', '錯誤持續出現時送修，請技術人員檢查處理器與主機板'],
                     causes=[_cause('處理器或記憶體不穩定', True, f'已知答案的計算有 {errors} 次不相符', '就像計算機按 1+1 偶爾跑出 3，代表硬體在某些情況下算錯。', '關閉超頻、檢查散熱，再做一次完整檢查')])
    slow = (perf is not None and perf < 70) or (drop is not None and drop < .8)
    pc = int(cpu.get('NumberOfCores') or 0)
    if pc >= 2 and c['scaling'] < .35 * pc: slow = True
    causes = cpu_causes(inv, m)
    if slow:
        why = []
        if perf is not None and perf < 70: why.append(f'高負載時只跑到額定速度的 {perf:.0f}%')
        if drop is not None and drop < .8: why.append(f'測試後段的運算量掉到前段的 {drop * 100:.0f}%')
        if pc >= 2 and c['scaling'] < .35 * pc: why.append(f'{pc} 個核心一起工作只快了 {c["scaling"]:.1f} 倍')
        return _item('cpu', '處理器 CPU', '運算正常嗎？', WARN, '電腦速度比預期慢', explain + '這次計算都正確，但速度低於它應有的表現。', pro=pro,
                     impact='開程式、轉檔或玩遊戲時會比較慢，風扇也可能一直很吵。', advice=['看下方「可能原因」中標示「有證據」的項目先處理'],
                     causes=causes, finding='；'.join(why))
    return _item('cpu', '處理器 CPU', '運算正常嗎？', OK, '電腦運算正常', explain + '這次計算全部正確，速度也維持穩定。', pro=pro, causes=causes)


def cpu_causes(inv, m):
    s = m.get('stress') or {}
    heat = bool(s.get('throttle_reasons')) or (s.get('temp_max') or 0) >= 90
    heat_finding = (f"感測器最高 {s['temp_max']:.0f}°C" if s.get('temp_max') is not None else '這台電腦沒有開放溫度感測器') + \
                   ('，且 Windows 回報因溫度限制速度' if s.get('throttle_reasons') else '')
    scheme = str(inv.get('power_scheme') or '').lower()
    bat = as_list(inv.get('battery'))
    on_battery = any(b.get('BatteryStatus') == 1 for b in bat)
    power = POWER_SAVER in scheme or on_battery
    power_finding = '；'.join(x for x in ['目前使用「省電」電源計畫' if POWER_SAVER in scheme else '',
                                         '筆電正在使用電池（未接電源）' if on_battery else '']) or '電源計畫不是省電，也沒有在用電池'
    idle = m.get('idle_util'); top = m.get('top_processes') or []
    busy = (idle or 0) > 25 or any(p['share'] >= 20 for p in top)
    busy_finding = (f'測試前處理器已經在忙 {idle:.0f}%' if idle is not None else '沒有取得測試前的處理器使用率') + \
                   ('；最忙的程式：' + '、'.join(f"{p['name']} {p['share']:.0f}%" for p in top[:3]) if top else '')
    return [
        _cause('散熱可能不夠好', heat if s.get('temp_max') is not None or s.get('throttle_reasons') else None, heat_finding,
               '就像人在太熱的環境運動會放慢速度，處理器也會為了避免過熱而降低運算速度。', '清潔通風口與風扇灰塵；筆電放在硬桌面上，不要放在棉被或腿上'),
        _cause('省電設定限制了速度', power, power_finding,
               '省電模式會刻意讓處理器跑慢一點，換取更長的電池時間。', '到「設定 → 系統 → 電源」改成「平衡」或「最佳效能」；筆電接上電源再使用'),
        _cause('其他程式正在使用處理器', busy, busy_finding,
               '就像同一個廚師同時要煮好幾桌菜，每一桌都會出得比較慢。', '按 Ctrl＋Shift＋Esc 開啟工作管理員，看看哪個程式在用處理器，不需要的就關掉'),
    ]


def eval_ram(inv, m):
    total = inv.get('ram_total') or E.mem_gb() * 2 ** 30
    sticks = as_list(inv.get('ram'))
    pro = [['總容量', f'{total / 2 ** 30:.1f} GB'], ['記憶體條', '、'.join(f"{(s.get('Capacity') or 0) / 2 ** 30:.0f} GB {s.get('ConfiguredClockSpeed') or s.get('Speed') or '?'} MT/s" for s in sticks) or '未取得']]
    t = m.get('memory')
    diag = as_list(inv.get('memdiag'))
    last = diag[0] if diag else None
    if last: pro.append(['Windows 記憶體診斷（最近一次）', f"{last.get('Time')} · 事件 {last.get('Id')}（{'發現錯誤' if last.get('Id') == 1202 else '沒有錯誤' if last.get('Id') == 1201 else '其他'}）"])
    explain = 'RAM 是電腦工作時使用的暫時記憶空間，就像書桌的桌面：桌面越大，能同時攤開的工作越多。'
    advice_full = '想完整檢查全部記憶體，請按「開啟 Windows 記憶體診斷」，它會在重新開機時檢查約 10–20 分鐘'
    if t: pro += [['這次測試範圍', f"{t['tested_mb']} MB（佔 {t['tested_mb'] * 1048576 / total * 100:.0f}%），{t['passes']} 種資料樣式"], ['不一致的區塊', str(t['errors'])]]
    if (t and t['errors']) or (last and last.get('Id') == 1202):
        where = '這次測試' if t and t['errors'] else 'Windows 記憶體診斷'
        return _item('ram', '記憶體 RAM', '記憶體會不會出錯？', BAD, f'{where}發現記憶體錯誤', explain, pro=pro,
                     impact='記憶體出錯會讓程式莫名當機、檔案存檔後內容壞掉，或出現藍色畫面。',
                     advice=['先備份重要資料', '若有多條記憶體，一次只留一條，逐條檢查找出有問題的那條', '桌機可重新插拔記憶體並清潔金手指', '確認 BIOS 沒有開啟記憶體超頻（XMP／EXPO）後再測'],
                     causes=[_cause('記憶體寫進去的資料讀出來不一樣', True, f'{where}偵測到不一致', '就像在白板上寫字，回頭看時字變了。', advice_full)])
    if last and last.get('Id') == 1201:
        return _item('ram', '記憶體 RAM', '記憶體會不會出錯？', OK, '完整記憶體診斷沒有發現錯誤', explain + f"Windows 記憶體診斷在 {last.get('Time')} 完整檢查過，沒有錯誤。", pro=pro)
    if not t:
        return _item('ram', '記憶體 RAM', '記憶體會不會出錯？', UNTESTED, '需要重啟電腦才能完整檢查', explain, pro=pro,
                     advice=[advice_full], not_tested=['這次沒有執行記憶體測試', '整部記憶體只能在 Windows 啟動前檢查'])
    return _item('ram', '記憶體 RAM', '記憶體會不會出錯？', PARTIAL, f"測試的 {t['tested_mb']} MB 正常，完整檢查需要重新開機", explain +
                 '程式在 Windows 執行中只能測一部分記憶體，這部分沒有發現錯誤。', pro=pro, advice=[advice_full],
                 not_tested=['作業系統與其他程式正在使用的記憶體無法在執行中測試'])


def eval_storage(inv, m):
    disks = as_list(inv.get('disks'))
    events = as_list(inv.get('ev_disk'))
    t = m.get('disk') or {}
    explain = '硬碟（SSD 或傳統硬碟）是存放檔案、照片和 Windows 本身的地方，就像電腦的櫃子。'
    pro, bad, warn, notes, not_tested = [], [], [], [], []
    for d in disks:
        rel = d.get('Reliability') or {}
        got = {k: v for k, v in rel.items() if v is not None}
        pro.append([d.get('Name') or '磁碟', f"{d.get('Media') or ''} {d.get('Bus') or ''} · {(d.get('Size') or 0) / 1e9:.0f} GB · 健康狀態 {d.get('Health') or '未取得'}"])
        if got: pro.append(['　SMART／可靠性計數', '、'.join(f'{k}={v}' for k, v in got.items())])
        else: not_tested.append(f"{d.get('Name') or '磁碟'} 的詳細 SMART 計數需要系統管理員權限才能讀取")
        if d.get('Health') and d.get('Health') not in ('Healthy', '0'): bad.append(f"{d.get('Name')} 的健康狀態為 {d.get('Health')}")
        if (got.get('ReadErrorsUncorrected') or 0) > 0 or (got.get('WriteErrorsUncorrected') or 0) > 0:
            bad.append(f"{d.get('Name')} 有無法修正的讀寫錯誤")
        wear = got.get('Wear')
        if isinstance(wear, (int, float)) and wear >= 90: bad.append(f"{d.get('Name')} 的使用壽命已用掉 {wear}%")
        elif isinstance(wear, (int, float)) and wear >= 70: warn.append(f"{d.get('Name')} 的使用壽命已用掉 {wear}%")
        temp = got.get('Temperature')
        if isinstance(temp, (int, float)) and temp >= 70: warn.append(f"{d.get('Name')} 溫度 {temp}°C 偏高")
    if not disks: not_tested.append('沒有取得實體磁碟清單')
    if t.get('bad_blocks'): bad.append(f"讀寫驗證有 {t['bad_blocks']} 個區塊讀回的資料和寫入的不同")
    if t.get('mb'): pro.append(['讀寫驗證', f"{t['drive']} 寫入並讀回 {t['mb']} MB · 寫 {t['write_mbps']} MB/s、讀 {t['read_mbps']} MB/s（讀取可能受系統快取影響）"])
    elif t.get('skipped'): not_tested.append(t['skipped'])
    if events: warn.append(f'過去 {EVENT_DAYS} 天 Windows 記錄了 {len(events)} 次磁碟讀寫錯誤')
    if not inv: not_tested.append('無法讀取 Windows 的磁碟健康資料')
    advice = ['立刻備份重要資料到另一顆硬碟或雲端', '用硬碟廠商的工具確認健康度', '準備更換硬碟']
    if bad:
        return _item('storage', '儲存裝置 SSD／硬碟', '我的檔案安全嗎？', BAD, '偵測到資料讀取錯誤' if t.get('bad_blocks') or events else bad[0], explain,
                     impact='硬碟出問題時，檔案可能讀不出來、損毀，甚至整顆硬碟突然無法使用。', advice=advice, finding='；'.join(bad + warn),
                     pro=pro, events=events, not_tested=not_tested)
    if warn:
        return _item('storage', '儲存裝置 SSD／硬碟', '我的檔案安全嗎？', WARN, warn[0], explain + '目前還能使用，但出現值得注意的紀錄。',
                     impact='讀寫錯誤若持續增加，檔案可能損毀。', advice=['先備份重要資料', '留意錯誤次數是否增加，一週後再檢查一次', '連接線鬆動也會造成錯誤：桌機可重新插好 SATA 線'],
                     finding='；'.join(warn), pro=pro, events=events, not_tested=not_tested)
    if not disks and not t.get('mb'):
        return _item('storage', '儲存裝置 SSD／硬碟', '我的檔案安全嗎？', UNTESTED, '沒有取得硬碟資料', explain, pro=pro, not_tested=not_tested)
    if not disks:
        return _item('storage', '儲存裝置 SSD／硬碟', '我的檔案安全嗎？', PARTIAL, '讀寫驗證正常，但沒有取得硬碟健康資料', explain, pro=pro, not_tested=not_tested)
    return _item('storage', '儲存裝置 SSD／硬碟', '我的檔案安全嗎？', OK, '硬碟狀態正常', explain + '健康狀態、錯誤記錄與讀寫驗證都沒有發現問題。',
                 pro=pro, events=events, not_tested=not_tested)


def eval_gpu(inv, m):
    gpus = as_list(inv.get('gpu')); tdr = as_list(inv.get('ev_display')); enc = m.get('gpu_encode') or {}
    explain = '顯示卡負責把畫面畫出來，也負責影片播放、轉檔加速和遊戲畫面。'
    pro = [[g.get('Name') or '顯示卡', f"狀態 {g.get('Status') or '?'} · 驅動 {g.get('DriverVersion') or '?'}（{g.get('DriverDate') or '?'}）"] for g in gpus]
    not_tested = ['3D 遊戲畫面與顯示記憶體（VRAM）壓力測試尚未提供']
    if enc and enc.get('hw'): pro.append(['影音硬體編碼測試', f"{enc.get('encoder')} · {'通過' if enc.get('ok') else '失敗：' + enc.get('error', '')}"])
    elif enc: not_tested.append('影音硬體加速：沒有偵測到可用的顯示卡編碼器，影片轉檔會使用處理器')
    broken = [g for g in gpus if (g.get('ConfigManagerErrorCode') or 0) != 0 or (g.get('Status') and g.get('Status') != 'OK')]
    if broken:
        code = broken[0].get('ConfigManagerErrorCode') or 0
        return _item('gpu', '顯示卡 GPU', '畫面和遊戲會不會出問題？', BAD, f"{broken[0].get('Name')}：{DEVICE_CODES.get(code, '裝置回報錯誤')}", explain,
                     impact='畫面可能變得很慢、解析度變低，或遊戲與影片無法使用硬體加速。',
                     advice=['到顯示卡廠商網站（NVIDIA／AMD／Intel）下載最新驅動程式並安裝', '安裝後重新開機'], pro=pro, events=tdr, not_tested=not_tested)
    if tdr:
        return _item('gpu', '顯示卡 GPU', '畫面和遊戲會不會出問題？', WARN, f'過去 {EVENT_DAYS} 天畫面驅動停止回應 {len(tdr)} 次', explain + '每次 Windows 都自動恢復了，但次數多代表不穩定。',
                     impact='使用中可能突然黑畫面一下、遊戲閃退。', advice=['更新顯示卡驅動程式', '檢查顯示卡散熱與灰塵', '關閉顯示卡超頻'], pro=pro, events=tdr, not_tested=not_tested)
    if enc and not enc.get('ok') and enc.get('hw'):
        return _item('gpu', '顯示卡 GPU', '畫面和遊戲會不會出問題？', WARN, '顯示卡影音加速無法使用', explain, impact='影片轉檔會改用處理器，速度比較慢。',
                     advice=['更新顯示卡驅動程式'], pro=pro, not_tested=not_tested)
    if not gpus:
        return _item('gpu', '顯示卡 GPU', '畫面和遊戲會不會出問題？', UNTESTED, '沒有取得顯示卡資料', explain, pro=pro, not_tested=not_tested)
    return _item('gpu', '顯示卡 GPU', '畫面和遊戲會不會出問題？', OK, '畫面與圖形運算正常', explain + ('裝置狀態、錯誤記錄與影音編碼測試都正常。' if enc.get('hw') else '裝置狀態與錯誤記錄都正常。'), pro=pro, events=tdr, not_tested=not_tested)


def eval_cooling(inv, m):
    s = m.get('stress') or {}
    explain = '電腦工作時會發熱，靠風扇和散熱片把熱帶走。散熱不好時，電腦會自動降速保護自己。'
    pro = []
    if s.get('temp_max') is not None: pro.append(['溫度感測器（ACPI 熱區）', f"閒置 {s.get('temp_idle', '?')}°C → 負載最高 {s['temp_max']:.0f}°C"])
    if s.get('perf_median') is not None: pro.append(['負載下效能中位數', f"{s['perf_median']:.0f}%"])
    if s.get('throttle_reasons'): pro.append(['Windows 熱區節流原因代碼', str(s['throttle_reasons'])])
    not_tested = ['風扇轉速：Windows 沒有提供一般程式讀取風扇的標準方式']
    note = '這裡的溫度來自主機板的 ACPI 熱區，不一定是處理器核心溫度；實際警告門檻依處理器型號與廠商規格而定。'
    if not s:
        return _item('cooling', '散熱', '電腦會不會過熱？', UNTESTED, '這次沒有執行負載測試', explain, not_tested=not_tested + ['穩定性測試沒有執行'])
    if s.get('temp_max') is None and not s.get('perf_samples'):
        return _item('cooling', '散熱', '電腦會不會過熱？', UNTESTED, '這台電腦沒有開放溫度與時脈資料', explain, pro=pro,
                     not_tested=not_tested + ['溫度感測器：沒有開放給一般程式讀取'])
    hot = (s.get('temp_max') or 0) >= 95; warm = (s.get('temp_max') or 0) >= 85
    throttled = bool(s.get('throttle_reasons')) or ((s.get('rate_drop') or 1) < .8 and (warm or s.get('throttle_reasons')))
    if hot or throttled:
        return _item('cooling', '散熱', '電腦會不會過熱？', WARN, '溫度過高並同時降速' if throttled else f"負載時溫度達 {s['temp_max']:.0f}°C",
                     explain + note, impact='過熱會讓電腦變慢、風扇很吵，長期下來也會縮短零件壽命。',
                     advice=['清潔通風口與風扇灰塵', '筆電放在硬桌面上，或使用散熱墊', '桌機確認機殼風扇都有在轉', '多年沒換的話，可請技術人員更換散熱膏'],
                     causes=[c for c in cpu_causes(inv, m) if c['title'].startswith('散熱')], pro=pro, not_tested=not_tested)
    if s.get('temp_max') is None:
        return _item('cooling', '散熱', '電腦會不會過熱？', PARTIAL, '負載時速度穩定，但沒有溫度感測器可讀', explain + '測試期間處理器速度沒有明顯下降。', pro=pro,
                     not_tested=not_tested + ['溫度感測器：沒有開放給一般程式讀取'])
    return _item('cooling', '散熱', '電腦會不會過熱？', OK, '散熱正常', explain + f"負載時最高 {s['temp_max']:.0f}°C，速度維持穩定。" + note, pro=pro, not_tested=not_tested)


def eval_network(inv, m, opts):
    n = m.get('network'); adapters = as_list(inv.get('net'))
    explain = '網路連線讓電腦能上網、收信和同步雲端資料。這裡測的是延遲與掉封包，不測下載速度。'
    pro = [[a.get('Name') or '網路卡', f"{a.get('InterfaceDescription') or ''} · {a.get('Status')} · {a.get('LinkSpeed') or ''}"] for a in adapters]
    not_tested = ['下載／上傳速度：需要連到外部測速伺服器，本程式不使用']
    if not opts.get('network'):
        return _item('network', '網路連線', '網路連線穩定嗎？', UNTESTED, '你選擇不測網路', explain, pro=pro, not_tested=not_tested + ['網路測試已關閉'])
    if not n:
        return _item('network', '網路連線', '網路連線穩定嗎？', UNTESTED, '這次沒有執行網路測試', explain, pro=pro, not_tested=not_tested)
    gw, net, dns = n.get('gateway_ping'), n.get('internet'), n.get('dns')
    if gw: pro.append([f"路由器 {n.get('gateway')}", f"延遲 {gw['avg']} ms · 掉封包 {gw['loss']}% · 抖動 {gw['jitter']} ms"])
    if net: pro.append(['網際網路（1.1.1.1／8.8.8.8 TCP 443）', f"延遲 {net['avg']} ms · 失敗 {net['loss']}% · 抖動 {net['jitter']} ms"])
    if dns: pro.append(['網址查詢（DNS）', f"成功 {dns['sent'] - dns['lost']}／{dns['sent']}" + (f"，平均 {dns['avg']} ms" if dns.get('avg') else '')])
    up = [a for a in adapters if str(a.get('Status')) == 'Up']
    if adapters and not up:
        return _item('network', '網路連線', '網路連線穩定嗎？', BAD, '沒有連上任何網路', explain, impact='無法上網。',
                     advice=['確認網路線有插好或 Wi-Fi 已連線', '重新開機路由器'], pro=pro, not_tested=not_tested)
    if net and net['loss'] == 100:
        return _item('network', '網路連線', '網路連線穩定嗎？', BAD, '連不上網際網路' + ('，但路由器有回應' if gw and gw['loss'] < 100 else ''), explain,
                     impact='無法上網或網頁打不開。', advice=['重新開機路由器與數據機', '確認網路費用與線路狀態，必要時聯絡網路業者'], pro=pro, not_tested=not_tested)
    problems = []
    if gw and gw['loss'] >= 10: problems.append(f"到路由器掉了 {gw['loss']}% 的封包")
    if net and net['loss'] >= 10: problems.append(f"連外失敗 {net['loss']}%")
    if net and net.get('avg') and net['avg'] >= 150: problems.append(f"連外延遲 {net['avg']} ms 偏高")
    if gw and gw.get('avg') and gw['avg'] >= 30: problems.append(f"到路由器延遲 {gw['avg']} ms 偏高")
    if dns and dns['lost']: problems.append('網址查詢有失敗')
    if problems:
        wifi = any(a.get('Wireless') for a in up)
        return _item('network', '網路連線', '網路連線穩定嗎？', WARN, '網路連線不太穩定', explain, impact='視訊會議可能斷斷續續，網頁偶爾打不開。',
                     advice=(['靠近 Wi-Fi 路由器，或改用網路線'] if wifi else []) + ['重新開機路由器', '問題持續時聯絡網路業者'],
                     finding='；'.join(problems), pro=pro, not_tested=not_tested)
    return _item('network', '網路連線', '網路連線穩定嗎？', OK, '網路連線測試正常', explain + '連到路由器與網際網路都沒有掉封包，延遲正常。', pro=pro, not_tested=not_tested)


def eval_devices(inv):
    devs = as_list(inv.get('problem_devices'))
    explain = '電腦裡的每個零件（藍牙、音效、相機、USB 控制器…）都需要「驅動程式」才能運作。'
    pro = [[d.get('Name') or d.get('DeviceID') or '裝置', f"{d.get('PNPClass') or ''} · 代碼 {d.get('ConfigManagerErrorCode')}（{DEVICE_CODES.get(d.get('ConfigManagerErrorCode'), '其他')}）"] for d in devs]
    if not inv: return _item('devices', '其他裝置與驅動程式', '零件都有被 Windows 認得嗎？', UNTESTED, '無法讀取裝置清單', explain)
    real = [d for d in devs if d.get('ConfigManagerErrorCode') not in (22, 24, 45)]   # disabled or unplugged is not a fault
    if real:
        return _item('devices', '其他裝置與驅動程式', '零件都有被 Windows 認得嗎？', WARN, f'{len(real)} 個裝置無法正常運作', explain,
                     impact='對應的功能可能無法使用，例如沒有聲音、藍牙或相機不能用。',
                     advice=['執行 Windows Update（含「選用更新」中的驅動程式）', '到電腦或主機板廠商網站下載驅動程式', '在「裝置管理員」中對該裝置按右鍵 → 更新驅動程式'],
                     finding='、'.join(f"{d.get('Name')}（{DEVICE_CODES.get(d.get('ConfigManagerErrorCode'), '錯誤')}）" for d in real[:5]), pro=pro)
    return _item('devices', '其他裝置與驅動程式', '零件都有被 Windows 認得嗎？', OK, '所有裝置都正常運作', explain + ('有些裝置是停用或未連接，這不算問題。' if devs else ''), pro=pro)


def eval_stability(inv, m):
    whea, power, bug = as_list(inv.get('ev_whea')), as_list(inv.get('ev_power')), as_list(inv.get('ev_bugcheck'))
    explain = '這裡檢查 Windows 的記錄，看最近有沒有突然斷電關機、藍色畫面，或硬體自己回報的錯誤。'
    events = (bug + power + whea)[:40]
    pro = [['藍色畫面（BugCheck 1001）', f'{len(bug)} 次'], ['非正常關機（Kernel-Power 41）', f'{len(power)} 次'], ['硬體錯誤回報（WHEA）', f'{len(whea)} 次']]
    s = m.get('stress') or {}
    if s.get('errors'): pro.append(['穩定性測試運算錯誤', f"{s['errors']} 次"])
    if not inv:
        return _item('stability', '系統穩定性', '會不會突然當機？', UNTESTED if not s else PARTIAL,
                     '無法讀取 Windows 記錄' if not s else '穩定性測試沒有出錯，但無法讀取 Windows 記錄', explain, pro=pro,
                     not_tested=['Windows 事件記錄'])
    fatal = [e for e in whea if e.get('Level') in ('錯誤', 'Error', '重大', 'Critical') or e.get('Id') in (1, 18, 20, 46)]
    if bug or fatal or s.get('errors'):
        what = '、'.join(x for x in [f'藍色畫面 {len(bug)} 次' if bug else '', f'嚴重硬體錯誤 {len(fatal)} 次' if fatal else '',
                                     f"穩定性測試算錯 {s['errors']} 次" if s.get('errors') else ''] if x)
        return _item('stability', '系統穩定性', '會不會突然當機？', BAD, f'最近 {EVENT_DAYS} 天：{what}', explain,
                     impact='可能隨時當機，未存檔的工作會遺失。', advice=['先備份重要資料', '更新 Windows 與驅動程式', '關閉超頻並清潔散熱', '持續發生請送修'],
                     events=events, pro=pro)
    if power or len(whea) >= 5:
        what = '、'.join(x for x in [f'非正常關機 {len(power)} 次' if power else '', f'已修正的硬體錯誤 {len(whea)} 次' if len(whea) >= 5 else ''] if x)
        return _item('stability', '系統穩定性', '會不會突然當機？', WARN, f'最近 {EVENT_DAYS} 天：{what}', explain + '「非正常關機」也包含直接按電源鍵或停電。',
                     impact='若不是自己按掉的，代表電腦曾突然斷電或當機。', advice=['確認插座與電源線穩固，筆電電池是否老化', '更新 Windows 與驅動程式'],
                     events=events, pro=pro)
    return _item('stability', '系統穩定性', '會不會突然當機？', OK, f'最近 {EVENT_DAYS} 天沒有當機紀錄', explain + '沒有藍色畫面或非正常關機' +
                 (f'；Windows 自動修正過 {len(whea)} 次硬體小錯誤，次數少屬正常。' if whea else '，也沒有硬體錯誤。'), pro=pro, events=events)


def eval_battery(inv, m):
    rep = m.get('battery')
    if not as_list(inv.get('battery')): return None
    explain = '電池用久了能充的電會越來越少，就像水桶越來越小。'
    if not rep: return _item('battery', '電池', '電池還耐用嗎？', UNTESTED, '無法讀取電池報告', explain, not_tested=['powercfg 電池報告'])
    b = rep[0]; pct = b['full'] / b['design'] * 100
    pro = [[x['name'], f"設計 {x['design']:.0f} mWh · 目前充滿 {x['full']:.0f} mWh（{x['full'] / x['design'] * 100:.0f}%）" + (f" · 充放電 {x['cycles']} 次" if x['cycles'] else '')] for x in rep]
    if pct < 50:
        return _item('battery', '電池', '電池還耐用嗎？', BAD, f'電池只剩原本容量的 {pct:.0f}%', explain, impact='拔掉電源後很快就沒電，老化的電池也可能鼓脹。',
                     advice=['考慮更換電池', '若電池鼓起（外殼變形、觸控板凸起）請立刻停止使用並送修'], pro=pro)
    if pct < 70:
        return _item('battery', '電池', '電池還耐用嗎？', WARN, f'電池剩原本容量的 {pct:.0f}%', explain, impact='使用時間比新的時候短。',
                     advice=['長時間插電使用時，可在廠商工具中設定充電上限 80%'], pro=pro)
    return _item('battery', '電池', '電池還耐用嗎？', OK, f'電池容量剩 {pct:.0f}%', explain, pro=pro)


def eval_ports():
    return _item('ports', '連接埠', 'USB、耳機孔能用嗎？', UNTESTED, '需要你插上裝置才能測', '連接埠是插 USB 隨身碟、耳機、螢幕的孔。程式沒辦法自己插拔，所以不會假裝測過。',
                 advice=['插上隨身碟，確認能看到檔案並複製一個大檔案', '插上耳機播放聲音', '外接螢幕確認有畫面'], not_tested=['需要人工插拔外接裝置'])


def evaluate(inv, m, opts):
    items = [eval_cpu(inv, m), eval_gpu(inv, m), eval_ram(inv, m), eval_storage(inv, m), eval_cooling(inv, m),
             eval_network(inv, m, opts), eval_devices(inv), eval_stability(inv, m)]
    bat = eval_battery(inv, m)
    if bat: items.append(bat)
    items.append(eval_ports())
    counts = {k: sum(1 for i in items if i['state'] == k) for k in STATE_TEXT}
    issues = [i for i in items if i['state'] in (BAD, WARN)]
    if issues:
        title = f'發現 {len(issues)} 個需要處理的問題'
        issues.sort(key=lambda i: i['state'] != BAD)
        named = '、'.join(f"{i['name']}（{i['headline']}）" for i in issues[:3]) + ('等' if len(issues) > 3 else '')
        lead = ('你的電腦大部分功能正常，但' if counts[OK] >= len(items) / 2 else '需要處理的有：') + named + '。'
        if any(i['id'] in ('storage', 'ram', 'stability') and i['state'] == BAD for i in issues): lead += '建議先備份重要資料。'
    else:
        title = '沒有發現需要處理的問題'
        lead = '這次檢查的項目都正常。' + ('標示「未測試」或「部分檢查」的項目沒有完整量到，不代表一定正常。' if counts[UNTESTED] + counts[PARTIAL] else '')
    return dict(title=title, lead=lead, counts=counts, items=items)


# ---------------------------------------------------------------- the job

def _top_processes(inv, threads):
    out = []
    for p in as_list(inv.get('top_processes')):
        share = (p.get('PercentProcessorTime') or 0) / max(1, threads)
        if share >= 1: out.append(dict(name=p.get('Name'), share=round(share, 1)))
    return out


def _cpu_name():
    if os.name != 'nt': return ''
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    except OSError: return ''


def run(eng, job):
    opts = options(job.opt)
    folder = job.opt.get('out_dir') or os.path.join(E.data_dir(), 'hardware-tests')
    os.makedirs(folder, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    out = E.unique_path(os.path.join(folder, '電腦健康檢查_' + stamp + '.json'))
    cancelled = lambda: job.cancelled
    m = dict(threads=os.cpu_count() or 1, cpu_name=_cpu_name())
    inv = {}; mon = Monitor(); started = time.time()

    def stage(i, frac, detail):
        if job.cancelled: raise Cancelled
        job.progress = min(.999, (i + max(0, min(1, frac))) / len(STAGES))
        job.msg = f'第 {i + 1}／{len(STAGES)} 階段：{STAGES[i]}' + (f' · {detail}' if detail else '')
        job.stage = i

    try:
        # 1 inventory
        stage(0, 0, '讀取處理器、記憶體、硬碟與網路卡資訊')
        mon.start(); mon.mark('inventory')
        inv = inventory()
        stage(0, .6, '讀取電池資訊')
        if as_list(inv.get('battery')): m['battery'] = battery_report(folder)
        stage(0, .8, '量測閒置時的處理器使用率')
        mon.mark('idle')
        for _ in range(16):
            if job.cancelled: raise Cancelled
            time.sleep(.25)
        idle = mon.window('idle')
        m['idle_util'] = _median([s['util'] for s in idle[1:]]) if len(idle) > 1 else None
        m['top_processes'] = _top_processes(inv, m['threads'])
        temps = [s['temp'] for s in mon.window('inventory') + idle if s['temp'] is not None]

        # 2 devices: disk read/write, graphics encoder, network
        stage(1, 0, f"硬碟寫入並讀回 {opts['disk_mb']} MB")
        m['disk'] = disk_test(folder, opts['disk_mb'], cancelled, lambda f: stage(1, .45 * f, f"硬碟寫入並讀回 {opts['disk_mb']} MB"))
        stage(1, .5, '顯示卡影音編碼')
        hw = E.detect_hw(); enc = hw[0] if hw else 'libx264'
        try:
            eng._proc(job, [E.FFMPEG, '-hide_banner', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30:d=2', '-c:v', enc, '-f', 'null', '-'], '顯示卡影音編碼')
            m['gpu_encode'] = dict(encoder=enc, ok=True, hw=bool(hw))
        except Cancelled: raise
        except Exception as ex:
            if job.cancelled: raise Cancelled
            m['gpu_encode'] = dict(encoder=enc, ok=False, hw=bool(hw), error=str(ex)[:160])
        if opts['network']:
            stage(1, .65, '測量網路延遲與掉封包')
            m['network'] = network_test(inv.get('gateway'), opts['pings'], cancelled)

        # 3 compute: verified work on one and on all threads, then memory patterns
        stage(2, 0, '正在驗證處理器運算結果是否正確')
        mon.mark('single')
        r1, e1, t1, _ = cpu_run(1, 3, cancelled, lambda f: stage(2, .2 * f, '單核心運算'))
        threads = m['threads']; mon.mark('multi')
        r2, e2, t2, _ = cpu_run(threads, 5, cancelled, lambda f: stage(2, .2 + .3 * f, f'{threads} 個執行緒同時運算'))
        m['cpu'] = dict(single_rps=r1 / t1, multi_rps=r2 / t2, threads=threads, scaling=(r2 / t2) / max(1e-9, r1 / t1), errors=e1 + e2)
        mon.mark('memory')
        m['memory'] = memory_test(opts['mem_mb'], cancelled, lambda f: stage(2, .5 + .5 * f, f"記憶體寫入與比對 {opts['mem_mb']} MB"))

        # 4 stability: sustained load while sampling clock, load and temperature
        stage(3, 0, f"全部核心持續運算 {opts['stress']} 秒")
        mon.mark('stress')
        rs, es, ts, per_sec = cpu_run(threads, opts['stress'], cancelled, lambda f: stage(3, f, f"全部核心持續運算 {opts['stress']} 秒"))
        mon.mark('cool'); time.sleep(1.5)
        load = mon.window('stress')
        perf = [s['perf'] for s in load if isinstance(s.get('perf'), (int, float))]
        head = per_sec[1:max(3, len(per_sec) // 6)]; tail = per_sec[-max(2, len(per_sec) // 3):]
        st = dict(seconds=round(ts), rounds=rs, errors=es, per_second=per_sec,
                  rate_drop=round(statistics.mean(tail) / statistics.mean(head), 3) if head and tail and statistics.mean(head) else None,
                  perf_median=_median(perf[2:]) if len(perf) > 3 else None, perf_samples=len(perf),
                  temp_idle=round(statistics.mean(temps), 1) if temps else None,
                  throttle_reasons=sum(s.get('thr') or 0 for s in load))
        lt = [s['temp'] for s in load if s['temp'] is not None]
        st['temp_max'] = max(lt) if lt else None
        m['stress'] = st

        # 5 report
        stage(4, .5, '整理完整健康報告')
    except Cancelled:
        pass
    finally:
        mon.stop()
        result = evaluate(inv, m, opts)
        result.update(version=1, created=time.strftime('%Y-%m-%d %H:%M'), duration=round(time.time() - started), mode=opts['mode'],
                      mode_name=opts['name'], options=opts, cancelled=job.cancelled, stages=STAGES,
                      system=dict(os=inv.get('os'), admin=inv.get('admin'), inventory_error=inv.get('_error')),
                      samples=mon.samples[-2400:], measurements={k: v for k, v in m.items() if k not in ('battery',)}, battery=m.get('battery'))
        if job.cancelled: result.update(title='檢查已取消', lead='下面只列出取消前完成的部分，沒有完成的項目一律標為未測試。')
        with open(out, 'w', encoding='utf-8') as fh: json.dump(result, fh, ensure_ascii=False, indent=1, default=str)
        lines = report_lines(result)
        txt = os.path.splitext(out)[0] + '.txt'
        with open(txt, 'w', encoding='utf-8-sig') as fh: fh.write('\r\n'.join(lines) + '\r\n')
        job.output = txt; job.keep_output = True; job.encoder = '電腦健康檢查'
        job.validation = result['title']
        job.notes = [f"{i['state_text']}　{i['name']}：{i['headline']}" for i in result['items']]
    if job.cancelled: raise InterruptedError


def report_lines(r):
    L = [f"四維八德 電腦健康檢查（{r.get('mode_name', '')}）　{r.get('created', '')}", '', r['title'], r['lead'], '',
         '【檢查結果】'] + [f"{i['state_text']:　<4}　{i['name']}：{i['headline']}" for i in r['items']]
    issues = [i for i in r['items'] if i['state'] in (BAD, WARN)]
    if issues: L += ['', '【問題解釋與處理方式】']
    for i in issues:
        L += ['', f"■ {i['name']}：{i['headline']}", i['explain']]
        if i.get('finding'): L.append('這次發現：' + i['finding'])
        if i.get('impact'): L.append('可能影響：' + i['impact'])
        L += [f'　{n}. {a}' for n, a in enumerate(i['advice'], 1)]
        for c in i['causes']:
            tag = '有證據' if c['evidence'] else '沒有發現證據' if c['evidence'] is False else '無法判斷'
            L.append(f"　可能原因：{c['title']}（{tag}）— {c['finding']}")
    L += ['', '【專業資料】']
    for i in r['items']:
        if i['pro']: L += [f"〔{i['name']}〕"] + [f'　{k}：{v}' for k, v in i['pro']]
        for e in i['events'][:10]: L.append(f"　事件 {e.get('Time')} {e.get('Provider')} #{e.get('Id')}：{e.get('Message', '')[:120]}")
    nt = [(i['name'], x) for i in r['items'] for x in i['not_tested']]
    if nt: L += ['', '【沒有測到的部分】'] + [f'　{n}：{x}' for n, x in nt]
    L += ['', '說明：這份報告只描述這次實際量到的結果；「未測試」不代表正常。溫度感測器不一定是處理器核心溫度，警告門檻依廠商規格而定。']
    return L
