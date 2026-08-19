@echo off
REM Unitree G1 (unitree_sim_isaaclab) GUI 실행 -- DDS 없이 씬만 띄운다.
REM 사용법: 이 파일을 더블클릭하거나, 터미널에서 run_gui.bat [task]
setlocal

set TEMP=D:\ic\tmp
set TMP=D:\ic\tmp
set OMNI_KIT_ACCEPT_EULA=YES
set PROJECT_ROOT=D:\ic\repos\unitree_sim_isaaclab

set TASK=%1
if "%TASK%"=="" set TASK=Isaac-Stack-RgyBlock-G129-Dex1-Joint

cd /d D:\ic\repos\unitree_sim_isaaclab

echo ============================================================
echo  task : %TASK%
echo  씬 생성에 100초 이상 걸립니다. 첫 실행은 셰이더 컴파일로
echo  더 걸릴 수 있습니다. 멈춘 것이 아닙니다.
echo ============================================================

"D:\ic\env\python.exe" -u sim_view.py --task %TASK% --enable_cameras --device cuda

echo.
echo [종료됨] 창을 닫으려면 아무 키나 누르세요.
pause
