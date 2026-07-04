FROM python:3.12-slim
WORKDIR /app
COPY .docker-vendor/o-my/uci_common /app/packages/uci_common_omy
COPY .docker-vendor/o-my-sim/uci_common /app/packages/uci_common_sim
COPY services/rf-display/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir -e /app/packages/uci_common_omy -e /app/packages/uci_common_sim
COPY services/rf-display/api/app /app/app
COPY fixtures /app/fixtures
COPY scripts/run-rf-display-local.py /app/run-rf-display-local.py
ENV PYTHONUNBUFFERED=1
ENV REDIS_URL=memory://
ENV COMMLINK_DIRECTORY_XML=/app/fixtures/commlink-directory-v1.1.xml
EXPOSE 8005
CMD ["python", "/app/run-rf-display-local.py"]
