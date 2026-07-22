[CmdletBinding()]
param(
    [ValidatePattern('^[0-9A-Za-z][0-9A-Za-z.-]{0,79}$')]
    [string]$ArtifactLabel = "0.1.0-beta.2"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$workPath = Join-Path $projectRoot "build\pyinstaller"
$bundleRoot = Join-Path $projectRoot "build\beta-dist"
$bundlePath = Join-Path $bundleRoot "Skill DNA Compiler"
$releaseRoot = Join-Path $projectRoot "dist"
$archiveName = "skill-dna-compiler-$ArtifactLabel-windows-x64.zip"
$archivePath = Join-Path $releaseRoot $archiveName
$checksumPath = "$archivePath.sha256"

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Windows x64 is required to build this Beta."
}
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "The project virtual environment was not found: $pythonPath"
}
if ((Test-Path -LiteralPath $archivePath) -or (Test-Path -LiteralPath $checksumPath)) {
    throw "The requested archive or checksum already exists. Use a new ArtifactLabel."
}

Push-Location $projectRoot
try {
    & $pythonPath -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $bundleRoot `
        --workpath $workPath `
        "packaging\windows_beta.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $expectedPrefix = [IO.Path]::GetFullPath($bundleRoot) + [IO.Path]::DirectorySeparatorChar
    $resolvedBundle = [IO.Path]::GetFullPath($bundlePath)
    if (-not $resolvedBundle.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "The resolved bundle path escaped the build directory."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $bundlePath "Skill DNA Compiler.exe"))) {
        throw "The expected Beta executable was not generated."
    }
    $streamlitIndex = Join-Path $bundlePath "_internal\streamlit\static\index.html"
    if (-not (Test-Path -LiteralPath $streamlitIndex -PathType Leaf)) {
        throw "The Streamlit frontend assets were not included in the Beta bundle."
    }

    $forbiddenRuntimeFiles = Get-ChildItem -LiteralPath $bundlePath -Recurse -Force -File |
        Where-Object {
            $_.Name -in @(".env", ".env.local", "skill-dna.db", "SKILL.md") -or
            $_.Extension -in @(".db", ".sqlite", ".sqlite3")
        }
    if ($forbiddenRuntimeFiles) {
        $paths = ($forbiddenRuntimeFiles.FullName -join "; ")
        throw "Forbidden runtime files were included in the Beta bundle: $paths"
    }

    $betaExecutable = Join-Path $bundlePath "Skill DNA Compiler.exe"
    try {
        $env:SKILL_DNA_PACKAGE_SMOKE_TEST = "1"
        $packageSmokeOutput = & $betaExecutable 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "The packaged import smoke test failed with exit code $LASTEXITCODE."
        }
        if ($packageSmokeOutput -notcontains "SKILL_DNA_PACKAGE_IMPORTS_OK") {
            throw "The packaged import smoke test did not return its success marker."
        }
    }
    finally {
        Remove-Item Env:\SKILL_DNA_PACKAGE_SMOKE_TEST -ErrorAction SilentlyContinue
    }

    $docsPath = Join-Path $bundlePath "docs"
    New-Item -ItemType Directory -Path $docsPath -Force | Out-Null
    Copy-Item -LiteralPath "docs\beta-quick-start.md" -Destination $docsPath
    Copy-Item -LiteralPath "docs\beta-test-checklist.md" -Destination $docsPath
    Copy-Item -LiteralPath "docs\privacy.md" -Destination $docsPath
    Copy-Item -LiteralPath "docs\beta-quick-start.md" `
        -Destination (Join-Path $bundlePath "README.txt")
    Copy-Item -LiteralPath "LICENSE" -Destination $bundlePath
    Copy-Item -LiteralPath "THIRD_PARTY_NOTICES.md" -Destination $bundlePath
    $streamlitLicenseSource = Join-Path $projectRoot `
        "packaging\third_party_licenses\streamlit-1.59.2"
    $streamlitLicenseHashes = @{
        "LICENSE" = "C95BAE1D1CE0235ECCCD3560B772EC1EFB97F348A79F0FBE0A634F0C2CCEFE2C"
        "NOTICES" = "EB32D824D8F2CBDC8085BB32CA331A360E1CDCF2CB0F009058E4485C4FA83308"
    }
    foreach ($licenseName in $streamlitLicenseHashes.Keys) {
        $licensePath = Join-Path $streamlitLicenseSource $licenseName
        if (-not (Test-Path -LiteralPath $licensePath -PathType Leaf)) {
            throw "Required Streamlit license asset is missing: $licensePath"
        }
        $actualLicenseHash = (Get-FileHash -LiteralPath $licensePath -Algorithm SHA256).Hash
        if ($actualLicenseHash -ne $streamlitLicenseHashes[$licenseName]) {
            throw "Streamlit license asset hash mismatch: $licenseName"
        }
    }
    $streamlitLicenseDestination = Join-Path $bundlePath `
        "THIRD_PARTY_LICENSES\streamlit-1.59.2"
    New-Item -ItemType Directory -Path $streamlitLicenseDestination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $streamlitLicenseSource "LICENSE") `
        -Destination $streamlitLicenseDestination
    Copy-Item -LiteralPath (Join-Path $streamlitLicenseSource "NOTICES") `
        -Destination $streamlitLicenseDestination
    Copy-Item -LiteralPath "tests\fixtures\sample_vault" `
        -Destination (Join-Path $bundlePath "Sample Vault") -Recurse

    # `pip freeze` preserves an editable install's original VCS URL and commit, which can be
    # stale for an uncommitted Beta candidate. `pip list --format=freeze` records the actual
    # installed distribution versions without leaking that local source provenance.
    $dependencyLines = & $pythonPath -m pip list --format=freeze
    [IO.File]::WriteAllLines(
        (Join-Path $bundlePath "dependency-versions.txt"),
        [string[]]$dependencyLines,
        [Text.UTF8Encoding]::new($false)
    )
    $collectedLicensePath = Join-Path $bundlePath `
        "THIRD_PARTY_LICENSES\python-packages"
    & $pythonPath "tools\collect_dependency_licenses.py" `
        (Join-Path $bundlePath "dependency-versions.txt") `
        $collectedLicensePath `
        --allow-missing "skill-dna-compiler" `
        --allow-missing "streamlit"
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency license collection failed with exit code $LASTEXITCODE."
    }

    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
    Compress-Archive -LiteralPath $bundlePath -DestinationPath $archivePath -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText(
        $checksumPath,
        "$hash  $archiveName`r`n",
        [Text.UTF8Encoding]::new($false)
    )

    Write-Output "Beta ZIP: $archivePath"
    Write-Output "SHA-256: $hash"
}
finally {
    Pop-Location
}
