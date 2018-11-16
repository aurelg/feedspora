FROM python:3.6
LABEL maintainer="Strubbl-dockerfile@linux4tw.de"

ENV DATA_DIR /data
ENV MEDIA_DIR $DATA_DIR/media
RUN \
  mkdir $DATA_DIR \
  && mkdir -p $MEDIA_DIR \
  && pip install git+https://github.com/aurelg/shaarpy.git \
  && git clone https://github.com/aurelg/feedspora.git \
  && cd feedspora \
  && pip install -r requirements.txt \
  && python setup.py install

VOLUME $DATA_DIR
WORKDIR $DATA_DIR
CMD ["python", "-m", "feedspora"]

