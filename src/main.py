#!/usr/bin/env python

from __future__ import print_function
import RPi.GPIO as GPIO
import argparse
import json
import os.path
import pathlib2 as pathlib
import os
import subprocess
import re
import psutil
import logging
import time
import random
import snowboydecoder
import sys
import signal
import requests
import google.oauth2.credentials
from google.assistant.library import Assistant
from google.assistant.library.event import EventType
from google.assistant.library.file_helpers import existing_file
from google.assistant.library.device_helpers import register_device
from threading import Thread
from indicator import assistantindicator
from indicator import stoppushbutton
from hogwarts import award
from pathlib import Path
import yaml

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError

ROOT_PATH = os.path.realpath(os.path.join(__file__, '..', '..'))
USER_PATH = os.path.realpath(os.path.join(__file__, '..', '..', '..'))

with open('{}/src/config.yaml'.format(ROOT_PATH), 'r') as conf:
    configuration = yaml.load(conf)

WARNING_NOT_REGISTERED = """
    This device is not registered. This means you will not be able to use
    Device Actions or see your device in Assistant Settings. In order to
    register this device follow instructions at:

    https://developers.google.com/assistant/sdk/guides/library/python/embed/register-device
"""

logging.basicConfig(
    filename='/tmp/GassistPi.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

mutestopbutton = True

#Check if custom wakeword has been enabled
if configuration['Wakewords']['Custom_Wakeword'] == 'Enabled':
    custom_wakeword = True
else:
    custom_wakeword = False

models = configuration['Wakewords']['Custom_wakeword_models']


class Myassistant():
    def __init__(self):
        self.interrupted = False
        self.can_start_conversation = False
        self.assistant = None
        self.sensitivity = [0.5] * len(models)
        self.callbacks = [self.detected] * len(models)
        self.detector = snowboydecoder.HotwordDetector(models, sensitivity=self.sensitivity)
        self.t1 = Thread(target=self.start_detector)
        self.t2 = Thread(target=self.pushbutton)

    def signal_handler(self, signal, frame):
        self.interrupted = True

    def interrupt_callback(self, ):
        return self.interrupted

    def buttonsinglepress(self):
        if os.path.isfile("{}/.mute".format(USER_PATH)):
            os.system("sudo rm {}/.mute".format(USER_PATH))
            assistantindicator('unmute')
            if configuration['Wakewords']['Ok_Google'] == 'Disabled':
                self.assistant.set_mic_mute(True)
            else:
                self.assistant.set_mic_mute(False)
            subprocess.Popen(["aplay", "{}/sample-audio-files/Mic-On.wav".format(ROOT_PATH)],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
            print("Turning on the microphone")
        else:
            open('{}/.mute'.format(USER_PATH), 'a').close()
            assistantindicator('mute')
            self.assistant.set_mic_mute(True)
            subprocess.Popen(["aplay", "{}/sample-audio-files/Mic-Off.wav".format(ROOT_PATH)],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
            print("Turning off the microphone")

    def buttondoublepress(self):
        print('Stopped')
        stop()

    def buttontriplepress(self):
        print("Create your own action for button triple press")

    def pushbutton(self):
        while mutestopbutton:
            if GPIO.event_detected(stoppushbutton):
                GPIO.remove_event_detect(stoppushbutton)
                now = time.time()
                count = 1
                GPIO.add_event_detect(stoppushbutton, GPIO.RISING)
                while time.time() < now + 1:
                    if GPIO.event_detected(stoppushbutton):
                        count += 1
                        time.sleep(.25)
                if count == 2:
                    self.buttonsinglepress()
                    GPIO.remove_event_detect(stoppushbutton)
                    GPIO.add_event_detect(stoppushbutton, GPIO.FALLING)
                elif count == 3:
                    self.buttondoublepress()
                    GPIO.remove_event_detect(stoppushbutton)
                    GPIO.add_event_detect(stoppushbutton, GPIO.FALLING)
                elif count == 4:
                    self.buttontriplepress()
                    GPIO.remove_event_detect(stoppushbutton)
                    GPIO.add_event_detect(stoppushbutton, GPIO.FALLING)

    def process_event(self, event):
        """Pretty prints events.
        Prints all events that occur with two spaces between each new
        conversation and a single space between turns of a conversation.
        Args:
            event(event.Event): The current event to process.
        """
        print(event)
        if event.type == EventType.ON_START_FINISHED:
            self.can_start_conversation = True
            self.t2.start()
            if os.path.isfile("{}/.mute".format(USER_PATH)):
                assistantindicator('mute')
            if (configuration['Wakewords']['Ok_Google'] == 'Disabled'
                    or os.path.isfile("{}/.mute".format(USER_PATH))):
                self.assistant.set_mic_mute(True)
            if custom_wakeword:
                self.t1.start()

        if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
            self.can_start_conversation = False
            subprocess.Popen(["aplay", "{}/sample-audio-files/Fb.wav".format(ROOT_PATH)],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
            assistantindicator('listening')
            print()

        if (event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT or event.type == EventType.ON_NO_RESPONSE):
            self.can_start_conversation = True
            assistantindicator('off')
            if (configuration['Wakewords']['Ok_Google'] == 'Disabled'
                    or os.path.isfile("{}/.mute".format(USER_PATH))):
                self.assistant.set_mic_mute(True)
            if os.path.isfile("{}/.mute".format(USER_PATH)):
                assistantindicator('mute')

        if (event.type == EventType.ON_RESPONDING_STARTED and event.args
                and not event.args['is_error_response']):
            assistantindicator('speaking')

        if event.type == EventType.ON_RESPONDING_FINISHED:
            assistantindicator('off')

        if event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED:
            assistantindicator('off')

        if event.type == EventType.ON_ASSISTANT_ERROR:
            print('here is an indication')

        print(event)

        if (event.type == EventType.ON_CONVERSATION_TURN_FINISHED and event.args
                and not event.args['with_follow_on_turn']):
            self.can_start_conversation = True
            assistantindicator('off')
            if (configuration['Wakewords']['Ok_Google'] == 'Disabled'
                    or os.path.isfile("{}/.mute".format(USER_PATH))):
                self.assistant.set_mic_mute(True)
            if os.path.isfile("{}/.mute".format(USER_PATH)):
                assistantindicator('mute')
            print()

        if event.type == EventType.ON_DEVICE_ACTION:
            for command, params in event.actions:
                print('Do command', command, 'with params', str(params))
                if command == 'com.example.commands.AwardPoints':
                    award(params["house"], params["number"])

    def register_device(self, project_id, credentials, device_model_id, device_id):
        """Register the device if needed.
        Registers a new assistant device if an instance with the given id
        does not already exists for this model.
        Args:
           project_id(str): The project ID used to register device instance.
           credentials(google.oauth2.credentials.Credentials): The Google
                    OAuth2 credentials of the user to associate the device
                    instance with.
           device_model_id: The registered device model ID.
           device_id: The device ID of the new instance.
        """
        base_url = '/'.join([DEVICE_API_URL, 'projects', project_id, 'devices'])
        device_url = '/'.join([base_url, device_id])
        session = google.auth.transport.requests.AuthorizedSession(credentials)
        r = session.get(device_url)
        print(device_url, r.status_code)
        if r.status_code == 404:
            print('Registering....')
            r = session.post(
                base_url,
                data=json.dumps({
                    'id': device_id,
                    'model_id': device_model_id,
                    'client_type': 'SDK_LIBRARY'
                }))
            if r.status_code != 200:
                raise Exception('failed to register device: ' + r.text)
            print('\rDevice registered.')

    def detected(self):
        if self.can_start_conversation == True:
            self.assistant.set_mic_mute(False)
            self.assistant.start_conversation()
            print('Assistant is listening....')

    def start_detector(self):
        self.detector.start(
            detected_callback=self.callbacks, interrupt_check=self.interrupt_callback, sleep_time=0.02)

    def main(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument(
            '--device-model-id',
            '--device_model_id',
            type=str,
            metavar='DEVICE_MODEL_ID',
            required=False,
            help='the device model ID registered with Google')
        parser.add_argument(
            '--project-id',
            '--project_id',
            type=str,
            metavar='PROJECT_ID',
            required=False,
            help='the project ID used to register this device')
        parser.add_argument(
            '--device-config',
            type=str,
            metavar='DEVICE_CONFIG_FILE',
            default=os.path.join(
                os.path.expanduser('~/.config'), 'googlesamples-assistant', 'device_config_library.json'),
            help='path to store and read device configuration')
        parser.add_argument(
            '--credentials',
            type=existing_file,
            metavar='OAUTH2_CREDENTIALS_FILE',
            default=os.path.join(os.path.expanduser('~/.config'), 'google-oauthlib-tool', 'credentials.json'),
            help='path to store and read OAuth2 credentials')
        parser.add_argument(
            '-v', '--version', action='version', version='%(prog)s ' + Assistant.__version_str__())

        args = parser.parse_args()
        with open(args.credentials, 'r') as f:
            credentials = google.oauth2.credentials.Credentials(token=None, **json.load(f))

        device_model_id = None
        last_device_id = None
        try:
            with open(args.device_config) as f:
                device_config = json.load(f)
                device_model_id = device_config['model_id']
                last_device_id = device_config.get('last_device_id', None)
        except FileNotFoundError:
            pass

        if not args.device_model_id and not device_model_id:
            raise Exception('Missing --device-model-id option')

        # Re-register if "device_model_id" is given by the user and it differs
        # from what we previously registered with.
        should_register = (args.device_model_id and args.device_model_id != device_model_id)

        device_model_id = args.device_model_id or device_model_id
        with Assistant(credentials, device_model_id) as assistant:
            self.assistant = assistant
            subprocess.Popen(["aplay", "{}/sample-audio-files/Startup.wav".format(ROOT_PATH)],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
            events = assistant.start()
            device_id = assistant.device_id
            print('device_model_id:', device_model_id)
            print('device_id:', device_id + '\n')

            # Re-register if "device_id" is different from the last "device_id":
            if should_register or (device_id != last_device_id):
                if args.project_id:
                    register_device(args.project_id, credentials, device_model_id, device_id)
                    pathlib.Path(os.path.dirname(args.device_config)).mkdir(exist_ok=True)
                    with open(args.device_config, 'w') as f:
                        json.dump({
                            'last_device_id': device_id,
                            'model_id': device_model_id,
                        }, f)
                else:
                    print(WARNING_NOT_REGISTERED)

            for event in events:
                self.process_event(event)
                usrcmd = event.args
        if custom_wakeword:
            self.detector.terminate()


if __name__ == '__main__':
    try:
        Myassistant().main()
    except Exception as error:
        logger.exception(error)
