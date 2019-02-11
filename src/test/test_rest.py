import json
import unittest

from flask import Response

import main


class FlaskrTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = "/api/"

    def setUp(self):
        main.app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///:memory:"
        main.app.testing = True
        main.app.debug = True
        self.app = main.app.test_client()
        with main.app.app_context():
            main.setup_db()

    def open(self, method, url, content=None, args=None, throw_error=True, raw_response=False):
        """Utility method to send a query request to the server, only empty or json response is supported"""
        fwd_args = {
            "method": method,
            "query_string": args,
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

        return json.loads(data)

    def test_generic(self):
        mid = self.open("POST", "museum")["id"]

        response = self.open("PUT", "museum/%i" % mid, content={"name": "testmuse"})
        self.assertEqual(response["id"], mid)
        self.assertEqual(response["name"], "testmuse")

        # Add Room
        room_id = self.open("POST", "museum/%i/room" % mid, args={"name": "testroom"})["id"]

        # Add sensor
        response = self.open("POST", "museum/%i/sensor" % mid, content={
            "name": "testsensor",
            "room": room_id,
        })

        sensor_id = response["id"]
        self.assertEqual(mid, response["museum_id"])
        self.assertEqual(room_id, response["room"])

        # Let's test some errors
        response = self.open("PUT", "sensor/%i" % sensor_id, raw_response=True)
        self.assertEqual(400, response.status_code)
        self.assertIn("No data in update", json.loads(response.data)["message"])

        # Check the foreign keys
        response = self.open("PUT", "sensor/%i" % sensor_id, raw_response=True, content={
            "loc_map": "10000"
        })
        self.assertEqual(404, response.status_code)
        self.assertIn("map not found", json.loads(response.data)["message"])

        # Add map
        map_id = self.open("POST", "museum/%i/map" % mid)["id"]
        response = self.open("PUT", "sensor/%i" % sensor_id, content={
            "loc_map": map_id,
            "loc_x": 1234,
            "loc_y": 5678,
        })

        self.assertEqual(map_id, response["loc_map"])
        self.assertEqual(1234, response["loc_x"])
        self.assertEqual(5678, response["loc_y"])

        # Test Map image data
        response = self.app.put(self.prefix + "map/%i/image" % map_id, data=b"png image data", content_type="image/png")
        self.assertEqual(200, response.status_code)
        response = self.app.get(self.prefix + "map/%i/image" % map_id)
        self.assertEqual(200, response.status_code)
        self.assertEqual(b"png image data", response.data)


if __name__ == '__main__':
    unittest.main()
