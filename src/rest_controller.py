import io
from datetime import datetime
from functools import wraps
from typing import TypeVar, Type

from flask import send_file, request, g
from flask_restful import Api, Resource
from flask_restful.reqparse import RequestParser
from itsdangerous import TimedJSONWebSignatureSerializer, SignatureExpired, BadSignature
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Session
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from util import clean_dict, parse_date, date_format
from models import Site, Map, Channel, Sensor, db, User, UserAccess, ReadingData

# The secrets module was added only in python 3.6
# If it isn't present we can use urandom from the os module
try:
    from secrets import token_hex
except ImportError:
    from os import urandom

    def token_hex(nbytes=None):
        return urandom(nbytes).hex()

# This is the rest controller, it controls every query/update done trough rest (everything in the /api/* site section)

# sqlalchemy session used to make query and updates
session = db.session  # type: Session


api = Api()
api.prefix = "/api"


secret_key = token_hex(32)
passw_serializer = TimedJSONWebSignatureSerializer(secret_key, expires_in=600)


# ---------------- Utility methods ----------------
# Utility methods used to automate the creation and query of resources
# Every GET, POST and PUT can use an utility method that discovers which
# field to use/update, also checking foreign key constraints (that some databases
# could not check).
# These methods already handle cases such as resource not found and missing field
# and handle them accordingly (ex: source not found -> throw 404)


# Get method that throws 404 when
# (pidgeon meme) is this strong generic typing?
T = TypeVar('T')


def rest_get(clazz: Type[T], res_id: int) -> T:
    """
    Gets the resource using its id, throws 404 if it does not exist.

    This method verifies also that the user can view the site (only if the resource has an attribute called site_id)
    If the user cannot access the site the

    :param clazz: The resource model definition
    :param res_id: the resource id
    :return: The resource found
    """
    resource = session.query(clazz).filter(clazz.id == res_id).first()
    if resource is None or (hasattr(resource, "site_id") and verify_site_visible(resource.site_id)):
        raise NotFound("Cannot find %s '%s'" % (clazz.name, str(res_id)))
    return resource


def rest_create(clazz: Type[T], args: dict) -> T:
    """
    Creates a resource using it's model definition and the arguments expressed as field: value.
    The arguments must already be filtered using something as a RequestParser to limit external attacks.
    This method should manually check foreign keys, throwing the appropriate error if a constraint is violated.

    :param clazz: The resource model definition
    :param args: Arguments used to initialize the resource fields
    :return: The resource just created
    """

    # Manually check foreign keys
    for (key, val) in args.items():
        if val is None:
            continue
        attr = getattr(clazz, key)
        for fk in attr.foreign_keys:
            fok = fk  # type: ForeignKey
            table = fok.column.table  # type: Table
            if session.query(fok.column).filter(table.c["id"] == val).count() != 1:
                raise NotFound("Cannot find %s: '%s'" % (table.name, val))

    obj = clazz(**args)
    session.add(obj)
    session.commit()
    return obj


def rest_update(res_id, args: dict, res_class: Type[T], empty_throw=True, commit=True) -> T:
    """
    Updates a resource using it's model definition and the arguments expressed as field: value.
    The arguments must already be filtered using something as a RequestParser to limit external attacks
    (ex: no-one should be able to change the resource id).
    This method should manually check foreign keys, throwing the appropriate error if a constraint is violated.

    :param res_id: Id of the resource to update
    :param args: The filtered request parameters
    :param res_class: Model definition of the resouce to update
    :param empty_throw: Raises an exception if no data to update is found
    :return: A dict representing the updated object
    """

    update = {}

    for (key, val) in args.items():
        if val is None: continue
        attr = getattr(res_class, key)  # type: Column

        # Manually check foreign keys
        for fk in attr.foreign_keys:
            fok = fk  # type: ForeignKey
            table = fok.column.table  # type: Table
            if session.query(fok.column).filter(table.c["id"] == val).count() != 1:
                raise NotFound("Cannot find %s: '%s'" % (table.name, val))

        update[attr] = val

    if not update and empty_throw:
        raise BadRequest('No data in update (did you forget to send a json?)')
    else:
        res = session.query(res_class) \
            .filter(res_class.id == res_id) \
            .update(update)

        if res == 0:
            raise NotFound("Cannot find {} with id {}".format(res_class.__tablename__, res_id))

        if commit:
            session.commit()

    return rest_get(res_class, res_id)


# ---------------- Auth methods ----------------

def check_auth_token(token):
    """Check whether the token is valid"""

    if token is None:
        return None

    try:
        data = passw_serializer.loads(token)
    except (SignatureExpired, BadSignature):
        return None

    # The token was generated by the server (we are the only ones with the secret key that
    # is required to encode and decode the token) so we can confirm the authentication
    # The serializer also checks whether the timestamp in the token is expired

    # If the user is deleted return None
    return session.query(User).filter(User.id == data["id"]).first()


def verify_password(req=None):
    """Check whether the token is correct or if the username/password is valid"""
    if req is None:
        req = request

    user = check_auth_token(req.headers.get("Token"))

    if user is None:
        return False

    g.user = user
    return True


def generate_auth_token(user_id: str, expiration: int = 600) -> bytes:
    passw_serializer.expires_in = expiration
    return passw_serializer.dumps({"id": user_id})


def login_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if verify_password():
            return f(*args, **kwargs)
        raise Unauthorized("Invalid token")

    return decorator


def admin_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if g.user.permission != "A":
            raise Unauthorized("Insufficient permission")

        return f(*args, **kwargs)

    return login_required(decorator)


def check_site_visible(site_id) -> bool:
    """Check if the user can view the site"""
    if g.user.permission == "A":
        return True  # User has admin access
    count = session.query(UserAccess)\
                   .filter(UserAccess.user_id == g.user.id, UserAccess.site_id == site_id)\
                   .count()
    return count != 0


def verify_site_visible(site_id):
    """Verify that the current user can access the database, throw a NotFound (404) exception otherwise"""

    if not check_site_visible(site_id):
        # User cannot see the site (he doesn't know that it exists)
        raise NotFound("Cannot find site %s" % site_id)


# ---------------- Parsers initialization ----------------
# Parser are used to filter parameters passed to the rest links
# A request is valid only if every argument passed exists in the parser
# and if it's type corresponds to the one specified in the parser.
# When no type is specified the argument's type is a string (anything).
# If a request doesn't respect the parser validation it is discarded (throws a 4XX http error)

# General parser that parses only the id
id_parser = RequestParser()
id_parser.add_argument("id", type=int, required=True)


# Login
login_parser = RequestParser()
login_parser.add_argument("username", type=str)
login_parser.add_argument("password", type=str)

# User
user_parser = RequestParser()
user_parser.add_argument("username", type=str)
user_parser.add_argument("password", type=str)
user_parser.add_argument("permission", type=str)

# Site
site_parser = RequestParser()
site_parser.add_argument("name", type=str)
site_parser.add_argument("id_cnr", type=str)

# Sensor
sensor_parser = RequestParser()
sensor_parser.add_argument("id_cnr", type=str)
sensor_parser.add_argument("name", type=str)

sensor_parser.add_argument("loc_map", type=str)
sensor_parser.add_argument("loc_x", type=int)
sensor_parser.add_argument("loc_y", type=int)

sensor_parser.add_argument("enabled", type=bool)

# Channel
channel_parser = RequestParser()
channel_parser.add_argument("id_cnr", type=str)

channel_parser.add_argument("name", type=str)

channel_parser.add_argument("measure_unit", type=str)
channel_parser.add_argument("range_min", type=int)
channel_parser.add_argument("range_max", type=int)


# ---------------- Resource definitions ----------------
# REST resource definition
# They control the access to the REST API, defining the logic that sits behind the site API entry-point
# Every call should check for: authorization, database stability, parameter validity, resource existence...
# throwing the appropriate error every time one of those layers is broken.
# Be aware that this is the public API that every frontend will use,
# try to restrict access and prevent bugs that might lead to attacks by hackers

@api.resource("/token")
class Token(Resource):
    def get(self):
        # Check username and password
        data = login_parser.parse_args(strict=True)

        # Try to authenticate with user and password

        user = session.query(User).filter(User.username == data["username"]).first()

        if user is None or not user.verify_password(data["password"]):
            raise NotFound("Wrong username or password")

        duration = 600  # in seconds
        g.user = user
        token = generate_auth_token(user.id, duration)
        return {
            "token": token.decode("ascii"),
            "duration": duration
        }


@api.resource("/user_me")
class RUserMe(Resource):
    @login_required
    def get(self):
        return g.user.to_dict()


@api.resource("/user")
class RUserList(Resource):
    @admin_required
    def get(self):
        return [x.id for x in db.session.query(User).all()]

    @admin_required
    def post(self):
        args = user_parser.parse_args(strict=True)
        passw = args.get("password")

        if passw is None or passw is "":
            raise NotFound("Password not found")

        if "username" not in args:
            raise NotFound("Username not found")

        del args["password"]

        if session.query(User).filter(User.username == args["username"]).count() == 1:
            raise NotFound("Username already in use")

        user = rest_create(User, args)

        user.hash_password(passw)

        session.commit()
        return clean_dict(user.to_dict()), 201


@api.resource("/user/<uid>")
class RUser(Resource):
    @admin_required
    def get(self, uid):
        return clean_dict(rest_get(User, uid).to_dict())

    @admin_required
    def put(self, uid):
        args = user_parser.parse_args(strict=True)
        passw = args["password"]
        del args["password"]
        user = rest_update(uid, args, User, empty_throw=passw is not None, commit=False)  # type: User

        if passw is not None:
            user.hash_password(passw)

        session.commit()
        return clean_dict(user.to_dict())

    @admin_required
    def delete(self, uid):
        deleted = session.query(User).filter(User.id == uid).delete()
        if deleted == 0:
            raise BadRequest('Cannot find user ' + str(uid))
        session.commit()
        return None, 202


@api.resource("/user/<uid>/access")
class RUserAccess(Resource):
    @admin_required
    def get(self, uid):
        return [x.id for x in rest_get(User, uid).sites]

    @admin_required
    def post(self, uid):
        args = id_parser.parse_args(strict=True)

        session.add(UserAccess(user_id=uid, site_id=args["id"]))
        session.commit()


@api.resource("/user/<uid>/access/<aid>")
class RUserAccessEntry(Resource):
    @admin_required
    def delete(self, uid, mid):
        deleted = session.query(UserAccess).filter(UserAccess.user_id == uid, UserAccess.site_id == mid).delete()
        if deleted == 0:
            raise BadRequest('Cannot find entry ' + str((uid, mid)))
        session.commit()
        return None, 202


@api.resource("/site")
class RSiteList(Resource):
    @login_required
    def get(self):
        if g.user.permission == "A":
            # Admins can see every site
            sites = db.session.query(Site).all()
        else:
            sites = g.user.sites

        return [x.id for x in sites]

    @admin_required
    def post(self):
        args = site_parser.parse_args(strict=True)
        site = rest_create(Site, args)
        return clean_dict(site.to_dict()), 201

    @admin_required
    def delete(self):
        args = id_parser.parse_args(strict=True)

        session.query(Site).filter(Site.id == args["id"]).delete()
        session.commit()
        return None, 202


@api.resource("/site/<mid>")
class RSite(Resource):
    @login_required
    def get(self, mid):
        verify_site_visible(mid)
        return clean_dict(rest_get(Site, mid).to_dict())

    @admin_required
    def put(self, mid):
        return clean_dict(rest_update(mid, site_parser.parse_args(strict=True), Site).to_dict())

    @admin_required
    def delete(self, mid):
        deleted = session.query(Site).filter(Site.id == mid).delete()
        if deleted == 0:
            raise BadRequest('Cannot find site' + str(mid))
        session.commit()
        return None, 202


@api.resource("/site/<mid>/sensor")
class RSiteSensors(Resource):
    @login_required
    def get(self, mid):
        verify_site_visible(mid)

        ids = session.query(Sensor)\
                     .filter(Sensor.site_id == mid)\
                     .with_entities(Sensor.id)\
                     .all()
        return [x[0] for x in ids]

    @admin_required
    def post(self, mid):
        sensor = RSensor.create_from_req(mid)
        return clean_dict(sensor.to_dict()), 201


@api.resource("/site/<mid>/map")
class RSiteMaps(Resource):
    @login_required
    def get(self, mid):
        verify_site_visible(mid)

        ids = session.query(Map)\
                     .filter(Map.site_id == mid)\
                     .with_entities(Map.id)\
                     .all()
        return [x[0] for x in ids]

    @admin_required
    def post(self, mid):
        map = Map(site_id=mid)
        session.add(map)
        session.commit()
        return clean_dict(map.to_dict()), 201


@api.resource("/sensor/<sid>/channel")
class RSiteChannels(Resource):
    @login_required
    def get(self, sid):
        ids = session.query(Channel)\
                     .filter(Channel.sensor_id == sid)\
                     .with_entities(Channel.id)\
                     .all()
        return [x[0] for x in ids]

    @admin_required
    def post(self, sid):
        args = channel_parser.parse_args(strict=True)
        args["sensor_id"] = sid
        return clean_dict(rest_create(Channel, args).to_dict()), 201


@api.resource("/sensor/<sid>")
class RSensor(Resource):
    @login_required
    def get(self, sid):
        # rest_get verifies that the site is visible from the user
        return clean_dict(rest_get(Sensor, sid).to_dict())

    @admin_required
    def put(self, sid):
        return clean_dict(rest_update(sid, sensor_parser.parse_args(strict=True), Sensor).to_dict())

    @admin_required
    def delete(self, sid):
        deleted = session.query(Sensor).filter(Sensor.id == sid).delete()
        if deleted == 0:
            raise NotFound('Cannot find sensor' + str(sid))
        session.commit()
        return None, 202

    @staticmethod
    def create_from_req(site_id, req=None):
        args = sensor_parser.parse_args(strict=True, req=req)
        args["site_id"] = site_id
        return rest_create(Sensor, args)


@api.resource("/map/<mid>")
class RMap(Resource):
    @login_required
    def get(self, mid):
        # rest_get verifies that the site is visible from the user
        return clean_dict(rest_get(Map, mid).to_dict())

    @admin_required
    def delete(self, mid):
        deleted = session.query(Map).filter(Map.id == mid).delete()
        if deleted == 0:
            raise NotFound('Cannot find map' + str(mid))
        session.commit()
        return None, 202

    @staticmethod
    def create_from_req(self, site_id, req=None):
        args = sensor_parser.parse_args(strict=True, req=req)
        args["site_id"] = site_id
        return rest_create(Map, args)


@api.resource("/map/<mid>/image")
class RMapImage(Resource):
    @login_required
    def get(self, mid):
        # rest_get verifies that the site is visible from the user
        map = rest_get(Map, mid)

        if map.image is None:
            raise NotFound("Map image not found")

        return send_file(io.BytesIO(map.image),
                         attachment_filename='map.png',
                         mimetype='image/png')

    @admin_required
    def put(self, mid):
        if request.content_type != 'image/png':
            raise BadRequest("Image must be 'image/png'")
        # TODO: check request.content_length
        rest_get(Map, mid).image = request.get_data()
        session.commit()


@api.resource("/map/<mid>/sensors")
class RMapSensors(Resource):
    @login_required
    def get(self, mid):
        # rest_get verifies that the site is visible from the user
        return [x.id for x in rest_get(Map, mid).sensors]


@api.resource("/channel/<cid>")
class RChannel(Resource):
    @login_required
    def get(self, cid):
        channel = rest_get(Channel, cid)
        rest_get(Sensor, channel.sensor_id)  # Check if museum visible (performed automatically when site_id is present)

        return clean_dict(channel.to_dict())

    @admin_required
    def put(self, cid):
        return clean_dict(rest_update(cid, channel_parser.parse_args(strict=True), Channel).to_dict())

    @admin_required
    def delete(self, cid):
        session.delete(rest_get(Channel, cid))
        session.commit()
        return None, 202

    @staticmethod
    def create_from_req(self, sensor_id, req=None):
        args = channel_parser.parse_args(strict=True, req=req)
        args["sensor_id"] = sensor_id
        return rest_create(Channel, args)


@api.resource("/channel/<cid>/readings")
class RChannelData(Resource):
    def __init__(self):
        self.request_parser = RequestParser()
        self.request_parser.add_argument("start", type=parse_date, required=True, nullable=False)
        self.request_parser.add_argument("end", type=parse_date, required=True, nullable=False)
        self.request_parser.add_argument("precision", choices=["atomic"], default="atomic")

    def get_atomic(self, site_id: int, station_id: int, channel_id: int, start: datetime, end: datetime):
        data = session.query(ReadingData).filter(
            ReadingData.site_id == site_id,
            ReadingData.station_id == station_id,
            ReadingData.channel_id == channel_id,
            ReadingData.date >= start,
            ReadingData.date <= end
        ).all()

        return [
            clean_dict({
                "date": x.date.strftime(date_format),
                "value_min": str(x.value_min),
                "value_avg": str(x.value_avg),
                "value_max": str(x.value_max),
                "deviation": str(x.deviation),
                "error": x.error,
            }) for x in data
        ]

    @login_required
    def get(self, cid):
        args = self.request_parser.parse_args(strict=True)
        channel = rest_get(Channel, cid)
        sensor = rest_get(Sensor, channel.sensor_id)
        site = rest_get(Site, sensor.site_id)
        start = args["start"]
        end = args["end"]
        precision = args["precision"]

        if precision is "atomic":
            return self.get_atomic(site.id_cnr, sensor.id_cnr, channel.id_cnr, start, end)
        else:
            raise "Unkown precision " + precision


@api.resource("/sensor/<sid>/channels")
class RSensorChannels(Resource):
    @login_required
    def get(self, sid):
        # TODO: get only ids
        return [x.id for x in rest_get(Sensor, sid).channels]
