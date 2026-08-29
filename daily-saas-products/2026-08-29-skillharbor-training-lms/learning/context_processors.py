from .models import Membership


def workspace(request):
    if not request.user.is_authenticated:
        return {}
    try:
        membership = request.user.learning_membership
    except Membership.DoesNotExist:
        return {}
    return {
        "active_organization": membership.organization,
        "active_membership": membership,
    }
