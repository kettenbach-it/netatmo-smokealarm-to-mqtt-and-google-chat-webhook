FROM python:3.9-slim-buster

LABEL maintainer="Volker Kettenbach <volker@vicosmo.de>"

WORKDIR /srv

COPY requirements.txt ./

RUN apt update && apt upgrade -y
RUN apt install -y curl bash procps inetutils-ping
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install gunicorn && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x boot.sh
RUN cp /usr/share/zoneinfo/Europe/Berlin /etc/localtime

ENV FLASK_APP app.py
ENTRYPOINT ["./boot.sh"]
