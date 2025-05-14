FROM python:3.11-slim
# пример подключения к consul кластеру при помощи локально запущенного агента для python приложения

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN apt-get update && \
    apt-get install -y curl unzip && \
    curl -fsSL https://releases.hashicorp.com/consul/1.16.2/consul_1.16.2_linux_amd64.zip -o consul.zip && \
    unzip consul.zip && \
    mv consul /usr/local/bin/ && \
    rm -rf consul.zip && \
    apt-get remove -y curl unzip && \
    apt-get autoremove -y && \
    apt-get clean

COPY start.sh /start.sh
RUN chmod +x /start.sh

ENTRYPOINT ["/start.sh"]

# CMD ["uvicorn", "stonfi_web_service:app", "--host", "0.0.0.0", "--port", "8100"]