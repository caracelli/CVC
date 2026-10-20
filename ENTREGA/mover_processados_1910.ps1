# Move para PROCESSADOS os arquivos da ENTRADA que ja estao no banco de 19/10.
# Sem -Executar: so mostra o que faria. Com -Executar: move.
# A matriz de lojas e o de-para do SIG NAO estao na lista: ficam soltos de proposito.
param([switch]$Executar,
      [string]$Raiz = '\\intra.cvc\fscvc\Processos_Antlia\CVC\CVC_IAM_ANALYTICS')
$arquivos = @(
    'RH\ATIVOS\PROJETOIAM.CSV',
    'RH\DESLIGADOS\PROJETOIAMDESLIGADOS.CSV',
    'SISTEMAS\AD_DESLIGADOS\10-2026\ou_desligados_16_10_2026_06-00.csv',
    'SISTEMAS\AD_DESLIGADOS\10-2026\ou_desligados_17_10_2026_06-00.csv',
    'SISTEMAS\AD_DESLIGADOS\10-2026\ou_desligados_18_10_2026_06-00.csv',
    'SISTEMAS\AD_DESLIGADOS\10-2026\ou_desligados_19_10_2026_06-00.csv',
    'SISTEMAS\AD_FRANQUEADOS\10-2026\ou_franqueados_16_10_2026_06-10.csv',
    'SISTEMAS\AD_FRANQUEADOS\10-2026\ou_franqueados_17_10_2026_06-10.csv',
    'SISTEMAS\AD_FRANQUEADOS\10-2026\ou_franqueados_18_10_2026_06-10.csv',
    'SISTEMAS\AD_FRANQUEADOS\10-2026\ou_franqueados_19_10_2026_06-10.csv',
    'SISTEMAS\AD_PRESTADORES\10-2026\ou_prestadores_16_10_2026_06-20.csv',
    'SISTEMAS\AD_PRESTADORES\10-2026\ou_prestadores_17_10_2026_06-20.csv',
    'SISTEMAS\AD_PRESTADORES\10-2026\ou_prestadores_18_10_2026_06-20.csv',
    'SISTEMAS\AD_PRESTADORES\10-2026\ou_prestadores_19_10_2026_06-20.csv',
    'SISTEMAS\IC\10-2026\view_IC_16_10_2026_07-10.csv',
    'SISTEMAS\IC\10-2026\view_IC_17_10_2026_07-10.csv',
    'SISTEMAS\IC\10-2026\view_IC_18_10_2026_07-10.csv',
    'SISTEMAS\IC\10-2026\view_IC_19_10_2026_07-10.csv',
    'SISTEMAS\SICA_ESFERA\SICA_ESFERA_19_10.csv',
    'SISTEMAS\SICA_RA\10-2026\sica_ra_16_10_2026_06-30.csv',
    'SISTEMAS\SICA_RA\10-2026\sica_ra_17_10_2026_06-30.csv',
    'SISTEMAS\SICA_RA\10-2026\sica_ra_18_10_2026_06-30.csv',
    'SISTEMAS\SICA_RA\10-2026\sica_ra_19_10_2026_06-30.csv',
    'SISTEMAS\SICA_RA\SICA_RA_19_10.csv',
    'SISTEMAS\SIG\10-2026\view_sig_14_10_2026_07-05.csv',
    'SISTEMAS\SIG\10-2026\view_sig_15_10_2026_07-05.csv',
    'SISTEMAS\SIG\10-2026\view_sig_16_10_2026_07-05.csv',
    'SISTEMAS\SIG\10-2026\view_sig_17_10_2026_07-05.csv',
    'SISTEMAS\SIG\10-2026\view_sig_18_10_2026_07-05.csv',
    'SISTEMAS\SIG\10-2026\view_sig_19_10_2026_07-05.csv',
    'SISTEMAS\SIGOT\SIGOT_19_10.csv',
    'SISTEMAS\SYSTUR\10-2026\view_systur_16_10_2026_07-00.csv',
    'SISTEMAS\SYSTUR\10-2026\view_systur_17_10_2026_07-00.csv',
    'SISTEMAS\SYSTUR\10-2026\view_systur_18_10_2026_07-00.csv',
    'SISTEMAS\SYSTUR\10-2026\view_systur_19_10_2026_07-00.csv'
)
$n = 0; $faltam = 0
foreach ($rel in $arquivos) {
    $origem = Join-Path (Join-Path $Raiz 'ENTRADA') $rel
    if (-not (Test-Path -LiteralPath $origem)) { Write-Host "  (nao encontrado) $rel"; $faltam++; continue }
    $dest = Join-Path (Split-Path $origem -Parent) 'PROCESSADOS'
    $nome = Split-Path $origem -Leaf
    $alvo = Join-Path $dest $nome
    if (Test-Path -LiteralPath $alvo) {
        $alvo = Join-Path $dest ([IO.Path]::GetFileNameWithoutExtension($nome) + '_1910' + [IO.Path]::GetExtension($nome))
    }
    if ($Executar) {
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        Move-Item -LiteralPath $origem -Destination $alvo
        Write-Host "  movido: $rel"
    } else { Write-Host "  moveria: $rel" }
    $n++
}
Write-Host ""
if ($Executar) { Write-Host "$n arquivo(s) movido(s); $faltam nao encontrado(s)." }
else { Write-Host "$n arquivo(s) seriam movidos; $faltam nao encontrado(s). Rode de novo com -Executar para mover." }
