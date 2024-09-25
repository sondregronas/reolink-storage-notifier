FROM python:3.12

# Variables
ENV REOLINK_USERNAME=""
ENV REOLINK_PASSWORD=""

ENV SMTP_SERVER=""
ENV SMTP_PORT=587
ENV SMTP_USERNAME=""
ENV SMTP_PASSWORD=""
ENV SMTP_FROM=""

# Timezone
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ='Europe/Oslo'
RUN apt-get update && apt-get install -y tzdata && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install dependencies and copy source code
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src src

# Run the application
CMD ["python", "src/main.py"]