#!/usr/bin/env python3
import os

from setuptools import setup
from setuptools import find_packages

base_dir = os.path.dirname(__file__)

about = {}
with open(os.path.join(base_dir, "src", "munch", "__about__.py")) as f:
    exec(f.read(), about)


with open(os.path.join(base_dir, "README.rst")) as f:
    long_description = f.read()

dependency_links = []


requires = [
    # Project
    'celery==3.1.23',
    'chardet==2.3.0',
    'clamd==1.0.2',
    'click==6.6',
    'cssutils==1.0.1',
    'Django==1.10.1',
    'django-filter==0.13.0',
    'django-fsm==2.4.0',
    'django-humanize==0.1.2',
    'djangorestframework==3.4.1',
    'djangorestframework-jwt==1.8.0',
    'djangorestframework-csv==1.4.1',
    'djangorestframework-bulk==0.2.1',
    'dnspython3==1.12.0',
    'html2text==2016.9.19',
    'Jinja2==2.8',
    'Markdown==2.6.6',
    'msgpack-python==0.4.8',
    'Pillow==3.3.0',
    'premailer==3.0.1',
    'Pygments==2.1.3',
    'python-magic>=0.4.10',
    'python-slimta==4.0.0',
    'requests==2.10.0',
    # munch-contacts
    'django-ipware==1.1.5',
    # Database
    'psycopg2==2.6.2',
    'psycogreen==1.0',
    # Cache
    'django-redis==4.4.4',
    # Fixtures
    'PyYAML==3.11',
    # Email backend
    'munch-mailsend==0.1.2',
]


setup(
    name=about["__title__"],
    version=about["__version__"],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    long_description=long_description,
    include_package_data=True,
    description=about["__summary__"],
    author=about["__author__"],
    author_email=about["__email__"],
    url=about["__uri__"],
    install_requires=requires,
    dependency_links=dependency_links,
    license=about["__license__"],
    entry_points={
        'console_scripts': [
            'munch = munch.runner:main']
    },
    extras_require={
        'dev': [
            'bumpversion==0.5.3',
            'docker-compose==1.8.0',
            'mkdocs==0.16.0',
            'mkdocs-bootswatch==0.4.0',
            'django-cors-headers==2.0.2'],
        'tests': [
            'flake8==3.2.0',
            'libfaketime==0.4.2',
            'factory-boy==2.7.0',
            'fake-factory==0.5.10'],
    },
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',  # noqa
    ]
)
