# 下载 COLMAP Windows 预编译包（断点续传，失败自动换镜像）
# 用法: powershell -ExecutionPolicy Bypass -File tools/fetch_colmap.ps1
$ErrorActionPreference = 'Continue'

$dir = Join-Path $PSScriptRoot '..\engines\colmap' | Resolve-Path -ErrorAction SilentlyContinue
if (-not $dir) { $dir = Join-Path $PSScriptRoot '..\engines\colmap' }
New-Item -ItemType Directory -Force $dir | Out-Null
$zip = Join-Path $dir 'colmap.zip'
$expected = 127731595

$urls = @(
  'https://gh-proxy.com/https://github.com/colmap/colmap/releases/download/4.2.1/colmap-x64-windows-nocuda.zip',
  'https://ghproxy.net/https://github.com/colmap/colmap/releases/download/4.2.1/colmap-x64-windows-nocuda.zip',
  'https://github.com/colmap/colmap/releases/download/4.2.1/colmap-x64-windows-nocuda.zip'
)

for ($i = 0; $i -lt 40; $i++) {
  $len = 0
  if (Test-Path $zip) { $len = (Get-Item $zip).Length }
  if ($len -ge $expected) { break }

  $u = $urls[$i % $urls.Count]
  Write-Host ("[{0}] {1:N1} MB / {2:N1} MB - {3}" -f $i, ($len / 1MB), ($expected / 1MB), ($u -split '/')[2])
  curl.exe -L -C - --max-time 900 --retry 2 --retry-delay 5 --retry-all-errors `
    --speed-limit 3000 --speed-time 90 -s -o $zip $u
}

$final = 0
if (Test-Path $zip) { $final = (Get-Item $zip).Length }
if ($final -ne $expected) {
  Write-Error "下载未完成: $final / $expected，可重复运行本脚本续传"
  exit 1
}

Write-Host '解压中...'
Expand-Archive -Path $zip -DestinationPath $dir -Force
$exe = Get-ChildItem $dir -Recurse -Filter 'colmap.exe' | Select-Object -First 1
if ($exe) {
  Write-Host "COLMAP: $($exe.FullName)"
  & $exe.FullName -h 2>&1 | Select-Object -First 2
} else {
  Write-Error '解压后未找到 colmap.exe'
  exit 1
}
