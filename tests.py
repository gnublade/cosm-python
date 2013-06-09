# -*- coding: utf-8 -*-

import json
import unittest

from datetime import datetime

try:
    from io import BytesIO
except TypeError:
    from StringIO import StringIO as BytesIO  # NOQA

import requests

from mock import Mock, call, patch

import fixtures
import xively
import xively.api
import xively.client
import xively.managers
from xively.exceptions import ExceptionsWrapper, ResourceNotFound

BASE_URL = "http://api.xively.com/v2"


class RequestsFixtureMixin(object):
    """Mixin to mock request.Session.request from the xively module."""

    def setUp(self, *args, **kwargs):  # NOQA
        """Installs our own request handler."""
        patcher = patch('xively.client.Session.request')
        self.request = patcher.start()
    setUp.__test__ = False  # Don't test this method.

    def tearDown(self, *args, **kwargs):  # NOQA
        """Ensures the original request object is reinstated."""
        self.request.stop()
    tearDown.__test__ = False  # Don't test this method.

    def request(self, *args, **kwargs):
        """Returns a new mock object by default. Override in implementors."""
        return Mock()


class BaseTestCase(RequestsFixtureMixin, unittest.TestCase):
    """Common base class for Xively api tests."""

    def setUp(self):  # NOQA
        super(BaseTestCase, self).setUp()
        self.api = xively.api.XivelyAPIClient("API_KEY")
        self.client = self.api.client
        # Ensure that the jsonified output is in a known order.
        self.client._json_encoder.sort_keys = True
        response = requests.Response()
        response.status_code = 200
        self.request.return_value = self.response = response

    def _create_feed(self, **data):
        feed_manager = xively.managers.FeedsManager(self.client)
        feed = feed_manager._coerce_feed(data)
        return feed

    def _create_datastream(self, **data):
        datastream = xively.Datastream(**data)
        datastream._manager = xively.managers.DatastreamsManager(self.feed)
        return datastream

    def _create_datapoint(self, **data):
        datapoint = xively.Datapoint(**data)
        manager = xively.managers.DatapointsManager(self.datastream)
        datapoint._manager = manager
        return datapoint

    def _create_trigger(self, **data):
        id = data.pop('id', None)
        trigger = xively.Trigger(self.feed.id, self.datastream.id, **data)
        if id is not None:
            trigger._data['id'] = id
        trigger._manager = xively.managers.TriggersManager(self.client)
        return trigger

    def _sorted_json(self, s):
        return json.dumps(json.loads(s.decode('utf8')), sort_keys=True)


class KeyAuthTest(unittest.TestCase):
    """
    Key based authentication tests.
    """

    def test_api_key_header(self):
        """Tests the X-ApiKey header is set on requests using KeyAuth."""
        request = requests.Request()
        auth = xively.client.KeyAuth("ABCDE")
        auth(request)
        self.assertEqual(request.headers['X-ApiKey'], "ABCDE")


class ClientTest(BaseTestCase):
    """
    Low level Xively Client tests.
    """

    def test_create(self):
        """Tests that we can create a client object."""
        xively.Client("ABCDE")

    def test_request_relative_url(self):
        """Tests relative urls are requested with absolute url."""
        client = xively.Client("API_KEY")
        client.request('GET', "/v2/feeds")
        self.request.assert_called_with('GET', BASE_URL + "/feeds")

    def test_request_absolute_url(self):
        """Tests absolute urls are requested for a different host."""
        client = xively.Client("API_KEY")
        client.request('GET', "http://example.com")
        self.request.assert_called_with('GET', "http://example.com")

    def test_serialise_data(self):
        """Tests data is serialised using __getstate__ when requested."""
        class TestObject:
            def __getstate__(self):
                return self.__dict__
        obj = TestObject()
        obj.title = "This is an object"
        obj.value = 42
        self.client.request('POST', "/v2/feeds", data=obj)
        self.request.assert_called_with(
            'POST', BASE_URL + "/feeds",
            data=json.dumps(
                {"title": "This is an object", "value": 42},
                sort_keys=True))


class ManagerTest(BaseTestCase):

    def test_base_url(self):
        class Manager(xively.managers.ManagerBase):
            pass
        manager = Manager()
        url = "http://www.example.com/path/to/resource"
        manager.base_url = url
        self.assertEqual(manager.base_url, url)


class FeedTest(BaseTestCase):

    def test_init_feed(self):
        datastream = xively.Datastream(id="0")
        feed = xively.Feed(title="Feed Test", datastreams=[datastream])
        self.assertEqual(feed.id, None)
        self.assertEqual(feed.title, "Feed Test")
        self.assertEqual(feed.datastreams[0], datastream)

    def test_update_feed(self):
        feed = self._create_feed(id='123', title="Office")
        feed.private = True
        feed.update()
        self.assertEqual(self.request.call_args[0],
                         ('PUT', BASE_URL + '/feeds/123'))
        payload = json.loads(self.request.call_args[1]['data'])
        self.assertEqual(payload['private'], True)

    def test_update_feed_fields(self):
        feed = self._create_feed(id='123', title="Office")
        feed.private = True
        feed.update(fields=['private'])
        self.request.assert_called_with(
            'PUT', BASE_URL + '/feeds/123', data='{"private": true}')

    def test_update_feed_with_datastreams(self):
        feed = self._create_feed(
            id='1977', title="Xively Office environment",
            website='http://www.haque.co.uk/', tags=['Tag1', 'Tag2'],
            location=xively.Location(
                disposition='fixed', ele='23.0', name="office",
                lat=51.5235375648154, exposure="indoor",
                lon=-0.0807666778564453, domain="physical"),
            datastreams=[
                xively.Datastream(id='0', current_value="211",
                                  max_value="20.0", min_value="7.0"),
                xively.Datastream(id='3', current_value="312",
                                  max_value="999.0", min_value="7.0"),
            ])
        feed.datastreams = [
            xively.Datastream(id='4', current_value="-333"),
        ] + list(feed.datastreams)
        feed.update()
        self.request.assert_called_with(
            'PUT', BASE_URL + '/feeds/1977',
            data=self._sorted_json(fixtures.UPDATE_FEED_JSON))

    def test_delete_feed(self):
        feed = self._create_feed(id='456', title="Home")
        feed.delete()
        self.request.assert_called_with('DELETE', BASE_URL + '/feeds/456')

    def test_set_datastreams(self):
        feed = self._create_feed(id='123', title="Feed with datastreams")
        feed.datastreams = [xively.Datastream(id='0', current_value=42)]
        self.assertEqual(feed.datastreams[0].id, '0')
        self.assertEqual(feed.datastreams[0].current_value, 42)


class FeedsManagerTest(BaseTestCase):

    def test_create_feed(self):
        """Tests a request is sent to create a feed."""
        self.response.status_code = 201
        self.response.headers['location'] = BASE_URL + "/feeds/1977"
        feed = self.api.feeds.create(
            title="Xively Office environment",
            website="http://www.example.com/",
            tags=["Tag1", "Tag2"],
            location=xively.Location(
                name="office",
                disposition='fixed',
                exposure='indoor',
                domain='physical',
                lat=51.5235375648154,
                lon=-0.0807666778564453,
                ele="23.0"),
            datastreams=[
                xively.Datastream(
                    id="0",
                    current_value="123",
                    min_value="-10.0",
                    max_value="10000.0",
                    tags=["humidity"]),
                xively.Datastream(
                    id="1",
                    current_value="987",
                    min_value="-10.0",
                    max_value="10000.0",
                    tags=["humidity"]),
            ])
        self.assertEqual(feed.feed, BASE_URL + "/feeds/1977")
        self.request.assert_called_with(
            'POST', BASE_URL + '/feeds',
            data=self._sorted_json(fixtures.CREATE_FEED_JSON))

    def test_update_feed(self):
        """Tests a request is sent to update a feed."""
        self.api.feeds.update(51, private=True)
        self.request.assert_called_with(
            'PUT', BASE_URL + '/feeds/51', data='{"private": true}')

    def test_list_feeds(self):
        """Tests a request is sent to list all feeds."""
        self.response.raw = BytesIO(fixtures.LIST_FEEDS_JSON)
        (feed,) = self.api.feeds.list()
        self.assertEqual(self.request.call_args[0],
                         ('GET', BASE_URL + '/feeds'))
        self.assertEqual(feed.feed, BASE_URL + '/feeds/5853.json')
        self.assertEqual(feed.location.domain, "physical")
        self.assertEqual(feed.datastreams[0].id, "0")
        self.assertEqual(feed.datastreams[1].id, "1")

    def test_view_feed(self):
        """Tests a request is sent to view a feed (by id) returning json."""
        self.response.raw = BytesIO(fixtures.GET_FEED_JSON)
        feed = self.api.feeds.get(7021)
        self.assertEqual(self.request.call_args[0],
                         ('GET', BASE_URL + '/feeds/7021'))
        self.assertEqual(feed.title, "Xively Office environment")
        self.assertEqual(feed.location.name, "office")

    def test_view_device_feed(self):
        """Tests a request is sent to view a feed (by id) returning json."""
        self.response.raw = BytesIO(fixtures.GET_DEVICE_JSON)
        feed = self.api.feeds.get(7021)
        self.assertEqual(self.request.call_args[0],
                         ('GET', BASE_URL + '/feeds/7021'))
        self.assertEqual(feed.title, "Xively Office environment")
        self.assertEqual(feed.location.name, "office")
        self.assertEqual(feed.product_id, "EK0JEccOD_cVJUeD2eNw")
        self.assertEqual(feed.device_serial, "ZEG9G6FAADJK")

    def test_get_feeds_with_datastream_history(self):
        self.response.raw = BytesIO(fixtures.HISTORY_FEED_JSON)
        feed = self.api.feeds.get(61916,
                                  start=datetime(2013, 1, 1, 14, 0, 0),
                                  end=datetime(2013, 1, 1, 16, 0, 0),
                                  interval=900)
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/61916',
            allow_redirects=True, params={
                'start': '2013-01-01T14:00:00Z',
                'end': '2013-01-01T16:00:00Z',
                'interval': 900,
            })
        self.assertEqual(feed.id, 61916)
        self.assertEqual(feed.datastreams[0].id, "random5")
        self.assertEqual(feed.datastreams[0].datapoints[2].at,
                         datetime(2013, 1, 1, 14, 44, 55, 111267))
        self.assertEqual(feed.datastreams[0].datapoints[2].value, "0.40271227")

    def test_delete_feed(self):
        """Tests a DELETE request is sent for a feed by its id."""
        self.api.feeds.delete(7021)
        self.request.assert_called_with('DELETE', BASE_URL + '/feeds/7021')

    def test_mobile_feed(self):
        self.response.raw = BytesIO(fixtures.MOBILE_FEED_JSON)
        feed = self.api.feeds.get(3819, duration='1day')
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/3819',
            allow_redirects=True, params={'duration': '1day'})
        self.assertEqual(feed.location.disposition, 'mobile')
        self.assertEqual(feed.location.lat, 24.9965)
        self.assertEqual(feed.location.lon, 55.06633)
        self.assertEqual(len(feed.location.waypoints), 6)
        self.assertEqual(feed.location.waypoints[0].at,
                         datetime(2012, 6, 1, 12, 25, 5, 999502))
        self.assertEqual(feed.location.waypoints[0].lat, 24.9966)
        self.assertEqual(feed.location.waypoints[0].lon, 55.06608)
        self.assertEqual(feed.datastreams[2].unit.label, 'knots')


class DatastreamTest(BaseTestCase):

    def setUp(self):  # NOQA
        super(DatastreamTest, self).setUp()
        self.feed = self._create_feed(id=7021, title="Rother")

    def test_create_datastream(self):
        datastream = xively.Datastream(id="energy")
        self.assertEqual(datastream.id, "energy")

    def test_update_datastream(self):
        datastream = self._create_datastream(id="energy", current_value=211)
        datastream.current_value = 294
        datastream.update()
        self.assertEqual(
            self.request.call_args[0],
            ('PUT', BASE_URL + '/feeds/7021/datastreams/energy'))
        payload = json.loads(self.request.call_args[1]['data'])
        self.assertEqual(payload['current_value'], 294)

    def test_update_datastream_fields(self):
        datastream = self._create_datastream(id="energy", current_value=211)
        datastream.current_value = 294
        datastream.update(fields=['current_value'])
        self.request.assert_called_with(
            'PUT', BASE_URL + '/feeds/7021/datastreams/energy',
            data='{"current_value": 294}')

    def test_delete_datastream(self):
        datastream = self._create_datastream(id="energy")
        datastream.delete()
        self.request.assert_called_with(
            'DELETE', BASE_URL + '/feeds/7021/datastreams/energy')


class DatastreamsManagerTest(BaseTestCase):

    def setUp(self):  # NOQA
        super(DatastreamsManagerTest, self).setUp()
        self.feed = self._create_feed(id=7021, title="Rother")

    def test_create_datastream(self):
        datastream = self.feed.datastreams.create(
            id="flow",
            current_value=34000,
            unit=xively.Unit(symbol='l/s'))
        self.assertEqual(
            self.request.call_args[0],
            ('POST', BASE_URL + '/feeds/7021/datastreams'))
        self.assertEqual(datastream.id, "flow")
        self.assertEqual(datastream.current_value, 34000)
        self.assertEqual(datastream.unit.symbol, 'l/s')

    def test_update_datastream(self):
        self.feed.datastreams.update('energy', current_value=294)
        self.assertEqual(
            self.request.call_args[0],
            ('PUT', BASE_URL + '/feeds/7021/datastreams/energy'))
        payload = json.loads(self.request.call_args[1]['data'])
        self.assertEqual(payload['current_value'], 294)

    def test_list_datastreams(self):
        self.response.raw = BytesIO(fixtures.GET_FEED_JSON)
        datastreams = self.feed.datastreams.list()
        self.assertEqual([d.id for d in datastreams], ["3", "4"])
        # Note that this url isnt' at .../datastreams
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/7021/',
            allow_redirects=True, params={})

    def test_view_datastream(self):
        self.response.raw = BytesIO(fixtures.GET_DATASTREAM_JSON)
        datastream = self.feed.datastreams.get('1')
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/7021/datastreams/1',
            allow_redirects=True, params={})
        self.assertEqual(datastream.id, '1')
        self.assertEqual(list(datastream.datapoints), [])

    def test_get_datastream_with_history(self):
        self.response.raw = BytesIO(fixtures.HISTORY_DATASTREAM_JSON)
        datastream = self.feed.datastreams.get(
            'random5',
            start=datetime(2013, 1, 1, 14, 0, 0),
            end=datetime(2013, 1, 1, 16, 0, 0),
            interval=900)
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/7021/datastreams/random5',
            allow_redirects=True, params={
                'start': '2013-01-01T14:00:00Z',
                'end': '2013-01-01T16:00:00Z',
                'interval': 900,
            })
        self.assertEqual(datastream.id, 'random5')
        self.assertEqual(datastream.datapoints[0].at,
                         datetime(2013, 1, 1, 14, 14, 55, 118845))
        self.assertEqual(datastream.datapoints[0].value, "0.25741970")

    def test_delete_datastream(self):
        self.feed.datastreams.delete("energy")
        self.request.assert_called_with(
            'DELETE', BASE_URL + '/feeds/7021/datastreams/energy')


class DatapointTest(BaseTestCase):

    def setUp(self):  # NOQA
        super(DatapointTest, self).setUp()
        self.feed = self._create_feed(id=1977, title="Rother")
        self.datastream = self._create_datastream(id='1', current_value="100")

    def test_create_datapoint(self):
        now = datetime.now()
        datapoint = xively.Datapoint(at=now, value=123)
        self.assertEqual(datapoint.at, now)
        self.assertEqual(datapoint.value, 123)

    def test_update_datapoint(self):
        datapoint = self._create_datapoint(
            at=datetime(2010, 7, 28, 7, 48, 22, 14326), value="296")
        datapoint.value = "297"
        datapoint.update()
        self.request.assert_called_with(
            'PUT', BASE_URL + '/feeds/1977/datastreams/1/datapoints/'
            '2010-07-28T07:48:22.014326Z',
            data='{"value": "297"}')

    def test_delete_datapoint(self):
        datapoint = self._create_datapoint(
            at=datetime(2010, 7, 28, 7, 48, 22, 14326), value="297")
        datapoint.delete()
        self.request.assert_called_with(
            'DELETE', BASE_URL + '/feeds/1977/datastreams/1/datapoints/'
            '2010-07-28T07:48:22.014326Z',
            params={})


class DatapointsManagerTest(BaseTestCase):

    def setUp(self):  # NOQA
        super(DatapointsManagerTest, self).setUp()
        self.feed = self._create_feed(id=1977, title="Rother")
        self.datastream = self._create_datastream(id='1', current_value="100")

    def test_create_datapoint(self):
        # Create with a datetime object.
        datapoint1 = self.datastream.datapoints.create(
            at=datetime(2010, 5, 20, 11, 1, 43), value="294")
        # Create with a iso8601 formatted string.
        datapoint2 = self.datastream.datapoints.create(
            at="2010-05-20T11:01:44Z", value="295")
        # Create with no timestamp.
        with patch('xively.managers.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2010, 5, 20, 11, 1, 45)
            datapoint3 = self.datastream.datapoints.create(value="296")

        self.assertEqual(datapoint1.at, datetime(2010, 5, 20, 11, 1, 43))
        self.assertEqual(datapoint1.value, "294")
        self.assertEqual(datapoint2.at, "2010-05-20T11:01:44Z")
        self.assertEqual(datapoint2.value, "295")
        self.assertEqual(datapoint3.at, datetime(2010, 5, 20, 11, 1, 45))
        self.assertEqual(datapoint3.value, "296")

        url = BASE_URL + '/feeds/1977/datastreams/1/datapoints'
        calls = [
            call('POST', url, data=json.dumps({
                'datapoints': [{"at": "2010-05-20T11:01:43Z", "value": "294"}]
            }, sort_keys=True)),
            call('POST', url, data=json.dumps({
                'datapoints': [{"at": "2010-05-20T11:01:44Z", "value": "295"}]
            }, sort_keys=True)),
            call('POST', url, data=json.dumps({
                'datapoints': [{"at": "2010-05-20T11:01:45Z", "value": "296"}]
            }, sort_keys=True)),
        ]
        self.request.assert_has_calls(calls)

    def test_update_datapoint(self):
        self.datastream.datapoints.update(
            datetime(2010, 7, 28, 7, 48, 22, 14326), value="297")
        self.request.assert_called_with(
            'PUT', BASE_URL + '/feeds/1977/datastreams/1/datapoints/'
            '2010-07-28T07:48:22.014326Z',
            data='{"value": "297"}')

    def test_datapoint_history(self):
        self.response.raw = BytesIO(fixtures.HISTORY_DATASTREAM_JSON)
        datapoints = list(self.datastream.datapoints.history(
            start=datetime(2013, 1, 1, 14, 0, 0),
            end=datetime(2013, 1, 1, 16, 0, 0),
            interval=900))
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/1977/datastreams/1',
            allow_redirects=True, params={
                'start': '2013-01-01T14:00:00Z',
                'end': '2013-01-01T16:00:00Z',
                'interval': 900,
            })
        self.assertEqual(datapoints[0].at,
                         datetime(2013, 1, 1, 14, 14, 55, 118845))
        self.assertEqual(datapoints[0].value, "0.25741970")

    def test_datapoint_history_empty(self):
        self.response.raw = BytesIO(b'''{
            "at": "2013-03-06T14:56:20.844980Z",
            "id": "empty",
            "version": "1.0.0"
        }''')
        datapoints = list(self.datastream.datapoints.history())
        self.assertEqual(datapoints, [])

    def test_view_datapoint(self):
        self.response.raw = BytesIO(fixtures.GET_DATAPOINT_JSON)
        at = datetime(2010, 7, 28, 7, 48, 22, 14326)
        datapoint = self.datastream.datapoints.get(at)
        self.assertEqual(datapoint.at, at)
        self.assertEqual(datapoint.value, "297")
        self.request.assert_called_with(
            'GET', BASE_URL + '/feeds/1977/datastreams/1/datapoints/'
            '2010-07-28T07:48:22.014326Z',
            allow_redirects=True)

    def test_delete_datapoint(self):
        at = datetime(2010, 7, 28, 7, 48, 22, 14326)
        self.datastream.datapoints.delete(at)
        self.request.assert_called_with(
            'DELETE', BASE_URL + '/feeds/1977/datastreams/1/datapoints/'
            '2010-07-28T07:48:22.014326Z',
            params={})

    def test_delete_multiple_datapoints(self):
        self.datastream.datapoints.delete(
            start=datetime(2010, 7, 28, 7, 48, 22, 14326))
        self.request.assert_called_with(
            'DELETE', BASE_URL + '/feeds/1977/datastreams/1/datapoints',
            params={'start': '2010-07-28T07:48:22.014326Z'})


class TriggerTest(BaseTestCase):

    def setUp(self):  # NOQA
        super(TriggerTest, self).setUp()
        self.feed = self._create_feed(id=8470, title="Dave")
        self.datastream = self._create_datastream(id="0")

    def test_create_trigger(self):
        trigger = xively.Trigger(
            self.feed.id, self.datastream.id,
            url="http://www.postbin.org/1ijyltn",
            trigger_type="lt",
            threshold_value="15.0")
        self.client.post('/v2/triggers', data=trigger)
        self.request.assert_called_with(
            'POST', BASE_URL + '/triggers',
            data=json.dumps({
                'environment_id': 8470,
                'stream_id': "0",
                'url': "http://www.postbin.org/1ijyltn",
                'trigger_type': 'lt',
                'threshold_value': "15.0",
            }, sort_keys=True))

    def test_update_trigger(self):
        trigger = self._create_trigger(
            id=14,
            url="http://www.postbin.org/1ijyltn",
            trigger_type='lt',
            threshold_value="15.0")
        trigger.threshold_value = "20.0"
        trigger.update()
        self.request.assert_called_with(
            'PUT', BASE_URL + '/triggers/14', data=json.dumps({
                'threshold_value': "20.0",
                'stream_id': "0",
                'environment_id': 8470,
                'url': "http://www.postbin.org/1ijyltn",
                'trigger_type': 'lt',
            }, sort_keys=True))

    def test_update_trigger_field(self):
        trigger = self._create_trigger(
            id=14,
            url="http://www.postbin.org/1ijyltn",
            trigger_type='lt',
            threshold_value="15.0")
        trigger.threshold_value = "20.0"
        trigger.update(fields=['threshold_value'])
        self.request.assert_called_with(
            'PUT', BASE_URL + '/triggers/14',
            data='{"threshold_value": "20.0"}')

    def test_delete_trigger(self):
        trigger = self._create_trigger(
            id=14,
            url="http://www.postbin.org/1ijyltn",
            trigger_type='lt',
            threshold_value="15.0")
        trigger.delete()
        self.request.assert_called_with('DELETE', BASE_URL + '/triggers/14')


class TriggerManagerTest(BaseTestCase):

    def test_create_trigger(self):
        self.response.status_code = 201
        self.response.headers.update({
            'location': "http://xively.api.com/v2/triggers/14",
        })
        trigger = self.api.triggers.create(
            8470, "0", url="http://www.postbin.org/1ijyltn",
            trigger_type='lt', threshold_value="15.0")
        self.request.assert_called_with(
            'POST', BASE_URL + '/triggers',
            data=json.dumps({
                'environment_id': 8470,
                'stream_id': "0",
                'url': "http://www.postbin.org/1ijyltn",
                'trigger_type': 'lt',
                'threshold_value': "15.0",
            }, sort_keys=True))
        self.assertEqual(trigger.id, 14)

    def test_view_trigger(self):
        self.response.raw = BytesIO(fixtures.GET_TRIGGER_JSON)
        trigger = self.api.triggers.get(14)
        self.request.assert_called_with(
            'GET', BASE_URL + '/triggers/14', allow_redirects=True)
        self.assertEqual(trigger._data, {
            'id': 14,
            'environment_id': 8470,
            'stream_id': "0",
            'user': 'xively',
            'url': "http://www.postbin.org/1ijyltn",
            'trigger_type': "lt",
            'threshold_value': "15.0",
        })

    def test_update_trigger(self):
        self.api.triggers.update(14, threshold_value="20.0")
        self.request.assert_called_with(
            'PUT', BASE_URL + '/triggers/14',
            data='{"threshold_value": "20.0"}')

    def test_list_triggers(self):
        self.response.raw = BytesIO(fixtures.LIST_TRIGGERS_JSON)
        triggers = list(self.api.triggers.list())
        self.request.assert_called_with(
            'GET', BASE_URL + '/triggers', allow_redirects=True, params={})
        self.assertEqual(triggers[0].id, 13)
        self.assertEqual(triggers[1].id, 14)

    def test_list_triggers_for_feed(self):
        self.response.raw = BytesIO(fixtures.LIST_TRIGGERS_JSON)
        triggers = list(self.api.triggers.list(feed_id=1233))
        self.request.assert_called_with(
            'GET', BASE_URL + '/triggers',
            allow_redirects=True, params={'feed_id': 1233})
        self.assertEqual(triggers[0].id, 13)
        self.assertEqual(triggers[1].id, 14)

    def test_delete_trigger(self):
        self.api.triggers.delete(42)
        self.request.assert_called_with('DELETE', BASE_URL + '/triggers/42')


class KeyTest(BaseTestCase):

    def test_create_key(self):
        now = datetime.now()
        key = xively.Key("sharing key", [], expires_at=now)
        self.assertEqual(key.label, "sharing key")
        self.assertEqual(key.permissions, [])
        self.assertEqual(key.expires_at, now)

    def test_delete_key(self):
        key_id = "1nAYR5W8jUqiZJXIMwu3923Qfuq_lnFCDOKtf3kyw4g"
        key = self.api.keys._coerce_key({
            'label': "sharing key",
            'api_key': key_id
        })
        key.delete()
        self.request.assert_called_with('DELETE', BASE_URL + '/keys/' + key_id)


class KeyManagerTest(BaseTestCase):

    def test_create_key(self):
        self.response.status_code = 201
        self.response.headers['Location'] = (
            BASE_URL + '/keys/1nAYR5W8jUqiZJXIMwu3923Qfuq_lnFCDOKtf3kyw4g')
        key = self.api.keys.create(
            label="sharing key",
            private_access=True,
            permissions=[
                xively.Permission(
                    access_methods=['put'],
                    source_ip="128.44.98.129",
                    resources=[xively.Resource(feed_id=504)]),
                xively.Permission(access_methods=['get']),
            ])
        self.request.assert_called_with(
            'POST', BASE_URL + '/keys',
            data=self._sorted_json(fixtures.CREATE_KEY_JSON))
        self.assertEqual(key.api_key,
                         "1nAYR5W8jUqiZJXIMwu3923Qfuq_lnFCDOKtf3kyw4g")

    def test_create_key_from_dict(self):
        self.response.status_code = 201
        self.response.headers['Location'] = (
            BASE_URL + '/keys/1nAYR5W8jUqiZJXIMwu3923Qfuq_lnFCDOKtf3kyw4g')
        key = self.api.keys.create(
            label="sharing key",
            private_access=True,
            permissions=[{
                'access_methods': ['put'],
                'source_ip': "128.44.98.129",
                'resources': [{'feed_id': 504}]
            },
                xively.Permission(access_methods=['get']),
            ])
        self.request.assert_called_with(
            'POST', BASE_URL + '/keys',
            data=self._sorted_json(fixtures.CREATE_KEY_JSON))
        self.assertEqual(key.api_key,
                         "1nAYR5W8jUqiZJXIMwu3923Qfuq_lnFCDOKtf3kyw4g")

    def test_list_keys(self):
        self.response.raw = BytesIO(fixtures.LIST_KEYS_JSON)
        keys = list(self.api.keys.list())
        self.request.assert_called_with(
            'GET', BASE_URL + '/keys', allow_redirects=True, params={})
        self.assertEqual(keys[0].api_key,
                         "CeWzga_cNja15kjwSVN5x5Mut46qj5akqKPvFxKIec0")
        self.assertEqual(keys[0].label, "sharing key 1")
        self.assertEqual(keys[0].permissions[0].access_methods, ['get'])
        self.assertEqual(keys[1].api_key,
                         "zR9eEw3WfrSY1-abcdefghasdfaoisdj109usasdf0a9sf")
        self.assertEqual(keys[1].label, "sharing key 2")
        self.assertEqual(keys[1].permissions[0].access_methods, ['put'])
        self.assertEqual(keys[1].permissions[0].source_ip, "123.12.123.123")

    def test_view_key(self):
        self.response.raw = BytesIO(fixtures.GET_KEY_JSON)
        key_id = "CeWzga_cNja15kjwSVN5x5Mut46qj5akqKPvFxKIec0"
        key = self.api.keys.get(key_id)
        self.request.assert_called_with(
            'GET', BASE_URL + "/keys/" + key_id, allow_redirects=True)
        self.assertEqual(key.api_key, key_id)
        self.assertEqual(key.label, "sharing key")
        self.assertEqual(key.permissions[0].access_methods, ['get', 'put'])

    def test_delete_key(self):
        key_id = "CeWzga_cNja15kjwSVN5x5Mut46qj5akqKPvFxKIec0"
        self.api.keys.delete(key_id)
        self.request.assert_called_with('DELETE', BASE_URL + '/keys/' + key_id)


class PermissionTest(BaseTestCase):

    def test_create_permission(self):
        permission = xively.Permission(['get'])
        self.assertEqual(permission.access_methods, ['get'])


class ResourceTest(BaseTestCase):

    def test_create_resource(self):
        resource = xively.Resource(feed_id=424, datastream_id="fan1")
        self.assertEqual(resource.feed_id, 424)
        self.assertEqual(resource.datastream_id, "fan1")


class LocationTest(BaseTestCase):

    def test_create_location(self):
        location = xively.Location(
            name="office",
            domain="physical",
            exposure="indoor",
            disposition="fixed",
            lat=51.5235375648154,
            lon=-0.0807666778564453,
            ele="23.0")
        self.assertEqual(location.name, "office")


class WaypointTest(BaseTestCase):

    def test_create_waypoint(self):
        waypoint = xively.Waypoint(
            at=datetime(2012, 6, 1, 13, 40, 4, 589002),
            lat=51.5235375648154,
            lon=-0.0807666778564453)
        self.assertEqual(waypoint.at, datetime(2012, 6, 1, 13, 40, 4, 589002))
        self.assertEqual(waypoint.lat, 51.5235375648154)
        self.assertEqual(waypoint.lon, -0.0807666778564453)


class UnitTest(BaseTestCase):

    def test_create_unit(self):
        unit = xively.Unit(label='Celsius', type='basicSI', symbol='C')
        self.assertEqual(unit.label, 'Celsius')
        self.assertEqual(unit.type, 'basicSI')
        self.assertEqual(unit.symbol, 'C')


class ExceptionsWrapperTest(unittest.TestCase):

    def test_call_success(self):
        @ExceptionsWrapper()
        def func():
            pass
        try:
            func()
        except:
            self.fail("No exception was expected")

    def test_call_exception_ignored(self):
        @ExceptionsWrapper()
        def func():
            error = requests.HTTPError()
            error.response = requests.Response()
            error.response.status_code = 408  # Teapot.
            raise error
        self.assertRaises(requests.HTTPError, func)

    def test_call_exception_wrapped(self):
        @ExceptionsWrapper()
        def func():
            error = requests.HTTPError()
            error.response = requests.Response()
            error.response.status_code = 404
            error.response.raw = BytesIO(fixtures.NOT_FOUND_JSON)
            raise error
        self.assertRaises(ResourceNotFound, func)


class DoesNotExistExceptionTest(BaseTestCase):

    def setUp(self):  # NOQA
        super(DoesNotExistExceptionTest, self).setUp()
        self.response.status_code = 404
        self.response.raw = BytesIO(fixtures.NOT_FOUND_JSON)
        self.feed = self._create_feed(id=7021, title="Rother")
        self.datastream = self._create_datastream(id='1')

    def test_get_feed(self):
        self.assertRaises(ResourceNotFound, self.api.feeds.get, 666)

    def test_update_feed(self):
        with self.assertRaises(ResourceNotFound):
            self.api.feeds.update(51, title="Doesn't exist")

    def test_delete_feed(self):
        self.assertRaises(ResourceNotFound, self.api.feeds.delete, 51)

    def test_mobile_feed(self):
        with self.assertRaises(ResourceNotFound):
            self.api.feeds.get(666, duration='1day')

    def test_create_datastream(self):
        with self.assertRaises(ResourceNotFound):
            self.feed.datastreams.create(id="feed_doesnt_exist")

    def test_update_datastream(self):
        with self.assertRaises(ResourceNotFound):
            self.feed.datastreams.update("datastream_doesnt_exist")

    def test_list_datastreams(self):
        with self.assertRaises(ResourceNotFound):
            list(self.feed.datastreams.list())

    def test_view_datastream(self):
        with self.assertRaises(ResourceNotFound):
            self.feed.datastreams.get("datastream_doesnt_exist")

    def test_delete_datastream(self):
        with self.assertRaises(ResourceNotFound):
            self.feed.datastreams.delete("datastream_doesnt_exist")

    def test_create_datapoint(self):
        with self.assertRaises(ResourceNotFound):
            self.datastream.datapoints.create(value="42")

    def test_update_datapoint(self):
        now = datetime.now()
        with self.assertRaises(ResourceNotFound):
            self.datastream.datapoints.update(at=now, value="42")

    def test_datapoint_history(self):
        with self.assertRaises(ResourceNotFound):
            list(self.datastream.datapoints.history())

    def test_view_datapoint(self):
        now = datetime.now()
        with self.assertRaises(ResourceNotFound):
            self.datastream.datapoints.get(at=now)

    def test_delete_datapoint(self):
        now = datetime.now()
        with self.assertRaises(ResourceNotFound):
            self.datastream.datapoints.delete(at=now)

    def test_create_trigger(self):
        with self.assertRaises(ResourceNotFound):
            self.api.triggers.create(666, "0", url='http://example.com',
                                     trigger_type='lt')

    def test_view_trigger(self):
        with self.assertRaises(ResourceNotFound):
            self.api.triggers.get(666)

    def test_update_trigger(self):
        with self.assertRaises(ResourceNotFound):
            self.api.triggers.update(666, threshold_value="20.0")

    def test_list_triggers_for_feed(self):
        with self.assertRaises(ResourceNotFound):
            list(self.api.triggers.list())

    def test_delete_trigger(self):
        with self.assertRaises(ResourceNotFound):
            self.api.triggers.delete(666)

    def test_create_key(self):
        with self.assertRaises(ResourceNotFound):
            self.api.keys.create("doesn't exist", [])

    def test_list_keys(self):
        with self.assertRaises(ResourceNotFound):
            list(self.api.keys.list())

    def test_view_key(self):
        with self.assertRaises(ResourceNotFound):
            self.api.keys.get(666)

    def test_delete_key(self):
        with self.assertRaises(ResourceNotFound):
            self.api.keys.delete(666)


class JSONEncoderTest(unittest.TestCase):

    def setUp(self):  # NOQA
        self.encoder = xively.client.JSONEncoder(sort_keys=True)

    def test_encode_datetime(self):
        encoded = self.encoder.encode(datetime(2013, 5, 22, 18, 32, 10, 12345))
        self.assertEqual(encoded, '"2013-05-22T18:32:10.012345Z"')

    def test_encode_state(self):
        class StatefulObject(object):
            def __init__(self, **kwargs):
                self.state = kwargs

            def __getstate__(self):
                return self.state
        encoded = self.encoder.encode(StatefulObject(state='MA'))
        self.assertEqual(encoded, '{"state": "MA"}')

    def test_encode_default(self):
        class OtherObject(object):
            pass
        with self.assertRaises(TypeError):
            self.encoder.encode(OtherObject())
