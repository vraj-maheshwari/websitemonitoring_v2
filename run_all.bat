@echo off

echo Starting run.py...
start "Run Server" cmd /k python run.py

echo Starting Celery Worker...
start "Celery Worker" cmd /k python -m celery -A app.workers.tasks.celery worker --loglevel=info

echo Starting Celery Beat...
start "Celery Beat" cmd /k python -m celery -A app.workers.tasks.celery beat --loglevel=info

echo All services started!
pause