#!/usr/bin/env python3
import os
import sys
import pathlib
import io
from time import time

# ensure project root is on sys.path so `import eacis` works when run from tools/
pkg_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_root))
from eacis.app import create_app

app = create_app()

with app.app_context():
    # ensure DB tables exist so upload/delete endpoints can work in tests
    try:
        from eacis.extensions import db
    except Exception:
        from extensions import db

    # import models (so SQLAlchemy metadata is populated) then create tables
    try:
        from eacis.models.user import User
        from eacis.models.product import Product
        from eacis.models.product_image import ProductImage
    except Exception:
        from models.user import User
        from models.product import Product
        from models.product_image import ProductImage

    db.create_all()

    # Create test seller and product (if not exists)
    seller = User.query.filter_by(email='seller_test@example.com').first()
    if not seller:
        seller = User(email='seller_test@example.com', role='seller', full_name='Test Seller')
        seller.set_password('password')
        seller.seller_verification_status = 'approved'
        db.session.add(seller)
        db.session.commit()
    else:
        # ensure seller is approved so seller-restricted routes are accessible
        if getattr(seller, 'seller_verification_status', '') in ('pending', 'rejected'):
            seller.seller_verification_status = 'approved'
            db.session.commit()

    product_ref = 'TEST-UPLOAD'
    product = Product.query.filter_by(product_ref=product_ref).first()
    if not product:
        product = Product(product_ref=product_ref, seller_id=seller.id, name='Test Product', price=100)
        db.session.add(product)
        db.session.commit()

    # disable CSRF for test client runs
    app.config['WTF_CSRF_ENABLED'] = False
    # enable upload debug prints in the app
    app.config['DEBUG_UPLOADS'] = True
    client = app.test_client()

    # log in the test seller by setting session keys used by flask-login
    with client.session_transaction() as sess:
        sess['_user_id'] = str(seller.id)
        sess['_fresh'] = True

    # verify authentication by requesting a seller-only page
    auth_check = client.get(f'/seller/products/{product_ref}', follow_redirects=True)
    try:
        auth_body = auth_check.get_data(as_text=True)
        print('AUTH_CHECK_STATUS', auth_check.status_code)
        print('AUTH_CHECK_CONTAINS_LOGIN', 'Sign in' in auth_body or 'Sign In' in auth_body or 'Login' in auth_body)
    except Exception:
        pass

    # Perform upload
    upload_dir = os.path.join(app.instance_path, 'uploads', 'products', product_ref)
    os.makedirs(upload_dir, exist_ok=True)
    data = {'file': (io.BytesIO(b'\xff\xd8\xff'), 'upload.jpg')}
    # let the test client set the multipart boundary for us
    resp = client.post(f'/seller/products/{product_ref}/images/upload', data=data)
    print('UPLOAD_STATUS', resp.status_code)
    print('UPLOAD_HEADERS', dict(resp.headers))
    try:
        print('UPLOAD_JSON', resp.get_json())
    except Exception:
        try:
            print('UPLOAD_BODY', resp.get_data(as_text=True)[:800])
        except Exception:
            pass

    imgs = ProductImage.query.filter_by(product_id=product.id).all()
    print('DB_IMAGES_AFTER_UPLOAD', len(imgs))

    # list files on disk and check whether the product_images table exists
    try:
        print('UPLOAD_DIR_LISTING', os.listdir(upload_dir))
    except Exception as e:
        print('UPLOAD_DIR_LISTING_ERROR', e)
    try:
        from sqlalchemy import inspect as sqlalchemy_inspect
        print('TABLE_product_images_exists', sqlalchemy_inspect(db.engine).has_table('product_images'))
    except Exception as e:
        print('TABLE_INSPECT_ERROR', e)

    if imgs:
        img = imgs[0]
        fpath = os.path.join(app.instance_path, 'uploads', 'products', product_ref, img.filename)
        print('FILE_EXISTS', os.path.exists(fpath))

        # delete via endpoint
        resp2 = client.post(f'/seller/products/{product_ref}/images/{img.id}/delete', follow_redirects=True)
        print('DELETE_STATUS', resp2.status_code)
        exists_after = os.path.exists(fpath)
        print('FILE_EXISTS_AFTER_DELETE', exists_after)
        imgs_after = ProductImage.query.filter_by(product_id=product.id).count()
        print('DB_IMAGES_AFTER_DELETE', imgs_after)

    # If no DB record or file was created, try uploading using a real temporary file
    if len(imgs) == 0:
        tmp_path = os.path.join(app.instance_path, 'uploads', 'products', product_ref, f'tmp_{int(time())}.jpg')
        try:
            with open(tmp_path, 'wb') as tf:
                tf.write(b'\xff\xd8\xff')
            with open(tmp_path, 'rb') as fobj:
                data2 = {'file': (fobj, 'upload2.jpg')}
                respb = client.post(f'/seller/products/{product_ref}/images/upload', data=data2, follow_redirects=True)
                print('UPLOAD2_STATUS', respb.status_code)
            imgs2 = ProductImage.query.filter_by(product_id=product.id).all()
            print('DB_IMAGES_AFTER_UPLOAD2', len(imgs2))
            try:
                print('UPLOAD_DIR_LISTING_AFTER2', os.listdir(upload_dir))
            except Exception as e:
                print('UPLOAD_DIR_LISTING_AFTER2_ERROR', e)
        except Exception as e:
            print('UPLOAD2_ERROR', e)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        # If the file exists on disk but no DB record was created, try inserting a ProductImage record directly
        try:
            files = os.listdir(upload_dir)
            if files:
                fname = files[0]
                print('ATTEMPT_MANUAL_DB_INSERT', fname)
                manual_img = ProductImage(product_id=product.id, filename=fname, position=1)
                db.session.add(manual_img)
                db.session.commit()
                print('MANUAL_INSERTED_COUNT', ProductImage.query.filter_by(product_id=product.id).count())
        except Exception as e:
            print('MANUAL_INSERT_ERROR', e)

    # leave test data in DB for inspection if needed
    # raw SQL check for rows in product_images table
    try:
        from sqlalchemy import text
        rows = db.session.execute(text('SELECT id, product_id, filename, position FROM product_images')).fetchall()
        print('RAW_PRODUCT_IMAGES_ROWS', rows)
    except Exception as e:
        print('RAW_PRODUCT_IMAGES_QUERY_ERROR', e)

    # Try a direct manual insert to verify DB commit path
    try:
        manual_img = ProductImage(product_id=product.id, filename='manual_test.jpg', position=1)
        db.session.add(manual_img)
        db.session.commit()
        print('MANUAL_INSERTED_COUNT', ProductImage.query.filter_by(product_id=product.id).count())
        # cleanup manual test row
        try:
            db.session.delete(manual_img)
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception as e:
        print('MANUAL_INSERT_ERROR', e)
