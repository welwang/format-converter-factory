param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference='Stop'
try {
    $dialog=New-Object -ComObject WIA.CommonDialog
    $image=$dialog.ShowAcquireImage(1,0,0,'{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}',$false,$true,$false)
    if ($null -eq $image) { exit 1 }
    $image.SaveFile($Destination)
} catch { exit 1 }
