FROM alpine:latest

RUN apk add --update clamav clamav-libunrar freshclam ca-certificates

RUN freshclam

RUN mkdir -p /run/clamav
RUN chown clamav.clamav /run/clamav
RUN sed -i 's/#TCPAddr.*$/TCPAddr 0.0.0.0/' /etc/clamav/clamd.conf
RUN sed -i 's/^#Foreground.*$/Foreground yes/' /etc/clamav/clamd.conf
RUN sed -i 's/^#LogFile.*$/LogFile no/' /etc/clamav/clamd.conf
RUN sed -i 's/^#LogVerbose.*$/LogVerbose yes/' /etc/clamav/clamd.conf

EXPOSE 3310
CMD ["clamd", "--config-file=/etc/clamav/clamd.conf"]
