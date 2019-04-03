from flask_sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context


# Here's the sql representation of the data we need to store
# don't put any logic in this file, it should only contain sql definitions
# If you don't understand any of this go read the sqlalchemy documentation
from sqlalchemy.dialects.mysql import DOUBLE

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(128))

    # A: Admin
    # U: User (no permission)
    permission = db.Column(db.String(1), default="U")

    sites = db.relationship("Site", secondary="user_access")

    def hash_password(self, password):
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password) -> bool:
        return pwd_context.verify(password, self.password_hash)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "permission": self.permission,
        }


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100))
    id_cnr = db.Column(db.String(50))

    maps = db.relationship("Map")
    sensors = db.relationship("Sensor")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "id_cnr": self.id_cnr,
        }


class UserAccess(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), ondelete="CASCADE", primary_key=True, index=True)
    site_id = db.Column(db.Integer, db.ForeignKey(Site.id), ondelete="CASCADE", primary_key=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "site_id": self.site_id,
        }


class Map(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    site_id = db.Column(db.Integer, db.ForeignKey(Site.id), nullable=False)
    nPiano = db.Column(db.Integer)

    image = db.Column(db.LargeBinary)

    sensors = db.relationship("Sensor")

    def to_dict(self):
        return {
            "id": self.id,
            "site_id": self.site_id,
            "n_piano": self.nPiano,
        }


class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    site_id = db.Column(db.Integer, db.ForeignKey(Site.id), nullable=False)
    id_cnr = db.Column(db.String(50))

    name = db.Column(db.String(50))

    loc_map = db.Column(db.Integer, db.ForeignKey(Map.id))
    loc_x = db.Column(db.Integer)
    loc_y = db.Column(db.Integer)

    enabled = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(100), nullable=False, default="ok")

    channels = db.relationship("Channel")

    def to_dict(self):
        return {
            "id": self.id,
            "site_id": self.site_id,
            "id_cnr": self.id_cnr,
            "name": self.name,
            "loc_map": self.loc_map,
            "loc_x": self.loc_x,
            "loc_y": self.loc_y,
            "enabled": self.enabled,
            "status": self.status,
        }


class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey(Sensor.id), nullable=False)
    id_cnr = db.Column(db.String(50))

    name = db.Column(db.String(50))

    measure_unit = db.Column(db.String(50))
    range_min = db.Column(db.Numeric)
    range_max = db.Column(db.Numeric)

    def to_dict(self):
        return {
            "id": self.id,
            "sensor_id": self.sensor_id,
            "id_cnr": self.id_cnr,
            "name": self.name,
            "measure_unit": self.measure_unit,
            "range_min": self.range_min,
            "range_max": self.range_max,
        }


# CNR readings table
# It stores all the channel readings
# It's in a different database (hence the bind_key)
class ReadingData(db.Model):
    __bind_key__ = 'cnr'
    __tablename__ = 't_rilevamento_dati'
    __table_args__ = (
        db.PrimaryKeyConstraint('data', 'idsito', 'idstanza', 'idstazione', 'idsensore', 'canale', 'misura'),
        db.Index('ind_t_rilevamento_centrali', 'idsito', 'idstanza', 'idstazione', 'idsensore', 'data', 'misura'),
        db.Index('index_sito_sta_ch', 'idsito', 'idstazione', 'canale'),
        {
            'mysql_engine': 'MYISAM',
            'mysql_charset': 'latin1'
        }
    )

    site_id = db.Column("idsito", db.String(50), nullable=False, default="")
    room_id = db.Column("idstanza", db.String(50), nullable=False, default="")
    station_id = db.Column("idstazione", db.String(50), nullable=False, default="")
    sensor_id = db.Column("idsensore", db.String(50), nullable=False, default="")
    channel_id = db.Column("canale", db.String(50), nullable=False, default="")
    value_min = db.Column("valore_min", DOUBLE, nullable=False, default=0)
    value_avg = db.Column("valore_med", DOUBLE)
    value_max = db.Column("valore_max", DOUBLE)
    deviation = db.Column("scarto", DOUBLE)
    date = db.Column("data", db.DateTime, nullable=False)
    error = db.Column("errore", db.String(1))
    measure_unit = db.Column("misura", db.String(50), nullable=False, default="")
    step = db.Column("step", db.Float)
