FROM python:3.12-slim
WORKDIR /app
COPY services/display-portal/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/display-portal/display_landing.py /app/display_landing.py
COPY services/display-portal/app /app/app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
EXPOSE 8888
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
