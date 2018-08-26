import os
import json
from urlparse import urlparse
import urllib
from collections import OrderedDict
from flask import Flask, render_template, request, jsonify
from flask_redis import FlaskRedis
from flask_redis_sentinel import SentinelExtension
from flask_bootstrap import Bootstrap
import redis_sentinel_url

redis_sentinel = SentinelExtension()
redis_db = redis_sentinel.default_connection

app = Flask(__name__)

def find_redis_instance(services):
  for service_name, instances in services.items():
      for instance in instances:
          if 'redis' in instance.get('tags', []):
              return instance
  return None

# Handle Cloud Foundry with Sentinel
if 'VCAP_SERVICES' in os.environ:
  services = json.loads(os.getenv('VCAP_SERVICES'))
  instance = find_redis_instance(services)
  if not instance:
      raise RuntimeError('No redis service found')

  creds = instance['credentials']
  redis_password = creds['password']
  if not os.getenv('NO_URL_QUOTING'):
      redis_password = urllib.quote(redis_password, safe='')
  app.config['REDIS_URL'] = 'redis+sentinel://:%s@%s:%s/%s/0' % (
    redis_password,
    creds['sentinel_addrs'][0],
    creds['sentinel_port'],
    urllib.quote(creds['name'], safe=''))

redis_sentinel.init_app(app)
Bootstrap(app)

@app.route('/execute', methods=['POST'])
def execute():
    req = request.get_json()
    try:
        response = redis_db.execute_command(*req['command'].split())
    except Exception as err:
        response = 'Exception: %s' % err
    return jsonify({
        'response': response
    })

def get_conn_info(url):
    conn_info = []
    if url.startswith('redis://'):
        urlparts = urlparse(url)
        netloc = urlparts[1].partition(':')
        conn_info = [
            ('Address', netloc[0]),
            ('Port', (netloc[2] or '6379'))
        ]
    elif url.startswith('redis+sentinel://'):
        result = redis_sentinel_url.parse_sentinel_url(url)
        print result.hosts
        conn_info = [
            ('Sentinel Hosts', ','.join(['%s:%s' % (pair[0], pair[1])
                                         for pair in result.hosts])),
            ('Service', result.default_client.service)
        ]

    return conn_info

@app.route('/')
def index():
    return render_template('index.html', config=app.config,
                           conninfo=get_conn_info(app.config['REDIS_URL']))
