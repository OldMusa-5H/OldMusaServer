import datetime
from typing import List, Dict

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from contact import Contacter
from models import Channel, ReadingData, Sensor, Site

from util.db import session_scope
from util.timer import RepeatingTimer
import logging

from pathlib import Path


class AlarmedChannelData:
    def __init__(self, site_id, sensor_id, channel_id,
                 cnr_site_id, cnr_sensor_id, cnr_channel_id,
                 range_min, range_max):

        self.site_id = site_id
        self.sensor_id = sensor_id
        self.channel_id = channel_id

        # cnr id
        self.cnr_site_id = cnr_site_id
        self.cnr_sensor_id = cnr_sensor_id
        self.cnr_channel_id = cnr_channel_id

        # alarm ranges
        self.range_min = range_min
        self.range_max = range_max

    def __repr__(self):
        return str(self.__dict__)


# This checks if there are any reading values out of min or max range of its own channel
class AlarmFinder:
    def __init__(self):
        self.file_path = None  # type: Path
        self.last_time = None  # type: datetime.datetime

    def load_config(self, file_path):
        self.file_path = Path(file_path)

        self.file_path.parent.mkdir(exist_ok=True)

        if not self.file_path.is_file():
            # If no file is found reset last_time
            self.last_time = datetime.datetime.min
            return

        with open(self.file_path, "rt") as fp:
            date = fp.read().split(" ")
            self.last_time = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), int(date[3]), int(date[4]),
                                               int(date[5]), int(date[6]))

    def ultimate_time(self, session):
        """Returns the date and hour of the last reading in the CNR database."""

        query = session.query(ReadingData.date).order_by(desc(ReadingData.date)).first().all()[0]
        return query

    def control_data(self, session):
        """
        Returns two lists in which there is a record for each channel with its minimum and maximum value.
        It is collected only records written after the last control and it is written this datetime values on a file.
        """

        logging.debug(f"Checking after {self.last_time}")

        query_min = session.query(
            func.min(ReadingData.value_min), ReadingData.channel_id, ReadingData.station_id,
            ReadingData.sensor_id, ReadingData.room_id, ReadingData.site_id, ReadingData.date). \
            group_by(ReadingData.channel_id). \
            group_by(ReadingData.station_id). \
            group_by(ReadingData.sensor_id). \
            group_by(ReadingData.room_id). \
            group_by(ReadingData.site_id).\
            filter(ReadingData.date > self.last_time).all()

        query_max = session.query(
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
            self.file_path.parent.mkdir(exist_ok=True)
            self.file_path.write_text(time_string)

        return query_min, query_max

    def compare_data(self, session: Session):
        """
        Returns two dictionaries with the value and the date of every record containing an alarming measure.
        It is defined as alarming value a reading value which is under its channel minimum range or over
        its channel maximum range.
        """

        alarm_max = {}
        alarm_min = {}
        query_min, query_max = self.control_data(session)
        channels = session.\
            query(
                Channel.id.label("channel_id"), Channel.id_cnr.label("channel_cnr_id"), Channel.range_min, Channel.range_max,
                Sensor.id.label("sensor_id"),  Sensor.id_cnr.label("sensor_cnr_id"),
                Site.id.label("site_id"), Site.id_cnr.label("site_cnr_id")
        ).\
            filter(Sensor.id == Channel.sensor_id).\
            filter(Site.id == Sensor.site_id).\
            filter(Sensor.enabled == True).\
            all()

        for record in query_min:
            for ch in channels:
                if ch.channel_cnr_id == record.channel_id and ch.site_cnr_id == record.site_id:
                    if record[0] <= ch.range_min:
                        channel = AlarmedChannelData(
                            ch.site_id, ch.sensor_id, ch.channel_id,
                            ch.site_cnr_id, ch.sensor_cnr_id, ch.channel_cnr_id,
                            ch.range_min, ch.range_max
                        )
                        alarm_min[channel] = [record[0], record.date]

        for record in query_max:
            for ch in channels:
                if ch.channel_cnr_id == record.channel_id and ch.site_cnr_id == record.site_id:
                    if record[0] >= ch.range_max:
                        channel = AlarmedChannelData(
                            ch.site_id, ch.sensor_id, ch.channel_id,
                            ch.site_cnr_id, ch.sensor_cnr_id, ch.channel_cnr_id,
                            ch.range_min, ch.range_max
                        )
                        alarm_max[channel] = [record[0], record.date]

        if alarm_min or alarm_max:
            logging.info(f"alarm_compare_data, found min: {alarm_min} max: {alarm_max}")

        return alarm_min, alarm_max

    def check_alarmed(self, session: Session, channel_data: List[AlarmedChannelData]):
        res = {}

        # Could we use less queries?
        # answer: yes, with a custom table and with at least 3/4 complex queries, good luck doing that
        # Doing this seems fine, the number of queries is the same as the number of concurrent fired alarms.
        # This should be efficient, unless global warning burns every site at once

        for channel in channel_data:
            last_mes = session.query(ReadingData.date, ReadingData.value_min, ReadingData.value_max).\
                filter(ReadingData.site_id == channel.cnr_site_id, ReadingData.sensor_id == channel.cnr_sensor_id, ReadingData.channel_id == channel.cnr_channel_id).\
                order_by(ReadingData.date.desc()).\
                first()

            logging.info(f"Channel {channel.channel_id} {last_mes}")

            res[channel] = last_mes.value_min > channel.range_min and last_mes.value_max < channel.range_max

        return res


MIN_MEASURE = 1
MAX_MEASURE = 2


class AlarmManager:
    """
    This class manages all the alarm-related events and classes,
    When an alarm is found the contacter is called and the sensor status is changed appropriately
    """
    def __init__(self, contacter: Contacter):
        self.alarm_finder = AlarmFinder()
        self.timer = RepeatingTimer(1, self.on_timer_tick)
        self.contacter = contacter

        self.alarmed_channels = {}  # type: Dict[AlarmedChannelData, datetime]
        self.alarmed_channels_by_sensor = {}  # type: Dict[int, List[AlarmedChannelData]]

    def load_config(self, file_path, check_interval):
        self.timer.interval = check_interval
        self.alarm_finder.load_config(file_path)

    def on_timer_tick(self):
        # Oh, just look at the time!

        # Check for alarming measures
        with session_scope() as session:
            alarm_min, alarm_max = self.alarm_finder.compare_data(session)

            for channel_data, (min_measure, date) in alarm_min.items():
                if channel_data not in self.alarmed_channels:
                    self.on_alarm_start(session, date, channel_data, min_measure, MIN_MEASURE)
                else:
                    self.on_alarm_continue(session, channel_data, min_measure, MIN_MEASURE)

            for channel_data, (max_measure, date) in alarm_max.items():
                if channel_data not in self.alarmed_channels:
                    self.on_alarm_start(session, date, channel_data, max_measure, MAX_MEASURE)
                else:
                    self.on_alarm_continue(session, channel_data, max_measure, MAX_MEASURE)

            # Check the alarmed channels for updates
            status = self.alarm_finder.check_alarmed(session, list(self.alarmed_channels.keys()))

            for channel, alarm_extinguished in status.items():
                if not alarm_extinguished: continue
                self.on_alarm_end(session, channel)

    def update_sensor_status(self, session: Session, sensor_id):
        sites = self.alarmed_channels_by_sensor.get(sensor_id)

        if sites is None:
            sites = []

        channel_ids = [s.channel_id for s in sites]

        sensor = session.query(Sensor).filter(Sensor.id == sensor_id).first()
        if sensor is None:
            logging.warning("Unable to update sensor {}, sensor not found".format(sensor_id))
            return

        if len(channel_ids) > 0:
            status = f"{channel_ids} fired"
        else:
            status = "ok"

        sensor.status = status
        session.commit()

    def on_alarm_start(self, session: Session, date, channel_data: AlarmedChannelData, measure, measure_type):
        logging.warning(f"on_alarm_started!, {date} {channel_data} {measure} {measure_type}")
        self.alarmed_channels[channel_data] = date

        if channel_data.sensor_id in self.alarmed_channels_by_sensor:
            self.alarmed_channels_by_sensor[channel_data.sensor_id].append(channel_data)
        else:
            self.alarmed_channels_by_sensor[channel_data.sensor_id] = [channel_data]

        self.update_sensor_status(session, channel_data.sensor_id)

        self.contacter.send_alarm(channel_data.channel_id, str(measure))

    def on_alarm_continue(self, session: Session, channel_data, measure, measure_type):
        logging.warning(f"on_alarm_continue!, {channel_data} {measure} {measure_type}")
        pass

    def on_alarm_end(self, session: Session, channel_data):
        logging.warning(f"on_alarm_end!, {channel_data}")

        del self.alarmed_channels[channel_data]

        sensor_channels = self.alarmed_channels_by_sensor[channel_data.sensor_id]
        sensor_channels.remove(channel_data)
        if len(sensor_channels) == 0:
            del self.alarmed_channels_by_sensor[channel_data.sensor_id]

        self.update_sensor_status(session, channel_data.sensor_id)

    def start_timer_async(self):
        self.timer.start_async()


