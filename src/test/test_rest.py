import json
import unittest

from flask import Response

import main

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
        if data is None or data is "":
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

        # Check the foreign keys
        response = self.open("PUT", "sensor/%i" % sensor_id, raw_response=True, content={
            "loc_map": "10000"
        })
        self.assertEqual(404, response.status_code)
        self.assertIn("Cannot find map", json.loads(response.data.decode())["message"])

        # Add map
        map_id = self.open("POST", "site/%i/map" % mid)["id"]
        response = self.open("PUT", "sensor/%i" % sensor_id, content={
            "loc_map": map_id,
            "loc_x": 1234,
            "loc_y": 5678,
        })

        self.assertEqual(map_id, response["loc_map"])
        self.assertEqual(1234, response["loc_x"])
        self.assertEqual(5678, response["loc_y"])

        # Test Map image data
        response = self.app.put(self.prefix + "map/%i/image" % map_id, data=b"png image data", content_type="image/png", headers=self.headers)
        self.assertEqual(200, response.status_code)
        response = self.app.get(self.prefix + "map/%i/image" % map_id, headers=self.headers)
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


    def test_foreign_key(self):
        self.login_root()

        mid = self.open("POST", "site")["id"]

        # Add map
        response = self.open("POST", "site/%i/map" % mid)
        map_id = response["id"]

        # Add sensor
        response = self.open("POST", "site/%i/sensor" % mid, content={ "loc_map": map_id })
        sid = response["id"]

        # Add channel
        response = self.open("POST", "sensor/%i/channel" % sid)
        ch_id = response["id"]

        self.open("DELETE", "map/%i" % map_id)
