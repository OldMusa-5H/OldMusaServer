import datetime
import json
import unittest

from flask import Response

import main
import models
import alarm_controller
from rest_controller import session
from util import date_format, parse_date

root_password = main.config.setdefault("password", "password")


class FlaskrTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = "/api/"
        self.headers = {}
        self.app = main.app.test_client()

    @classmethod
    def setUpClass(cls):
        main.app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
        main.app.testing = True
        main.app.debug = True
        with main.app.app_context():
            main.setup_db()

    def open(self, method, url, content=None, args=None, throw_error=True, raw_response=False, headers=None):
        """Utility method to send a query request to the server, only empty or json response is supported"""

        if headers is None:
            headers = self.headers

        fwd_args = {
            "method": method,
            "query_string": args,
            "headers": headers
        }
        if content is not None:
            fwd_args["json"] = content

        response = self.app.open(self.prefix + url, **fwd_args)  # type: Response

        if raw_response:
            return response

        if throw_error and (response.status_code // 100) != 2:
            raise RuntimeError("Error while sending a {} to {}\n{} - {}"
                               .format(method, self.prefix + url, response.status, response.data))

        data = response.data
        if data is None or data == "":
            return data

        return json.loads(data.decode())

    def login(self, username, password):
        res = self.open("GET", "token", content={"username": username, "password": password})
        self.headers["Token"] = res["token"]

    def login_root(self):
        self.login("root", root_password)

    def test_generic(self):
        self.login_root()

        mid = self.open("POST", "site")["id"]

        response = self.open("PUT", "site/%i" % mid, content={"name": "testmuse"})
        self.assertEqual(response["id"], mid)
        self.assertEqual(response["name"], "testmuse")

        # Add sensor
        response = self.open("POST", "site/%i/sensor" % mid, content={
            "name": "testsensor",
        })

        sensor_id = response["id"]
        self.assertEqual(mid, response["site_id"])

        # Let's test some errors
        response = self.open("PUT", "sensor/%i" % sensor_id, raw_response=True)
        self.assertEqual(400, response.status_code)
        self.assertIn("No data in update", json.loads(response.data.decode())["message"])

        # Add sensor location
        response = self.open("PUT", "sensor/%i" % sensor_id, content={
            "loc_x": 1234,
            "loc_y": 5678,
        })

        self.assertEqual(1234, response["loc_x"])
        self.assertEqual(5678, response["loc_y"])

        # Test Map image data
        response = self.app.put(self.prefix + "site/%i/map" % mid, data=b"png image data", content_type="image/png", headers=self.headers)
        self.assertEqual(200, response.status_code)
        response = self.app.get(self.prefix + "site/%i/map" % mid, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual(b"png image data", response.data)

        # Add Channel
        response = self.open("POST", "sensor/%i/channel" % sensor_id, content={ "name": "testchannel" })
        ch_id = response["id"]
        self.assertEqual("testchannel", response["name"])
        self.assertEqual(sensor_id, response["sensor_id"])

        response = self.open("PUT", "channel/%i" % ch_id, content={
            "name": "pioppo",
            "measure_unit": "nonno"
        })

        self.assertEqual("pioppo", response["name"])
        self.assertEqual("nonno", response["measure_unit"])

        response = self.open("GET", "sensor/%i/channel" % sensor_id)
        self.assertEqual(len(response), 1)

        # Cleanup
        self.open("DELETE", "site/%i" % mid)

    def test_permission_view(self):
        self.login_root()

        mus1 = self.open("POST", "site")["id"]
        mus2 = self.open("POST", "site")["id"]
        mus3 = self.open("POST", "site")["id"]

        uid = self.open("POST", "user", content={"username": "paolo", "password": "123"})["id"]
        self.open("POST", "user/%i/access" % uid, content={"id": mus1})
        self.open("POST", "user/%i/access" % uid, content={"id": mus2})

        for musId in [mus1, mus2, mus3]:
            self.assertIn(musId, self.open("GET", "site"))

        self.headers = {}
        self.login("paolo", "123")

        user = self.open("GET", "user_me")
        self.assertEqual(user["username"], "paolo")
        self.assertEqual(user["permission"], "U")

        self.assertEqual(self.open("GET", "site"), [mus1, mus2])

        # The user cannot see the third site so it throws 404
        response = self.open("GET", "site/%i" % mus3, raw_response=True)
        self.assertEqual(404, response.status_code)
        self.assertIn("Cannot find site %i" % mus3, json.loads(response.data.decode())["message"])

        # Cleanup
        self.login_root()
        self.open("DELETE", "site/%i" % mus1)
        self.open("DELETE", "site/%i" % mus2)
        self.open("DELETE", "site/%i" % mus3)
        self.open("DELETE", "user/%i" % uid)

    def test_foreign_key(self):
        self.login_root()

        mid = self.open("POST", "site")["id"]

        # Add sensor
        response = self.open("POST", "site/%i/sensor" % mid)
        sid = response["id"]

        # Add channel
        self.open("POST", "sensor/%i/channel" % sid)

        # Cleanup and test for foreign constraints
        self.open("DELETE", "site/%i" % mid)

    def test_readings(self):

        models.db.create_all(bind="cnr")

        if session.query(models.ReadingData).count() > 0:
            raise unittest.SkipTest("Cnr database not empty, are you using a real database?")

        self.login_root()

        site = self.open("POST", "site", content={"name": "testsite"})["id"]

        cnr_site = site + 100000

        self.open("PUT", "site/%i" % site, content={"id_cnr": cnr_site})

        # Add sensor
        sensor = self.open("POST", "site/%i/sensor" % site, content={"name": "testsensor"})["id"]

        cnr_station = sensor + 100000

        self.open("PUT", "sensor/%i" % sensor, content={"id_cnr": cnr_station})

        # Add Channel
        channel = self.open("POST", "sensor/%i/channel" % sensor, content={"name": "testchannel"})["id"]

        cnr_channel = channel + 100000
        self.open("PUT", "channel/%i" % channel, content={"id_cnr": cnr_channel})

        test_value_count = 10

        start_date = datetime.datetime.now()
        end_date = start_date + datetime.timedelta(minutes=test_value_count)

        data = [{
            "value_min": (x * 10 + 1),
            "value_avg": (x * 10 + 2),
            "value_max": (x * 10 + 3),
            "date": (start_date + datetime.timedelta(minutes=x)),
        } for x in range(0, test_value_count)]

        mods = [
            models.ReadingData(
                site_id=cnr_site, station_id=cnr_station, channel_id=cnr_channel,
                **d
            ) for d in data
        ]

        session.add_all(mods)
        session.commit()

        def comp_data_list(a, b):
            self.assertEqual(len(a), len(b))

            for x, y in zip(a, b):
                self.assertEqual(parse_date(x["date"]), parse_date(y["date"]))
                self.assertAlmostEqual(float(x["value_min"]), float(y["value_min"]))
                self.assertAlmostEqual(float(x["value_avg"]), float(y["value_avg"]))
                self.assertAlmostEqual(float(x["value_max"]), float(y["value_max"]))

        result = self.open("GET", "channel/%i/readings" % channel, content={
            "start": start_date.strftime(date_format),
            "end": end_date.strftime(date_format),
        })
        comp_data_list(data, result)

        result = self.open("GET", "channel/%i/readings" % channel, content={
            "start": start_date.strftime(date_format),
            "end": (start_date + datetime.timedelta(minutes=5)).strftime(date_format),
        })
        comp_data_list(data[:6], result)

        result = self.open("GET", "channel/%i/readings" % channel, content={
            "start": start_date.strftime(date_format),
            "end": start_date.strftime(date_format),
        })
        comp_data_list([data[0]], result)

        for x in mods:
            session.delete(x)
        session.commit()

        self.open("DELETE", "site/%i" % site)

    def test_contacter(self):
        self.login_root()

        mus1 = self.open("POST", "site")["id"]

        user1 = self.open("POST", "user", content={"username": "user1", "password": "123"})["id"]
        user2 = self.open("POST", "user", content={"username": "user2", "password": "123"})["id"]
        user3 = self.open("POST", "user", content={"username": "user3", "password": "123"})["id"]

        self.open("POST", "user/%i/access" % user1, content={"id": mus1})
        self.open("POST", "user/%i/access" % user2, content={"id": mus1})

        self.open("PUT", "user/%i/contact/fcm/%s" % (user1, "user1_fcm1"))
        self.open("PUT", "user/%i/contact/fcm/%s" % (user1, "user1_fcm2"))
        self.open("PUT", "user/%i/contact/fcm/%s" % (user2, "user2_fcm"))
        self.open("PUT", "user/%i/contact/fcm/%s" % (user3, "user3_fcm"))

        self.assertEqual(["user1_fcm1", "user1_fcm2", "user2_fcm"], main.contacter.get_fcm_listeners(mus1))

        mus2 = self.open("POST", "site")["id"]
        self.open("POST", "user/%i/access" % user1, content={"id": mus2})
        self.open("POST", "user/%i/access" % user3, content={"id": mus2})

        self.assertEqual(["user1_fcm1", "user1_fcm2", "user3_fcm"], main.contacter.get_fcm_listeners(mus2))

        self.open("DELETE", "user/%i" % user1)
        self.open("DELETE", "user/%i" % user2)
        self.open("DELETE", "user/%i" % user3)
        self.open("DELETE", "site/%i" % mus1)
        self.open("DELETE", "site/%i" % mus2)

    def test_user_password_misc(self):
        self.login_root()

        mus1 = self.open("POST", "site")["id"]

        user1 = self.open("POST", "user", content={"username": "usre1", "password": "password11"})["id"]
        user2 = self.open("POST", "user", content={"username": "user2", "password": "password21"})["id"]

        # An admin should be able to change any user's data (both username and password)
        self.open("PUT", "user/%i" % user1, content={"username": "user1", "password": "password12"})
        # An user should NOT be able to change another user's details
        self.login("user2", "password21")
        self.open("GET", "user_me")
        response = self.open("PUT", "user/%i" % user1, content={"password": "something"}, raw_response=True)
        self.assertEqual(401, response.status_code)

        # Check token invalidation on password change
        self.open("PUT", "user/%i" % user2, content={"password": "password22"})
        self.open("GET", "user_me", throw_error=False)  # The password was updated and the token has been invalidated
        self.assertEqual(401, response.status_code)

        # Once we get use the new token we can login again
        self.login("user2", "password22")
        self.open("GET", "user_me")

        # The user should be able to change it's contacts
        self.open("PUT", "user/%i/contact/fcm/%s" % (user2, "fcm2"))
        # But it not be able to change other user's contacts
        response = self.open("PUT", "user/%i/contact/fcm/%s" % (user1, "fcm1"), raw_response=True)
        self.assertEqual(401, response.status_code)

        # Admins should always be able to change the user's personal data
        self.login_root()
        self.open("PUT", "user/%i/contact/fcm/%s" % (user1, "fcm1"))

        # Cleanup
        self.login_root()
        self.open("DELETE", "site/%i" % mus1)
        self.open("DELETE", "user/%i" % user1)
        self.open("DELETE", "user/%i" % user2)

    def test_alarm_controller(self):
        models.db.create_all(bind="cnr")

        if session.query(models.ReadingData).count() > 0:
            raise unittest.SkipTest("Cnr database not empty, are you using a real database?")

        self.login_root()

        # First Site
        site = self.open("POST", "site", content={"name": "testsite"})["id"]
        sensor = self.open("POST", "site/%i/sensor" % site, content={"name": "testsensor", "enabled": True, "id_cnr": 1111})["id"]

        # Add Channel
        channel = self.open("POST", "sensor/%i/channel" % sensor, content={"name": "testchannel"})["id"]
        cnr_channel = channel + 1000
        self.open("PUT", "channel/%i" % channel, content={
            "id_cnr": cnr_channel,
            "range_min": "100",
            "range_max": "200"
        })

        # Add Readings
        readings = [
            models.ReadingData(site_id=site, room_id="1", station_id=sensor, sensor_id=1111, channel_id=cnr_channel,
                               value_min="150", value_max="170", date=datetime.datetime(2019, 5, 2, 8)),
            models.ReadingData(site_id=site, room_id="1", station_id=sensor, sensor_id=1111, channel_id=cnr_channel,
                               value_min="50", value_max="170", date=datetime.datetime(2019, 5, 2, 9)),
            models.ReadingData(site_id=site, room_id="1", station_id=sensor, sensor_id=1111, channel_id=cnr_channel,
                               value_min="140", value_max="180", date=datetime.datetime(2019, 5, 2, 10)),
            models.ReadingData(site_id=site, room_id="1", station_id=sensor, sensor_id=1111, channel_id=cnr_channel,
                               value_min="150", value_max="250", date=datetime.datetime(2019, 5, 2, 11))
        ]
        session.add_all(readings)
        session.commit()

        # Second Site
        site2 = self.open("POST", "site", content={"name": "testsite"})["id"]
        sensor2 = self.open("POST", "site/%i/sensor" % site2, content={"name": "testsensor2", "enabled": True, "id_cnr": 2222})["id"]

        # Add Channel
        channel2 = self.open("POST", "sensor/%i/channel" % sensor2, content={"name": "testchannel2"})["id"]
        cnr_channel2 = channel2 + 1000
        self.open("PUT", "channel/%i" % channel2, content={
            "id_cnr": cnr_channel2,
            "range_min": "70",
            "range_max": "90"
        })

        # Add Readings
        readings2 = [
            models.ReadingData(site_id=site2, room_id="3", station_id=sensor2, sensor_id=2222, channel_id=cnr_channel2,
                               value_min="51", value_max="78", date=datetime.datetime(2019, 5, 2, 8)),
            models.ReadingData(site_id=site2, room_id="3", station_id=sensor2, sensor_id=2222, channel_id=cnr_channel2,
                               value_min="71", value_max="78", date=datetime.datetime(2019, 5, 2, 9)),
            models.ReadingData(site_id=site2, room_id="3", station_id=sensor2, sensor_id=2222, channel_id=cnr_channel2,
                               value_min="71", value_max="78", date=datetime.datetime(2019, 5, 2, 10)),
            models.ReadingData(site_id=site2, room_id="3", station_id=sensor2, sensor_id=2222, channel_id=cnr_channel2,
                               value_min="71", value_max="88", date=datetime.datetime(2019, 5, 2, 11)),
        ]

        session.add_all(readings2)
        session.commit()

        finder = alarm_controller.AlarmFinder()
        mmin, mmax = finder.compare_data()
        self.assertEqual(50.0, mmin[channel][0])
        self.assertEqual(51.0, mmin[channel2][0])
        self.assertEqual(250.0, mmax[channel][0])
        self.assertEqual(1, len(mmax))
        self.assertEqual(2, len(mmin))