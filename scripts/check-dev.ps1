Write-Output "IQO Strategy Lab - verificacao de ambiente de desenvolvimento"
Write-Output "----------------------------------------------------------"

function Test-Tool {
    param([string]$Name, [string]$Command, [string]$VersionArg = "--version")

    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if ($found) {
        try {
            $version = & $Command $VersionArg 2>&1 | Select-Object -First 1
        } catch {
            $version = "instalado (versao nao detectada)"
        }
        Write-Output "[OK]     $Name -> $version"
    } else {
        Write-Output "[FALTA]  $Name nao encontrado no PATH"
    }
}

Test-Tool -Name "Python" -Command "python"
Test-Tool -Name "uv"     -Command "uv"
Test-Tool -Name "Node"   -Command "node"
Test-Tool -Name "npm"    -Command "npm"
Test-Tool -Name "Docker" -Command "docker"
Test-Tool -Name "Git"    -Command "git"

Write-Output "----------------------------------------------------------"
Write-Output "Este script apenas verifica. Nada e instalado automaticamente."
