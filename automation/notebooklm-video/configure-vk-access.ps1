param(
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [string]$ConfigFile = (Join-Path $PSScriptRoot "config.json")
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $EnvFile)) { throw "Не найден временный .env: $EnvFile" }
if (-not (Test-Path -LiteralPath $ConfigFile)) { throw "Не найден config.json: $ConfigFile" }
$entries = @{}
foreach ($line in [System.IO.File]::ReadAllLines($EnvFile)) {
    if ($line -match '^\s*(VK_GROUP_TOKEN|VK_GROUP_ID)\s*=\s*(.*?)\s*$') {
        $key = $Matches[1]
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
             ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $entries[$key] = $value
    }
}
if ($entries.Count -ne 2 -or [string]::IsNullOrWhiteSpace($entries["VK_GROUP_TOKEN"])) {
    throw ".env должен содержать VK_GROUP_ID и VK_GROUP_TOKEN"
}
$groupId = 0L
if (-not [long]::TryParse($entries["VK_GROUP_ID"], [ref]$groupId) -or $groupId -le 0) {
    throw "VK_GROUP_ID должен быть положительным числом"
}
if ($entries["VK_GROUP_TOKEN"].Length -lt 20) { throw "VK_GROUP_TOKEN слишком короткий" }

Add-Type -AssemblyName System.Security
$plain = [Text.Encoding]::UTF8.GetBytes($entries["VK_GROUP_TOKEN"])
try {
    $encrypted = [Security.Cryptography.ProtectedData]::Protect(
        $plain, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
} finally {
    [Array]::Clear($plain, 0, $plain.Length)
}
$accessFile = Join-Path (Split-Path -Parent $ConfigFile) "vk-access.json"
$payload = @{protocol=1;tokenDpapi=[Convert]::ToBase64String($encrypted)} | ConvertTo-Json
$config = [System.IO.File]::ReadAllText($ConfigFile, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
if (-not $config.vkPublish) {
    $config | Add-Member -NotePropertyName vkPublish -NotePropertyValue ([pscustomobject]@{})
}
$properties = @{
    enabled = $true
    automaticEnabled = $false
    groupId = $groupId
    playlistId = 1
    playlistTitle = "Сводки по ИИ"
    accessFile = $accessFile
    templateFile = (Join-Path (Split-Path -Parent $ConfigFile) "vk-publication-template.txt")
}
foreach ($key in $properties.Keys) {
    if ($config.vkPublish.PSObject.Properties.Name -contains $key) {
        $config.vkPublish.$key = $properties[$key]
    } else {
        $config.vkPublish | Add-Member -NotePropertyName $key -NotePropertyValue $properties[$key]
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
$configBackup = "$ConfigFile.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $ConfigFile -Destination $configBackup -Force
[IO.File]::WriteAllText("$accessFile.tmp", $payload, $utf8)
Move-Item -LiteralPath "$accessFile.tmp" -Destination $accessFile -Force
[IO.File]::WriteAllText("$ConfigFile.tmp", ($config | ConvertTo-Json -Depth 30), $utf8)
Move-Item -LiteralPath "$ConfigFile.tmp" -Destination $ConfigFile -Force

Write-Host "Параметры сообщества и плейлиста добавлены в config.json."
Write-Host "VK_GROUP_TOKEN защищён Windows DPAPI CurrentUser в vk-access.json."
Write-Host "vkPublish.automaticEnabled=false: автоматический пятый этап НЕ включён."
Write-Host "Временный .env оставлен нетронутым. После проверки потребуется отдельная очистка."
Write-Host "Резервная копия config.json: $configBackup"
