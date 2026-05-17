FROM mcr.microsoft.com/dotnet/sdk:8.0
RUN dotnet tool install --global pbi-tools
ENV PATH="$PATH:/root/.dotnet/tools"
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.11 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip3 install -r requirements.txt --break-system-packages
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
