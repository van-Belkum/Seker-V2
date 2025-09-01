\
Param(
  [Parameter(Mandatory=$true)][string]$SourceFolder,
  [string]$OutFolder = ".\chunks",
  [int]$MaxMB = 180
)
$ErrorActionPreference="Stop"
New-Item -ItemType Directory -Force -Path $OutFolder | Out-Null
$files = Get-ChildItem -Recurse -File $SourceFolder
$chunk=0;$size=0;$bag=@();$limit=$MaxMB*1MB
foreach($f in $files){
  if(($size+$f.Length) -gt $limit -and $bag.Count -gt 0){
    $zip="$OutFolder\guidance_chunk_$chunk.zip"
    Compress-Archive -Path $bag.FullName -DestinationPath $zip -Force
    $chunk++;$size=0;$bag=@()
  }
  $bag += $f; $size+=$f.Length
}
if($bag.Count -gt 0){
  $zip="$OutFolder\guidance_chunk_$chunk.zip"
  Compress-Archive -Path $bag.FullName -DestinationPath $zip -Force
}
Write-Host "Created chunks in $OutFolder"
