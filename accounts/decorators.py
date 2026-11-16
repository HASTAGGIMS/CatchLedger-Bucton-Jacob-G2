from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """
    Allow only logged-in users whose role is in ``roles``.

    * Anonymous users are redirected to the login page (like @login_required).
    * Logged-in users with a different role get a 403 page, so typing another
      role's URL never opens that role's dashboard.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("You do not have access to this page.")
            return view_func(request, *args, **kwargs)

        return login_required(_wrapped)

    return decorator
