.PHONY: test
test: pep8
	export PYTHONPATH=$(pwd)/src;
	export MEDIA_DIR=/tmp && cd tests \
		&& pytest --cov-report term-missing --cov feedspora

.PHONY: reqs
reqs:
	pip install -r requirements.txt
	pip install -r requirements_dev.txt

.PHONY: pep8
pep8: reqs
	pylint --exit-zero src tests/*.py

.PHONY: clean-pyc clean-build clean
clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr *.egg

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
