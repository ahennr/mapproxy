# -:- encoding: utf8 -:-
# This file is part of the MapProxy project.
# Copyright (C) 2015 Omniscale <http://omniscale.de>
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

from __future__ import division

import functools

from io import BytesIO

import pytest

from mapproxy.request.wmts import WMTS100TileRequest, WMTS100CapabilitiesRequest
from mapproxy.request.wms import WMS111CapabilitiesRequest
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.http import MockServ
from mapproxy.test.helper import validate_with_xsd
from mapproxy.test.system import SysTest


@pytest.fixture(scope="module")
def config_file():
    return "multi_cache_layers.yaml"


ns_wmts = {
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
    "xlink": "http://www.w3.org/1999/xlink",
}


TEST_TILE = create_tmp_image((256, 256))


class TestMultiCacheLayer(SysTest):

    def setup_method(self):
        self.common_cap_req = WMTS100CapabilitiesRequest(
            url="/service?",
            param=dict(service="WMTS", version="1.0.0", request="GetCapabilities"),
        )
        self.common_tile_req = WMTS100TileRequest(
            url="/service?",
            param=dict(
                service="WMTS",
                version="1.0.0",
                tilerow="0",
                tilecol="0",
                tilematrix="01",
                tilematrixset="GLOBAL_WEBMERCATOR",
                layer="multi_cache",
                format="image/png",
                style="",
                request="GetTile",
            ),
        )

    def test_image_config(self, app):
        resp = app.get("/tms/1.0.0/")
        assert "http://localhost/tms/1.0.0/cache_image/EPSG25832" in resp

    def test_tms_capabilities(self, app):
        resp = app.get("/tms/1.0.0/")
        assert "http://localhost/tms/1.0.0/multi_cache/EPSG25832" in resp
        assert "http://localhost/tms/1.0.0/multi_cache/EPSG3857" in resp
        assert "http://localhost/tms/1.0.0/multi_cache/CRS84" in resp
        assert "http://localhost/tms/1.0.0/multi_cache/EPSG31467" in resp
        assert "http://localhost/tms/1.0.0/cache/EPSG25832" in resp
        xml = resp.lxml
        assert xml.xpath("count(//TileMap)") == 8

    def test_wmts_capabilities(self, app):
        req = str(self.common_cap_req)
        resp = app.get(req)
        assert resp.content_type == "application/xml"
        xml = resp.lxml

        assert validate_with_xsd(
            xml, xsd_name="wmts/1.0/wmtsGetCapabilities_response.xsd"
        )
        assert set(
            xml.xpath("//wmts:Layer/ows:Identifier/text()", namespaces=ns_wmts)
        ) == set(["cache", "multi_cache", "cache_image"])
        assert set(
            xml.xpath(
                "//wmts:Contents/wmts:TileMatrixSet/ows:Identifier/text()",
                namespaces=ns_wmts,
            )
        ) == set(["gk3", "GLOBAL_WEBMERCATOR", "utm32", "InspireCrs84Quad"])

    def test_wms_capabilities(self, app):
        req = WMS111CapabilitiesRequest(url="/service?")
        resp = app.get(req)
        assert resp.content_type == "application/vnd.ogc.wms_xml"
        xml = resp.lxml
        assert (
            xml.xpath(
                "//GetMap//OnlineResource/@xlink:href",
                namespaces=dict(xlink="http://www.w3.org/1999/xlink"),
            )[0]
            == "http://localhost/service?"
        )

        layer_names = set(xml.xpath("//Layer/Layer/Name/text()"))
        expected_names = set(["wms_only", "cache", "cache_image"])
        assert layer_names == expected_names

    def test_get_tile_webmerc(self, app):
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=-20037508.3428,0.0,0.0,20037508.3428&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A3857&request=GetMap&height=256"
        ).returns(TEST_TILE)
        with serv:
            resp = app.get(str(self.common_tile_req))
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_tile_utm(self, app):
        serv = MockServ(42423, bbox_aware_query_comparator=True)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=-46133.17,5675047.40429,580038.965712,6301219.54&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        self.common_tile_req.params["tilematrixset"] = "utm32"

        with serv:
            resp = app.get(str(self.common_tile_req))
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_tile_cascaded_cache(self, app):
        serv = MockServ(42423, bbox_aware_query_comparator=True, unordered=True)
        # gk3 cache requests UTM tiles
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=423495.931784,5596775.88732,501767.448748,5675047.40429&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=345224.41482,5596775.88732,423495.931784,5675047.40429&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=345224.41482,5518504.37036,423495.931784,5596775.88732&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=423495.931784,5518504.37036,501767.448748,5596775.88732&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=345224.41482,5440232.8534,423495.931784,5518504.37036&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        serv.expects(
            "/service?layers=foo,bar&width=256&version=1.1.1&bbox=423495.931784,5440232.8534,501767.448748,5518504.37036&service=WMS&format=image%2Fpng&styles=&srs=EPSG%3A25832&request=GetMap&height=256"
        ).returns(TEST_TILE)
        self.common_tile_req.params["tilematrixset"] = "gk3"
        with serv:
            resp = app.get(str(self.common_tile_req))
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
