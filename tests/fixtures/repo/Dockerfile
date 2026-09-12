FROM python:3.13-slim
RUN useradd --create-home app
USER app
WORKDIR /home/app
COPY app/ ./app/
CMD ["python", "-m", "app.inventory"]
