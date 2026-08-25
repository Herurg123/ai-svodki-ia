param(
    [string]$AccessFile = "C:\NotebookLMBot\ftp-access.json"
)

$ErrorActionPreference = "Stop"

function Read-Default([string]$Prompt, [string]$DefaultValue) {
    $value = Read-Host "$Prompt [$DefaultValue]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $DefaultValue }
    return $value.Trim()
}

$hostName = Read-Host "FTP host"
if ([string]::IsNullOrWhiteSpace($hostName)) {
    throw "FTP host не может быть пустым."
}

$portText = Read-Default "FTP port" "21"
[int]$port = 0
if (-not [int]::TryParse($portText, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
    throw "FTP port должен быть числом от 1 до 65535."
}

$secureText = Read-Default "FTP secure: false / true / implicit" "false"
$secure = switch ($secureText.ToLowerInvariant()) {
    "false" { $false }
    "true" { $true }
    "implicit" { "implicit" }
    default { throw "FTP secure должен быть false, true или implicit." }
}

$userName = Read-Host "FTP user"
if ([string]::IsNullOrWhiteSpace($userName)) {
    throw "FTP user не может быть пустым."
}

$uuidSecure = Read-Host "uuid" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($uuidSecure)
try {
    $uuidValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrEmpty($uuidValue)) {
    throw "uuid не может быть пустым."
}

$payload = [ordered]@{
    host = $hostName.Trim()
    port = $port
    secure = $secure
    user = $userName.Trim()
    uuid = $uuidValue
    protocol = 0
}

$parent = Split-Path -Parent $AccessFile
if ($parent) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

$tmp = "$AccessFile.tmp"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, ($payload | ConvertTo-Json -Depth 5), $utf8NoBom)

if (Test-Path $AccessFile) {
    $backup = "$AccessFile.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $AccessFile $backup -Force
    Write-Host "Резервная копия: $backup"
}
Move-Item $tmp $AccessFile -Force

Write-Host "Готово: $AccessFile"
Write-Host "protocol=0. На ближайшем запуске worker при включённой FTP-доставке локально переведёт файл в protocol=1."
