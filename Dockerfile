FROM python:alpine

ENV PIP_ROOT_USER_ACTION=ignore

RUN apk update && apk add tzdata
RUN pip install --upgrade pip
WORKDIR /app

ENV TZ="Europe/Bratislava"
ENV PUID=1000
ENV PGID=1000

COPY requirements.txt requirements.txt
COPY websupportsk_ddns/__init__.py websupportsk_ddns/__init__.py
COPY websupportsk_ddns/logger.conf websupportsk_ddns/logger.conf
COPY websupportsk_ddns/websupportsk_ddns.py websupportsk_ddns/websupportsk_ddns.py
COPY websupportsk_ddns/notifiers.py websupportsk_ddns/notifiers.py
COPY websupportsk_ddns/logging_handlers.py websupportsk_ddns/logging_handlers.py
COPY bin bin

RUN pip install -r requirements.txt
RUN chown root:root bin/entrypoint
RUN chmod u+x bin/entrypoint

WORKDIR /app/websupportsk_ddns
ENTRYPOINT ["/app/bin/entrypoint"]
CMD ["python3", "websupportsk_ddns.py", "--repeat"]
