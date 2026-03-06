from myapp.models import Message, Notification


def global_counts(request):
    if not request.user.is_authenticated:
        return {
            "notification_count": 0,
            "notification_has_unread": False,
            "unread_messages": 0,
        }

    notification_count = Notification.objects.filter(
        receiver=request.user,
        is_read=False
    ).count()
    unread_messages = Message.objects.filter(
        receiver=request.user,
        is_seen=False
    ).values("sender_id").distinct().count()

    return {
        "notification_count": notification_count,
        "notification_has_unread": notification_count > 0,
        "unread_messages": unread_messages,
    }
