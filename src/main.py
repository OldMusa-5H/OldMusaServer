import logging

from flask import Flask

from models import db
from rest_controller import api

# Setup logging to file (it is in the git.ignore file so it won't be pushed)
# Log every sqlalchemy entry that is at least of INFO level
logging.basicConfig(filename='db.log')
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Setup flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # Use in memory SQLite db, will change later
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


def setup_db():
    # Init db definitions
    db.app = app
    db.init_app(app)

    # Create all tables
    db.create_all()

    # Init rest declarations
    api.app = app
    api.init_app(app)


# Main index route, for testing purposes only (it only displays static text for now)
@app.route("/")
def index():
    return "This is the oldmusa website! we still don't have a WEB Interface ¯\\_(ツ)_/¯"

if __name__ == '__main__':
    setup_db()
    app.run()
