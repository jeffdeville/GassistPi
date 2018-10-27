import requests
from requests.auth import HTTPBasicAuth
import subprocess
import os

ROOT_PATH = os.path.realpath(os.path.join(__file__, '..', '..'))


def award(house, points):
    print('hogwarts.award')
    points = int(points)
    if points in [25, 50, 75, 100]:
        request = {'queryResult': {'parameters': {'number': points, 'House': house}}}
        r = requests.post(
            'https://gryffindor.duckdns.org/award/', auth=('hogwarts', 'r%ZSFc5&01b6C9M'), json=request)
        resp = r.json()
        print(resp)
        print("Points awarded")
        return None
    else:
        subprocess.Popen(["aplay", "{}/sample-audio-files/HP-SS-careful.wav".format(ROOT_PATH)],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        print('sound played')
    return None
