from .models import Membership


def workspace(request):
    if not request.user.is_authenticated:
        return {}
    try:
        return {"current_organization": request.user.schedule_membership.organization}
    except Membership.DoesNotExist:
        return {}
