#!/usr/bin/env python
from functools import reduce

__version__ = '0.2.1'

import requests
import xmltodict
import dateutil.parser
import lxml.builder as lb

from lxml import etree
from xml.parsers.expat import ExpatError


class SpreedlyError(Exception):

    """
    Exception Handling
    """

    def __init__(self, message=None, response=None):
        self.response = response
        self.code = response.status_code
        self.message = message

    def json(self):
        return Client.parse_xml(self.response)

    @property
    def is_formatted_error(self):
        return 'errors' in self.json()


class Client(object):

    """
    A client for the Spreedly API.

    See https://docs.spreedly.com
    for complete documentation for the API.
    """

    user_agent = 'SpreedlySdk/rest-sdk-spreedly 0.1'

    def __init__(self, environment_key, access_secret,
                 version='1', format_type='xml'):

        self.environment_key = environment_key
        self.access_secret = access_secret
        self.version = version
        self.format_type = format_type

    def endpoint(self, action):
        return 'https://core.spreedly.com/v{version}/{action}.{type}'.format(
            version=self.version, action=action, type=self.format_type)

    @property
    def headers(self):
        return {
            'User-Agent': self.user_agent,
            'Content-Type': 'application/' + self.format_type
        }

    @classmethod
    def _postprocessor(cls, item, key, data):
        if isinstance(data, dict):
            item_type = data.get('@type')

            if item_type == 'boolean':
                data = data['#text'] == 'true'

            elif item_type in ('dateTime', 'datetime'):
                data = dateutil.parser.parse(data['#text'])

            elif item_type == 'integer':
                data = int(data['#text'])

            elif data.get('@key'):
                data = {data['@key']: data['#text']}

            elif data.get('@nil'):
                data = None

        return key, data

    @classmethod
    def parse_xml(cls, response):
        return xmltodict.parse(
            response.text, postprocessor=cls._postprocessor,
            dict_constructor=dict)

    @classmethod
    def _dict_to_xml(cls, d, name='data'):
        def buildxml(r, d):
            if isinstance(d, dict):
                for k, v in d.items():
                    s = etree.SubElement(r, k)
                    buildxml(s, v)
            elif isinstance(d, tuple) or isinstance(d, list):
                for v in d:
                    s = etree.SubElement(r, 'i')
                    buildxml(s, v)
            elif isinstance(d, str):
                r.text = d
            else:
                r.text = str(d)
            return r
        r = etree.Element(name)
        return buildxml(r, d)

    def request(self, url, method, data=None, headers=None, **kwargs):
        http_headers = self.headers
        http_headers.update(headers or {})

        if data is not None:
            data = etree.tostring(data)

        response = requests.request(method, url, auth=(
            self.environment_key, self.access_secret),
            data=data, headers=http_headers, **kwargs)

        if response.status_code == 401:
            raise SpreedlyError('Unauthorized', response)

        if response.status_code == 402:
            raise SpreedlyError('Payment Required', response)

        if response.status_code == 422:
            raise SpreedlyError('Unprocessable', response)

        try:
            data = Client.parse_xml(response)
        except ExpatError:
            raise SpreedlyError('XML parse error', response)

        if not (200 <= response.status_code < 300):
            raise SpreedlyError('Client error', response)

        return data

    def get(self, action, params=None, headers=None):
        return self.request(self.endpoint(
            action), 'GET', params=None, headers=headers)

    def since(self, action, since_token=None):
        params = {}

        if since_token is not None:
            params['since_token'] = since_token

        return self.get(action, params=params)

    def post(self, action, data=None, headers=None):
        return self.request(self.endpoint(
            action), 'POST', data=data, headers=headers)

    def put(self, action, data=None, headers=None):
        return self.request(self.endpoint(
            action), 'PUT', data=data, headers=headers)

    def _nested(*keys):
        def wrap(f):
            def wrapped(self, *args, **kwargs):
                response = f(self, *args, **kwargs)
                return reduce(lambda d, k: d and d[k], keys, response)
            return wrapped
        return wrap

    @_nested('gateway')
    def gateway(self, gateway_type='test', **kwargs):
        data = lb.E.gateway(lb.E.gateway_type(gateway_type))

        for param, value in kwargs.items():
            etree.SubElement(data, param).text = value

        return self.post('gateways', data=data)

    @_nested('gateway')
    def get_gateway(self, gateway_token):
        return self.get("gateways/{}".format(gateway_token))

    @_nested('gateways', 'gateway')
    def get_gateway_list(self, since_token=None):
        return self.since('gateways', since_token)

    def update_gateway(self, gateway_token, login, password):
        data = lb.E.gateway(lb.E.login(login), lb.E.password(password))
        return self.put("gateways/{}".format(gateway_token), data=data)

    @_nested('transaction')
    def retain(self, gateway_token):
        return self.put("gateways/{}/retain".format(gateway_token))

    @_nested('transaction')
    def store(self, gateway_token, payment_method_token):
        data = lb.E.transaction(
            lb.E.payment_method_token(payment_method_token))
        return self.post("gateways/{}/store".format(
            gateway_token), data=data)

    @_nested('transaction')
    def redact(self, gateway_token):
        return self.put("gateways/{}/redact".format(gateway_token))

    @_nested('payment_method')
    def get_payment_method(self, payment_method):
        return self.get("payment_methods/{}".format(payment_method))

    @_nested('payment_methods', 'payment_method')
    def get_payment_method_list(self, since_token=None):
        """ API Issue: Empty list """
        return self.since('payment_methods', since_token)

    @_nested('transaction')
    def retain_payment_method(self, payment_method):
        return self.put("payment_methods/{}/retain".format(payment_method))

    @_nested('transaction')
    def verify(
            self, gateway_token, payment_method_token, retain_on_success=True):

        data = lb.E.transaction(
            lb.E.payment_method_token(payment_method_token))

        if retain_on_success:
            etree.SubElement(data, 'retain_on_success').text = 'true'

        return self.post("gateways/{}/verify".format(gateway_token), data=data)

    @_nested('transaction')
    def purchase(
        self, amount, currency_code, payment_method_token, gateway_token,
            retain_on_success=True, payment_type='purchase', gateway_specific_fields=None):

        data = lb.E.transaction(
            lb.E.amount(str(amount)),
            lb.E.currency_code(currency_code),
            lb.E.payment_method_token(payment_method_token))

        if retain_on_success:
            etree.SubElement(data, 'retain_on_success').text = 'true'

        if gateway_specific_fields:
            item_specific_fields = self._dict_to_xml(gateway_specific_fields, 'gateway_specific_fields')
            data.append(item_specific_fields)

        return self.post("gateways/{}/{}".format(
            gateway_token, payment_type), data=data)

    @_nested('transaction')
    def reference(self, amount, currency_code, transaction_token):
        data = lb.E.transaction(
            lb.E.amount(str(amount)),
            lb.E.currency_code(currency_code))

        return self.post("transactions/{}/purchase".format(
            transaction_token), data=data)

    def authorize(
        self, amount, currency_code, payment_method_token,
            gateway_token, retain_on_success=True, **kwargs):

        return self.purchase(
            amount, currency_code, payment_method_token,
            gateway_token, retain_on_success, payment_type='authorize', **kwargs)

    @_nested('transaction')
    def capture(self, transaction_token):
        return self.post("transactions/{}/capture".format(transaction_token))

    @_nested('transaction')
    def void(self, transaction_token):
        return self.post("transactions/{}/void".format(transaction_token))

    @_nested('transaction')
    def credit(self, transaction_token, amount=None):
        if amount is not None:
            data = lb.E.transaction(lb.E.amount(str(amount)))
        else:
            data = None
        return self.post("transactions/{}/credit".format(
            transaction_token), data=data)

    @_nested('transaction')
    def get_transaction(self, transaction_token):
        return self.get("transactions/{}".format(transaction_token))

    @_nested('transactions', 'transaction')
    def get_transaction_list(self, since_token=None):
        return self.since('transactions', since_token)

    @_nested('transactions', 'transaction')
    def get_payment_method_transaction_list(
            self, payment_method_token, since_token=None):
        action = "payment_methods/{}/transactions".format(payment_method_token)
        return self.since(action, since_token)

    @_nested('transactions', 'transaction')
    def get_gateway_transaction_list(self, gateway_token, since_token=None):
        action = "gateways/{}/transactions".format(gateway_token)
        return self.since(action, since_token)

    @_nested('transaction')
    def redact_payment_method(self, transaction_token, gateway_token=None):
        if gateway_token:
            data = lb.E.transaction(lb.E.remove_from_gateway(gateway_token))
        else:
            data = None
        return self.put("payment_methods/{}/redact".format(transaction_token), data)
