import requests
import subprocess

ROOT_PATH = os.path.realpath(os.path.join(__file__, '..', '..'))


def award(house, points):
    request = {'queryResult': {'parameters': {'number': points, 'House': house}}}
    r = requests.post('https://gryffindor.duckdns.org/award', json=request)
    subprocess.Popen(["aplay", "{}/sample-audio-files/snowboy.wav".format(ROOT_PATH)],
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
    resp = r.json()
    print(resp)
