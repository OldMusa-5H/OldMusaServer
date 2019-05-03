import io
import datetime
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from models import Channel, ReadingData
import rest_controller

class Alarm_finder():
    def __init__(self):
        self.last_time = datetime.datetime.min

    def ultimate_time(self):
        query = rest_controller.session.query(ReadingData.data).order_by(desc(ReadingData.data)).all()[0]
        return query

    def data_controller(self):
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

        return query_min, query_max

    def data_comparing(self):
        alarm_max = {}
        alarm_min = {}
        query_min, query_max = self.data_controller()
        channels = rest_controller.session.query(Channel.id_cnr, Channel.range_min, Channel.range_max).all()
        for record in query_min:
            for ch in channels:
                if ch.id_cnr == record.channel_id:
                    if record[0] <= ch.range_min:
                        alarm_min.update({ch.id_cnr:[record[0], record.date]})

        for record in query_max:
            for ch in channels:
                if ch.id_cnr == record.channel_id:
                    if record[0] >= ch.range_max:
                        alarm_max.update({ch.id_cnr: [record[0], record.date]})

        if len(alarm_max) == 0 and len(alarm_min) == 0:
            return None
        return alarm_min, alarm_max

