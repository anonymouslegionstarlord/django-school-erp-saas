from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from .models import Membership


def workspace_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.get_full_path()}")
        membership = (
            Membership.objects.select_related("organization").filter(user=request.user).first()
        )
        if membership is None:
            raise PermissionDenied("Your account does not belong to a RoutePilot workspace.")
        request.membership = membership
        request.organization = membership.organization
        return view_func(request, *args, **kwargs)

    return wrapped


def manager_required(view_func):
    @workspace_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.membership.can_manage:
            raise PermissionDenied("Dispatcher access is required.")
        return view_func(request, *args, **kwargs)

    return wrapped
