$src = 'C:\Users\Ivann\Downloads\Eacis\Products'
$dst = 'C:\Users\Ivann\Downloads\Eacis\eacis\static\assets\products'

if (!(Test-Path -Path $dst)) { New-Item -ItemType Directory -Path $dst | Out-Null }

Get-ChildItem -Path $src -File | ForEach-Object {
  $base = $_.BaseName -replace '\s+','-' -replace '[\(\)]','' -replace '&','and' -replace '[^a-zA-Z0-9._-]','-'
  $base = $base.Trim('-').ToLower()
  $ext = $_.Extension
  $dest = Join-Path -Path $dst -ChildPath ($base + $ext)
  Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
  Write-Output "Copied $($_.Name) -> $dest"
}
