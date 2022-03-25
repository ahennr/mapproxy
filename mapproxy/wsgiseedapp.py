# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
The seeder WSGI application.
"""
from __future__ import print_function

import json
import logging
import re

from mapproxy.config.loader import load_configuration, ConfigurationError
from mapproxy.response import Response
from mapproxy.wsgiapp import wrap_wsgi_debug

from mapproxy.seed.cachelock import DummyCacheLocker
from mapproxy.seed.config import SeedingConfiguration
from mapproxy.seed.script import seed
from mapproxy.seed.util import ProgressLog

log = logging.getLogger('mapproxy.config')
log_wsgi_app = logging.getLogger('mapproxy.wsgiapp')


def make_wsgi_seed_app(services_conf=None, debug=False):
    """
    Create a Seed REST endpoint app
    """

    try:
        conf = load_configuration(mapproxy_conf=services_conf, ignore_warnings=False)
    except ConfigurationError as e:
        log.fatal(e)
        raise

    app = SeedRestApp(conf)
    if debug:
        app = wrap_wsgi_debug(app, {})

    return app


def not_supported_response():
    import mapproxy.version
    html = "<html><body><h1>TODO: Welcome to MapProxy Seed REST endpoint, POST only%s</h1>" % mapproxy.version.version
    return Response(html, mimetype='text/html')


def result_resp():
    test = b'{"result": "ok"}'
    return Response(test, mimetype='application/json')


class SeedRestApp(object):
    """
    The seed REST WSGI application.
    """
    handler_path_re = re.compile(r'^/(\w+)')

    def __init__(self, mapproxy_conf):
        self.mapproxy_conf = mapproxy_conf

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] != 'POST':
            resp = not_supported_response()
            print("Öhm, Nö.")
            return resp(environ, start_response)

        # error-handling!!
        # auth (!)
        # Polling / Job queue

        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
        except ValueError:
            request_body_size = -1

        br = environ.get('wsgi.input')
        seed_conf_complete = json.loads(br.read(request_body_size))
        seed_conf = seed_conf_complete['seedConfig']
        options = seed_conf_complete['config']

        seed_cfg = SeedingConfiguration(seed_conf, self.mapproxy_conf)
        seed_tasks = seed_cfg.seeds()
        # perform seeding
        cache_locker = DummyCacheLocker()
        logger = ProgressLog(verbose=True, silent=False)
        seed(seed_tasks, progress_logger=logger, dry_run=options['dry_run'],
             concurrency=options['concurrency'], cache_locker=cache_locker,
             skip_geoms_for_last_levels=options['geom_levels'])

        # return result
        resp = result_resp()
        return resp(environ, start_response)
