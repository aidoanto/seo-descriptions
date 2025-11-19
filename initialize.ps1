# Get the current folder name (use as project name)
$projectName = Split-Path -Leaf (Get-Location)

Write-Host "Setting up project: $projectName"

# Copy .env.example → .env (only if .env doesn't exist)
if (-Not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item -Path ".env.example" -Destination ".env"
        Write-Host "Created .env from .env.example"
    } else {
        Write-Host "No .env.example found. Skipping..."
    }
} else {
    Write-Host ".env already exists. Skipping copy."
}

# Update pyproject.toml [project] name to match folder name
if (Test-Path "pyproject.toml") {
    $toml = Get-Content "pyproject.toml"
    $newToml = $toml -replace '^name\s*=\s*".*"$', "name = `"$projectName`""
    Set-Content "pyproject.toml" $newToml
    Write-Host "Updated pyproject.toml → project.name = $projectName"
} else {
    Write-Host "No pyproject.toml found. Skipping..."
}

# Setup virtual environment + install dependencies
Write-Host "Creating virtual environment and syncing dependencies..."
uv venv
uv sync

Write-Host "✅ Setup complete for $projectName"

# --- Self-delete mechanism ---
Write-Host "🧹 Cleanup: Deleting initialization scripts..."

# Delete both initialization scripts
Remove-Item -Path "initialize.sh" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "initialize.ps1" -Force

Write-Host "🧹 Initialization scripts removed!"
