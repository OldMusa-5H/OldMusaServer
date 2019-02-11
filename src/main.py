import logging

from flask import Flask

from models import db
from rest_controller import api

logging.basicConfig(filename='db.log')
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


def setup_db():
    db.app = app
    db.init_app(app)

    db.create_all()

    api.app = app
    api.init_app(app)


@app.route("/")
def index():
    return "This is the oldmusa website! we still don't have a WEB Interface ¯\\_(ツ)_/¯"
