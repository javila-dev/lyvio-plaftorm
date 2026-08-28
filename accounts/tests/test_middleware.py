from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils import timezone
from django.conf import settings

from accounts.middleware import AutoLogoutMiddleware

User = get_user_model()

class AutoLogoutMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Ensure a predictable timeout for tests
        settings.AUTO_LOGOUT_DELAY = 2  # 2 seconds for fast tests
        self.middleware = AutoLogoutMiddleware(get_response=lambda r: r)

    def _add_session(self, request):
        """Attach a session to the request object (Django test RequestFactory needs this helper)."""
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()

    def test_authenticated_user_stays_when_active(self):
        # Create user and attach to request
        user = User.objects.create_user(username='user1', email='u@example.com', password='pass')
        request = self.factory.get('/')
        self._add_session(request)
        request.user = user

        # First call sets last_activity
        resp = self.middleware(request)
        self.assertIn('last_activity', request.session)

        # Call again immediately -> should still have last_activity and user unchanged
        resp = self.middleware(request)
        self.assertIn('last_activity', request.session)
        # user should remain authenticated in request (middleware doesn't replace request.user)
        self.assertTrue(hasattr(request, 'user'))

    def test_authenticated_user_logged_out_after_timeout(self):
        user = User.objects.create_user(username='user2', email='u2@example.com', password='pass')
        request = self.factory.get('/')
        self._add_session(request)
        request.user = user

        # Set last_activity in the past beyond the timeout
        past = (timezone.now().timestamp() - 10)
        request.session['last_activity'] = past
        request.session.save()

        # Middleware should logout and flush session
        resp = self.middleware(request)
        # After logout the session should be empty (flushed)
        # Accessing session keys may recreate the session, so check that last_activity is not present
        self.assertNotIn('last_activity', request.session)

    def test_anonymous_user_clears_last_activity(self):
        request = self.factory.get('/')
        self._add_session(request)
        # Simulate previous last_activity
        request.session['last_activity'] = timezone.now().timestamp()
        request.session.save()

        # Anonymous user
        class Anonymous:
            is_authenticated = False
        request.user = Anonymous()

        resp = self.middleware(request)
        self.assertNotIn('last_activity', request.session)
