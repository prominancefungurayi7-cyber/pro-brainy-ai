import unittest
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app import app
from models.user import SignupSignal, User, db
from services.auth_security import _client_ip
from tests.helpers import csrf_token


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.get('/register')
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_register_login_and_logout_flow(self):
        register_response = self.client.post(
            '/register',
            data={
                'username': 'testuser',
                'email': 'test@example.com',
                'password': 'securepass123',
                '_csrf_token': csrf_token(self.client),
            },
            follow_redirects=False,
        )
        self.assertEqual(register_response.status_code, 302)

        with app.app_context():
            user = User.query.filter_by(email='test@example.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.username, 'testuser')

        dashboard_response = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(dashboard_response.status_code, 200)

        logout_response = self.client.post('/logout', data={'_csrf_token': csrf_token(self.client)}, follow_redirects=False)
        self.assertEqual(logout_response.status_code, 302)

        protected_response = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(protected_response.status_code, 302)

    def test_register_rejects_short_password(self):
        response = self.client.post(
            '/register',
            data={
                'username': 'testuser',
                'email': 'short@example.com',
                'password': 'short',
                '_csrf_token': csrf_token(self.client),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password must be at least 12 characters long.', response.data)

    def test_login_with_invalid_credentials(self):
        response = self.client.post(
            '/login',
            data={'email': 'missing@example.com', 'password': 'wrongpassword', '_csrf_token': csrf_token(self.client)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid login credentials', response.data)

    def test_login_checks_dummy_hash_for_unknown_account(self):
        with patch('routes.auth_routes.check_password_hash', return_value=False) as check:
            response = self.client.post('/login', data={
                'email': 'missing@example.com', 'password': 'wrongpassword',
                '_csrf_token': csrf_token(self.client),
            })
        self.assertEqual(response.status_code, 302)
        check.assert_called_once()

    def test_existing_account_with_legacy_email_can_still_log_in(self):
        with app.app_context():
            db.session.add(User(username='Legacy', email='legacy@example',
                                password=generate_password_hash('securepass123')))
            db.session.commit()
        response = self.client.post('/login', data={
            'email': 'legacy@example', 'password': 'securepass123',
            '_csrf_token': csrf_token(self.client),
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.headers['Location'])

    def test_registration_rejects_malformed_email(self):
        for address in ('a@@example.com', 'a@example', 'a@.example.com',
                        'a@example..com', 'a@example.com extra'):
            with self.subTest(address=address):
                response = self.client.post('/register', data={
                    '_csrf_token': csrf_token(self.client),
                    'username': 'Valid Name', 'email': address, 'password': 'securepass123',
                }, follow_redirects=True)
                self.assertIn(b'check your account details', response.data)
        with app.app_context():
            self.assertEqual(User.query.count(), 0)

    def test_registration_rolls_back_duplicate_insert_race(self):
        with patch.object(db.session, 'flush', side_effect=IntegrityError('duplicate', {}, None)):
            response = self.client.post('/register', data={
                '_csrf_token': csrf_token(self.client),
                'username': 'Race', 'email': 'race@example.com', 'password': 'securepass123',
            })
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(User.query.count(), 0)

    def test_render_client_ip_uses_validated_forwarded_address(self):
        with app.test_request_context('/login', headers={
            'X-Forwarded-For': '203.0.113.8, 10.0.0.1',
        }, environ_base={'REMOTE_ADDR': '10.0.0.2'}):
            with patch.dict('os.environ', {'RENDER': 'true'}):
                self.assertEqual(_client_ip(), '203.0.113.8')
            with patch.dict('os.environ', {'RENDER': ''}):
                self.assertEqual(_client_ip(), '10.0.0.2')
        with app.test_request_context('/login', headers={
            'X-Forwarded-For': 'not-an-ip, 10.0.0.1',
        }, environ_base={'REMOTE_ADDR': '10.0.0.2'}):
            with patch.dict('os.environ', {'RENDER': 'true'}):
                self.assertEqual(_client_ip(), '10.0.0.2')
        with app.test_request_context('/login', environ_base={'REMOTE_ADDR': '10.0.0.2'}):
            with patch.dict('os.environ', {'RENDER': 'true'}):
                self.assertEqual(_client_ip(), '10.0.0.2')

    def test_tool_requires_login(self):
        for path in ('/humanizer', '/detector', '/grammar', '/essay', '/composition', '/summarizer', '/resume', '/ppt'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.headers['Location'])

    def test_one_login_opens_every_tool_and_restores_a_lost_session_cookie(self):
        self.client.environ_base['wsgi.url_scheme'] = 'https'
        register_response = self.client.post('/register', data={
            '_csrf_token': csrf_token(self.client),
            'username': 'Member', 'email': 'member@example.com', 'password': 'securepass123',
        })
        self.assertEqual(register_response.status_code, 302)
        self.assertIsNotNone(self.client.get_cookie('remember_token'))
        self.client.delete_cookie('session')
        for path in ('/dashboard', '/humanizer', '/detector', '/grammar', '/essay',
                     '/composition', '/summarizer', '/resume', '/ppt'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        logout = self.client.post('/logout', data={'_csrf_token': csrf_token(self.client)})
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(self.client.get('/humanizer').status_code, 302)

    def test_remember_cookie_is_secure_when_sessions_are_secure(self):
        self.client.environ_base['wsgi.url_scheme'] = 'https'
        with patch.dict(app.config, {
            'SESSION_COOKIE_SECURE': True, 'REMEMBER_COOKIE_SECURE': True,
        }):
            response = self.client.post('/register', data={
                '_csrf_token': csrf_token(self.client),
                'username': 'Secure Member', 'email': 'secure@example.com', 'password': 'securepass123',
            })
        remember_header = next(header for header in response.headers.getlist('Set-Cookie')
                               if header.startswith('remember_token='))
        session_header = next(header for header in response.headers.getlist('Set-Cookie')
                              if header.startswith('session='))
        self.assertIn('Secure', remember_header)
        self.assertIn('HttpOnly', remember_header)
        self.assertIn('SameSite=Lax', remember_header)
        self.assertIn('Secure', session_header)
        self.assertIn('Expires=', session_header)

    def test_post_requires_csrf_token(self):
        response = self.client.post('/register', data={
            'username': 'missingtoken', 'email': 'missing@example.com', 'password': 'securepass123',
        })
        self.assertEqual(response.status_code, 400)

    def test_same_name_on_same_browser_is_blocked(self):
        self.client.post('/register', data={
            '_csrf_token': csrf_token(self.client),
            'username': 'Same Name', 'email': 'one@example.com', 'password': 'securepass123',
        })
        self.client.post('/logout', data={'_csrf_token': csrf_token(self.client)})
        self.client.get('/register')
        response = self.client.post('/register', data={
            '_csrf_token': csrf_token(self.client),
            'username': '  same   name ', 'email': 'two@example.com', 'password': 'securepass123',
        }, follow_redirects=True)
        self.assertIn(b'Registration limit reached', response.data)
        with app.app_context():
            self.assertEqual(User.query.count(), 1)

    def test_login_is_throttled_after_repeated_failures(self):
        for _ in range(5):
            response = self.client.post('/login', data={
                '_csrf_token': csrf_token(self.client),
                'email': 'absent@example.com', 'password': 'wrong-password',
            })
            self.assertEqual(response.status_code, 302)
        response = self.client.post('/login', data={
            '_csrf_token': csrf_token(self.client),
            'email': 'absent@example.com', 'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 429)

    def test_browser_signup_limit(self):
        for index in range(3):
            response = self.client.post('/register', data={
                '_csrf_token': csrf_token(self.client),
                'username': f'Person {index}',
                'email': f'person{index}@example.com',
                'password': 'securepass123',
            })
            self.assertEqual(response.status_code, 302)
            self.client.post('/logout', data={'_csrf_token': csrf_token(self.client)})
            self.client.get('/register')
        response = self.client.post('/register', data={
            '_csrf_token': csrf_token(self.client),
            'username': 'Person 4', 'email': 'person4@example.com',
            'password': 'securepass123',
        }, follow_redirects=True)
        self.assertIn(b'Registration limit reached', response.data)

    def test_same_name_across_browsers_is_flagged_not_blocked(self):
        self.client.post('/register', data={
            '_csrf_token': csrf_token(self.client),
            'username': 'Common Name', 'email': 'first@example.com',
            'password': 'securepass123',
        })
        other = app.test_client()
        other.get('/register')
        response = other.post('/register', data={
            '_csrf_token': csrf_token(other),
            'username': 'common  name', 'email': 'second@example.com',
            'password': 'securepass123',
        })
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(User.query.count(), 2)
            self.assertTrue(SignupSignal.query.filter_by(user_id=2).one().duplicate_name_seen)


if __name__ == '__main__':
    unittest.main()
