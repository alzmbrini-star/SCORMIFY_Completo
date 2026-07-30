$ErrorActionPreference = "Stop"

$gh = "C:\Program Files\GitHub CLI\gh.exe"
$repository = "alzmbrini-star/SCORMIFY_Completo"
$baseBranch = "main"
$targetBranch = "agent/render-bootstrap"
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path -LiteralPath $gh)) {
    throw "GitHub CLI não encontrado em $gh"
}

$files = @(
    ".dockerignore",
    ".gitignore",
    "LOCAL_DEVELOPMENT.md",
    "MULTI_TENANT_DEPLOYMENT.md",
    "render.yaml",
    "backend/.env.example",
    "backend/Dockerfile",
    "backend/Dockerfile.bootstrap",
    "backend/bootstrap-requirements.txt",
    "backend/bootstrap_app.py",
    "backend/requirements-production.txt",
    "backend/requirements.txt",
    "backend/emergentintegrations/__init__.py",
    "backend/emergentintegrations/llm/__init__.py",
    "backend/emergentintegrations/llm/chat.py",
    "backend/routes/export.py",
    "backend/routes/ai_gen.py",
    "backend/routes/aesthetics.py",
    "backend/routes/admin.py",
    "backend/routes/auth.py",
    "backend/routes/projects_crud.py",
    "backend/routes/scenarios.py",
    "backend/routes/whiteboard.py",
    "backend/server.py",
    "backend/services/whiteboard_store.py",
    "backend/services/whiteboard_ai_plan.py",
    "backend/services/whiteboard_plan_renderer.py",
    "backend/services/scorm_exporter.py",
    "backend/services/scorm_single_page_exporter.py",
    "backend/services/scenario_service.py",
    "backend/services/export_assets/player.js",
    "backend/tests/test_job_tenant_access.py",
    "backend/tests/test_aesthetics_auto_fix.py",
    "backend/tests/test_ai_text_generation_openai.py",
    "backend/tests/test_export_backend_url_resolution.py",
    "backend/tests/test_llm_compat.py",
    "backend/tests/test_openai_tutor.py",
    "backend/tests/test_tutor_friendly_errors.py",
    "backend/tests/test_scorm_whiteboard_asset.py",
    "backend/tests/test_scenario_generation_reliability.py",
    "backend/tests/test_scorm_mobile_typography.py",
    "backend/tests/test_whiteboard_export_persistence.py",
    "backend/tests/test_whiteboard_semantic_geometry.py",
    "frontend/.env.example",
    "frontend/src/App.js",
    "frontend/src/contexts/AuthContext.jsx",
    "frontend/src/components/editor/AestheticsPanel.jsx",
    "frontend/src/components/editor/Timeline.jsx",
    "frontend/src/components/editor/Timeline.test.jsx",
    "frontend/src/pages/Editor/dialogs/WhiteboardDialog.jsx",
    "frontend/src/components/scenario/ScenarioCreator.jsx",
    "frontend/src/pages/Editor/hooks/useEditorAI.js",
    "frontend/src/pages/ChangePassword.jsx",
    "frontend/src/pages/Dashboard.jsx",
    "frontend/src/pages/Admin.jsx",
    "frontend/src/utils/authFetch.js",
    "frontend/src/utils/apiUrl.js",
    "scripts/configure-local-secrets.ps1",
    "scripts/publish-render-bootstrap.ps1"
)

function Invoke-GitHubApi {
    param(
        [Parameter(Mandatory = $true)][string]$Endpoint,
        [ValidateSet("GET", "POST", "PATCH")][string]$Method = "GET",
        [object]$Body = $null
    )

    $arguments = @("api", $Endpoint, "--method", $Method)
    if ($null -eq $Body) {
        $output = & $gh @arguments
    }
    else {
        $json = $Body | ConvertTo-Json -Depth 20 -Compress
        $output = $json | & $gh @arguments --input -
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao chamar a API do GitHub: $Endpoint"
    }

    return $output | ConvertFrom-Json
}

& $gh auth status | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI não está autenticado."
}

foreach ($relativePath in $files) {
    $fullPath = Join-Path $projectRoot ($relativePath -replace "/", "\")
    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "Arquivo esperado não encontrado: $relativePath"
    }

    $text = [IO.File]::ReadAllText($fullPath)
    if ($text -match "sk-proj-[A-Za-z0-9_-]{20,}") {
        throw "Possível chave OpenAI encontrada em $relativePath. Publicação interrompida."
    }
    if ($text -match "mongodb(?:\+srv)?://[^:\s]+:[^@\s]+@") {
        throw "Possível credencial MongoDB encontrada em $relativePath. Publicação interrompida."
    }
}

Write-Host "Atualizando a branch segura no GitHub..."

$baseRef = Invoke-GitHubApi -Endpoint "repos/$repository/git/ref/heads/$targetBranch"
$baseCommitSha = $baseRef.object.sha
$baseCommit = Invoke-GitHubApi -Endpoint "repos/$repository/git/commits/$baseCommitSha"
$baseTreeSha = $baseCommit.tree.sha

$treeEntries = @()
foreach ($relativePath in $files) {
    $fullPath = Join-Path $projectRoot ($relativePath -replace "/", "\")
    $bytes = [IO.File]::ReadAllBytes($fullPath)
    $blob = Invoke-GitHubApi `
        -Endpoint "repos/$repository/git/blobs" `
        -Method "POST" `
        -Body @{
            content = [Convert]::ToBase64String($bytes)
            encoding = "base64"
        }

    $treeEntries += @{
        path = $relativePath
        mode = "100644"
        type = "blob"
        sha = $blob.sha
    }
}

$tree = Invoke-GitHubApi `
    -Endpoint "repos/$repository/git/trees" `
    -Method "POST" `
    -Body @{
        base_tree = $baseTreeSha
        tree = $treeEntries
    }

$commit = Invoke-GitHubApi `
    -Endpoint "repos/$repository/git/commits" `
    -Method "POST" `
    -Body @{
        message = "Preserve authored font sizes on mobile SCORM"
        tree = $tree.sha
        parents = @($baseCommitSha)
    }

Invoke-GitHubApi `
    -Endpoint "repos/$repository/git/refs/heads/$targetBranch" `
    -Method "PATCH" `
    -Body @{
        sha = $commit.sha
        force = $false
    } | Out-Null

Write-Host "PUBLICAÇÃO_CONCLUÍDA"
Write-Host "Branch: $targetBranch"
Write-Host "Commit: $($commit.sha)"
