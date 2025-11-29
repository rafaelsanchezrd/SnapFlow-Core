#!/bin/bash
set -e

# Copy shared library from lib folder
cp -r ../../../lib/shared .

# Create virtualenv and install dependencies
virtualenv --without-pip virtualenv
pip install -r requirements.txt --target virtualenv/lib/python3.11/site-packages
