FROM python:alpine
RUN apk update && apk add tzdata
WORKDIR /app

ENV TZ="Europe/Bratislava"
ENV PUID=1000
ENV PGID=1000

COPY websupportsk_ddns/__init__.py websupportsk_ddns/__init__.py
COPY websupportsk_ddns/logger.conf websupportsk_ddns/logger.conf
COPY websupportsk_ddns/websupportsk_ddns.py websupportsk_ddns/websupportsk_ddns.py
COPY websupportsk_ddns/notifiers.py websupportsk_ddns/notifiers.py
COPY websupportsk_ddns/logging_handlers.py websupportsk_ddns/logging_handlers.py
COPY bin bin
COPY run-sync .

RUN chown root:root bin/entrypoint
RUN chmod u+x run-sync
RUN chmod u+x bin/entrypoint

ENTRYPOINT ["/app/bin/entrypoint"]
CMD ["/app/run-sync", "--repeat"]