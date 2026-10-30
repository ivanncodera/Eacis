from importlib import import_module

try:
    import_module('eacis.services.otp_service')
    print('OTP SERVICE IMPORT OK')
except Exception as e:
    print('IMPORT FAILED')
    raise
