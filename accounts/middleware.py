from django.conf import settings
from django.contrib import auth
from django.utils import timezone

class AutoLogoutMiddleware:
    """Middleware to auto-logout users after a period of inactivity.

    - Records 'last_activity' timestamp in the session on each request.
    - If the delta between now and 'last_activity' is greater than
      settings.AUTO_LOGOUT_DELAY, the user is logged out and the session is flushed.

    Notes:
    - This middleware intentionally does not save the session on every request
      (unless SESSION_SAVE_EVERY_REQUEST is True). It writes last_activity only
      when the user is authenticated or when needed to clear the session.
    - Put this middleware after AuthenticationMiddleware in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only consider authenticated users with a session
        if not request.user.is_authenticated:
            # Clear any stale last_activity for anonymous users
            request.session.pop('last_activity', None)
            return self.get_response(request)

        now = timezone.now().timestamp()
        last = request.session.get('last_activity')

        # If we have a last activity timestamp, check timeout
        if last is not None:
            try:
                last = float(last)
            except (TypeError, ValueError):
                last = None

        if last is not None:
            elapsed = now - last
            timeout = getattr(settings, 'AUTO_LOGOUT_DELAY', 30 * 60)
            if elapsed > timeout:
                # Invalidate session and log out
                auth.logout(request)
                request.session.flush()
                # After logout, continue — views can redirect to login if needed
                return self.get_response(request)

        # Update last activity timestamp
        request.session['last_activity'] = now
        # Optionally save session every request if configured
        if getattr(settings, 'SESSION_SAVE_EVERY_REQUEST', False):
            request.session.save()

        return self.get_response(request)
