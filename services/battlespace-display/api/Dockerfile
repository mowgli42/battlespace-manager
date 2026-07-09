FROM python:3.12-slim
WORKDIR /app
COPY .docker-vendor/o-my/uci_common /app/packages/o-my-uci_common
COPY .docker-vendor/o-my-sim/uci_common /app/packages/uci_common
COPY services/battlespace-display/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e /app/packages/o-my-uci_common -e /app/packages/uci_common
COPY services/display-portal/display_landing.py /app/app/display_landing.py
COPY services/display-portal/portal_routes.py /app/app/portal_routes.py
COPY services/display-portal/service_status_bus.py /app/app/service_status_bus.py
COPY services/battlespace-display/api/app /app/app
COPY scripts/run-battlespace-local.py /app/run-battlespace-local.py
COPY scripts/run-battlespace-bus.py /app/run-battlespace-bus.py
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/packages/o-my-uci_common/src:/app/packages/uci_common/src
ENV ADVISOR_EMBEDDED=0
ENV REDIS_URL=redis://redis:6379/0
ENV BUS_PICTURE_MODE=1
EXPOSE 8004
CMD ["python", "/app/run-battlespace-bus.py"]
