import requests
from requests.auth import HTTPBasicAuth
import subprocess
import os

ROOT_PATH = os.path.realpath(os.path.join(__file__, '..', '..'))


def award(house, points):
    print('hogwarts.award')
    subprocess.Popen(["aplay", "{}/sample-audio-files/snowboy.wav".format(ROOT_PATH)],
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
    print('sound played')
    request = {'queryResult': {'parameters': {'number': points, 'House': house}}}
    r = requests.post(
        'https://gryffindor.duckdns.org/award/', auth=('hogwarts', 'r%ZSFc5&01b6C9M'), json=request)
    resp = r.json()
    print(resp)
    return None
