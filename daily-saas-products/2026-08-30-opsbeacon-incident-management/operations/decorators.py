from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

from .models import Membership


def workspace_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        try:
            membership = request.user.operations_membership
        except Membership.DoesNotExist:
            return HttpResponseForbidden("Your account is not attached to an operations workspace.")
        request.membership = membership
        request.organization = membership.organization
        return view(request, *args, **kwargs)

    return wrapped
