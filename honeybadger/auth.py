"""Auth Module.

Handles all authorization and authentication concerns.

"""

import base64
import hashlib
import os
import json
import requests

from flask import Blueprint, redirect, url_for, g, render_template, session, request
from functools import wraps

from honeybadger.services import get_access_token
from honeybadger.config import ConfigurationFactory
from honeybadger.logger import logger

bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logger()


def code_verifier(n_bytes=64):
    """
    Generates a 'code_verifier' as described in section 4.1 of RFC 7636.
    This is a 'high-entropy cryptographic random string' that will be
    impractical for an attacker to guess.
    Args:
        n_bytes: integer between 31 and 96, inclusive. default: 64
            number of bytes of entropy to include in verifier.
    Returns:
        Bytestring, representing urlsafe base64-encoded random data.
    """
    verifier = base64.urlsafe_b64encode(os.urandom(n_bytes)).rstrip(b'=')
    # https://tools.ietf.org/html/rfc7636#section-4.1
    # minimum length of 43 characters and a maximum length of 128 characters.
    if len(verifier) < 43:
        raise ValueError("Verifier too short. n_bytes must be > 30.")
    elif len(verifier) > 128:
        raise ValueError("Verifier too long. n_bytes must be < 97.")
    else:
        return verifier


def code_challenge(verifier):
    """
    Creates a 'code_challenge' as described in section 4.2 of RFC 7636
    by taking the sha256 hash of the verifier and then urlsafe
    base64-encoding it.
    Args:
        verifier: bytestring, representing a code_verifier as generated by
            code_verifier().
    Returns:
        Bytestring, representing a urlsafe base64-encoded sha256 hash digest,
            without '=' padding.
    """
    digest = hashlib.sha256(verifier).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=')


def code_verifier(n_bytes=64):
    """
    Generates a 'code_verifier' as described in section 4.1 of RFC 7636.
    This is a 'high-entropy cryptographic random string' that will be
    impractical for an attacker to guess.
    Args:
        n_bytes: integer between 31 and 96, inclusive. default: 64
            number of bytes of entropy to include in verifier.
    Returns:
        Bytestring, representing urlsafe base64-encoded random data.
    """
    verifier = base64.urlsafe_b64encode(os.urandom(n_bytes)).rstrip(b'=')
    # https://tools.ietf.org/html/rfc7636#section-4.1
    # minimum length of 43 characters and a maximum length of 128 characters.
    if len(verifier) < 43:
        raise ValueError("Verifier too short. n_bytes must be > 30.")
    elif len(verifier) > 128:
        raise ValueError("Verifier too long. n_bytes must be < 97.")
    else:
        return verifier


def code_challenge(verifier):
    """
    Creates a 'code_challenge' as described in section 4.2 of RFC 7636
    by taking the sha256 hash of the verifier and then urlsafe
    base64-encoding it.
    Args:
        verifier: bytestring, representing a code_verifier as generated by
            code_verifier().
    Returns:
        Bytestring, representing a urlsafe base64-encoded sha256 hash digest,
            without '=' padding.
    """
    digest = hashlib.sha256(verifier).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=')


def login_required(view):
    """View decorator that redirects unknown users to a simple login page."""

    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login', _external=True))
        return view(**kwargs)
    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    name = session.get('name')
    if name:
        g.user = name
    else:
        g.user = None


@bp.route('/login')
def login():
    if g.user:
        return redirect(url_for('mci.index'))
    # verifier = code_verifier()
    # challenge = code_challenge(verifier)
    # return render_template('auth/login.html', code_challenge=challenge, code_challenge_method='S256')
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    session.clear()
    g.user = None
    return redirect(url_for('auth.login'))


@bp.route('/callback')
def oauth2_callback():
    code = request.args.get('code')
    config = ConfigurationFactory.from_env()
    if code:
        data = {'client_id': config.github_client_id,
                'client_secret': config.github_client_secret,
                'code': code}
        headers = {'content-type': 'application/json',
                   'accept': 'application/json'}
        r = requests.post(config.github_oauth2_url,
                          headers=headers, data=json.dumps(data))
        token = r.json()['access_token']
        headers = {'content-type': 'application/json',
                   'authorization': 'token {}'.format(token)}
        r = requests.get(config.github_profile_url, headers=headers)
        session['name'] = r.json()['name']
        return redirect(url_for('home.index'))
    return redirect(url_for('auth.login'))


@bp.route('/redirect')
def oauth2_callback_bh():
    code = request.args.get('code')
    scope = request.args.get('scope')
    config = ConfigurationFactory.from_env()
    if code:
        # print('The code verifier is {}'.format(g.verifier))
        data = {'client_id': config.authserver_client_id,
                'grant_type': 'authorization_code',
                'code': code,
                'scope': scope,
                # 'code_verifier': CODE_VERIFIER,
                'redirect_uri': config.authserver_redirect_url}
        headers = {'content-type': 'application/x-www-form-urlencoded',
                   'accept': 'application/json'}
        r = requests.post(config.authserver_oauth2_url,
                          headers=headers, data=data)
        # print(r.json())
        logger.info(r.json())
        print(r.json())
        token = r.json()['access_token']
        headers = {'content-type': 'application/json',
                   'authorization': 'bearer {}'.format(token)}
        r = requests.get(config.authserver_profile_url, headers=headers)
        user_details = r.json()
        try:
            session['name'] = '{} {}'.format(
                user_details['firstname'], user_details['lastname'])
        except Exception:
            session['name'] = 'Unknown'
            logger.warn('User not currently logged in')

        return redirect(url_for('home.index'))
    return redirect(url_for('auth.login'))
