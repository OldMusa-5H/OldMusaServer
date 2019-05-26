import json
import logging
import logging.config
from pathlib import Path

from flask import Flask

import util
from alarm import AlarmManager
from contact import Contacter
from models import db, User
from rest_controller import api, site_image
from util.db import session_scope
from util.dependency import DependencyManager
from util.logging import fix_add_parent_mkdir_on_log_write

import logging.handlers

CONFIG_PATHS = ["config.json", "../config.json", "~/.old_musa_server/config.json"]


class Main:
    def __init__(self):
        self.__setup_done = False
        self.config = None  # type: dict
        self.contacter = Contacter()
        self.alarm_manager = AlarmManager(self.contacter)
        self.app = None  # type: Flask
        self.startup = DependencyManager()
        self.startup.register_all(
            self.load_config,
            self.setup_patch_fixes,
            self.setup_flask,
            self.setup_db,
            self.setup_root_password,
            self.setup_flask_routes,
            self.setup_flask_routes_api
        )

    def find_config_file(self):
        for path in CONFIG_PATHS:
            path = Path(path)
            if path.is_file():
                return path.resolve()
        raise Exception("Cannot find config file, are you running the program from the right path?")

    def load_logging(self):
        fix_add_parent_mkdir_on_log_write()

        logging.config.dictConfig(self.config["log_settings"])

    def load_config(self):
        config_path = self.find_config_file()

        print("Using config: " + str(config_path))
        with config_path.open("rt") as f:
            self.config = json.load(f)

        # Apply config to who needs it
        self.load_logging()
        logging.info("LOGGING TEST")

        vardata_path = Path(self.config["vardata_folder"])

        site_image.set_storage_dir(vardata_path / "images")
        self.alarm_manager.load_config(
            vardata_path,
            check_interval=self.config["alarm_check_interval"]
        )
        self.contacter.load_config(**self.config["contacter"])

    def setup_root_password(self):
        root_psw = self.config["root_password"]

        if root_psw is None:
            return

        with session_scope() as session:
            root = session.query(User).filter(User.username == "root").first()

            if root is None:
                root = User(username="root", permission="A")
                session.add(root)

            root.hash_password(root_psw)

    def setup_patch_fixes(self):
        util.install_sqlite3_foreign_fix()

    def setup_flask(self):
        # Setup flask
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = self.config['config_db']
        self.app.config['SQLALCHEMY_BINDS'] = {
            'cnr': self.config['cnr_db']
        }
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    def setup_flask_routes(self):
        # Main index route, for testing purposes only (it only displays static text for now)
        @self.app.route("/")
        def index():
            return "This is the oldmusa website! we still don't have a WEB Interface ¯\\_(ツ)_/¯"

    def setup_flask_routes_api(self):
        # Init rest declarations
        api.app = self.app
        api.init_app(self.app)

    def setup_db(self):
        # Init db definitions
        db.app = self.app
        db.init_app(self.app)

        # Fix collations
        util.fix_db_string_collation(db)

        # Create all tables
        db.create_all(bind=None)

    def setup(self):
        if self.__setup_done:
            return
        self.__setup_done = True

        self.startup.call()
        self.startup = None
        logging.info("Startup done! Ready to run!")

    def start(self, run_app=True):
        self.setup()

        self.alarm_manager.start_timer_async()
        self.alarm_manager.start()

        if run_app:
            self.app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)


if __name__ == '__main__':
    main = Main()
    main.start()
