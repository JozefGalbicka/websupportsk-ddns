FROM python:alpine
RUN apk update && apk add tzdata
WORKDIR /app

ENV TZ="Europe/Bratislava"

COPY websupportsk_ddns/__init__.py websupportsk_ddns/__init__.py
COPY websupportsk_ddns/logger.conf websupportsk_ddns/logger.conf
COPY websupportsk_ddns/websupportsk_ddns.py websupportsk_ddns/websupportsk_ddns.py
COPY bin bin
COPY run-sync .

RUN chmod u+x run-sync
RUN chmod u+x bin/entrypoint

RUN echo "*/5 * * * * /app/run-sync >/proc/1/fd/1 2> /proc/1/fd/2" > /etc/crontabs/root
ENTRYPOINT ["./bin/entrypoint"]
CMD ["/app/run-sync", "--repeat"]