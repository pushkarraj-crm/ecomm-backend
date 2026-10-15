import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings


class RazorpayXError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


class RazorpayXConfigurationError(RazorpayXError):
    def __init__(self):
        super().__init__('RazorpayX bank verification is not configured.', status_code=503)


class RazorpayXGateway:
    API_BASE_URL = 'https://api.razorpay.com/v1'

    def __init__(self):
        self.key_id = settings.RAZORPAYX_KEY_ID
        self.key_secret = settings.RAZORPAYX_KEY_SECRET
        self.source_account_number = settings.RAZORPAYX_SOURCE_ACCOUNT_NUMBER
        if not self.key_id or not self.key_secret or not self.source_account_number:
            raise RazorpayXConfigurationError()

    def create_contact(self, name, email, reference_id):
        return self._request('POST', '/contacts', {
            'name': name[:50],
            'email': email,
            'type': 'vendor',
            'reference_id': reference_id[:40],
        })

    def create_bank_fund_account(self, contact_id, name, ifsc, account_number):
        return self._request('POST', '/fund_accounts', {
            'contact_id': contact_id,
            'account_type': 'bank_account',
            'bank_account': {
                'name': name,
                'ifsc': ifsc,
                'account_number': account_number,
            },
        })

    def create_account_validation(self, fund_account_id, amount_paise, seller_id):
        return self._request('POST', '/fund_accounts/validations', {
            'account_number': self.source_account_number,
            'fund_account': {'id': fund_account_id},
            'amount': amount_paise,
            'currency': 'INR',
            'notes': {
                'purpose': 'seller_bank_verification',
                'seller_id': str(seller_id),
            },
        })

    def fetch_account_validation(self, validation_id):
        return self._request(
            'GET',
            f'/fund_accounts/validations/{quote(validation_id, safe="")}',
        )

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
            raise RazorpayXError(
                'RazorpayX could not process the bank verification request.',
                status_code=502 if error.code >= 500 else 400,
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            raise RazorpayXError('Unable to reach RazorpayX for bank verification.') from error

        if not isinstance(result, dict):
            raise RazorpayXError('RazorpayX returned an invalid response.')
        return result
