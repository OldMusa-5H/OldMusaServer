import logging
import os
import sys
from pathlib import Path

from flask import Flask

from models import db
from rest_controller import api
import json


CONFIG_PATHS = ["config.json", "../config.json", "~/.old_musa_server/config.json"]
config_path = None


for path in CONFIG_PATHS:
    path = Path(path).resolve()
    if path.is_file():
        config_path = path
        break

if config_path is None:
    print("Cannot file config file!", file=sys.stderr)
    sys.exit(1)

print("Using config: " + str(config_path))
with config_path.open("rt") as f:
    config = json.load(f)


# Setup logging to file (it is in the git.ignore file so it won't be pushed)
# Log every sqlalchemy entry that is at least of INFO level
if config['sql_log']['enabled']:
    logging.basicConfig(filename=config['sql_log']['output'])
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Setup flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config['config_db']
app.config['SQLALCHEMY_BINDS'] = {
    'cnr':  config['cnr_db']
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


def setup_db():
    # Init db definitions
    db.app = app
    db.init_app(app)

    # Create all tables
    db.create_all(bind=None)

    # Init rest declarations
    api.app = app
    api.init_app(app)


# Main index route, for testing purposes only (it only displays static text for now)
@app.route("/")
def index():
    return "This is the oldmusa website! we still don't have a WEB Interface ¯\\_(ツ)_/¯"


if __name__ == '__main__':
    setup_db()
    app.run(host=config["listen_addr"], port=config["listen_port"])
