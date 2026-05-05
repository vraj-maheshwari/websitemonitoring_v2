web: python run.py
worker: celery -A app.workers.tasks.celery worker --loglevel=info
beat: celery -A app.workers.tasks.celery beat --loglevel=info
