Add-Type -AssemblyName System.Drawing
$fontColl = New-Object System.Drawing.Text.PrivateFontCollection
$fontPath = Join-Path $PSScriptRoot "lucide.ttf"
$fontColl.AddFontFile($fontPath)
$family = $fontColl.Families[0]

$icons = @{
    "search" = 0xe151
    "filter" = 0xe29a
    "book-open" = 0xe05f
    "user-plus" = 0xe1a2
    "book-plus" = 0xe3f3
    "bookmark" = 0xe060
    "calendar" = 0xe063
    "check" = 0xe06c
    "rotate-ccw" = 0xe148
    "x" = 0xe1b2
    "arrow-right-left" = 0xe417
}

foreach ($name in $icons.Keys) {
    $code = $icons[$name]
    $size = 20
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    $font = New-Object System.Drawing.Font($family, 14, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 30, 41, 59))
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    $char = [char]$code
    $rect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
    $g.DrawString($char, $font, $brush, $rect, $sf)

    $dest = Join-Path $PSScriptRoot "$name.png"
    $bmp.Save($dest, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    Write-Host "Generated $name.png"
}
