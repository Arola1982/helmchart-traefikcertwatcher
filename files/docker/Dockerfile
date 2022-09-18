FROM alpine:3.14.0

LABEL Maintainer="Adam Copley <adam.copley@arola.co.uk>"

RUN apk add \
    python3 \
    python3-dev \
    libc-dev \
    py3-pip \
    gcc

WORKDIR /app

COPY src/ /app/

RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

CMD kopf run --standalone /app/main.py