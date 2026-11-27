@echo off
rem 全套自动测试（Windows）：导入资源 → 逐个脚本语法检查 → 机器人测试。用法：tests\run_tests.cmd <godot.exe> [浸泡秒数]
rem 结果写 tests\out\test.log，末尾 RESULT PASS/FAIL 和 EXITCODE。注意：不要用 >nul（沙盒会把它改写坏），一律写日志文件。
setlocal
set GODOT=%~1
set SOAK=%~2
if "%SOAK%"=="" set SOAK=60
cd /d %~dp0..
if not exist tests\out mkdir tests\out
"%GODOT%" --headless --path . --import > tests\out\import.log 2>&1
echo == syntax > tests\out\test.log
for %%f in (side\*.gd) do "%GODOT%" --headless --path . --check-only --script %%f >> tests\out\test.log 2>&1
findstr /c:"Parse Error" /c:"Failed to load script" tests\out\test.log && (echo RESULT FAIL  syntax errors, autotest skipped >> tests\out\test.log & echo EXITCODE 2 >> tests\out\test.log & exit /b 2)
echo == autotest >> tests\out\test.log
"%GODOT%" --headless --path . --fixed-fps 60 -- --autotest --soak=%SOAK% >> tests\out\test.log 2>&1
echo EXITCODE %ERRORLEVEL% >> tests\out\test.log
