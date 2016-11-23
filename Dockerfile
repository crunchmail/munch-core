FROM python:3.4.5
MAINTAINER Crunchmail <dev@crunchmail.com>

WORKDIR /app

COPY README.rst README.rst
COPY setup.py setup.py
COPY src/ src

RUN pip install --process-dependency-links -e .

RUN addgroup --gid 54321 munch
RUN adduser --disabled-password --gecos '' \
    --uid 54321 --gid 54321 --home /app \
    --shell /bin/bash munch

RUN chown -R munch.munch /app
USER munch:munch

ENV DJANGO_SETTINGS_MODULE munch.settings

ENTRYPOINT ["/usr/local/bin/munch"]
CMD ["--help"]
