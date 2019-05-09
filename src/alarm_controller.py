import datetime
import os

from sqlalchemy import func, desc

import rest_controller
from models import Channel, ReadingData, Sensor


# This class warn the whole system if it find readings values out of min or max range of its own channel


class AlarmFinder:
    def __init__(self):
        self.file_path = None  # type: str
        self.last_time = None  # type: datetime.datetime

    def load_config(self, file_path):
        self.file_path = file_path

        if not os.path.isfile(self.file_path):
            # If no file is found reset last_time
            self.last_time = datetime.datetime.min
            return

        with open(self.file_path, "rt") as fp:
            date = fp.read().split(" ")
            self.last_time = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), int(date[3]), int(date[4]),
                                               int(date[5]), int(date[6]))

    def ultimate_time(self):
        """Returns the date and hour of the last reading in the CNR database."""

        query = rest_controller.session.query(ReadingData.date).order_by(desc(ReadingData.date)).first().all()[0]
        return query

    def control_data(self):
        """
        Returns two lists in which there is a record for each channel with its minimum and maximum value.
        It is collected only records written after the last control and it is written this datetime values on a file.
        """

        query_min = rest_controller.session.query(
            func.min(ReadingData.value_min), ReadingData.channel_id, ReadingData.station_id,
            ReadingData.sensor_id, ReadingData.room_id, ReadingData.site_id, ReadingData.date). \
            group_by(ReadingData.channel_id). \
            group_by(ReadingData.station_id). \
            group_by(ReadingData.sensor_id). \
            group_by(ReadingData.room_id). \
            group_by(ReadingData.site_id).\
            filter(ReadingData.date > self.last_time).all()

        query_max = rest_controller.session.query(
            func.max(ReadingData.value_max), ReadingData.channel_id, ReadingData.station_id,
            ReadingData.sensor_id, ReadingData.room_id, ReadingData.site_id, ReadingData.date). \
            group_by(ReadingData.channel_id). \
            group_by(ReadingData.station_id). \
            group_by(ReadingData.sensor_id). \
            group_by(ReadingData.room_id). \
            group_by(ReadingData.site_id). \
            filter(ReadingData.date > self.last_time).all()

        self.last_time = datetime.datetime.now()
        time_string = str(self.last_time.year) + " " + str(self.last_time.month) + " " + str(self.last_time.day) + \
                      " " + str(self.last_time.hour) + " " + str(self.last_time.minute) + \
                      " " + str(self.last_time.second) + " " + str(self.last_time.microsecond)

        if self.file_path is not None:
            with open(self.file_path, "w") as fp:
                fp.write(time_string)

        return query_min, query_max

    def compare_data(self):
        """
        Returns two dictionaries with the value and the date of every record containing an alarming measure.
        It is defined as alarming value a reading value which is under its channel minimum range or over
        its channel maximum range.
        """

        alarm_max = {}
        alarm_min = {}
        query_min, query_max = self.control_data()
        channels = rest_controller.session.\
            query(Channel.id_cnr.label("channel_cnr"), Channel.id, Channel.range_min, Channel.range_max, Sensor.id_cnr.label("sensor_cnr")).\
            filter(Sensor.id == Channel.sensor_id).\
            filter(Sensor.enabled == True).all()

        for record in query_min:
            for ch in channels:
                if ch.channel_cnr == record.channel_id and ch.sensor_cnr == record.sensor_id:
                    if record[0] <= ch.range_min:
                        alarm_min[ch.id] = [record[0], record.date]

        for record in query_max:
            for ch in channels:
                if ch.channel_cnr == record.channel_id and ch.sensor_cnr == record.sensor_id:
                    if record[0] >= ch.range_max:
                        alarm_max[ch.id] = [record[0], record.date]

        if len(alarm_max) == 0 and len(alarm_min) == 0:
            return None
        return alarm_min, alarm_max

