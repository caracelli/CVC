@echo off
rem ==========================================================================
rem  Sobe o Arquivos_origem\ENTRADAS.zip (arquivos de entrada da rede) para o
rem  GitHub pelo Git LFS. Arquivo acima de 100 MB fora do LFS e' recusado pelo
rem  GitHub — foi o que travou o push de 08/10/2026.
rem
rem  Uso (de qualquer pasta):
rem      scripts\subir_entradas_lfs.bat
rem      scripts\subir_entradas_lfs.bat Arquivos_origem\OUTRO.zip
rem
rem  O .gitattributes ja' marca Arquivos_origem/ENTRADAS.zip como LFS.
rem  Para outro nome, o script acrescenta a regra (e ela vai junto no commit).
rem ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0.."

set "ARQ=%~1"
if "%ARQ%"=="" set "ARQ=Arquivos_origem\ENTRADAS.zip"
set "ARQ_GIT=%ARQ:\=/%"

echo.
echo === Subir "%ARQ%" pelo Git LFS ===
echo.

if not exist "%ARQ%" (
    echo [ERRO] Arquivo nao encontrado: %ARQ%
    goto :fim_erro
)

git lfs version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Git LFS nao esta instalado nesta maquina.
    echo        Instale em https://git-lfs.com e rode de novo.
    goto :fim_erro
)
git lfs install --local >nul

rem --- branch certa e atualizada -------------------------------------------
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set "BR=%%b"
if /i not "%BR%"=="sig-fase1" (
    echo [ERRO] Voce esta na branch "%BR%". Rode: git checkout sig-fase1
    goto :fim_erro
)
echo Atualizando com o GitHub...
git pull --ff-only origin sig-fase1
if errorlevel 1 (
    echo [ERRO] Nao consegui atualizar. Ha commits locais pendentes?
    echo        Veja "git status -sb" e me mande a saida.
    goto :fim_erro
)

rem --- regra de LFS para o arquivo (se ainda nao houver) --------------------
git check-attr filter -- "%ARQ_GIT%" | findstr /i "lfs" >nul
if errorlevel 1 (
    echo Marcando %ARQ_GIT% como LFS no .gitattributes...
    git lfs track "%ARQ_GIT%" >nul
    git add .gitattributes
)

rem --- commit ----------------------------------------------------------------
rem -f: forca a inclusao mesmo se um .gitignore GLOBAL da maquina ignorar
rem *.zip — sem isso o add era recusado em silencio e o commit saia vazio
rem ("Your branch is up to date"), o que aconteceu em 08/10.
git check-ignore -q "%ARQ_GIT%" && (
    echo Aviso: esta maquina ignora este arquivo por uma regra local:
    git check-ignore -v "%ARQ_GIT%"
    echo        Incluindo assim mesmo ^(git add -f^).
)
git add -f "%ARQ_GIT%"
git diff --cached --quiet -- "%ARQ_GIT%"
if not errorlevel 1 (
    echo [ERRO] O arquivo nao entrou no commit.
    echo        Ele e' igual ao que ja esta no GitHub, ou o git nao o enxerga.
    echo        Mande a saida de:  git status -sb   e   dir "%ARQ%"
    goto :fim_erro
)
git commit -m "arquivos de entrada da rede: %ARQ_GIT%"
if errorlevel 1 (
    echo [ERRO] O commit falhou. Copie a mensagem acima e me mande.
    goto :fim_erro
)

rem --- confere que foi MESMO como LFS antes de empurrar ---------------------
git lfs ls-files -n | findstr /i /c:"%ARQ_GIT%" >nul
if errorlevel 1 (
    echo [ERRO] O arquivo NAO entrou como LFS. Desfazendo o commit local...
    git reset --soft HEAD~1
    goto :fim_erro
)
echo OK: o arquivo entrou como LFS.

rem --- push ------------------------------------------------------------------
echo.
echo Enviando (o upload do LFS pode levar alguns minutos)...
git push origin sig-fase1
if errorlevel 1 (
    echo [ERRO] O push falhou. Copie a mensagem acima e me mande.
    goto :fim_erro
)

echo.
echo === PRONTO: arquivo enviado. Pode avisar. ===
git log --oneline -1
pause
exit /b 0

:fim_erro
echo.
pause
exit /b 1
