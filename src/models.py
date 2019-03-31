from flask_sqlalchemy import SQLAlchemy


# Here's the sql representation of the data we need to store
# don't put any logic in this file, it should only contain sql definitions
# If you don't understand any of this go read the sqlalchemy documentation
from sqlalchemy.dialects.mysql import DOUBLE

db = SQLAlchemy()


class Museum(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)
    id_cnr = db.Column(db.String)

    maps = db.relationship("Map")
    sensors = db.relationship("Sensor")
    channels = db.relationship("Channel")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "id_cnr": self.id_cnr,
        }


class Map(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    museum_id = db.Column(db.Integer, db.ForeignKey(Museum.id), nullable=False)
    nPiano = db.Column(db.Integer)

    image = db.Column(db.LargeBinary)

    sensors = db.relationship("Sensor")

    def to_dict(self):
        return {
            "id": self.id,
            "museum_id": self.museum_id,
            "n_piano": self.nPiano,
        }


class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    museum_id = db.Column(db.Integer, db.ForeignKey(Museum.id), nullable=False)
    id_cnr = db.Column(db.String)

    name = db.Column(db.String)

    loc_map = db.Column(db.Integer, db.ForeignKey(Map.id))
    loc_x = db.Column(db.Integer)
    loc_y = db.Column(db.Integer)

    enabled = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String, nullable=False, default="ok")

    channels = db.relationship("Channel")

    def to_dict(self):
        return {
            "id": self.id,
            "museum_id": self.museum_id,
            "id_cnr": self.id_cnr,
            "name": self.name,
            "room": self.room,
            "range_min": self.range_min,
            "range_max": self.range_max,
            "loc_map": self.loc_map,
            "loc_x": self.loc_x,
            "loc_y": self.loc_y,
            "enabled": self.enabled,
            "status": self.status,
        }


class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey(Sensor.id), nullable=False)
    museum_id = db.Column(db.Integer, db.ForeignKey(Museum.id), nullable=False)
    id_cnr = db.Column(db.String)

    name = db.Column(db.String)

    measure_unit = db.Column(db.String)
    range_min = db.Column(db.Numeric)
    range_max = db.Column(db.Numeric)

    def to_dict(self):
        return {
            "id": self.id,
            "sensor_id": self.sensor_id,
            "museum_id": self.museum_id,
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
