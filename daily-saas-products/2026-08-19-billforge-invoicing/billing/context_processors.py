from .models import Membership


def workspace(request):
    if not request.user.is_authenticated:
        return {}
    try:
        return {"current_organization": request.user.billing_membership.organization}
    except Membership.DoesNotExist:
        return {}
