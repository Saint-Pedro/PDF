FROM python:3.12-slim
# Optional engines: LibreOffice (Office -> PDF), Ghostscript (compression, PDF/A), OCRmyPDF + Tesseract (OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw \
      ghostscript ocrmypdf tesseract-ocr-fra tesseract-ocr-eng \
      fonts-dejavu fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY static static
ENV PDFSTUDIO_DATA=/data
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
