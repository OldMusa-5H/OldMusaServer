import io
from typing import TypeVar, Type

from flask import send_file, request
from flask_restful import Api, Resource
from flask_restful.reqparse import RequestParser
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, NotFound

from models import Museum, Map, Room, Sensor, db

# sqlalchemy session used to make query and updates
session = db.session  # type: Session


# TODO: user auth (https://blog.miguelgrinberg.com/post/restful-authentication-with-flask)
# TODO: permissions

api = Api()
api.prefix = "/api"


# ---------------- Utility methods ----------------


# Get method that throws 404 when
# (pidgeon meme) is this strong generic typing?
T = TypeVar('T')


def rest_get(clazz: Type[T], res_id: int) -> T:
    museum = session.query(clazz).filter(clazz.id == res_id).first()
    if museum is None:
        raise BadRequest('Cannot find ' + clazz.name + str(res_id))
    return museum


def rest_create(clazz, args):
    # Manually check foreign keys
    for (key, val) in args.items():
        if val is None:
            continue
        attr = getattr(clazz, key)
        for fk in attr.foreign_keys:
            fok = fk  # type: ForeignKey
            table = fok.column.table  # type: Table
            if session.query(fok.column).filter(table.c["id"] == val).count() != 1:
                print("Cannot find room: '%s'" % val)
                raise NotFound(table.name + " not found")

    obj = clazz(**args)
    session.add(obj)
    session.commit()
    return obj


def rest_update(id, parser: RequestParser, res_class):
    args = parser.parse_args(strict=True)

    update = {}

    for (key, val) in args.items():
        if val is None: continue
        attr = getattr(res_class, key)  # type: Column

        # Manually check foreign keys
        for fk in attr.foreign_keys:
            fok = fk  # type: ForeignKey
            table = fok.column.table  # type: Table
            if session.query(fok.column).filter(table.c["id"] == val).count() != 1:
                raise NotFound(table.name + " not found")

        update[attr] = val

    if not update:
        raise BadRequest('No data in update (did you forget to send a json?)')

    res = session.query(res_class) \
        .filter(res_class.id == id) \
        .update(update)

    if res == 0:
        raise NotFound("Cannot find {} with id {}".format(res_class.__tablename__, id))

    session.commit()

    return rest_get(res_class, id).to_dict()


# ---------------- Parsers initialization ----------------

# General parser that parses only the id
id_parser = RequestParser()
id_parser.add_argument("id", type=int)

# Museum
museum_parser = RequestParser()
museum_parser.add_argument("name")

# Sensor
sensor_parser = RequestParser()
sensor_parser.add_argument("name", type=str)
sensor_parser.add_argument("room", type=str)

sensor_parser.add_argument("range_min", type=int)
sensor_parser.add_argument("range_max", type=int)

sensor_parser.add_argument("loc_map", type=str)
sensor_parser.add_argument("loc_x", type=int)
sensor_parser.add_argument("loc_y", type=int)

sensor_parser.add_argument("enabled", type=bool)

# Room
room_parser = RequestParser()
room_parser.add_argument("name", type=str)


# ---------------- Resource definitions ----------------

@api.resource("/museum")
class RMuseumList(Resource):
    def get(self):
        return [x.to_dict() for x in db.session.query(Museum).all()]

    def post(self):
        args = museum_parser.parse_args(strict=True)
        museum = rest_create(Museum, args)
        return museum.to_dict(), 201

    def delete(self):
        args = id_parser.parse_args(strict=True)
        session.query(Museum).filter(Museum.id == args["id"]).delete()
        session.commit()
        return None, 202


@api.resource("/museum/<mid>")
class RMuseum(Resource):
    def get(self, mid):
        return rest_get(Museum, mid).to_dict()

    def put(self, mid):
        return rest_update(mid, museum_parser, Museum)

    def delete(self, mid):
        deleted = session.query(Museum).filter(Museum.id == mid).delete()
        if deleted == 0:
            raise BadRequest('Cannot find museum' + str(mid))
        session.commit()
        return None, 202


@api.resource("/museum/<mid>/sensor")
class RMuseumSensors(Resource):
    def get(self, mid):
        ids = session.query(Sensor)\
                     .filter(Sensor.museum_id == mid)\
                     .with_entities(Sensor.id)\
                     .all()
        return [x[0] for x in ids]

    def post(self, mid):
        sensor = RSensor.create_from_req(mid)
        return sensor.to_dict(), 201


@api.resource("/museum/<mid>/map")
class RMuseumMaps(Resource):
    def get(self, mid):
        ids = session.query(Map)\
                     .filter(Map.museum_id == mid)\
                     .with_entities(Map.id)\
                     .all()
        return [x[0] for x in ids]

    def post(self, mid):
        map = Map(museum_id=mid)
        session.add(map)
        session.commit()
        return map.to_dict(), 201


@api.resource("/museum/<mid>/room")
class RMuseumRooms(Resource):
    def get(self, mid):
        ids = session.query(Room)\
                     .filter(Room.museum_id == mid)\
                     .with_entities(Room.id)\
                     .all()
        return [x[0] for x in ids]

    def post(self, mid):
        args = room_parser.parse_args(strict=True)
        args["museum_id"] = mid
        return rest_create(Room, args).to_dict(), 201


@api.resource("/sensor/<sid>")
class RSensor(Resource):
    def get(self, sid):
        return rest_get(Sensor, sid).to_dict()

    def put(self, sid):
        return rest_update(sid, sensor_parser, Sensor)

    def delete(self, sid):
        deleted = session.query(Sensor).filter(Sensor.id == sid).delete()
        if deleted == 0:
            raise NotFound('Cannot find sensor' + str(sid))
        session.commit()
        return None, 202

    @staticmethod
    def create_from_req(museum_id, req=None):
        args = sensor_parser.parse_args(strict=True, req=req)
        args["museum_id"] = museum_id
        return rest_create(Sensor, args)


@api.resource("/map/<mid>")
class RMap(Resource):
    def delete(self, mid):
        deleted = session.query(Map).filter(Map.id == mid).delete()
        if deleted == 0:
            raise NotFound('Cannot find map' + str(mid))
        session.commit()
        return None, 202

    @staticmethod
    def create_from_req(self, museum_id, req=None):
        args = sensor_parser.parse_args(strict=True, req=req)
        args["museum_id"] = museum_id
        return rest_create(Map, args)


@api.resource("/map/<mid>/image")
class RMapImage(Resource):
    def get(self, mid):
        map = rest_get(Map, mid)

        if map.image is None:
            raise NotFound("Map image not found")

        return send_file(io.BytesIO(map.image),
                         attachment_filename='map.png',
                         mimetype='image/png')

    def put(self, mid):
        if request.content_type != 'image/png':
            raise BadRequest("Image must be 'image/png'")
        # TODO: check request.content_length
        rest_get(Map, mid).image = request.get_data()
        session.commit()


@api.resource("/map/<mid>/sensors")
class RMapSensors(Resource):
    def get(self, mid):
        # TODO: get only ids
        return [x.id for x in rest_get(Map, mid).sensors]


@api.resource("/room/<rid>")
class RRoom(Resource):
    def get(self, rid):
        return rest_get(Room, rid).to_dict()

    def put(self, rid):
        return rest_update(rid, room_parser, Room)

    def delete(self, rid):
        session.delete(rest_get(Room, rid))
        return None, 202

    @staticmethod
    def create_from_req(self, museum_id, req=None):
        args = room_parser.parse_args(strict=True, req=req)
        args["museum_id"] = museum_id
        return rest_create(Room, args)

