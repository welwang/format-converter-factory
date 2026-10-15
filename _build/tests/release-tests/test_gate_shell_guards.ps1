# 以會回報失敗、零通知及非零結束碼的替身程式，驗證外殼閘門會阻擋失敗。
$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '缺少本機 .NET Framework C# 編譯器' }
$parent = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'scratch'))
$root = [IO.Path]::GetFullPath((Join-Path $parent ('gate-guards-' + [guid]::NewGuid().ToString('N'))))
if (-not $root.StartsWith($parent + '\', [StringComparison]::OrdinalIgnoreCase)) { throw '測試目錄超出工作區' }
New-Item -ItemType Directory -Force -Path $root | Out-Null
$oldMode = $env:SWBD_GATE_GUARD_MODE
try {
    $source = Join-Path $root 'fake-smoke.cs'
    $fake = Join-Path $root 'fake-smoke.exe'
    @'
using System;
using System.IO;
class FakeSmoke {
    static int Main(string[] args) {
        string mode = Environment.GetEnvironmentVariable("SWBD_GATE_GUARD_MODE");
        string ok = mode == "reported-failure" ? "false" : "true";
        int notifications = mode == "zero-notifications" ? 0 : 1;
        string report = "{\"_swbd_smoke\":true,\"ok\":" + ok +
            ",\"preview\":true,\"error_rejection\":true,\"formats\":10,\"mixed_jobs\":2,\"completion_notifications\":" + notifications + "}";
        File.WriteAllText(args[1], report);
        return mode == "nonzero-exit" ? 1 : 0;
    }
}
'@ | Set-Content -LiteralPath $source -Encoding UTF8
    & $compiler /nologo /target:winexe "/out:$fake" $source
    if ($LASTEXITCODE -ne 0) { throw '測試替身編譯失敗' }
    [IO.File]::WriteAllBytes((Join-Path $root 'swbd-core.exe'), [byte[]]@())
    $fixtures = Join-Path $root 'smoke-fixtures'
    New-Item -ItemType Directory -Force -Path $fixtures | Out-Null
    foreach ($name in 'video.mp4', 'image.png', 'smoke.pdf') {
        [IO.File]::WriteAllBytes((Join-Path $fixtures $name), [byte[]]@())
    }
    $results = @()
    foreach ($mode in 'pass', 'reported-failure', 'zero-notifications', 'nonzero-exit') {
        $env:SWBD_GATE_GUARD_MODE = $mode
        $report = Join-Path $root ($mode + '.json')
        $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + (Join-Path $PSScriptRoot 'gate_shell.ps1') + '"'),
                  '-Exe', ('"' + $fake + '"'), '-OutJson', ('"' + $report + '"'), '-AppRoot', ('"' + $root + '"'))
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $start.Arguments = $args -join ' '
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        $process = [System.Diagnostics.Process]::Start($start)
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(30000)) { $process.Kill(); throw '外殼閘門負面測試逾時' }
        $rejected = $process.ExitCode -ne 0
        $expected = $mode -ne 'pass'
        if ($rejected -ne $expected) { throw "外殼閘門錯誤接受或拒絕：$mode（exit=$($process.ExitCode)） $($stderr.Result) $($stdout.Result)" }
        $results += [pscustomobject]@{ case=$mode; exit=$process.ExitCode; rejected=$rejected; ok=$true }
        $process.Dispose()
    }
    $results | ConvertTo-Json
} finally {
    $env:SWBD_GATE_GUARD_MODE = $oldMode
    $resolved = [IO.Path]::GetFullPath($root)
    if ($resolved.StartsWith($parent + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
