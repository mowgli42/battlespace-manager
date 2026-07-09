FROM python:3.12-slim
WORKDIR /app
COPY .docker-vendor/o-my/uci_common /app/packages/o-my-uci_common
COPY .docker-vendor/commlink-directory-v1.1.xml /app/fixtures/commlink-directory-v1.1.xml
COPY services/entity-display/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e /app/packages/o-my-uci_common
COPY services/display-portal/display_landing.py /app/app/display_landing.py
COPY services/display-portal/portal_routes.py /app/app/portal_routes.py
COPY services/display-portal/service_status_bus.py /app/app/service_status_bus.py
COPY services/entity-display/api/app /app/app
ENV PYTHONUNBUFFERED=1
ENV COMMLINK_DIRECTORY_XML=/app/fixtures/commlink-directory-v1.1.xml
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
