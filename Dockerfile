FROM python:3.8
LABEL maintainer="Strubbl-dockerfile@linux4tw.de"

ENV DATA_DIR /data
ENV MEDIA_DIR $DATA_DIR/media
COPY . feedspora
RUN \
  mkdir $DATA_DIR \
  && mkdir -p $MEDIA_DIR \
  && cd feedspora \
  && pip install -r requirements.txt \
  && python setup.py install

VOLUME $DATA_DIR
WORKDIR $DATA_DIR
CMD ["python", "-m", "feedspora"]

