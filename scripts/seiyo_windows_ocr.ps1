param(
    [Parameter(Mandatory = $true)] [string] $InputDirectory,
    [Parameter(Mandatory = $true)] [string] $OutputDirectory
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]

function Await-WinRt {
    param($Operation, [Type] $ResultType)
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
        } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    return $task.GetAwaiter().GetResult()
}

function Read-Ocr {
    param([string] $Path, $Engine)
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $stream = $null
    $sourceBitmap = $null
    $ocrBitmap = $null
    try {
        $file = Await-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($resolved)) ([Windows.Storage.StorageFile])
        $stream = Await-WinRt ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $sourceBitmap = Await-WinRt ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocrBitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert(
            $sourceBitmap,
            [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,
            [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore
        )
        $result = Await-WinRt ($Engine.RecognizeAsync($ocrBitmap)) ([Windows.Media.Ocr.OcrResult])
        return [ordered]@{
            source = [System.IO.Path]::GetFileName($resolved)
            width = $ocrBitmap.PixelWidth
            height = $ocrBitmap.PixelHeight
            text = $result.Text
            lines = @($result.Lines | ForEach-Object {
                [ordered]@{
                    text = $_.Text
                    words = @($_.Words | ForEach-Object {
                        [ordered]@{
                            text = $_.Text
                            x = $_.BoundingRect.X
                            y = $_.BoundingRect.Y
                            width = $_.BoundingRect.Width
                            height = $_.BoundingRect.Height
                        }
                    })
                }
            })
        }
    }
    finally {
        if ($null -ne $ocrBitmap) { $ocrBitmap.Dispose() }
        if ($null -ne $sourceBitmap) { $sourceBitmap.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

$language = New-Object Windows.Globalization.Language('ja')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) {
    throw 'Japanese Windows OCR engine is unavailable.'
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$files = @(Get-ChildItem -LiteralPath $InputDirectory -Filter '*.png' | Sort-Object Name)
if ($files.Count -lt 1) {
    throw 'No rendered Seiyo PDF pages were found.'
}
foreach ($source in $files) {
    $target = Join-Path $OutputDirectory ($source.BaseName + '.json')
    $payload = Read-Ocr $source.FullName $engine
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $target -Encoding utf8
    Write-Output $source.Name
}
