FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "app_v3.py", "--server.port=8501", "--server.address=0.0.0.0"]
