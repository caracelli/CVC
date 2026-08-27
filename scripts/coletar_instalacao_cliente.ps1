<#
.SYNOPSIS
  Backup + coleta da instalacao do cliente. Rodar ANTES de aplicar o update.

.DESCRIPTION
  Faz duas coisas, nesta ordem:

  1. BACKUP (a rede de seguranca). O update nao toca DADOS/ nem INTERACOES/,
     mas o Processador REESCREVE o banco na primeira execucao. Se algo der
     errado, e' este backup que devolve a instalacao ao estado anterior.
       - DADOS/BANCO/*.db (+ -wal/-shm, se houver)
       - INTERACOES/ inteira (os .jsonl que ainda nao foram dobrados)

  2. COLETA (o que trazemos de volta). Os arquivos de entrada do cliente NAO
     sao versionados e a maquina de desenvolvimento so' tem uma foto de 05/08 +
     extratos de 30/04 e 24/06. Com a ENTRADA real da'-se para reproduzir o
     ambiente dela aqui e medir em cima do dado de verdade.
       - ENTRADA/ (zip)  - LOGS/ (zip)  - config.xml  - RESUMO.txt

  PowerShell puro de proposito: a maquina do cliente nao tem Python.

  ATENCAO: O que sai daqui tem CPF, nome e acesso de gente real. NAO commitar,
     NAO deixar em pasta sincronizada com nuvem publica.

.PARAMETER Raiz
  Pasta CVC_IAM_ANALYTICS da instalacao (a que tem EXECUTAVEIS/, DADOS/, ENTRADA/).

.PARAMETER Destino
  Onde gravar o snapshot. Padrao: <Raiz>\..\SNAPSHOT_CLIENTE_<data-hora>

.EXAMPLE
  .\coletar_instalacao_cliente.ps1 -Raiz "D:\CVC_IAM_ANALYTICS"

.EXAMPLE
  .\coletar_instalacao_cliente.ps1 -Raiz "D:\CVC_IAM_ANALYTICS" -Destino "E:\coleta"
#>
param(
    [Parameter(Mandatory = $true)][string]$Raiz,
    [string]$Destino
)

$ErrorActionPreference = "Stop"

function Falhar($msg) { Write-Host "FALHA: $msg" -ForegroundColor Red; exit 1 }
function Ok($msg)     { Write-Host "  OK    $msg" -ForegroundColor Green }
function Aviso($msg)  { Write-Host "  aviso $msg" -ForegroundColor Yellow }

if (-not (Test-Path $Raiz)) { Falhar "raiz nao encontrada: $Raiz" }
$Raiz = (Resolve-Path $Raiz).Path

# Confere que e' mesmo uma instalacao, e nao uma pasta qualquer
foreach ($sub in @("EXECUTAVEIS", "DADOS")) {
    if (-not (Test-Path (Join-Path $Raiz $sub))) {
        Falhar "'$Raiz' nao parece a pasta CVC_IAM_ANALYTICS (falta $sub\)"
    }
}

if (-not $Destino) {
    $carimbo = Get-Date -Format "yyyy-MM-dd_HH-mm"
    $Destino = Join-Path (Split-Path $Raiz -Parent) "SNAPSHOT_CLIENTE_$carimbo"
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$Destino = (Resolve-Path $Destino).Path

Write-Host ""
Write-Host "=== Coleta da instalacao do cliente ===" -ForegroundColor Cyan
Write-Host "  origem : $Raiz"
Write-Host "  destino: $Destino"
Write-Host ""

# --- guarda: o Processador nao pode estar rodando -------------------------
$lock = Join-Path $Raiz "DADOS\BANCO\_processando.lock"
if (Test-Path $lock) {
    Falhar "existe _processando.lock - o Processador esta rodando. Espere terminar."
}
$proc = Get-Process -Name "launcher_processador", "Processador" -ErrorAction SilentlyContinue
if ($proc) { Aviso "ha processo do Processador aberto ($($proc.Count)) - feche antes, o banco pode estar sendo escrito." }

# --- 1. BACKUP -------------------------------------------------------------
Write-Host "1) Backup (rede de seguranca)" -ForegroundColor Cyan
$bkp = Join-Path $Destino "backup"
New-Item -ItemType Directory -Force -Path (Join-Path $bkp "DADOS\BANCO") | Out-Null

$bancos = Get-ChildItem (Join-Path $Raiz "DADOS\BANCO") -File -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -like "*.db*" }
if (-not $bancos) { Aviso "nenhum banco em DADOS\BANCO (instalacao nunca processada?)" }
foreach ($b in $bancos) {
    Copy-Item $b.FullName (Join-Path $bkp "DADOS\BANCO\$($b.Name)") -Force
    Ok ("banco: {0} ({1:N1} MB)" -f $b.Name, ($b.Length / 1MB))
}

$intOrigem = Join-Path $Raiz "INTERACOES"
if (Test-Path $intOrigem) {
    Copy-Item $intOrigem (Join-Path $bkp "INTERACOES") -Recurse -Force
    $nInt = (Get-ChildItem (Join-Path $bkp "INTERACOES") -Recurse -File -ErrorAction SilentlyContinue).Count
    Ok "INTERACOES: $nInt arquivo(s) (tratativas ainda nao dobradas)"
} else {
    Aviso "sem pasta INTERACOES"
}

# --- 2. COLETA -------------------------------------------------------------
Write-Host ""
Write-Host "2) Coleta (o que voltamos com)" -ForegroundColor Cyan

function Zipar($origem, $zip, $rotulo) {
    if (-not (Test-Path $origem)) { Aviso "$rotulo nao existe"; return }
    $n = (Get-ChildItem $origem -Recurse -File -ErrorAction SilentlyContinue).Count
    if ($n -eq 0) { Aviso "$rotulo esta vazia"; return }
    Compress-Archive -Path (Join-Path $origem "*") -DestinationPath $zip -CompressionLevel Optimal -Force
    $mb = (Get-Item $zip).Length / 1MB
    Ok ("{0}: {1} arquivo(s) -> {2} ({3:N1} MB)" -f $rotulo, $n, (Split-Path $zip -Leaf), $mb)
}

Zipar (Join-Path $Raiz "ENTRADA") (Join-Path $Destino "ENTRADA.zip") "ENTRADA"
Zipar (Join-Path $Raiz "DADOS\LOGS") (Join-Path $Destino "LOGS.zip") "LOGS"

$cfg = Join-Path $Raiz "EXECUTAVEIS\CONFIG\config.xml"
if (Test-Path $cfg) {
    Copy-Item $cfg (Join-Path $Destino "config.xml") -Force
    Ok "config.xml"
} else { Aviso "config.xml nao encontrado" }

# jira.xml NAO viaja: e' o unico arquivo da instalacao que pode ter credencial.
if (Test-Path (Join-Path $Raiz "EXECUTAVEIS\CONFIG\jira.xml")) {
    Aviso "jira.xml existe na instalacao e NAO foi coletado (pode conter token)"
}

# --- 3. RESUMO -------------------------------------------------------------
$versao = "?"
if (Test-Path $cfg) {
    $m = Select-String -Path $cfg -Pattern "<versao>(.*?)</versao>"
    if ($m) { $versao = $m.Matches[0].Groups[1].Value }
}
# A ENTRADA tem duas populacoes e confundi-las engana: o que ainda vai ser
# importado, e o historico em PROCESSADOS (o Processador MOVE para la depois de
# ler). Contar so' um dos dois faz o resumo brigar com o tamanho do zip.
$entradaDir = Join-Path $Raiz "ENTRADA"
$aProcessar = @(); $nProcessados = 0
if (Test-Path $entradaDir) {
    $todos = Get-ChildItem $entradaDir -Recurse -File -ErrorAction SilentlyContinue
    $nProcessados = @($todos | Where-Object { $_.FullName -like "*\PROCESSADOS\*" }).Count
    $aProcessar = $todos |
        Where-Object { $_.FullName -notlike "*\PROCESSADOS\*" } |
        Group-Object {
            $rel = $_.Directory.FullName.Substring($entradaDir.Length).TrimStart("\")
            if ($rel) { $rel } else { "(raiz da ENTRADA)" }
        } | Sort-Object Name
}

$resumo = @()
$resumo += "Snapshot da instalacao do cliente"
$resumo += "Coletado em : $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"
$resumo += "Maquina     : $env:COMPUTERNAME  (usuario $env:USERNAME)"
$resumo += "Origem      : $Raiz"
$resumo += "Versao      : $versao"
$resumo += ""
$nAProcessar = ($aProcessar | Measure-Object -Property Count -Sum).Sum
if (-not $nAProcessar) { $nAProcessar = 0 }
$resumo += "ENTRADA: $nAProcessar arquivo(s) a processar + $nProcessados em PROCESSADOS (historico)"
$resumo += "         o zip leva os dois."
$resumo += ""
$resumo += "A processar, por pasta:"
if ($aProcessar) {
    foreach ($g in $aProcessar) { $resumo += ("  {0,-52} {1,4}" -f $g.Name, $g.Count) }
} else {
    $resumo += "  (nenhum - tudo ja foi importado; a ENTRADA so tem historico)"
}
$resumo += ""
$resumo += "Backup incluido: DADOS\BANCO + INTERACOES"
$resumo += "NAO coletado   : jira.xml (credencial), EXECUTAVEIS (temos no repo)"
$resumo += ""
$resumo += "ATENCAO: contem CPF, nome e acesso de pessoas reais."
$resumo += "Nao commitar. Nao subir para nuvem publica."
$resumo | Set-Content (Join-Path $Destino "RESUMO.txt") -Encoding UTF8

Write-Host ""
Write-Host "=== Pronto ===" -ForegroundColor Cyan
Get-Content (Join-Path $Destino "RESUMO.txt") | Write-Host
Write-Host ""
$tot = (Get-ChildItem $Destino -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host ("Snapshot em: {0}  ({1:N1} MB)" -f $Destino, $tot) -ForegroundColor Green
Write-Host "Guarde o backup ate confirmar que o update rodou bem." -ForegroundColor Yellow
