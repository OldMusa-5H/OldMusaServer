#!/bin/bash

cd src

gunicorn --bind 0.0.0.0:8080 wsgi

