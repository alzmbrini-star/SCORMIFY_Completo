$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$examplePath = Join-Path $projectRoot "backend\.env.example"
$envPath = Join-Path $projectRoot "backend\.env"

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath $examplePath -Destination $envPath
}

function Read-SecretValue {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $secureValue = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines($envPath)) {
        $lines.Add($line)
    }

    $updated = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^$([Regex]::Escape($Name))=") {
            $lines[$index] = "$Name=$Value"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $lines.Add("$Name=$Value")
    }

    [IO.File]::WriteAllLines(
        $envPath,
        $lines,
        [Text.UTF8Encoding]::new($false)
    )
}

Write-Host "Configuração local do SCORMIFY"
Write-Host "Os valores serão gravados somente em backend\.env, que está ignorado pelo Git."

$openAiKey = Read-SecretValue "Cole sua OpenAI Project API key (Enter para pular)"
if (-not [string]::IsNullOrWhiteSpace($openAiKey)) {
    Set-EnvValue -Name "OPENAI_API_KEY" -Value $openAiKey.Trim()
    # Several legacy routes only use this variable as a presence check.
    # The compatibility layer still prioritizes OPENAI_API_KEY for OpenAI calls.
    Set-EnvValue -Name "EMERGENT_LLM_KEY" -Value $openAiKey.Trim()
    Write-Host "Chave OpenAI configurada para o backend local."
}

$mongoUrl = Read-SecretValue "Cole a URI do MongoDB Atlas (Enter para manter a atual)"
if (-not [string]::IsNullOrWhiteSpace($mongoUrl)) {
    Set-EnvValue -Name "MONGO_URL" -Value $mongoUrl.Trim()
    Write-Host "Conexão MongoDB configurada para o backend local."
}

$openAiKey = $null
$mongoUrl = $null
Write-Host "Configuração concluída. Reinicie o backend para aplicar as alterações."
