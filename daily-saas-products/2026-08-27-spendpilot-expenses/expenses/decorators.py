from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .models import Membership


def workspace_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            membership = Membership.objects.select_related("organization").get(user=request.user)
        except Membership.DoesNotExist:
            return HttpResponseForbidden("This account is not assigned to a SpendPilot workspace.")
        request.membership = membership
        request.organization = membership.organization
        return view_func(request, *args, **kwargs)

    return wrapped
