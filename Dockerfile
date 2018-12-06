FROM python:3.6
LABEL maintainer="Strubbl-dockerfile@linux4tw.de"

ARG GIT_REPO=https://github.com/aurelg/feedspora.git
ARG GIT_REPO_REV=master
ENV DATA_DIR /data
ENV MEDIA_DIR $DATA_DIR/media
RUN \
  mkdir $DATA_DIR \
  && mkdir -p $MEDIA_DIR \
  && git clone $GIT_REPO \
  && cd feedspora \
  && git checkout $GIT_REPO_REV \
  && pip install -r requirements.txt \
  && python setup.py install

VOLUME $DATA_DIR
WORKDIR $DATA_DIR
CMD ["python", "-m", "feedspora"]

