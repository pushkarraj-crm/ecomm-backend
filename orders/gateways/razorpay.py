import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings


class RazorpayGatewayError(Exception):
    status_code = 502

    def __init__(self, message, status_code=None, definitive=False):
        super().__init__(message)
        self.status_code = status_code or type(self).status_code
        self.definitive = definitive


class RazorpayConfigurationError(RazorpayGatewayError):
    status_code = 503

    def __init__(self, message):
        super().__init__(message, definitive=True)


class RazorpayGateway:
    API_BASE_URL = 'https://api.razorpay.com/v1'

    def __init__(self):
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        if not self.key_id or not self.key_secret:
            raise RazorpayConfigurationError('Razorpay API keys are not configured.')

    def create_order(self, amount_paise, currency, receipt):
        return self._request(
            method='POST',
            path='/orders',
            payload={
                'amount': amount_paise,
                'currency': currency,
                'receipt': receipt,
                'notes': {'source': 'marketplace-api'},
            },
        )

    def fetch_payment(self, payment_id):
        return self._request(
            method='GET',
            path=f'/payments/{quote(payment_id, safe="")}',
        )

    def create_refund(self, payment_id, amount_paise, notes):
        return self._request(
            method='POST',
            path=f'/payments/{quote(payment_id, safe="")}/refund',
            payload={
                'amount': amount_paise,
                'notes': notes,
            },
        )

    def verify_payment_signature(self, order_id, payment_id, signature):
        message = f'{order_id}|{payment_id}'.encode('utf-8')
        expected_signature = hmac.new(
            self.key_secret.encode('utf-8'),
            message,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def _request(self, method, path, payload=None):
        credentials = base64.b64encode(
            f'{self.key_id}:{self.key_secret}'.encode('utf-8')
        ).decode('ascii')
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = Request(
            f'{self.API_BASE_URL}{path}',
            data=body,
            method=method,
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )

        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
        except HTTPError as error:
            raise RazorpayGatewayError(
                'Unable to complete the Razorpay request.',
                definitive=400 <= error.code < 500,
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            raise RazorpayGatewayError('Unable to complete the Razorpay request.') from error

        if not isinstance(result, dict):
            raise RazorpayGatewayError('Razorpay returned an invalid response.')
        return result
