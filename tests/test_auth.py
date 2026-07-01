import unittest

from app import app
from models.user import User, db


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
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

        logout_response = self.client.get('/logout', follow_redirects=False)
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
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password must be at least 8 characters long.', response.data)

    def test_login_with_invalid_credentials(self):
        response = self.client.post(
            '/login',
            data={'email': 'missing@example.com', 'password': 'wrongpassword'},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid login credentials', response.data)


if __name__ == '__main__':
    unittest.main()
