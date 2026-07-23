FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app .

RUN chmod +x entrypoint.sh

EXPOSE 50051
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
