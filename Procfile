web: gunicorn core.wsgi --log-file=- 
celery: celery -A core worker --beat --loglevel=info
