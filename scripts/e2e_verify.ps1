$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = Get-RepoRoot
Set-Location $root

$ffmpeg = Join-Path $root "tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffmpeg.exe"
$ffprobe = Join-Path $root "tools/ffmpeg/ffmpeg-8.1-essentials_build/bin/ffprobe.exe"
if (!(Test-Path $ffmpeg) -or !(Test-Path $ffprobe)) {
  throw "FFmpeg not found. Expected: $ffmpeg"
}

$work = Join-Path $root "data/_e2e"
New-Item -ItemType Directory -Force -Path $work | Out-Null

$video = Join-Path $work "base.mp4"
$red = Join-Path $work "red.png"
$blueGif = Join-Path $work "blue.gif"
$green = Join-Path $work "green.mp4"
$srt = Join-Path $work "subtitles.srt"
$csv = Join-Path $work "config.csv"

Write-Host "Generating test assets in $work ..."
& $ffmpeg -v error -y -f lavfi -i "color=c=white:s=640x360:d=5" -pix_fmt yuv420p $video
& $ffmpeg -v error -y -f lavfi -i "color=c=red:s=120x120:d=1" -frames:v 1 $red
& $ffmpeg -v error -y -f lavfi -i "color=c=blue:s=120x120:d=1" -vf "fps=10" $blueGif
& $ffmpeg -v error -y -f lavfi -i "color=c=green:s=120x120:d=1" -pix_fmt yuv420p $green

@"
from pathlib import Path

srt = Path(r"$srt")
csv = Path(r"$csv")

srt.write_text(
    "1\n00:00:00,500 --> 00:00:01,500\n\u5bb6\u4eba\u4eec\n\n"
    "2\n00:00:02,000 --> 00:00:03,000\n\u5bb6\u4eba\u4eec \u91cd\u70b9\n\n"
    "3\n00:00:03,500 --> 00:00:04,500\n\u91cd\u70b9\n",
    encoding="utf-8",
)

csv.write_text(
    "\u5173\u952e\u5b57,\u7d20\u6750\u6587\u4ef6\u540d,\u7d20\u6750\u7c7b\u578b,\u663e\u793a\u65f6\u957f(\u79d2),\u5165\u573a\u504f\u79fb(\u79d2),\u4e5d\u5bab\u683c\u4f4d\u7f6e,\u900f\u660e\u5ea6,\u662f\u5426\u5faa\u73af,\u89e6\u53d1\u89c4\u5219\n"
    "\u5bb6\u4eba\u4eec,red.png,\u56fe\u7247,1.0,0,1,100,0,\u9996\u6b21\u89e6\u53d1\n"
    "\u91cd\u70b9,blue.gif,GIF,0.8,0,5,50,1,\u6bcf\u6b21\u89e6\u53d1\n",
    encoding="utf-8",
)
"@ | python -

function Get-FreePort([int]$startPort) {
  for ($p = $startPort; $p -lt ($startPort + 50); $p++) {
    try {
      $inUse = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
      if (-not $inUse) { return $p }
    } catch {
      return $p
    }
  }
  return $startPort
}

$port = Get-FreePort 8003
Write-Host "Starting backend (port $port) ..."
$backend = Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList @(
  "-m","uvicorn","backend.main:app","--host","127.0.0.1","--port",$port
) -PassThru

try {
  # Wait until backend is reachable
  $ready = $false
  for ($i=0; $i -lt 30; $i++) {
    try {
      $null = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/stats" -TimeoutSec 2
      $ready = $true
      break
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  if (-not $ready) { throw "Backend not ready on port $port" }

  Write-Host "Setting system settings ..."
  $settingsBody = @{
    output_format = "MP4"
    resolution = "720P"
    video_bitrate_kbps = 1500
    subtitle_encoding = "utf-8"
    subtitle_time_offset_seconds = 0
  } | ConvertTo-Json
  Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:$port/api/settings" -ContentType "application/json" -Body $settingsBody | Out-Null

  Write-Host "Uploading materials ..."
  $uploadRes = & curl.exe -s -X POST `
    -F "files=@$red" `
    -F "files=@$blueGif" `
    -F "files=@$green" `
    "http://127.0.0.1:$port/api/materials"
  $uploadJson = $uploadRes | ConvertFrom-Json
  if (($uploadJson.failed | Measure-Object).Count -gt 0) {
    Write-Host "Material upload failures:" -ForegroundColor Yellow
    $uploadJson.failed | Format-Table | Out-String | Write-Host
  }

  Write-Host "Creating task via CSV config ..."
  $taskRes = & curl.exe -s -X POST `
    -F "task_name=e2e_test_1" `
    -F "video=@$video" `
    -F "subtitle=@$srt" `
    -F "config_csv=@$csv" `
    "http://127.0.0.1:$port/api/tasks"
  $task = $taskRes | ConvertFrom-Json
  $taskId = [int]$task.id
  Write-Host "Task ID: $taskId"

  Write-Host "Polling task status ..."
  $deadline = (Get-Date).AddMinutes(3)
  do {
    Start-Sleep -Seconds 2
    $t = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/tasks/$taskId"
    Write-Host ("  status={0} progress={1}" -f $t.status, $t.progress)
    if ($t.status -eq "completed" -or $t.status -eq "failed") { break }
  } while ((Get-Date) -lt $deadline)

  if ($t.status -ne "completed") {
    throw "Task did not complete. status=$($t.status)"
  }

  $out = Join-Path $work "output.mp4"
  $rep = Join-Path $work "report.xlsx"
  $log = Join-Path $work "log.txt"
  & curl.exe -s -L "http://127.0.0.1:$port/api/tasks/$taskId/output" -o $out
  & curl.exe -s -L "http://127.0.0.1:$port/api/tasks/$taskId/report" -o $rep
  & curl.exe -s -L "http://127.0.0.1:$port/api/tasks/$taskId/log" -o $log

  if (!(Test-Path $out)) { throw "Output missing: $out" }
  if (!(Test-Path $rep)) { throw "Report missing: $rep" }
  if (!(Test-Path $log)) { throw "Log missing: $log" }

  Write-Host "Frame-level sanity checks ..."
  function AvgRgb($time, $vf) {
    $raw = Join-Path $work ("frame_{0}.raw" -f ($time.ToString().Replace('.','_')))
    if (Test-Path $raw) { Remove-Item $raw -Force }
    & $ffmpeg -v error -ss $time -i $out -vf $vf -frames:v 1 -f rawvideo -pix_fmt rgb24 $raw 2>$null
    $arr = [IO.File]::ReadAllBytes($raw)
    if ($arr.Length -eq 0) { throw "No frame bytes for t=$time" }
    $len = $arr.Length
    $sumR = 0L; $sumG = 0L; $sumB = 0L
    for ($i=0; $i -lt $len; $i+=3) {
      $sumR += $arr[$i]
      $sumG += $arr[$i+1]
      $sumB += $arr[$i+2]
    }
    $px = [double]($len/3)
    return @{ r = $sumR/$px; g = $sumG/$px; b = $sumB/$px }
  }

  # 1) red overlay should appear at top-left around 1.0s
  $a1 = AvgRgb 1.0 "crop=60:60:0:0,format=rgb24"
  # 2) red overlay should NOT appear around 2.2s (首次触发 only)
  $a2 = AvgRgb 2.2 "crop=60:60:0:0,format=rgb24"
  # 3) blue overlay should appear around 3.8s in center (opacity 50)
  $a3 = AvgRgb 3.8 "crop=60:60:(in_w-60)/2:(in_h-60)/2,format=rgb24"

  Write-Host ("  t=1.0 top-left avg rgb: {0:N1},{1:N1},{2:N1}" -f $a1.r,$a1.g,$a1.b)
  Write-Host ("  t=2.2 top-left avg rgb: {0:N1},{1:N1},{2:N1}" -f $a2.r,$a2.g,$a2.b)
  Write-Host ("  t=3.8 center avg rgb:   {0:N1},{1:N1},{2:N1}" -f $a3.r,$a3.g,$a3.b)

  if (!($a1.r -gt ($a1.g + 40) -and $a1.r -gt ($a1.b + 40))) { throw "Expected red overlay at t=1.0" }
  if (!([math]::Abs($a2.r - $a2.g) -lt 10 -and [math]::Abs($a2.r - $a2.b) -lt 10 -and $a2.r -gt 220)) { throw "Expected no red overlay at t=2.2 (white region)" }
  if (!($a3.b -gt $a3.r -and $a3.b -gt $a3.g)) { throw "Expected blue overlay at t=3.8" }

  Write-Host "E2E verification PASSED." -ForegroundColor Green
}
finally {
  if ($backend -and !$backend.HasExited) { Stop-Process -Id $backend.Id -Force }
}
