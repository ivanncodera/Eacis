import pytest
from eacis.validation import validate_password_complexity, validate_seller_product_payload


def test_password_too_short():
    err = validate_password_complexity('Ab1!')
    assert err is not None
    assert 'at least 8 characters' in err


def test_password_missing_requirements():
    err = validate_password_complexity('abcdefgh')  # 8 lowercase letters
    assert err is not None
    assert 'at least one uppercase letter' in err
    assert 'at least one number' in err
    assert 'at least one special character' in err


def test_password_contains_email():
    err = validate_password_complexity('MyEmail!1', confirm_pwd='MyEmail!1', email_local='myemail')
    assert err is not None
    assert 'email address' in err


def test_password_confirm_mismatch():
    err = validate_password_complexity('GoodPass1!', confirm_pwd='BadPass1!')
    assert err is not None
    assert 'Passwords do not match' in err


def test_password_valid():
    err = validate_password_complexity('GoodPass1!', confirm_pwd='GoodPass1!', email_local='other', first_nm='John', last_nm='Doe')
    assert err is None


def test_seller_product_price_zero():
    payload = {'name': 'ProductX', 'category': 'Cat', 'price': '0', 'stock': '10', 'warranty_months': '12', 'is_active': '1'}
    errors, norm = validate_seller_product_payload(payload)
    assert 'price' in errors
    assert errors['price'] == 'Price must be greater than ₱0.'
    assert norm['price'] == 0.0


def test_seller_product_compare_price_error():
    payload = {'name': 'ProductY', 'category': 'Cat', 'price': '100', 'compare_price': '100', 'stock': '10'}
    errors, norm = validate_seller_product_payload(payload)
    assert 'compare_price' in errors


def test_seller_product_compare_price_valid():
    payload = {'name': 'ProductZ', 'category': 'Cat', 'price': '100', 'compare_price': '150', 'stock': '10'}
    errors, norm = validate_seller_product_payload(payload)
    assert 'compare_price' not in errors
    assert norm['compare_price'] == 150.0


def test_seller_product_invalid_price_parse():
    payload = {'name': 'ProductValid', 'category': 'Cat', 'price': 'abc', 'stock': '10'}
    errors, norm = validate_seller_product_payload(payload)
    assert 'price' in errors
    assert norm['price'] == -1
