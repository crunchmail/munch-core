FROM alpine:latest

RUN apk add --update spamassassin wget ca-certificates

RUN sa-update

RUN mkdir -p /var/spool/mail/.spamassassin
RUN chown -R mail.mail /var/spool/mail/

COPY spamd.cf /etc/mail/spamassassin/99-custom.cf

EXPOSE 783
CMD /usr/sbin/spamd -x --syslog-socket none -m 1 -H -u mail -g mail -p 783 -i 0.0.0.0 -A 0.0.0.0/0
