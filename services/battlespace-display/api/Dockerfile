FROM python:3.12-slim
WORKDIR /app
COPY .docker-vendor/o-my-sim/uci_common /app/packages/uci_common
COPY services/battlespace-display/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e /app/packages/uci_common
COPY services/battlespace-display/api/app /app/app
COPY scripts/run-battlespace-local.py /app/run-battlespace-local.py
ENV PYTHONUNBUFFERED=1
ENV ADVISOR_EMBEDDED=1
ENV REDIS_URL=memory://
EXPOSE 8004
CMD ["python", "/app/run-battlespace-local.py"]
