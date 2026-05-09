@echo off
setlocal
set FLASK_DEBUG=true

echo [1/4] Starting Flask API Server...
start "Pulse API" cmd /k "python run.py"

echo [2/4] Starting Celery Worker...
start "Pulse Worker" cmd /k "python -m celery -A app.workers.tasks.celery worker --loglevel=info"

echo [3/4] Starting Celery Beat...
start "Pulse Beat" cmd /k "python -m celery -A app.workers.tasks.celery beat --loglevel=info"

echo [4/4] Starting React Frontend (Vite)...
cd frontend
start "Pulse Frontend" cmd /k "npm run dev"
cd ..

echo.
echo All Pulse services are starting...
echo API: http://localhost:5000
echo Frontend: http://localhost:5173
echo.
pause