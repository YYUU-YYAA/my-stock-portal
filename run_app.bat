@echo off
echo ============================================
echo  株価バリュエーション電卓 を起動中...
echo ============================================
cd /d "%~dp0"
.venv\Scripts\streamlit.exe run app.py --server.port 8501
pause
