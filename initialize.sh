#!/bin/bash

# Get the current folder name (use as project name)
projectName=$(basename "$(pwd)")

echo "Setting up project: $projectName"

# Copy .env.example → .env (only if .env doesn't exist)
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
        echo "Created .env from .env.example"
    else
        echo "No .env.example found. Skipping..."
    fi
else
    echo ".env already exists. Skipping copy."
fi

# Update pyproject.toml [project] name to match folder name
if [ -f "pyproject.toml" ]; then
    sed -i "s/^name *= *\".*\"/name = \"$projectName\"/" "pyproject.toml"
    echo "Updated pyproject.toml → project.name = $projectName"
else
    echo "No pyproject.toml found. Skipping..."
fi

# Setup virtual environment + install dependencies
echo "Creating virtual environment and syncing dependencies..."
uv venv
uv sync

echo "✅ Setup complete for $projectName"

# --- Self-delete mechanism ---
echo "🧹 Cleanup: Deleting initialization scripts..."

# Delete both initialization scripts
rm -f initialize.sh initialize.ps1

echo "🧹 Initialization scripts removed!"

