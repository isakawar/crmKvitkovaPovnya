FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD sh -c "ls -l /app && echo '--- alembic.ini ---' && cat /app/alembic.ini && flask db upgrade && python3 test_crud.py && gunicorn -w 4 -b 0.0.0.0:8000 run:app" 