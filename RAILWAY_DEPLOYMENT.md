# Railway Multi-Service Deployment Guide

This guide explains how to deploy the website monitoring application to Railway using separate services for better scalability and resource management.

## Option 2: Multiple Services Setup

### Architecture Overview
- **Web Service**: Flask application server
- **Worker Service**: Celery worker for background tasks
- **Beat Service**: Celery beat scheduler for periodic tasks

### Step-by-Step Deployment

#### 1. Create Railway Project
1. Go to [Railway.app](https://railway.app) and create a new project
2. Connect your GitHub repository

#### 2. Create Web Service
1. In your Railway project, click "Add Service" → "GitHub"
2. Select your repository
3. Railway will automatically detect the `railway.json` in the root directory
4. Configure environment variables (see Environment Variables section below)

#### 3. Create Worker Service
1. Click "Add Service" → "GitHub"
2. Select the same repository
3. In the service settings, change the "Root Directory" to `services/worker`
4. Railway will use the `services/worker/railway.json` configuration
5. Use the same environment variables as the web service

#### 4. Create Beat Service
1. Click "Add Service" → "GitHub"
2. Select the same repository
3. In the service settings, change the "Root Directory" to `services/beat`
4. Railway will use the `services/beat/railway.json` configuration
5. Use the same environment variables as the web service

### Environment Variables

Set these environment variables in each service (they should be the same for all services):

```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

### Database Setup
1. Add a PostgreSQL database to your Railway project
2. Add a Redis database to your Railway project
3. Run database migrations in the web service:
   ```bash
   flask db upgrade
   ```

### Service Configuration Details

#### Web Service (`railway.json`)
- Runs `python run.py`
- Health check on `/` with 300s timeout
- Auto-restart on failure (max 10 retries)

#### Worker Service (`services/worker/railway.json`)
- Runs `celery -A app.workers.tasks.celery worker --loglevel=info --concurrency=2`
- Optimized for background task processing
- Auto-restart on failure

#### Beat Service (`services/beat/railway.json`)
- Runs `celery -A app.workers.tasks.celery beat --loglevel=info`
- Manages periodic task scheduling
- Auto-restart on failure

### Scaling Considerations

- **Web Service**: Scale based on web traffic (start with 1 instance)
- **Worker Service**: Scale based on task queue length (start with 1-2 instances)
- **Beat Service**: Usually needs only 1 instance (schedules tasks for workers)

### Monitoring

- Check Railway logs for each service
- Monitor Redis queue lengths
- Use Railway's built-in metrics dashboard

### Troubleshooting

1. **Services not starting**: Check environment variables and database connectivity
2. **Tasks not running**: Verify Redis connection and Celery configuration
3. **Beat not scheduling**: Check Celery beat schedule configuration in settings

### Cost Optimization

- Use Railway's usage-based pricing
- Scale services based on actual load
- Consider Railway's sleep functionality for development environments