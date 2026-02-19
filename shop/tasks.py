from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import import_shop_from_yaml


@shared_task
def send_email_task(subject: str, message: str, recipient_list: list[str]) -> None:
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        fail_silently=True,
    )


@shared_task
def do_import(file_path: str) -> int:
    shop = import_shop_from_yaml(file_path)
    return shop.id
