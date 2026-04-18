from eacis.validation import validate_registration_payload


def test_customer_registration_requires_address_and_valid_fields():
    payload = {
        'first_name': 'John',
        'last_name': 'Doe',
        'address_line1': '12',  # too short
        'barangay': '',  # missing
        'city_municipality': 'Q',  # too short
        'province': 'M',  # too short
        'postal_code': '12',  # invalid
        'email': 'newuser@example.com',
        'password': 'Password1!',
        'confirm_password': 'Password1!',
        'terms_consent': '1',
        'privacy_consent': '1',
        'phone': '09171234567',
    }

    errors, normalized = validate_registration_payload(
        payload,
        'customer',
        postal_lookup={'quezon city': '1100'},
        email_exists=lambda e: False,
    )

    assert 'address_line1' in errors
    assert 'barangay' in errors
    assert 'city_municipality' in errors
    assert 'province' in errors
    assert 'postal_code' in errors


def test_password_must_not_contain_name_or_email_localpart():
    payload = {
        'first_name': 'Alice',
        'last_name': 'Walker',
        'address_line1': '123 Sample Street',
        'barangay': 'San Isidro',
        'city_municipality': 'Quezon City',
        'province': 'Metro Manila',
        'postal_code': '1100',
        'email': 'alice@example.com',
        'password': 'alice12345!',
        'confirm_password': 'alice12345!',
        'terms_consent': '1',
        'privacy_consent': '1',
        'phone': '09171234567',
    }

    errors, normalized = validate_registration_payload(
        payload,
        'customer',
        postal_lookup={'quezon city': '1100'},
        email_exists=lambda e: False,
    )

    assert 'password' in errors
