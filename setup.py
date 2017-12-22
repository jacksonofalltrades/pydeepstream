#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pip install twine

import io
import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command
from setuptools.command.install import install

import subprocess

# class InstallLocalPackage(install):
#     def run(self):
#         import sys
#         from distutils.core import run_setup
#         run_setup('./deepstreampy/setup.py', script_args=sys.argv[1:], stop_after='run')
#         install.run(self)


# Package meta-data.
NAME = 'deepstreampy_twisted'
VERSION = '0.1.2'
DESCRIPTION = 'A deepstream.io client for Twisted.'
URL = 'https://www.github.com/sapid/deepstreampy_twisted'
AUTHOR = 'Will Crawford'

# What packages are required for this module to be executed?
def requirements(filename='requirements.txt'):
    with open(filename) as f:
        requirements = f.read().splitlines()
        massaged_requirements = []
        for req in requirements:
            if req[0] != '-':
                massaged_requirements.append(req)
        massaged_requirements.append('deepstreampy==0.1.1')
        return massaged_requirements

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.rst' is present in your MANIFEST.in file!
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()

class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPi via Twine…')
        os.system('twine upload dist/*')

        sys.exit()


# Where the magic happens:
setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    author=AUTHOR,
    url=URL,
    packages=find_packages(exclude=('tests',)),
    # If your package is a single module, use this instead of 'packages':
    # py_modules=['mypackage'],

    # entry_points={
    #     'console_scripts': ['mycli=mymodule:cli'],
    # },
    install_requires=requirements(),
    dependency_links=['git+https://github.com/sapid/deepstreampy.git@patch-1#egg=deepstreampy-0.1.1'],
    include_package_data=True,
    license='MIT',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Intended Audience :: Developers'
    ],
    test_suite = 'tests',
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
    },
)
