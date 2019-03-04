from flask_sqlalchemy import SQLAlchemy


# Here's the sql representation of the data we need to store
# don't put any logic in this file, it should only contain sql definitions
# If you don't understand any of this go read the sqlalchemy documentation

db = SQLAlchemy()


class Museum(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)

    maps = db.relationship("Map")
    rooms = db.relationship("Room")
    sensors = db.relationship("Sensor")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }


class Map(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    museum_id = db.Column(db.Integer, db.ForeignKey(Museum.id), nullable=False)

    image = db.Column(db.LargeBinary)

    sensors = db.relationship("Sensor")

    def to_dict(self):
        return {
            "id": self.id,
            "museum_id": self.museum_id,
        }


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    museum_id = db.Column(db.Integer, db.ForeignKey(Museum.id), nullable=False)

    name = db.Column(db.String)

    sensors = db.relationship("Sensor")

    def to_dict(self):
        return {
            "id": self.id,
            "museum_id": self.museum_id,
            "name": self.name,
        }


class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    museum_id = db.Column(db.Integer, db.ForeignKey(Museum.id), nullable=False)

    name = db.Column(db.String)
    room = db.Column(db.Integer, db.ForeignKey(Room.id))

    range_min = db.Column(db.Numeric)
    range_max = db.Column(db.Numeric)

    loc_map = db.Column(db.Integer, db.ForeignKey(Map.id))
    loc_x = db.Column(db.Integer)
    loc_y = db.Column(db.Integer)

    enabled = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String, nullable=False, default="ok")

    def to_dict(self):
        return {
            "id": self.id,
            "museum_id": self.museum_id,
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
