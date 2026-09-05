FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Tashkent

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        libfreetype6 \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot.py config.py logging_setup.py ./
COPY db ./db
COPY filters ./filters
COPY handlers ./handlers
COPY keyboards ./keyboards
COPY middlewares ./middlewares
COPY services ./services
COPY texts ./texts
COPY assets ./assets

RUN mkdir -p /app/data /app/logs

CMD ["python", "bot.py"]
