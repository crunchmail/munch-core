DJANGO_SETTINGS_MODULE ?= munch.settings

default:
	@echo "Must call a specific subcommand"
	@exit 1

.assert-no-production:
ifeq ("$(DJANGO_SETTINGS_MODULE)", "munch.settings.production")
	echo "!! Cannot run this command in production environment"
	exit 1
endif

init_dev: .assert-no-production
	pip install -e .[dev,test] --process-dependency-links
	docker-compose up -d
ifneq ($(wildcard "./src/munch/settings/local.py"),)
	cp ./src/munch/settings/local.dist.py ./src/munch/settings/local.py
endif
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) django-admin migrate
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) django-admin loaddata dev
	@echo ""
	@echo " :: Default users"
	@echo "     - superadmin@example.com / password (django admin)"
	@echo "     - admin@example.com      / password (admin)"
	@echo "     - manager@example.com    / password (manager)"
	@echo "     - user@example.com       / password (user)"
	@echo ""
	@echo " :: Documentation can be found in *docs* directory"
	@echo " :: To build and open it: make build_docs && make open_docs"

reset_mq: .assert-no-production
	docker-compose exec rabbitmq rabbitmqctl stop_app
	docker-compose exec rabbitmq rabbitmqctl reset
	docker-compose exec rabbitmq rabbitmqctl start_app

reset_cache: .assert-no-production
	@echo "Purging cache..."
	docker-compose exec redis redis-cli flushall

reset_db: .assert-no-production
	@echo "Dropping database..."
	docker-compose exec postgres dropdb -U munch munch
	@echo "Creating database..."
	docker-compose exec postgres createdb -U munch munch

load_data: .assert-no-production
	@echo "Loading data..."
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) django-admin migrate
	DJANGO_SETTINGS_MODULE=$(DJANGO_SETTINGS_MODULE) django-admin loaddata dev

reset_app: .assert-no-production reset_mq reset_cache reset_db load_data

serve_docs: .assert-no-production
	cd docs && mkdocs serve

test:
	munch django test munch --settings=munch.settings.test

release:
	@echo "Releasing \"`python -c 'from munch import __version__ as v;print(v)'`\" on Pypi in 5 seconds..."
	@sleep 5
	python setup.py sdist bdist_wheel upload

.PHONY: init_dev reset_app serve_docs test release
