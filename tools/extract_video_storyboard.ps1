param(
    [Parameter(Mandatory = $true)][string]$VideoPath,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$player = New-Object System.Windows.Media.MediaPlayer
$player.Volume = 0
$player.ScrubbingEnabled = $true
$player.Open([Uri]$VideoPath)

for ($i = 0; $i -lt 100 -and $player.NaturalVideoWidth -le 0; $i++) {
    Start-Sleep -Milliseconds 100
}

$width = $player.NaturalVideoWidth
$height = $player.NaturalVideoHeight
if ($width -le 0 -or $height -le 0) {
    throw "Unable to open video with Windows Media Foundation: $VideoPath"
}

$duration = if ($player.NaturalDuration.HasTimeSpan) { $player.NaturalDuration.TimeSpan.TotalSeconds } else { 211.217 }
$times = @(0.05, 0.25, 0.45, 0.65, 0.85, 0.97) | ForEach-Object { [Math]::Min($duration - 0.5, $duration * $_) }

$index = 1
foreach ($seconds in $times) {
    $player.Position = [TimeSpan]::FromSeconds($seconds)
    $player.Play()
    Start-Sleep -Milliseconds 1200
    $player.Pause()

    $visual = New-Object System.Windows.Media.DrawingVisual
    $context = $visual.RenderOpen()
    $context.DrawVideo($player, (New-Object System.Windows.Rect(0, 0, $width, $height)))
    $context.Close()

    $bitmap = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(
        $width, $height, 96, 96, [System.Windows.Media.PixelFormats]::Pbgra32
    )
    $bitmap.Render($visual)

    $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
    $file = Join-Path $OutputDir ("frame-{0:D2}-{1:D3}s.png" -f $index, [int]$seconds)
    $stream = [System.IO.File]::Open($file, [System.IO.FileMode]::Create)
    try { $encoder.Save($stream) } finally { $stream.Dispose() }
    $index++
}

$player.Close()
Write-Output "Extracted $($times.Count) frames at ${width}x${height}, duration ${duration}s"
