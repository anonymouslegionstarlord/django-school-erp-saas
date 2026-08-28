from .models import Membership


def workspace(request):
    if not request.user.is_authenticated:
        return {}
    membership = getattr(request, "membership", None)
    if membership is None:
        try:
            membership = request.user.quality_membership
        except Membership.DoesNotExist:
            return {}
    return {"membership": membership, "organization": membership.organization}
