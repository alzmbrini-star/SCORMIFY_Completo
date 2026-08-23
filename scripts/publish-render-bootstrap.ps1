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
    "backend/models.py",
    "backend/emergentintegrations/__init__.py",
    "backend/emergentintegrations/llm/__init__.py",
    "backend/emergentintegrations/llm/chat.py",
    "backend/routes/export.py",
    "backend/routes/agent.py",
    "backend/routes/editor_chat.py",
    "backend/routes/company_assets.py",
    "backend/routes/health.py",
    "backend/routes/elevenlabs.py",
    "backend/routes/heygen.py",
    "backend/routes/kling.py",
    "backend/routes/ai_gen.py",
    "backend/routes/aesthetics.py",
    "backend/routes/density.py",
    "backend/routes/admin.py",
    "backend/routes/auth.py",
    "backend/routes/projects_crud.py",
    "backend/routes/projects_media.py",
    "backend/routes/questions.py",
    "backend/routes/question_bank.py",
    "backend/routes/scenarios.py",
    "backend/routes/whiteboard.py",
    "backend/server.py",
    "backend/services/whiteboard_store.py",
    "backend/services/ai_agent.py",
    "backend/services/llm_config.py",
    "backend/services/brand_library_picker.py",
    "backend/services/density_suggester.py",
    "backend/services/openai_image.py",
    "backend/services/text_density_analyzer.py",
    "backend/services/pdf_extractor.py",
    "backend/services/kling_ai.py",
    "backend/services/whiteboard_ai_plan.py",
    "backend/services/whiteboard_plan_renderer.py",
    "backend/services/whiteboard_renderer.py",
    "backend/services/scorm_exporter.py",
    "backend/services/scorm_single_page_exporter.py",
    "backend/services/scenario_service.py",
    "backend/services/single_page_exporter.py",
    "backend/services/sp_runtime/runtime.js",
    "backend/services/html_exporter.py",
    "backend/services/player_theme.py",
    "backend/services/question_engine.py",
    "backend/services/export_assets/player.js",
    "backend/services/export_assets/player_template.html",
    "backend/services/export_assets/tutor.css",
    "backend/services/export_assets/tutor.js",
    "backend/services/export_assets/scorm-api.js",
    "backend/tests/test_bunny_video_embed.py",
    "backend/tests/test_job_tenant_access.py",
    "backend/tests/test_kling_ai_integration.py",
    "backend/tests/test_ai_agent_media_resilience.py",
    "backend/tests/test_ai_agent_interactive_fallbacks.py",
    "backend/tests/test_player_theme.py",
    "backend/tests/test_question_engine.py",
    "backend/tests/test_aesthetics_auto_fix.py",
    "backend/tests/test_ai_text_generation_openai.py",
    "backend/tests/test_ai_html_generation_openai.py",
    "backend/tests/test_ai_quiz_generation_openai.py",
    "backend/tests/test_export_backend_url_resolution.py",
    "backend/tests/test_pdf_page_render_quality.py",
    "backend/tests/test_density_suggestions_openai.py",
    "backend/tests/test_density_image_openai.py",
    "backend/tests/test_llm_compat.py",
    "backend/tests/test_openai_tutor.py",
    "backend/tests/test_integrations_health_openai.py",
    "backend/tests/test_tutor_friendly_errors.py",
    "backend/tests/test_scorm_whiteboard_asset.py",
    "backend/tests/test_scenario_generation_reliability.py",
    "backend/tests/test_scorm_mobile_typography.py",
    "backend/tests/test_scorm_last_slide_completion.py",
    "backend/tests/test_scorm_simulator_fit.py",
    "backend/tests/test_font_family_export.py",
    "backend/tests/test_whiteboard_export_persistence.py",
    "backend/tests/test_whiteboard_ai_plan_jobs.py",
    "backend/tests/test_whiteboard_semantic_geometry.py",
    "backend/tests/test_editor_agent_theme_parity.py",
    "frontend/.env.example",
    "frontend/src/App.js",
    "frontend/src/contexts/AuthContext.jsx",
    "frontend/src/components/editor/AestheticsPanel.jsx",
    "frontend/src/components/admin/BrandLibraryDialog.jsx",
    "frontend/src/components/editor/SlideCanvas.jsx",
    "frontend/src/components/RichTextEditor.jsx",
    "frontend/src/components/editor/SlideCanvas.test.jsx",
    "frontend/src/components/editor/CoursePreview.jsx",
    "frontend/src/components/editor/SplitPreview.jsx",
    "frontend/src/components/editor/Timeline.jsx",
    "frontend/src/components/editor/Timeline.test.jsx",
    "frontend/src/components/DensitySuggestionsDialog.jsx",
    "frontend/src/components/quiz/QuizGenerator.jsx",
    "frontend/src/pages/Editor/dialogs/WhiteboardDialog.jsx",
    "frontend/src/pages/Editor/dialogs/MediaDialogs.jsx",
    "frontend/src/pages/Editor.jsx",
    "frontend/src/pages/Agent.jsx",
    "frontend/src/pages/Agent/components/GeneratedPanel.jsx",
    "frontend/src/pages/Agent/components/MediaConfigPanel.jsx",
    "frontend/src/pages/IntegrationsHealthPanel.jsx",
    "frontend/src/components/scenario/ScenarioCreator.jsx",
    "frontend/src/pages/Editor/hooks/useEditorAI.js",
    "frontend/src/pages/Editor/hooks/useEditorExport.js",
    "frontend/src/pages/Editor/components/ElementProperties.jsx",
    "frontend/src/pages/Editor/components/SlideProperties.jsx",
    "frontend/src/pages/Editor/components/SlideThumbnailContent.jsx",
    "frontend/src/pages/ChangePassword.jsx",
    "frontend/src/pages/Dashboard.jsx",
    "frontend/src/pages/Admin.jsx",
    "frontend/src/components/admin/GameQuestionBankPanel.jsx",
    "frontend/src/utils/authFetch.js",
    "frontend/src/utils/apiUrl.js",
    "frontend/src/utils/htmlUtils.js",
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
    $json = if ($null -eq $Body) { $null } else { $Body | ConvertTo-Json -Depth 20 -Compress }
    $maxAttempts = 5

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        # Windows PowerShell transforma stderr de programas nativos em
        # NativeCommandError quando ErrorActionPreference está em Stop.
        # Capture a saída primeiro para que falhas transitórias possam ser
        # classificadas e repetidas abaixo.
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            if ($null -eq $Body) {
                $output = & $gh @arguments 2>&1
            }
            else {
                $output = $json | & $gh @arguments --input - 2>&1
            }
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }

        $outputText = ($output | Out-String).Trim()

        if ($exitCode -eq 0) {
            if ([string]::IsNullOrWhiteSpace($outputText)) {
                return $null
            }
            return $outputText | ConvertFrom-Json
        }

        $isTransientFailure = $outputText -match '(?i)(HTTP\s+(429|500|502|503|504)|no server is currently available|temporar(?:y|ily)|timed?\s*out|connection reset)'
        if (-not $isTransientFailure -or $attempt -eq $maxAttempts) {
            throw "Falha ao chamar a API do GitHub: $Endpoint`n$outputText"
        }

        $delaySeconds = [Math]::Min(20, [Math]::Pow(2, $attempt))
        Write-Warning "GitHub indisponível temporariamente (tentativa $attempt de $maxAttempts). Tentando novamente em $delaySeconds segundos..."
        Start-Sleep -Seconds $delaySeconds
    }
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
        message = "Add multi-tenant educational game question bank"
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
