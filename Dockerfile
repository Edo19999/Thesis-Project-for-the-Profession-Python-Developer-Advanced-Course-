FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && \
    pip install django==5.2.11 djangorestframework==3.15.2 djangorestframework-simplejwt celery==5.4.0 redis==5.0.7 psycopg2-binary==2.9.10 pyyaml==6.0.2 gunicorn==23.0.0

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
