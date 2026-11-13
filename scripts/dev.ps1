# Run a developer task from the repository root, regardless of the caller's location.
[CmdletBinding()]
param(
    [ValidateSet('install', 'dev', 'test', 'lint', 'format', 'typecheck', 'audit', 'migrate', 'docs', 'up', 'down', 'clean', 'help')]
    [string]$Task = 'help'
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv/Scripts/python.exe'
$activateScript = Join-Path $repoRoot '.venv/Scripts/Activate.ps1'

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        $failure = [System.InvalidOperationException]::new(
            "$Executable $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
        )
        $failure.Data['ExitCode'] = $LASTEXITCODE
        throw $failure
    }
}

function Test-PythonLauncher {
    param([string]$Executable)

    # Windows PowerShell can turn redirected native stderr into an error record.
    $ErrorActionPreference = 'Continue'
    try {
        $global:LASTEXITCODE = 1
        & $Executable -3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Remove-PythonCaches {
    param([string]$Directory)

    foreach ($child in Get-ChildItem -LiteralPath $Directory -Directory -Force) {
        if ($child.Name -eq '.git' -or ($child.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            continue
        }
        if ($child.Name -eq '__pycache__') {
            Remove-Item -LiteralPath $child.FullName -Recurse -Force
        } else {
            Remove-PythonCaches $child.FullName
        }
    }
}

if ($Task -eq 'help') {
    @'
install    Create .venv and install runtime dependencies and the project
dev        Install developer tools and configure hooks when available
test       Run pytest with coverage (install requirements/test.txt first)
lint       Check Python files with Ruff
format     Format Python files with Ruff
typecheck  Run strict MyPy checks
audit      Audit runtime dependencies with pip-audit
migrate    Apply Alembic migrations when available
docs       Export OpenAPI when available
up         Build and start Docker Compose services when available
down       Stop Docker Compose services when available
clean      Remove local environments, caches, and build output
help       Show this list
'@
    exit 0
}

Push-Location -LiteralPath $repoRoot
try {
    if ($Task -eq 'clean') {
        foreach ($name in '.venv', '.mypy_cache', '.ruff_cache', '.pytest_cache', 'htmlcov', '.coverage', 'dist', 'build') {
            $path = Join-Path $repoRoot $name
            if (Test-Path -LiteralPath $path) {
                $item = Get-Item -LiteralPath $path -Force
                if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw "Cannot clean the linked path '$path'."
                }
                Remove-Item -LiteralPath $path -Recurse -Force
            }
        }
        Remove-PythonCaches $repoRoot
        exit 0
    }

    if ($Task -in 'up', 'down') {
        if (-not (Get-Command docker -CommandType Application -ErrorAction SilentlyContinue)) {
            throw 'Docker with the Compose plugin is required for this task.'
        }
        if ($Task -eq 'up') {
            Invoke-Checked docker @('compose', 'up', '--build', '-d')
        } else {
            Invoke-Checked docker @('compose', 'down')
        }
        exit 0
    }

    if ($Task -eq 'migrate' -and -not (Test-Path -LiteralPath 'alembic.ini' -PathType Leaf)) {
        throw 'Alembic configuration is not available yet.'
    }
    if ($Task -eq 'docs' -and -not (Test-Path -LiteralPath 'scripts/export_openapi.py' -PathType Leaf)) {
        throw 'The OpenAPI exporter is not available yet.'
    }

    $setup = $Task -in 'install', 'dev'
    $versionCheck = "import sys; sys.exit('Python 3.12+ is required') if sys.version_info < (3, 12) else None"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        if (-not $setup) {
            throw 'Missing .venv. Run scripts/dev.ps1 -Task dev first.'
        }
        $launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($launcher -and (Test-PythonLauncher $launcher.Source)) {
            Invoke-Checked $launcher.Source @('-3', '-m', 'venv', '.venv')
        } else {
            $python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if (-not $python) {
                throw 'Install Python 3.12 or newer and make it available through py or python.'
            }
            Invoke-Checked $python.Source @('-c', $versionCheck)
            Invoke-Checked $python.Source @('-m', 'venv', '.venv')
        }
    }

    & $activateScript
    try {
        if ($setup) {
            Invoke-Checked $venvPython @('-c', $versionCheck)
            $requirements = if ($Task -eq 'dev') { 'requirements/dev.txt' } else { 'requirements/base.txt' }
            Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', $requirements)
            Invoke-Checked $venvPython @('-m', 'pip', 'install', '-e', '.')
            if ($Task -eq 'dev') {
                if (Test-Path -LiteralPath '.pre-commit-config.yaml' -PathType Leaf) {
                    Invoke-Checked $venvPython @('-m', 'pre_commit', 'install')
                } else {
                    Write-Host 'Pre-commit setup is pending .pre-commit-config.yaml.'
                }
            }
        } else {
            switch ($Task) {
                'test' {
                    Invoke-Checked $venvPython @(
                        '-m', 'pytest', '-v', '--cov=src', '--cov-report=term-missing',
                        '--cov-report=html', '--cov-fail-under=80'
                    )
                }
                'lint' { Invoke-Checked $venvPython @('-m', 'ruff', 'check', '.') }
                'format' { Invoke-Checked $venvPython @('-m', 'ruff', 'format', '.') }
                'typecheck' { Invoke-Checked $venvPython @('-m', 'mypy', '--strict', 'src/') }
                'audit' { Invoke-Checked $venvPython @('-m', 'pip_audit', '-r', 'requirements/base.txt') }
                'migrate' { Invoke-Checked $venvPython @('-m', 'alembic', 'upgrade', 'head') }
                'docs' { Invoke-Checked $venvPython @('scripts/export_openapi.py') }
            }
        }
    } finally {
        deactivate
    }
} catch {
    [Console]::Error.WriteLine("Task '$Task' failed. $($_.Exception.Message)")
    $exitCode = $_.Exception.Data['ExitCode']
    if ($null -ne $exitCode) {
        exit $exitCode
    }
    exit 1
} finally {
    Pop-Location
}

exit 0
