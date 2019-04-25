import sys
from typing import List

import pyfcm
from sqlalchemy.orm import Session

import models

session = models.db.session  # type: Session


class Contacter:
    def __init__(self, fcm_api_key, telegram_api_key):
        if fcm_api_key is None or fcm_api_key == "":
            self.fcm = None
            self.warn("No FCM key found, disabling")
        else:
            self.fcm = pyfcm.FCMNotification(fcm_api_key)

    def warn(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def get_fcm_listeners(self, site_id) -> List[str]:
        users = session.query(models.User.id)\
            .select_from(models.User)\
            .join(models.UserAccess, models.UserAccess.user_id == models.User.id)\
            .filter(models.UserAccess.site_id == site_id)

        admins = session.query(models.User.id).select_from(models.User).filter(models.User.permission == "A")

        users = users.union(admins).distinct().subquery()

        receivers = session.query(models.FCMUserContact.registration_id)\
            .select_from(users)\
            .join(models.FCMUserContact, models.FCMUserContact.user_id == users.c.user_id)\
            .distinct()

        return [x[0] for x in receivers.all()]

    def send_alarm(self, channel_id, unitvalue):
        channel = session.query(models.Channel).filter(models.Channel.id == channel_id).one()  # type: models.Channel
        sensor = session.query(models.Sensor).filter(models.Sensor.id == channel.sensor_id).one()  # type: models.Sensor
        site = session.query(models.Site).filter(models.Site.id == sensor.site_id).one()  # type: models.Site

        # TODO: Add telegram

        if self.fcm is not None:
            listeners = self.get_fcm_listeners(site.id)

            data_message = {
                "type": "sensor_range_alarm",
                "site_name": site.name,
                "sensor_name": sensor.name,
                "channel_name": channel.name,
                "value":  unitvalue,
            }

            self.fcm.multiple_devices_data_message(registration_ids=listeners, data_message=data_message)
        else:
            self.warn("FCM disabled, skipping alarm notification")
