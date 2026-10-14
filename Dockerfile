FROM python:3.12-slim
WORKDIR /app
COPY server.py admin.html index.html style.css app.js form-config.js ./
COPY assets ./assets
ENV PORT=8000 DATA_DIR=/data
EXPOSE 8000
CMD ["python", "server.py"]
