import json
import logging
import sys
from pathlib import Path

from flask import Flask
from sqlalchemy.orm import Session

import contact
import site_image
import util
from models import db, User
from rest_controller import api

util.install_sqlite3_foreign_fix()

CONFIG_PATHS = ["config.json", "../config.json", "~/.old_musa_server/config.json"]
config_path = None

for path in CONFIG_PATHS:
    path = Path(path)
    if path.is_file():
        config_path = path.resolve()
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

site_image.set_storage_dir(config["map_storage_folder"])

# Setup flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config['config_db']
app.config['SQLALCHEMY_BINDS'] = {
    'cnr': config['cnr_db']
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

contacter = None  # type: contact.Contacter


def setup_db():
    # Init db definitions
    db.app = app
    db.init_app(app)

    # Fix collations
    util.fix_db_string_collation(db)

    # Create all tables
    db.create_all(bind=None)

    global contacter
    contacter = contact.Contacter(**config["contacter"])

    # Root psw?
    root_psw = config["root_password"]
    if root_psw is not None:
        session = db.session  # type: Session

        root = session.query(User).filter(User.username == "root").first()

        if root is None:
            root = User(username="root", permission="A")
            session.add(root)

        root.hash_password(root_psw)

        session.commit()

    # Init rest declarations
    api.app = app
    api.init_app(app)


# Main index route, for testing purposes only (it only displays static text for now)
@app.route("/")
def index():
    return "This is the oldmusa website! we still don't have a WEB Interface ¯\\_(ツ)_/¯"


if __name__ == '__main__':
    setup_db()
    app.run(host="0.0.0.0", port=8080)
