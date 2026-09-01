from .models import Membership


def workspace(request):
    if not request.user.is_authenticated:
        return {}
    membership = getattr(request, "membership", None)
    if membership is None:
        membership = (
            Membership.objects.select_related("organization").filter(user=request.user).first()
        )
    if membership is None:
        return {}
    return {"current_membership": membership, "current_organization": membership.organization}
