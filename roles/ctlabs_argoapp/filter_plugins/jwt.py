#!/usr/bin/env python3

# JWK / JWKS -> PEM, for Vault's jwt_validation_pubkeys.
#
# The cluster's service-account signing key only exists as JWK at
# /openid/v1/jwks (rsa n+e, base64url), but jwt_validation_pubkeys takes a
# list of PEM SPKI blocks. Runs on the controller inside the vault role, so
# the only dependency is cryptography, which the role installs on its target
# anyway (python3-cryptography) and which ansible itself ships.

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64url_decode(data):
  if isinstance(data, str):
    data = data.encode('ascii')
  # base64url without padding -- len % 4 is 2 or 3 for unpadded JWK members.
  return base64.urlsafe_b64decode(data + b'=' * (-len(data) % 4))


def _jwk_to_pem(jwk):
  # Only signature keys: an encryption key in the same JWKS would be accepted
  # by Vault and simply never match anything.
  if jwk.get('kty') != 'RSA' or jwk.get('use') not in (None, 'sig'):
    return None
  if not jwk.get('n') or not jwk.get('e'):
    return None
  numbers = rsa.RSAPublicNumbers(
    int.from_bytes(_b64url_decode(jwk['e']), 'big'),
    int.from_bytes(_b64url_decode(jwk['n']), 'big'),
  )
  return numbers.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
  ).decode('ascii')


def jwks_to_pems(jwks):
  if isinstance(jwks, dict):
    keys = jwks.get('keys', [])
  elif isinstance(jwks, list):
    keys = jwks
  else:
    keys = []
  pems = []
  for jwk in keys:
    if not isinstance(jwk, dict):
      continue
    pem = _jwk_to_pem(jwk)
    if pem is not None:
      pems.append(pem)
  return pems


class FilterModule(object):
  def filters(self):
    return {
      'jwks_to_pems': jwks_to_pems
    }
