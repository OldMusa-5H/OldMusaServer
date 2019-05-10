import sys
from typing import List, Optional

import pyfcm
from sqlalchemy.orm import Session

import models
import logging

session = models.db.session  # type: Session


class Contacter:
    def __init__(self):
        self.fcm = None  # type: Optional[pyfcm.FCMNotification]

    def load_config(self, fcm_api_key, telegram_api_key):
        if fcm_api_key is None or fcm_api_key == "":
            self.fcm = None
            logging.error("No FCM key found, disabling")
        else:
            self.fcm = pyfcm.FCMNotification(fcm_api_key)

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
        logging.warning(f"Sending alarm! {channel_id} {unitvalue}")

        channel = session.query(models.Channel).filter(models.Channel.id == channel_id).one()  # type: models.Channel
        sensor = session.query(models.Sensor).filter(models.Sensor.id == channel.sensor_id).one()  # type: models.Sensor
        site = session.query(models.Site).filter(models.Site.id == sensor.site_id).one()  # type: models.Site

        # TODO: Add telegram

        if self.fcm is not None:
            listeners = self.get_fcm_listeners(site.id)
            logging.info(f"Sending FCM alarm to {len(listeners)} devices")

            data_message = {
                "type": "sensor_range_alarm",
                "site_name": site.name,
                "sensor_name": sensor.name,
                "channel_name": channel.name,
                "value":  f"{unitvalue} {channel.measure_unit}"
            }

            self.fcm.multiple_devices_data_message(registration_ids=listeners, data_message=data_message)
        else:
            logging.warning("FCM disabled, skipping alarm notification")
