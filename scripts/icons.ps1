$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assetDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'apps\web\public'
New-Item -ItemType Directory -Path $assetDirectory -Force | Out-Null
foreach ($size in @(192, 512)) {
    $bitmap = New-Object System.Drawing.Bitmap($size, $size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#2455e6'))
    $pen = New-Object System.Drawing.Pen([System.Drawing.ColorTranslator]::FromHtml('#ffffff'), ($size * 0.065))
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $points = [System.Drawing.PointF[]]@(
        [System.Drawing.PointF]::new($size * 0.72, $size * 0.28),
        [System.Drawing.PointF]::new($size * 0.38, $size * 0.28),
        [System.Drawing.PointF]::new($size * 0.28, $size * 0.42),
        [System.Drawing.PointF]::new($size * 0.66, $size * 0.58),
        [System.Drawing.PointF]::new($size * 0.56, $size * 0.72),
        [System.Drawing.PointF]::new($size * 0.28, $size * 0.72)
    )
    $graphics.DrawLines($pen, $points)
    $bitmap.Save((Join-Path $assetDirectory "icon-$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $pen.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}
